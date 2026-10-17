// Mapa de la página inicial: parcelas coloreadas por conjunto, rendimiento, predicción o riesgo económico; el clic abre la ficha

// Colores por conjunto (paleta categórica validada para daltonismo)
const SET_COLORS = {
  ENTRENAMIENTO: "#2a78d6",
  PREDICCION: "#eb6834",
};
const SET_LABELS = {
  ENTRENAMIENTO: "Entrenamiento",
  PREDICCION: "Predicción",
};

// Clases de rendimiento en t/ha, de claro a oscuro; las usan el observado y la predicción
const YIELD_CLASSES = [
  { from: 2.0, to: 2.5, color: "#9ec5f4" },
  { from: 2.5, to: 3.0, color: "#6da7ec" },
  { from: 3.0, to: 3.5, color: "#3987e5" },
  { from: 3.5, to: 4.0, color: "#2a78d6" },
  { from: 4.0, to: 4.5, color: "#256abf" },
  { from: 4.5, to: 5.0, color: "#184f95" },
  { from: 5.0, to: 5.6, color: "#0d366b" },
];
const NO_DATA = { color: "#c3c2b7", border: "#898781" };
const LEGEND_TITLES = {
  yield: "Rendimiento observado (t/ha)",
  pred: "Rendimiento predicho (t/ha)",
};
const NO_DATA_LABELS = {
  yield: "Sin dato (predicción)",
  pred: "Entrenamiento (tiene dato observado)",
};
// Capas de riesgo económico: campo de semáforo que usa cada una y título de su leyenda
const RISK_LAYERS = new Map([
  ["risk_costs", { light: "light_costs", title: "Riesgo de no cubrir costos" }],
  ["risk_credit", { light: "light_credit", title: "Riesgo de no pagar el crédito" }],
]);
// Semáforo de la API (light_*): texto, rango de probabilidad, color y clase del badge; paleta Okabe-Ito, apta para daltonismo
const RISK_LEVELS = new Map([
  ["verde", { text: "bajo", range: "menos de 10 %", color: "#009E73", badge: "badge--bajo" }],
  ["amarillo", { text: "medio", range: "de 10 a 30 %", color: "#E69F00", badge: "badge--medio" }],
  ["rojo", { text: "alto", range: "30 % o más", color: "#D55E00", badge: "badge--alto" }],
]);

// Borde de las parcelas: gris oscuro semitransparente, para que lean sobre el mapa base gris claro
const BORDER = "#3d3c38";
const BORDER_OPACITY = 0.7;
const BORDER_HOVER = "#0b0b0b";

// Por debajo de este zoom las parcelas miden pocos píxeles y se dibujan como círculos en su centro
const POINT_ZOOM = 13;
const POINT_RADIUS = 6;

const mapElement = document.getElementById("map");
const layerSelect = document.getElementById("layer");
const stateSelect = document.getElementById("state");
const municipalitySelect = document.getElementById("municipality");
const countLabel = document.getElementById("count");
const predictionsLink = document.getElementById("download-predictions");
const economicsLink = document.getElementById("download-economics");
const filtersToggle = document.getElementById("filters-toggle");
const filtersActive = document.getElementById("filters-active");
const downloadMenu = document.querySelector(".download-menu");
// Indicadores sobre el mapa: cifra y nota de cada uno
const stats = Object.fromEntries(["shown", "to-predict", "pred-mean", "risk"].map((key) => [key, {
  value: document.getElementById(`stat-${key}`),
  note: document.getElementById(`stat-${key}-note`),
}]));

// Vista inicial sobre la zona de estudio; se ajusta al cargar las parcelas
const map = L.map(mapElement).setView([19.8, -98.4], 10);
// Mapa base de OpenStreetMap; map.css lo pasa a gris claro para que el color lo lleven solo las parcelas.
// (Los mosaicos grises de CARTO ya piden clave de API: sin ella llegan con una marca de agua)
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

let parcels = [];
let polygonsLayer = null;
let pointsLayer = null;
// Verdadero si la carga de economía falló; entonces las capas de riesgo están deshabilitadas
let economicsFailed = false;

// Índice de la clase de rendimiento de un valor; menos de 2.0 cae en la primera y 5.6 o más en la última
function yieldClassIndex(value) {
  const index = YIELD_CLASSES.findIndex((c) => value < c.to);
  return index === -1 ? YIELD_CLASSES.length - 1 : index;
}

function yieldColor(value) {
  return YIELD_CLASSES[yieldClassIndex(value)].color;
}

function colorValue(p) {
  // Rendimiento observado, o predicción del modelo solo para las 59 a predecir
  if (layerSelect.value === "yield") return p.yield_t_ha;
  return p.set === "PREDICCION" ? p.pred : null;
}

// Color de relleno de la parcela en la capa activa; null si la capa no tiene valor para ella
function fillColorOf(p) {
  const mode = layerSelect.value;
  if (mode === "set") return SET_COLORS[p.set];
  if (RISK_LAYERS.has(mode)) {
    const level = RISK_LEVELS.get(p[RISK_LAYERS.get(mode).light]);
    return level ? level.color : null;
  }
  const value = colorValue(p);
  return value === null || value === undefined ? null : yieldColor(value);
}

function featureStyle(feature) {
  const p = feature.properties;
  const base = { weight: 1, color: BORDER, opacity: BORDER_OPACITY, fillOpacity: 0.85, dashArray: null };
  const fillColor = fillColorOf(p);
  if (fillColor === null) {
    // Sin valor en este modo: gris con borde punteado, para no depender solo del color
    return { ...base, fillColor: NO_DATA.color, color: NO_DATA.border, opacity: 1, fillOpacity: 0.6, dashArray: "3 3" };
  }
  return { ...base, fillColor };
}

function pointStyle(feature) {
  const noData = fillColorOf(feature.properties) === null;
  // Anillo blanco para separar los círculos que se enciman; punteado gris si no hay valor
  return {
    ...featureStyle(feature),
    radius: POINT_RADIUS,
    weight: 1.5,
    color: noData ? NO_DATA.border : "#ffffff",
    opacity: 1,
    dashArray: noData ? "2 2" : null,
    fillOpacity: noData ? 0.7 : 0.95,
  };
}

function formatNumber(value, digits) {
  return value.toLocaleString("es-MX", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// Fila etiqueta–valor de la mini tarjeta del tooltip
function tipRow(label, value) {
  return `<div class="tip__row"><dt>${label}</dt><dd>${value}</dd></div>`;
}

// Fila de un riesgo: probabilidad y, si la API trae el semáforo, su nivel con texto (bajo, medio o alto)
function riskRow(label, probability, light) {
  const level = RISK_LEVELS.get(light);
  const badge = level ? ` <span class="badge ${level.badge}">Riesgo ${level.text}</span>` : "";
  return tipRow(label, `${formatNumber(probability * 100, 0)} %${badge}`);
}

// Mini tarjeta del tooltip: ID y conjunto, la cifra principal grande y filas etiqueta–valor
function tooltipHtml(p) {
  const training = p.set === "ENTRENAMIENTO";
  const dot = training ? "dot--entrenamiento" : "dot--prediccion";
  const rows = [tipRow("Municipio", `${p.municipality}, ${p.state}`)];
  if (!training) {
    rows.push(tipRow("Intervalo p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
    rows.push(tipRow("Probabilidad bajo 2.5 t/ha", `${formatNumber(p.prob_below * 100, 0)} %`));
  }
  rows.push(tipRow("Área", `${formatNumber(p.area_ha, 2)} ha`));
  // Riesgo económico, solo si se cargó la economía
  if (typeof p.prob_not_cover_costs === "number") {
    rows.push(riskRow("No cubrir costos", p.prob_not_cover_costs, p.light_costs));
  }
  if (typeof p.prob_not_pay_credit === "number") {
    rows.push(riskRow("No pagar el crédito", p.prob_not_pay_credit, p.light_credit));
  }
  return '<div class="tip">'
    + `<div class="tip__head"><strong class="tip__id">${p.id}</strong>`
    + `<span class="tip__set"><span class="dot ${dot}"></span>${SET_LABELS[p.set]}</span></div>`
    + `<p class="tip__value">${formatNumber(training ? p.yield_t_ha : p.pred, 2)} <span class="tip__unit">t/ha</span></p>`
    + `<p class="tip__caption">${training ? "Rendimiento observado" : "Rendimiento predicho por el modelo"}</p>`
    + `<dl class="tip__rows">${rows.join("")}</dl>`
    // Siempre es la última línea: avisa que el clic abre la ficha
    + '<p class="tip__hint">Clic para ver la ficha</p>'
    + "</div>";
}

function matchesFilters(p) {
  return (!stateSelect.value || p.state === stateSelect.value)
    && (!municipalitySelect.value || p.municipality === municipalitySelect.value);
}

function fillSelect(select, values) {
  // Conserva la primera opción ("Todos") y agrega las demás en orden alfabético
  select.length = 1;
  for (const value of [...new Set(values)].sort((a, b) => a.localeCompare(b, "es"))) {
    select.add(new Option(value, value));
  }
}

function updateMunicipalities() {
  const inState = parcels.filter((f) => !stateSelect.value || f.properties.state === stateSelect.value);
  fillSelect(municipalitySelect, inState.map((f) => f.properties.municipality));
}

function updateCount(selected) {
  const total = selected.length;
  const training = selected.filter((f) => f.properties.set === "ENTRENAMIENTO").length;
  const noun = total === 1 ? "parcela" : "parcelas";
  let text = `${total} ${noun}: ${training} de entrenamiento y ${total - training} por predecir`;
  // Sin economía, el aviso va en el contador (aria-live polite)
  if (economicsFailed) text += ". No se pudo cargar la economía; las capas de riesgo no están disponibles.";
  countLabel.textContent = text;
}

// Muestra la cifra (con su unidad, si la tiene) y la nota de un indicador
function setStat(key, value, unit, note) {
  stats[key].value.innerHTML = unit ? `${value} <span class="stat__unit">${unit}</span>` : value;
  stats[key].note.textContent = note;
}

// Indicadores de las parcelas mostradas: se recalculan con cada cambio de estado o municipio
function updateStats(selected) {
  const toPredict = selected.filter((f) => f.properties.set === "PREDICCION");
  setStat("shown", selected.length, "", `${selected.length - toPredict.length} de entrenamiento`);
  setStat("to-predict", toPredict.length, "", "Sin rendimiento observado");

  // Promedio simple de la predicción de las parcelas por predecir
  const preds = toPredict.map((f) => f.properties.pred).filter((v) => typeof v === "number");
  if (preds.length) {
    const mean = preds.reduce((sum, v) => sum + v, 0) / preds.length;
    setStat("pred-mean", formatNumber(mean, 2), "t/ha",
      preds.length === 1 ? "De la única parcela por predecir" : `Promedio simple de ${preds.length} parcelas por predecir`);
  } else {
    setStat("pred-mean", "—", "", "No hay parcelas por predecir en la selección");
  }

  // Parte de las parcelas mostradas con semáforo rojo en el crédito (probabilidad de 30 % o más).
  // Se usa el crédito y no los costos: casi todas las parcelas salen en rojo en costos y la cifra no distinguiría nada
  if (economicsFailed) {
    setStat("risk", "—", "", "No se pudo cargar la economía");
    return;
  }
  const withLight = selected.filter((f) => RISK_LEVELS.has(f.properties.light_credit));
  if (!withLight.length) {
    setStat("risk", "—", "", "Sin dato de riesgo en la selección");
    return;
  }
  const high = withLight.filter((f) => f.properties.light_credit === "rojo").length;
  setStat("risk", formatNumber((high / withLight.length) * 100, 0), "%",
    `${high} de ${withLight.length}, con probabilidad de 30 % o más`);
}

// Fila de la leyenda: muestra de color, rótulo y número de parcelas mostradas en esa clase
function legendRow(color, label, count, extraClass = "") {
  return `<div class="legend-row"><span class="legend-swatch ${extraClass}" style="background:${color}"></span>`
    + `<span class="legend-label">${label}</span><span class="legend-count">${count}</span></div>`;
}

// Leyenda plegable: el título (con el rótulo de la columna de conteos) abre y cierra las filas
function legendHtml(title, rows) {
  return `<details class="legend-details"${legendOpen ? " open" : ""}>`
    + `<summary class="legend-head"><strong>${title}</strong><span class="legend-count-title">Parcelas</span></summary>`
    + `<div class="legend-body">${rows.join("")}</div></details>`;
}

// Cuenta cuántas parcelas caen en cada clave; null agrupa las que no tienen valor
function countBy(selected, keyOf) {
  const counts = new Map();
  for (const f of selected) {
    const key = keyOf(f.properties);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

// En el celular la leyenda empieza plegada para no tapar el mapa; se recuerda si el usuario la abre o la cierra
let legendOpen = !window.matchMedia("(max-width: 600px)").matches;
const legend = L.control({ position: "bottomright" });
legend.onAdd = () => {
  const div = L.DomUtil.create("div", "legend");
  // Los clics en la leyenda no llegan al mapa; «toggle» no burbujea, por eso se escucha en captura
  L.DomEvent.disableClickPropagation(div);
  div.addEventListener("toggle", (event) => {
    legendOpen = event.target.open;
  }, true);
  return div;
};
legend.addTo(map);

// Leyenda de la capa activa, con el número de parcelas mostradas en cada clase
function updateLegend(selected) {
  const div = legend.getContainer();
  const mode = layerSelect.value;
  if (mode === "set") {
    const counts = countBy(selected, (p) => p.set);
    div.innerHTML = legendHtml("Conjunto",
      Object.keys(SET_COLORS).map((k) => legendRow(SET_COLORS[k], SET_LABELS[k], counts.get(k) ?? 0)));
  } else if (RISK_LAYERS.has(mode)) {
    // Los tres niveles del semáforo con su rango de probabilidad, y la entrada de sin dato
    const { light, title } = RISK_LAYERS.get(mode);
    const counts = countBy(selected, (p) => (RISK_LEVELS.has(p[light]) ? p[light] : null));
    div.innerHTML = legendHtml(title, [
      ...[...RISK_LEVELS].map(([key, level]) => legendRow(level.color, `Riesgo ${level.text}: ${level.range}`, counts.get(key) ?? 0)),
      legendRow(NO_DATA.color, "Sin dato", counts.get(null) ?? 0, "legend-swatch--no-data"),
    ]);
  } else {
    const counts = countBy(selected, (p) => {
      const value = colorValue(p);
      return value === null || value === undefined ? null : yieldClassIndex(value);
    });
    div.innerHTML = legendHtml(LEGEND_TITLES[mode], [
      ...YIELD_CLASSES.map((c, i) => legendRow(c.color, `${c.from.toFixed(1)} a ${c.to.toFixed(1)}`, counts.get(i) ?? 0)),
      legendRow(NO_DATA.color, NO_DATA_LABELS[mode], counts.get(null) ?? 0, "legend-swatch--no-data"),
    ]);
  }
}

function bindInteractions(feature, layer, reset) {
  layer.bindTooltip(tooltipHtml(feature.properties), { sticky: true, className: "parcel-tip", opacity: 1 });
  layer.on({
    mouseover: () => {
      layer.setStyle({ weight: 3, color: BORDER_HOVER, opacity: 1 });
      layer.bringToFront();
    },
    mouseout: reset,
    // Clic: va a la ficha de la parcela
    click: () => window.location.assign(detailUrl(feature.properties.id)),
  });
}

function showByZoom() {
  if (!polygonsLayer) return;
  const usePoints = map.getZoom() < POINT_ZOOM;
  const show = usePoints ? pointsLayer : polygonsLayer;
  const hide = usePoints ? polygonsLayer : pointsLayer;
  if (map.hasLayer(hide)) hide.remove();
  if (!map.hasLayer(show)) show.addTo(map);
}

function draw(fit) {
  if (polygonsLayer) polygonsLayer.remove();
  if (pointsLayer) pointsLayer.remove();
  const selected = parcels.filter((f) => matchesFilters(f.properties));

  polygonsLayer = L.geoJSON(selected, {
    style: featureStyle,
    onEachFeature: (feature, layer) => bindInteractions(feature, layer, () => polygonsLayer.resetStyle(layer)),
  });
  pointsLayer = L.featureGroup(selected.map((feature) => {
    const center = L.geoJSON(feature).getBounds().getCenter();
    const marker = L.circleMarker(center, pointStyle(feature));
    bindInteractions(feature, marker, () => marker.setStyle(pointStyle(feature)));
    return marker;
  }));

  updateCount(selected);
  updateStats(selected);
  updateLegend(selected);
  updateActiveFilters();
  if (fit && selected.length) map.fitBounds(polygonsLayer.getBounds(), { padding: [20, 20] });
  showByZoom();
}

function fetchJson(url) {
  return fetch(url).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });
}

// Ruta de la ficha: data-detail-url trae el marcador __ID__, que se cambia por el ID codificado
function detailUrl(id) {
  return mapElement.dataset.detailUrl.replace("__ID__", encodeURIComponent(id));
}

// URL de descarga en CSV: la base sale de data-* y solo se agregan los filtros que tienen valor
function csvUrl(base, filters) {
  const url = new URL(base, window.location.href);
  url.searchParams.set("format", "csv");
  for (const [key, value] of Object.entries(filters)) {
    if (value) url.searchParams.set(key, value);
  }
  return url.href;
}

function updateDownloadLinks() {
  predictionsLink.href = csvUrl(mapElement.dataset.predictionsUrl, {
    state: stateSelect.value,
    municipality: municipalitySelect.value,
  });
  economicsLink.href = csvUrl(mapElement.dataset.economicsUrl, {});
}

// Capa y filtros en location.hash, p. ej. #layer=risk_credit&state=Puebla&municipality=Chignahuapan
function saveState() {
  const params = new URLSearchParams({ layer: layerSelect.value });
  if (stateSelect.value) params.set("state", stateSelect.value);
  if (municipalitySelect.value) params.set("municipality", municipalitySelect.value);
  history.replaceState(null, "", `${location.pathname}${location.search}#${params}`);
}

// Se llama tras cada cambio: deja al día los enlaces de descarga y la URL
function syncState() {
  updateDownloadLinks();
  saveState();
}

// Valor si el selector tiene una opción habilitada con ese valor; si no, null
function enabledValue(select, value) {
  const option = [...select.options].find((o) => o.value === value);
  return option && !option.disabled ? value : null;
}

// Aplica la capa y los filtros del hash; lo que no exista o no esté habilitado se ignora
function restoreState() {
  const params = new URLSearchParams(location.hash.slice(1));
  layerSelect.value = enabledValue(layerSelect, params.get("layer")) ?? "set";
  stateSelect.value = enabledValue(stateSelect, params.get("state")) ?? "";
  // El municipio depende del estado: sus opciones se llenan antes de validarlo
  updateMunicipalities();
  municipalitySelect.value = enabledValue(municipalitySelect, params.get("municipality")) ?? "";
}

// Texto del botón «Capa y filtros» (celular): cuántos filtros de estado o municipio están activos
function updateActiveFilters() {
  const active = [stateSelect.value, municipalitySelect.value].filter(Boolean).length;
  filtersActive.textContent = active ? ` · ${active} ${active === 1 ? "filtro" : "filtros"}` : "";
}

// Sin economía, las capas de riesgo quedan deshabilitadas y el resto del mapa sigue igual
function disableRiskLayers() {
  for (const option of layerSelect.options) {
    if (RISK_LAYERS.has(option.value)) option.disabled = true;
  }
}

map.on("zoomend", showByZoom);
layerSelect.addEventListener("change", () => {
  draw(false);
  syncState();
});
stateSelect.addEventListener("change", () => {
  // Al cambiar de estado, el municipio vuelve a "Todos"
  updateMunicipalities();
  draw(true);
  syncState();
});
municipalitySelect.addEventListener("change", () => {
  draw(true);
  syncState();
});

// Botón «Capa y filtros» (solo se ve en el celular): abre o cierra el panel; el mapa recalcula su tamaño
filtersToggle.addEventListener("click", () => {
  const open = filtersToggle.getAttribute("aria-expanded") === "true";
  filtersToggle.setAttribute("aria-expanded", String(!open));
  map.invalidateSize();
});

// Menú «Descargar»: se cierra con Esc (el foco vuelve al botón), al hacer clic fuera o al elegir un archivo
downloadMenu.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && downloadMenu.open) {
    downloadMenu.open = false;
    downloadMenu.querySelector("summary").focus();
  }
});
document.addEventListener("click", (event) => {
  if (downloadMenu.open && !downloadMenu.contains(event.target)) downloadMenu.open = false;
});
for (const link of [predictionsLink, economicsLink]) {
  link.addEventListener("click", () => {
    downloadMenu.open = false;
  });
}

// La economía se pide a la par; si falla, el mapa se dibuja igual, sin las capas de riesgo
const economicsRequest = fetchJson(mapElement.dataset.economicsUrl).catch(() => null);

Promise.all([fetchJson(mapElement.dataset.parcelsUrl), fetchJson(mapElement.dataset.predictionsUrl), economicsRequest])
  .then(([geojson, predictions, economics]) => {
    // Une a cada parcela su predicción e intervalo
    const byId = new Map(predictions.map((r) => [r.id, r]));
    parcels = geojson.features;
    for (const f of parcels) {
      const r = byId.get(f.properties.id);
      if (r) Object.assign(f.properties, { pred: r.pred, p10: r.p10, p90: r.p90, prob_below: r.prob_below });
    }
    // Y a cada una su riesgo económico y su semáforo; sin economía, sus capas quedan deshabilitadas
    economicsFailed = !Array.isArray(economics);
    if (economicsFailed) {
      disableRiskLayers();
    } else {
      const economyById = new Map(economics.map((r) => [r.id, r]));
      for (const f of parcels) {
        const e = economyById.get(f.properties.id);
        if (e) {
          Object.assign(f.properties, {
            prob_not_cover_costs: e.prob_not_cover_costs,
            light_costs: e.light_costs,
            prob_not_pay_credit: e.prob_not_pay_credit,
            light_credit: e.light_credit,
          });
        }
      }
    }
    fillSelect(stateSelect, parcels.map((f) => f.properties.state));
    // La capa y los filtros vienen del hash si son válidos; luego se dibuja
    restoreState();
    updateDownloadLinks();
    draw(true);
  })
  .catch(() => {
    countLabel.textContent = "No se pudieron cargar las parcelas.";
  });
