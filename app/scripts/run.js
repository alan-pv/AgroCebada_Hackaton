// Página «Ejecutar el modelo»: elegir parcelas del conjunto de datos y calcularlas en vivo,
// probar parcelas nuevas (a mano o desde un CSV) y descargar los resultados.
// Las rutas y los límites salen de los atributos data-* de la plantilla; aquí no se escriben.

(function () {
  "use strict";

  // Reglas de una parcela nueva, las mismas que aplica la API
  const ID_PATTERN = /^[A-Za-z0-9_-]{1,40}$/;
  const MAX_AREA_HA = 1000;
  const REGIMES = ["A", "B"];
  // Número con punto decimal, como -98.37 o .5; la coma decimal no se acepta
  const DECIMAL_PATTERN = /^[+-]?(\d+\.?\d*|\.\d+)$/;
  // Nombres que acepta la cabecera del CSV; el primero es el nombre oficial
  const CSV_COLUMNS = {
    id: ["id"],
    lon: ["lon", "longitud"],
    lat: ["lat", "latitud"],
    area_ha: ["area_ha", "superficie_ha", "area"],
    regime: ["regimen", "regime"],
  };
  // Columnas del CSV de resultados, en este orden
  const RESULT_COLUMNS = [
    "id", "state", "municipality", "set", "pred", "p10", "p90", "prob_below",
    "confidence", "neighbors_400m", "nearest_neighbor_m", "threshold", "model_version",
  ];
  // Encabezados de la tabla de resultados; también son la etiqueta de cada celda en el celular
  const RESULT_LABELS = [
    "Parcela", "Estado", "Municipio", "Predicción (t/ha)", "Intervalo p10–p90 (t/ha)",
    "Rango frente al umbral", "Probabilidad bajo el umbral (%)", "Confianza",
  ];
  const SET_LABELS = { ENTRENAMIENTO: "Entrenamiento", PREDICCION: "Predicción" };
  // Punto de color de cada conjunto, el mismo del mapa
  const SET_DOTS = { ENTRENAMIENTO: "dot--entrenamiento", PREDICCION: "dot--prediccion" };
  // Paso de la escala de las barras de rango: sus extremos son múltiplos de 0.5 t/ha
  const RANGE_STEP = 0.5;
  // Confianza con el mismo semáforo de riesgo de la app: alta en verde, baja en rojo
  const CONFIDENCE = {
    alta: { text: "Confianza alta", className: "badge--bajo" },
    media: { text: "Confianza media", className: "badge--medio" },
    baja: { text: "Confianza baja", className: "badge--alto" },
  };
  // La confianza baja también ocurre cuando la superficie queda fuera del rango de su régimen
  const LOW_CONFIDENCE_WARNING = "Hay parcelas con confianza baja: están lejos de las parcelas medidas o su superficie queda fuera del rango de su régimen. Su resultado es menos fiable.";
  // Plantilla con BOM UTF-8, para que Excel lea bien los acentos
  const TEMPLATE_CSV = "﻿id,lon,lat,area_ha,regimen\r\nMI_PARCELA,-98.37,19.82,5.2,A\r\n";

  // Trozos de `size` elementos, en orden: chunk([1, 2, 3], 2) -> [[1, 2], [3]]
  function chunk(items, size) {
    const parts = [];
    for (let i = 0; i < items.length; i += size) parts.push(items.slice(i, i + size));
    return parts;
  }

  // Número con punto decimal; null si el texto no es un número así
  function parseNumber(text) {
    const value = String(text ?? "").trim();
    return DECIMAL_PATTERN.test(value) ? Number(value) : null;
  }

  // Nombre de columna sin BOM, acentos, espacios ni mayúsculas
  function normalizeHeader(text) {
    return String(text).replace(/^﻿/, "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();
  }

  // Separador de la cabecera: punto y coma si aparece más veces que la coma
  function detectDelimiter(headerLine) {
    const semicolons = (headerLine.match(/;/g) || []).length;
    const commas = (headerLine.match(/,/g) || []).length;
    return semicolons > commas ? ";" : ",";
  }

  // Separa el texto en registros de celdas. Respeta las comillas (dentro de ellas, "" es una
  // comilla) y acepta saltos CRLF, LF o CR. Cada registro guarda la línea donde empieza.
  function parseRecords(text, delimiter) {
    const records = [];
    let cells = [];
    let cell = "";
    let quoted = false;
    let line = 1;
    let recordLine = 1;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') {
          cell += '"';
          i++;
        } else if (ch === '"') {
          quoted = false;
        } else {
          if (ch === "\n") line++;
          cell += ch;
        }
      } else if (ch === '"' && cell === "") {
        quoted = true;
      } else if (ch === delimiter) {
        cells.push(cell);
        cell = "";
      } else if (ch === "\r" || ch === "\n") {
        if (ch === "\r" && text[i + 1] === "\n") i++;
        cells.push(cell);
        records.push({ line: recordLine, cells });
        cells = [];
        cell = "";
        line++;
        recordLine = line;
      } else {
        cell += ch;
      }
    }
    if (cell !== "" || cells.length > 0) {
      cells.push(cell);
      records.push({ line: recordLine, cells });
    }
    return records;
  }

  // Mensaje para un valor numérico que no se pudo leer
  function numberProblem(name, text) {
    return text === "" ? `falta ${name}` : `${name} "${text}" no es un número con punto decimal`;
  }

  // Lee el CSV de parcelas nuevas. Devuelve { parcels, errors }; si hay errores, no se calcula nada.
  // Cada error trae su línea del archivo (null si afecta a todo el archivo)
  function parseCsv(text, maxRows) {
    const clean = String(text).replace(/^﻿/, "");
    const firstLine = clean.split(/\r\n|\r|\n/)[0];
    const records = parseRecords(clean, detectDelimiter(firstLine))
      .filter((record) => record.cells.some((cell) => cell.trim() !== ""));
    if (records.length === 0) {
      return { parcels: [], errors: [{ line: null, message: "El archivo está vacío." }] };
    }

    const [header, ...body] = records;
    const names = header.cells.map(normalizeHeader);
    const column = {};
    for (const [key, aliases] of Object.entries(CSV_COLUMNS)) {
      column[key] = names.findIndex((name) => aliases.includes(name));
    }
    const missing = ["lon", "lat", "area_ha", "regime"].filter((key) => column[key] === -1);
    if (missing.length > 0) {
      const labels = missing.map((key) => CSV_COLUMNS[key][0]).join(", ");
      return { parcels: [], errors: [{ line: header.line, message: `Faltan columnas: ${labels}.` }] };
    }
    if (body.length > maxRows) {
      return {
        parcels: [],
        errors: [{ line: null, message: `El archivo tiene ${body.length} parcelas; el máximo es ${maxRows} por consulta.` }],
      };
    }

    const parcels = [];
    const errors = [];
    for (const record of body) {
      // Celda de la columna `key`; si la fila es más corta, la celda vale ""
      const value = (key) => (column[key] >= 0 && column[key] < record.cells.length
        ? record.cells[column[key]].trim()
        : "");
      const problems = [];
      const id = value("id");
      if (id !== "" && !ID_PATTERN.test(id)) {
        problems.push(`id "${id}" no es válido: usa de 1 a 40 letras, números, _ o -`);
      }
      const lon = parseNumber(value("lon"));
      if (lon === null) problems.push(numberProblem("lon", value("lon")));
      const lat = parseNumber(value("lat"));
      if (lat === null) problems.push(numberProblem("lat", value("lat")));
      const area = parseNumber(value("area_ha"));
      if (area === null) problems.push(numberProblem("area_ha", value("area_ha")));
      else if (area <= 0 || area > MAX_AREA_HA) problems.push(`area_ha debe ser mayor que 0 y como máximo ${MAX_AREA_HA}`);
      const regime = value("regime").toUpperCase();
      if (!REGIMES.includes(regime)) problems.push("regimen debe ser A o B");

      if (problems.length > 0) {
        errors.push({ line: record.line, message: problems.join("; ") });
      } else {
        parcels.push({ id: id || undefined, lon, lat, area_ha: area, regime });
      }
    }
    return { parcels, errors };
  }

  // Mensajes de error del CSV con su línea: «Línea 4: ...»
  function formatCsvErrors(errors) {
    return errors.map((error) => (error.line ? `Línea ${error.line}: ${error.message}` : error.message));
  }

  // Texto de una celda CSV: comillas si hay coma, comilla o salto de línea; las comillas se duplican
  function csvCell(value) {
    if (value === null || value === undefined) return "";
    const text = String(value);
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  // Archivo CSV completo: BOM UTF-8, cabecera y filas separadas por CRLF
  function toCsv(rows, columns) {
    const lines = [columns.map(csvCell).join(",")];
    for (const row of rows) {
      lines.push(columns.map((column) => csvCell(row[column])).join(","));
    }
    return `﻿${lines.join("\r\n")}\r\n`;
  }

  // Filas que cumplen los filtros: estado, municipio, conjunto y texto del ID (sin mayúsculas)
  function filterRows(rows, filters) {
    const query = (filters.query || "").trim().toLowerCase();
    return rows.filter((row) => (!filters.state || row.state === filters.state)
      && (!filters.municipality || row.municipality === filters.municipality)
      && (!filters.set || row.set === filters.set)
      && (!query || row.id.toLowerCase().includes(query)));
  }

  // Valores sin repetir, en orden alfabético en español
  function uniqueSorted(values) {
    return [...new Set(values)].sort((a, b) => a.localeCompare(b, "es"));
  }

  // Municipios del estado elegido, o de todos si no hay estado
  function municipalitiesIn(rows, state) {
    return uniqueSorted(rows.filter((row) => !state || row.state === state).map((row) => row.municipality));
  }

  // Texto y clase del semáforo de confianza; null si la API no trae un valor conocido
  function confidenceBadge(confidence) {
    return Object.prototype.hasOwnProperty.call(CONFIDENCE, confidence) ? CONFIDENCE[confidence] : null;
  }

  // Una fila de resultados: la predicción y, si la parcela está en el conjunto, sus datos
  // (estado, municipio, conjunto). Las parcelas nuevas no tienen esos datos
  function resultRow(prediction, info, meta) {
    return {
      id: prediction.id,
      state: info ? info.state : "",
      municipality: info ? info.municipality : "",
      set: info ? info.set : "",
      inDataset: Boolean(info),
      pred: prediction.pred,
      p10: prediction.p10,
      p90: prediction.p90,
      prob_below: prediction.prob_below,
      // Las claves de confianza pueden faltar; entonces quedan vacías
      confidence: prediction.confidence ?? "",
      neighbors_400m: prediction.neighbors_400m ?? "",
      nearest_neighbor_m: prediction.nearest_neighbor_m ?? "",
      threshold: meta.threshold,
      model_version: meta.model_version,
    };
  }

  // Número con dos decimales, como en el mapa (es-MX). Sin dato, "—"
  function formatNumber(value, digits) {
    if (value === null || value === undefined || !Number.isFinite(value)) return "—";
    return value.toLocaleString("es-MX", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  // Probabilidad de una fracción 0 a 1, en porcentaje sin decimales: 0.456 -> "46 %"
  function percentText(probability) {
    if (probability === null || probability === undefined) return "—";
    return `${formatNumber(probability * 100, 0)} %`;
  }

  // Intervalo p10 a p90 en t/ha; sin dato, "—"
  function intervalText(p10, p90) {
    if (p10 === null || p10 === undefined || p90 === null || p90 === undefined) return "—";
    return `${formatNumber(p10, 2)}–${formatNumber(p90, 2)}`;
  }

  // Escala común de las barras de rango: cubre todos los p10, p90 y predicciones y el umbral,
  // con extremos redondeados a RANGE_STEP. Así todas las filas se comparan a simple vista
  function rangeScale(rows, threshold) {
    const values = [threshold];
    for (const row of rows) {
      for (const value of [row.p10, row.p90, row.pred]) {
        if (Number.isFinite(value)) values.push(value);
      }
    }
    let min = Math.floor(Math.min(...values) / RANGE_STEP) * RANGE_STEP;
    let max = Math.ceil(Math.max(...values) / RANGE_STEP) * RANGE_STEP;
    if (max - min < RANGE_STEP) {
      min -= RANGE_STEP;
      max += RANGE_STEP;
    }
    return { min: Math.max(0, min), max };
  }

  // Posición de un valor en la escala, en porcentaje de 0 a 100
  function rangePercent(value, scale) {
    const percent = ((value - scale.min) / (scale.max - scale.min)) * 100;
    return Math.min(100, Math.max(0, percent));
  }

  // Valida los campos del formulario de parcela nueva. Devuelve la parcela lista para la API
  // y los errores, cada uno con el campo que falla
  function parseNewParcel(fields) {
    const errors = [];
    const parcel = {};
    const id = String(fields.id ?? "").trim();
    if (id !== "") {
      if (ID_PATTERN.test(id)) parcel.id = id;
      else errors.push({ field: "id", message: "El ID solo puede tener de 1 a 40 letras, números, guion bajo o guion." });
    }
    const lon = parseNumber(fields.lon);
    if (lon === null) errors.push({ field: "lon", message: "Escribe la longitud en grados, con punto decimal (por ejemplo -98.37)." });
    else parcel.lon = lon;
    const lat = parseNumber(fields.lat);
    if (lat === null) errors.push({ field: "lat", message: "Escribe la latitud en grados, con punto decimal (por ejemplo 19.82)." });
    else parcel.lat = lat;
    const area = parseNumber(fields.area);
    if (area === null || area <= 0 || area > MAX_AREA_HA) {
      errors.push({ field: "area", message: `Escribe la superficie en hectáreas: un número mayor que 0 y como máximo ${MAX_AREA_HA}.` });
    } else {
      parcel.area_ha = area;
    }
    const regime = String(fields.regime ?? "").trim().toUpperCase();
    if (REGIMES.includes(regime)) parcel.regime = regime;
    else errors.push({ field: "regime", message: "El régimen debe ser A o B." });
    return { parcel, errors };
  }

  // Escribe un mensaje en una zona con aria-live. Con una lista, muestra un punto por línea
  function showMessage(element, content, isError = false) {
    element.className = isError ? "message message--error" : "message";
    element.replaceChildren();
    if (Array.isArray(content)) {
      const list = document.createElement("ul");
      for (const item of content) {
        const li = document.createElement("li");
        li.textContent = item;
        list.append(li);
      }
      element.append(list);
    } else {
      element.textContent = content;
    }
  }

  // Celda de tabla con texto (nunca HTML) o con un nodo ya armado. `label` es la etiqueta que el
  // celular muestra antes del valor (data-label); `className` añade una clase a la celda
  function makeCell(tag, content, { label, className } = {}) {
    const cell = document.createElement(tag);
    if (content instanceof Node) cell.append(content);
    else cell.textContent = content;
    if (label !== undefined) cell.setAttribute("data-label", label);
    if (className) cell.className = className;
    return cell;
  }

  // Descarga un texto generado en el navegador, como archivo
  function downloadFile(text, name) {
    const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // POST con cuerpo JSON. Si el servidor responde con error, lanza un Error con su mensaje
  async function postJson(url, body) {
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (error) {
      throw new Error("No se pudo conectar con el servidor. Inténtalo de nuevo.");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && data.error) || `El servidor respondió con error ${response.status}.`);
    }
    if (!data) throw new Error("La respuesta del servidor no es válida.");
    return data;
  }

  function init() {
    const root = document.getElementById("run");
    if (!root) return;
    const el = (id) => document.getElementById(id);
    const predictUrl = root.dataset.predictUrl;
    const newUrl = root.dataset.newUrl;
    const detailUrl = root.dataset.detailUrl;
    const maxParcels = Number(root.dataset.maxParcels);
    const thresholdMin = Number(root.dataset.thresholdMin);
    const thresholdMax = Number(root.dataset.thresholdMax);

    const filterState = el("filter-state");
    const filterMunicipality = el("filter-municipality");
    const filterSet = el("filter-set");
    const filterId = el("filter-id");
    const selectVisible = el("select-visible");
    const selectionCount = el("selection-count");
    const tableBody = el("dataset-rows");
    const thresholdInput = el("threshold");
    const runButton = el("run-button");
    const datasetMessage = el("dataset-message");
    const newForm = el("new-form");
    const newMessage = el("new-message");
    const newSubmit = el("new-submit");
    const csvFile = el("csv-file");
    const csvRun = el("csv-run");
    const csvMessage = el("csv-message");
    const csvTemplate = el("csv-template");
    const csvFileName = el("csv-file-name");
    const resultsZone = el("results-zone");
    const downloadButton = el("download-button");

    // Lista de parcelas, selección, filas visibles, último resultado y si hay un cálculo en curso
    const view = { rows: [], byId: new Map(), selected: new Set(), visible: [], results: null, busy: false };

    // El valor por defecto del umbral sale del data-* de la página
    thresholdInput.value = root.dataset.thresholdDefault;
    csvTemplate.href = URL.createObjectURL(new Blob([TEMPLATE_CSV], { type: "text/csv;charset=utf-8" }));

    // Opciones de un <select>: se conserva «Todos» y se agregan las demás
    function fillSelect(select, values) {
      select.length = 1;
      for (const value of values) select.add(new Option(value, value));
    }

    function fillMunicipalities() {
      fillSelect(filterMunicipality, municipalitiesIn(view.rows, filterState.value));
      filterMunicipality.value = "";
    }

    function buildDatasetRow(row) {
      const tr = document.createElement("tr");
      const boxCell = document.createElement("td");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = view.selected.has(row.id);
      box.setAttribute("aria-label", `Seleccionar ${row.id}`);
      // La fila elegida se resalta; la casilla marcada ya lo dice sin depender del color
      tr.classList.toggle("is-selected", box.checked);
      box.addEventListener("change", () => {
        if (box.checked) view.selected.add(row.id);
        else view.selected.delete(row.id);
        tr.classList.toggle("is-selected", box.checked);
        updateSelectionInfo();
      });
      boxCell.append(box);
      const idCell = makeCell("th", row.id);
      idCell.scope = "row";
      // Conjunto con su punto de color, el mismo del mapa; el texto lo nombra
      const setNode = document.createElement("span");
      setNode.className = "set";
      const dot = document.createElement("span");
      dot.className = `dot ${SET_DOTS[row.set] || ""}`;
      dot.setAttribute("aria-hidden", "true");
      setNode.append(dot, SET_LABELS[row.set] || row.set);
      // Conjunto, Régimen y Estado se ocultan en el celular (clase hide-sm)
      tr.append(
        boxCell,
        idCell,
        makeCell("td", setNode, { className: "hide-sm" }),
        makeCell("td", row.regime, { className: "hide-sm" }),
        makeCell("td", row.state, { className: "hide-sm" }),
        makeCell("td", row.municipality),
        makeCell("td", formatNumber(row.area_ha, 2), { className: "num" }),
      );
      return tr;
    }

    // Dibuja las parcelas que pasan los filtros; la selección se conserva al filtrar
    function renderTable() {
      view.visible = filterRows(view.rows, {
        state: filterState.value,
        municipality: filterMunicipality.value,
        set: filterSet.value,
        query: filterId.value,
      });
      tableBody.replaceChildren();
      if (view.visible.length === 0) {
        const cell = makeCell("td", "No hay parcelas con esos filtros.");
        cell.colSpan = 7;
        cell.className = "muted";
        const tr = document.createElement("tr");
        tr.append(cell);
        tableBody.append(tr);
      } else {
        for (const row of view.visible) tableBody.append(buildDatasetRow(row));
      }
      updateSelectionInfo();
    }

    // Contador y estado de «Seleccionar las visibles» (marcada, a medias o libre)
    function updateSelectionInfo() {
      const picked = view.visible.filter((row) => view.selected.has(row.id)).length;
      selectVisible.disabled = view.visible.length === 0;
      selectVisible.checked = view.visible.length > 0 && picked === view.visible.length;
      selectVisible.indeterminate = picked > 0 && picked < view.visible.length;
      const total = view.selected.size;
      selectionCount.textContent = `${total} ${total === 1 ? "seleccionada" : "seleccionadas"}`;
    }

    // Umbral del campo de la primera tarjeta. Si no es válido, avisa en `messageEl` y devuelve null
    function readThreshold(messageEl) {
      const value = parseNumber(thresholdInput.value);
      if (value === null || value < thresholdMin || value > thresholdMax) {
        showMessage(messageEl, `El umbral debe ser un número entre ${thresholdMin.toFixed(1)} y ${thresholdMax.toFixed(1)} t/ha.`, true);
        return null;
      }
      return value;
    }

    // Mientras hay un cálculo, los botones de calcular no responden
    function setBusy(busy) {
      view.busy = busy;
      for (const button of [runButton, newSubmit, csvRun]) button.disabled = busy;
      resultsZone.setAttribute("aria-busy", String(busy));
    }

    // Barra de rango de una parcela: intervalo p10–p90, predicción como punto y umbral como línea,
    // en la escala común. El texto accesible (y el del cursor) dice los mismos valores
    function buildRange(row, scale, threshold) {
      if (![row.pred, row.p10, row.p90].every(Number.isFinite)) return "—";
      const text = `Predicción ${formatNumber(row.pred, 2)} t/ha; intervalo de ${formatNumber(row.p10, 2)} `
        + `a ${formatNumber(row.p90, 2)} t/ha; umbral ${formatNumber(threshold, 1)} t/ha`;
      const range = document.createElement("div");
      range.className = "range";
      range.setAttribute("role", "img");
      range.setAttribute("aria-label", text);
      range.title = text;
      const band = document.createElement("span");
      band.className = "range__band";
      band.style.left = `${rangePercent(row.p10, scale)}%`;
      band.style.width = `${rangePercent(row.p90, scale) - rangePercent(row.p10, scale)}%`;
      const line = document.createElement("span");
      line.className = "range__threshold";
      line.style.left = `${rangePercent(threshold, scale)}%`;
      const point = document.createElement("span");
      point.className = "range__pred";
      point.style.left = `${rangePercent(row.pred, scale)}%`;
      range.append(band, line, point);
      return range;
    }

    // Encabezado de la columna de barras: su nombre y los extremos de la escala común
    function buildRangeHeader(scale) {
      const th = makeCell("th", RESULT_LABELS[5]);
      th.scope = "col";
      th.className = "range-col";
      const axis = document.createElement("span");
      axis.className = "range-axis";
      axis.setAttribute("aria-hidden", "true");
      axis.append(makeCell("span", formatNumber(scale.min, 1)), makeCell("span", formatNumber(scale.max, 1)));
      th.append(axis);
      return th;
    }

    // Leyenda de las barras, con la escala en texto: el celular no muestra el encabezado
    function buildRangeLegend(scale, threshold) {
      const legend = document.createElement("p");
      legend.className = "range-legend";
      const item = (keyClass, label) => {
        const span = document.createElement("span");
        span.className = "range-legend__item";
        const key = document.createElement("span");
        key.className = `range-legend__key ${keyClass}`;
        key.setAttribute("aria-hidden", "true");
        span.append(key, label);
        return span;
      };
      legend.append(
        item("range-legend__key--band", "Intervalo p10–p90"),
        item("range-legend__key--pred", "Predicción"),
        item("range-legend__key--threshold", `Umbral ${formatNumber(threshold, 1)} t/ha`),
        makeCell("span", `Misma escala en todas las filas, de ${formatNumber(scale.min, 1)} a ${formatNumber(scale.max, 1)} t/ha`),
      );
      return legend;
    }

    function buildResultRow(row, scale, threshold) {
      let idNode = row.id;
      if (row.inDataset) {
        const link = document.createElement("a");
        link.href = detailUrl.replace("__ID__", encodeURIComponent(row.id));
        link.textContent = row.id;
        idNode = link;
      }
      let confidenceNode = "—";
      const badge = confidenceBadge(row.confidence);
      if (badge) {
        confidenceNode = document.createElement("span");
        confidenceNode.className = `badge ${badge.className}`;
        confidenceNode.textContent = badge.text;
      }
      // Cada celda lleva su etiqueta (data-label) para mostrarla en la tarjeta del celular
      const idCell = makeCell("th", idNode, { label: RESULT_LABELS[0] });
      idCell.scope = "row";
      const tr = document.createElement("tr");
      tr.append(
        idCell,
        makeCell("td", row.state || "—", { label: RESULT_LABELS[1] }),
        makeCell("td", row.municipality || "—", { label: RESULT_LABELS[2] }),
        makeCell("td", formatNumber(row.pred, 2), { label: RESULT_LABELS[3], className: "num" }),
        makeCell("td", intervalText(row.p10, row.p90), { label: RESULT_LABELS[4], className: "num" }),
        makeCell("td", buildRange(row, scale, threshold), { label: RESULT_LABELS[5], className: "range-col" }),
        makeCell("td", percentText(row.prob_below), { label: RESULT_LABELS[6], className: "num" }),
        makeCell("td", confidenceNode, { label: RESULT_LABELS[7] }),
      );
      return tr;
    }

    function buildResultsTable(rows, scale, threshold) {
      const wrap = document.createElement("div");
      wrap.className = "table-wrap";
      const table = document.createElement("table");
      table.className = "data results-table";
      const caption = makeCell("caption", "Resultados de la predicción, una fila por parcela");
      caption.className = "visually-hidden";
      const head = document.createElement("thead");
      const headRow = document.createElement("tr");
      RESULT_LABELS.forEach((title, index) => {
        if (index === 5) {
          headRow.append(buildRangeHeader(scale));
          return;
        }
        const th = makeCell("th", title);
        th.scope = "col";
        // Las cifras se alinean a la derecha, también su encabezado
        if (index === 3 || index === 4 || index === 6) th.className = "num";
        headRow.append(th);
      });
      head.append(headRow);
      const body = document.createElement("tbody");
      for (const row of rows) body.append(buildResultRow(row, scale, threshold));
      table.append(caption, head, body);
      wrap.append(table);
      return wrap;
    }

    // Muestra el resumen, el aviso de confianza baja y la tabla en la zona de resultados
    function renderResults(rows, meta) {
      view.results = { rows, meta };
      resultsZone.replaceChildren();
      // Resumen en una línea: cuántas parcelas, con qué umbral y qué versión del modelo
      const summary = document.createElement("p");
      summary.className = "summary";
      const count = document.createElement("strong");
      count.textContent = `${rows.length} ${rows.length === 1 ? "parcela" : "parcelas"}`;
      summary.append(count, ` · umbral ${meta.threshold} t/ha · modelo versión ${meta.model_version}`);
      resultsZone.append(summary);
      const lowIds = rows.filter((row) => row.confidence === "baja").map((row) => row.id);
      if (lowIds.length > 0) {
        const warning = document.createElement("div");
        warning.className = "warning";
        const text = document.createElement("p");
        text.textContent = LOW_CONFIDENCE_WARNING;
        const ids = document.createElement("p");
        ids.className = "warning__ids";
        ids.textContent = `Confianza baja en: ${lowIds.join(", ")}.`;
        warning.append(text, ids);
        resultsZone.append(warning);
      }
      const scale = rangeScale(rows, meta.threshold);
      resultsZone.append(buildRangeLegend(scale, meta.threshold), buildResultsTable(rows, scale, meta.threshold));
      downloadButton.hidden = false;
    }

    // Calcula las parcelas elegidas en lotes de como máximo `maxParcels` IDs, en orden
    async function runDataset() {
      if (view.busy) return;
      const threshold = readThreshold(datasetMessage);
      if (threshold === null) return;
      // En el orden de la tabla
      const ids = view.rows.filter((row) => view.selected.has(row.id)).map((row) => row.id);
      if (ids.length === 0) {
        showMessage(datasetMessage, "Elige al menos una parcela.", true);
        return;
      }
      setBusy(true);
      try {
        const batches = chunk(ids, maxParcels);
        const predictions = new Map();
        let meta = null;
        for (let i = 0; i < batches.length; i++) {
          const progress = batches.length > 1 ? ` (lote ${i + 1} de ${batches.length})` : "";
          showMessage(datasetMessage, `Calculando...${progress}`);
          const data = await postJson(predictUrl, { ids: batches[i], threshold, include_confidence: true });
          if (meta === null) meta = { model_version: data.model_version, threshold: data.threshold };
          for (const prediction of data.predictions) predictions.set(prediction.id, prediction);
        }
        // La API devuelve los IDs ordenados; aquí se muestran en el orden de la tabla
        const rows = ids.filter((id) => predictions.has(id))
          .map((id) => resultRow(predictions.get(id), view.byId.get(id), meta));
        renderResults(rows, meta);
        showMessage(datasetMessage, `Listo: ${rows.length} ${rows.length === 1 ? "parcela calculada" : "parcelas calculadas"}.`);
      } catch (error) {
        showMessage(datasetMessage, error.message, true);
      } finally {
        setBusy(false);
      }
    }

    // Calcula una lista de parcelas nuevas y muestra los resultados; los avisos van en `messageEl`
    async function runNew(parcels, messageEl) {
      if (view.busy) return;
      const threshold = readThreshold(messageEl);
      if (threshold === null) return;
      setBusy(true);
      showMessage(messageEl, "Calculando...");
      try {
        const data = await postJson(newUrl, { parcels, threshold });
        const meta = { model_version: data.model_version, threshold: data.threshold };
        const rows = data.predictions.map((prediction) => resultRow(prediction, null, meta));
        renderResults(rows, meta);
        showMessage(messageEl, `Listo: ${rows.length} ${rows.length === 1 ? "parcela calculada" : "parcelas calculadas"}.`);
      } catch (error) {
        showMessage(messageEl, error.message, true);
      } finally {
        setBusy(false);
      }
    }

    // Lee el CSV elegido; si tiene errores, los muestra por línea y no calcula nada
    async function runCsv() {
      if (view.busy) return;
      const file = csvFile.files[0];
      if (!file) {
        showMessage(csvMessage, "Elige un archivo CSV.", true);
        return;
      }
      let text;
      try {
        text = await file.text();
      } catch (error) {
        showMessage(csvMessage, "No se pudo leer el archivo.", true);
        return;
      }
      const { parcels, errors } = parseCsv(text, maxParcels);
      if (errors.length > 0) {
        showMessage(csvMessage, formatCsvErrors(errors), true);
        return;
      }
      if (parcels.length === 0) {
        showMessage(csvMessage, "El archivo no tiene parcelas.", true);
        return;
      }
      await runNew(parcels, csvMessage);
    }

    // Quita la marca de campo no válido de todo el formulario
    function clearInvalid() {
      for (const input of newForm.querySelectorAll("[aria-invalid]")) input.removeAttribute("aria-invalid");
    }

    filterState.addEventListener("change", () => {
      // Al cambiar de estado, el municipio vuelve a «Todos»
      fillMunicipalities();
      renderTable();
    });
    filterMunicipality.addEventListener("change", renderTable);
    filterSet.addEventListener("change", renderTable);
    filterId.addEventListener("input", renderTable);
    // Marca o desmarca todas las filas visibles, según estén todas marcadas o no
    selectVisible.addEventListener("change", () => {
      const allPicked = view.visible.every((row) => view.selected.has(row.id));
      for (const row of view.visible) {
        if (allPicked) view.selected.delete(row.id);
        else view.selected.add(row.id);
      }
      renderTable();
    });
    el("select-predicted").addEventListener("click", () => {
      view.selected = new Set(view.rows.filter((row) => row.set === "PREDICCION").map((row) => row.id));
      renderTable();
    });
    el("clear-selection").addEventListener("click", () => {
      view.selected.clear();
      renderTable();
    });
    runButton.addEventListener("click", runDataset);

    newForm.addEventListener("submit", (event) => {
      event.preventDefault();
      clearInvalid();
      const { parcel, errors } = parseNewParcel({
        id: el("new-id").value,
        lon: el("new-lon").value,
        lat: el("new-lat").value,
        area: el("new-area").value,
        regime: el("new-regime").value,
      });
      if (errors.length > 0) {
        for (const error of errors) el(`new-${error.field}`).setAttribute("aria-invalid", "true");
        showMessage(newMessage, errors.map((error) => error.message), true);
        el(`new-${errors[0].field}`).focus();
        return;
      }
      runNew([parcel], newMessage);
    });
    csvRun.addEventListener("click", runCsv);
    // El selector propio muestra el nombre del archivo elegido
    csvFile.addEventListener("change", () => {
      const file = csvFile.files[0];
      csvFileName.textContent = file ? file.name : "Ningún archivo seleccionado";
      csvFileName.classList.toggle("file__name--chosen", Boolean(file));
    });

    downloadButton.addEventListener("click", () => {
      if (!view.results) return;
      downloadFile(toCsv(view.results.rows, RESULT_COLUMNS), "agrocebada_resultados.csv");
    });

    // Carga las parcelas del conjunto de datos y arma la tabla
    (async function loadDataset() {
      try {
        const response = await fetch(root.dataset.predictionsUrl);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        view.rows = await response.json();
        view.byId = new Map(view.rows.map((row) => [row.id, row]));
        fillSelect(filterState, uniqueSorted(view.rows.map((row) => row.state)));
        fillMunicipalities();
        renderTable();
      } catch (error) {
        tableBody.replaceChildren();
        showMessage(datasetMessage, "No se pudieron cargar las parcelas. Recarga la página para intentarlo de nuevo.", true);
      }
    })();
  }

  // Exporta las funciones puras para probarlas con node; en el navegador no existe `module`
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {
      chunk, parseNumber, parseRecords, parseCsv, formatCsvErrors, toCsv, csvCell,
      filterRows, uniqueSorted, municipalitiesIn, resultRow, confidenceBadge, parseNewParcel,
      rangeScale, rangePercent,
    };
  }

  if (typeof document !== "undefined") init();
})();
