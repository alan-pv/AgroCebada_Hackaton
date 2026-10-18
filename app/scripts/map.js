// Mapa de la página inicial: parcelas coloreadas por conjunto, rendimiento, predicción o riesgo económico.
// El clic en una parcela la elige y abre su resumen en el panel; sin parcela elegida, el panel lista las
// parcelas por predecir ordenadas por riesgo. En el celular el panel es una hoja plegable bajo el mapa

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
// Nota de la leyenda en las capas de riesgo: cuántas de las mostradas salen en medio o alto, y que eso
// viene de los costos y precios por defecto, no de poca confianza en la predicción
function riskNote(counts) {
  const withLight = [...RISK_LEVELS.keys()].reduce((sum, key) => sum + (counts.get(key) ?? 0), 0);
  if (!withLight) return "";
  const notLow = (counts.get("amarillo") ?? 0) + (counts.get("rojo") ?? 0);
  return `${notLow} de ${withLight} salen en medio o alto con los costos y precios por defecto. `
    + "No es poca confianza en la predicción: ver «¿Cómo se lee el semáforo?».";
}
// Nivel de confianza de /api/parcels/<id>: texto y clase del badge, como en la ficha
const CONFIDENCE_LEVELS = new Map([
  ["alta", { text: "Confianza alta", badge: "badge--bajo" }],
  ["media", { text: "Confianza media", badge: "badge--medio" }],
  ["baja", { text: "Confianza baja", badge: "badge--alto" }],
]);
// Modelo municipal: clases de color de cada capa, en orden de leyenda. Rendimiento esperado en t/ha, con cortes fijos
const MUN_YIELD_CLASSES = [
  { to: 1.5, label: "Menos de 1.5", color: "#d3e5f9" },
  { to: 2.0, label: "1.5 a 2.0", color: "#9ec5f4" },
  { to: 2.5, label: "2.0 a 2.5", color: "#6da7ec" },
  { to: 3.0, label: "2.5 a 3.0", color: "#3987e5" },
  { to: Infinity, label: "3.0 o más", color: "#184f95" },
];
// Probabilidad de rendimiento bajo: los niveles del semáforo de riesgo (mismos cortes de 10 % y 30 %)
const MUN_RISK_CLASSES = [...RISK_LEVELS.values()].map((level) => ({ label: capitalize(level.range), color: level.color }));
// Confianza del modelo: paleta Okabe-Ito, tres colores distinguibles
const MUN_CONFIDENCE_CLASSES = [
  { key: "alta", label: "Confianza alta", color: "#0072B2" },
  { key: "media", label: "Confianza media", color: "#F0E442" },
  { key: "baja", label: "Confianza baja", color: "#CC79A7" },
];
// Municipios sin estimación (fuera del rango ambiental del modelo): gris claro con borde punteado
const MUN_NO_ESTIMATE = { color: "#e7e6e0", border: "#898781" };
// Capas del modelo municipal: título de su leyenda y clases
const MUN_LAYERS = new Map([
  ["mun-esperado", { title: "Rendimiento esperado (t/ha)", classes: MUN_YIELD_CLASSES }],
  ["mun-riesgo", { title: "Probabilidad de rendimiento bajo (< 2 t/ha)", classes: MUN_RISK_CLASSES }],
  ["mun-confianza", { title: "Confianza del modelo", classes: MUN_CONFIDENCE_CLASSES }],
]);

// Orden de la lista del panel. prob y light dicen qué riesgo muestra el badge de cada fila;
// al ordenar por rendimiento, el badge sigue mostrando el riesgo de no pagar el crédito
const SORTS = {
  credit: { prob: "prob_not_pay_credit", light: "light_credit", column: "No pagar el crédito",
            text: "de mayor a menor riesgo de no pagar el crédito", by: "riesgo" },
  costs: { prob: "prob_not_cover_costs", light: "light_costs", column: "No cubrir costos",
           text: "de mayor a menor riesgo de no cubrir costos", by: "riesgo" },
  pred: { prob: "prob_not_pay_credit", light: "light_credit", column: "No pagar el crédito",
          text: "de menor a mayor rendimiento predicho", by: "rendimiento" },
};

// Borde de las parcelas: gris oscuro semitransparente, para que lean sobre el mapa base gris claro
const BORDER = "#3d3c38";
const BORDER_OPACITY = 0.7;
const BORDER_HOVER = "#0b0b0b";
// Parcela elegida: borde negro más grueso, que se queda al quitar el puntero
const SELECTED_WEIGHT = 4;

// Por debajo de este zoom las parcelas miden pocos píxeles y se dibujan como círculos en su centro
const POINT_ZOOM = 13;
const POINT_RADIUS = 6;
// Zoom mínimo al centrar el mapa en una parcela elegida en la lista: ya se ve su polígono
const FOCUS_ZOOM = 15;

// Mapa base: estilo «Positron» de OpenFreeMap (vectorial, gratis y sin clave), dibujado con MapLibre GL dentro de Leaflet.
// Si el navegador no tiene WebGL, o el estilo no carga a tiempo, se usan los mosaicos de OpenStreetMap en gris
const BASEMAP_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const BASEMAP_ATTRIBUTION = '<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> '
  + '<a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">&copy; OpenMapTiles</a> '
  + 'Datos de <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';
const BASEMAP_TIMEOUT_MS = 10000;

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
// Panel: lista de parcelas por predecir y resumen de la parcela elegida
const panel = document.getElementById("map-panel");
const panelToggle = document.getElementById("panel-toggle");
const panelToggleText = document.getElementById("panel-toggle-text");
const panelOpenButton = document.getElementById("panel-open");
const listView = document.getElementById("panel-list");
const listTitle = document.getElementById("plist-title");
const listSummary = document.getElementById("plist-summary");
const listNote = document.getElementById("plist-note");
const listColumnRisk = document.getElementById("plist-col-risk");
const listItems = document.getElementById("plist-items");
const sortSelect = document.getElementById("plist-sort");
const parcelView = document.getElementById("panel-parcel");
const summaryContent = document.getElementById("psum-content");
const backButton = document.getElementById("psum-back");

// En el celular (hasta 600 px) el panel es una hoja inferior; en escritorio, una columna a la derecha
const mobileQuery = window.matchMedia("(max-width: 600px)");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Vista inicial sobre la zona de estudio; se ajusta al cargar las parcelas
const map = L.map(mapElement).setView([19.8, -98.4], 10);
// Municipios en su propio panel, por debajo de las parcelas (el de los polígonos de Leaflet es 400)
map.createPane("municipal").style.zIndex = 350;

let parcels = [];
// Parcelas que pasan los filtros, en el último dibujo
let shown = [];
let polygonsLayer = null;
let pointsLayer = null;
// Polígono y círculo de cada parcela mostrada, por ID: sirven para resaltar la elegida y centrar el mapa en ella
const layersById = new Map();
// Verdadero si la carga de economía falló; entonces las capas de riesgo están deshabilitadas
let economicsFailed = false;
// Modelo municipal: municipios (GeoJSON), pedido solo la primera vez que se elige una de sus capas; capa de Leaflet
let municipalFeatures = null;
let municipalRequest = null;
let municipalFailed = false;
let municipalLayer = null;

// Estado del panel: parcela elegida (o null), si está abierto (en el celular, si la hoja está desplegada)
// y a dónde vuelve el foco al cerrarlo
let selectedId = null;
let panelOpen = !mobileQuery.matches;
let returnFocus = null;
// Al cerrar el resumen, el panel vuelve a la lista si ya estaba abierto con ella; si estaba cerrado, se cierra
let closeToList = false;
// Confianza de cada parcela, pedida una sola vez a /api/parcels/<id>
const confidenceRequests = new Map();

// Mapa base

function hasWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

// Respaldo: mosaicos de OpenStreetMap; map.css los pasa a gris claro (clase map--osm) para que el color lo lleven las parcelas.
// (Los mosaicos grises de CARTO ya piden clave de API: sin ella llegan con una marca de agua)
function useOsmTiles() {
  mapElement.classList.add("map--osm");
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
}

// Etiquetas en español: Positron prefiere el nombre en inglés (name_en); aquí va name:es o el nombre local
function spanishLabels(style) {
  for (const layer of style.layers) {
    const field = layer.layout && layer.layout["text-field"];
    if (field && JSON.stringify(field).includes("name_en")) {
      layer.layout["text-field"] = ["coalesce", ["get", "name:es"], ["get", "name"]];
    }
  }
  return style;
}

function addBaseMap() {
  if (!window.maplibregl || !L.maplibreGL || !hasWebGL()) {
    useOsmTiles();
    return;
  }
  let glLayer = null;
  let settled = false;
  // Pasa al respaldo una sola vez y quita la capa vectorial si ya se había agregado
  const fallBack = () => {
    if (settled) return;
    settled = true;
    clearTimeout(timer);
    if (glLayer && map.hasLayer(glLayer)) {
      try {
        map.removeLayer(glLayer);
      } catch {
        glLayer.getContainer()?.remove();
      }
    }
    useOsmTiles();
  };
  const timer = setTimeout(fallBack, BASEMAP_TIMEOUT_MS);

  // El estilo se pide aparte: si falla, el respaldo entra de inmediato y no queda un fondo vacío
  fetchJson(BASEMAP_STYLE_URL).then((style) => {
    if (settled) return;
    glLayer = L.maplibreGL({
      style: spanishLabels(style),
      // Atribución fija: OpenFreeMap, OpenMapTiles y OpenStreetMap
      attributionControl: { customAttribution: BASEMAP_ATTRIBUTION },
    });
    try {
      glLayer.addTo(map);
    } catch {
      // Sin contexto WebGL, MapLibre falla al crearse; la capa queda a medias y se retira a mano
      glLayer.getContainer()?.remove();
      glLayer.onRemove = () => {};
      map.removeLayer(glLayer);
      glLayer = null;
      fallBack();
      return;
    }
    const glMap = glLayer.getMaplibreMap();
    glMap.once("load", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
    });
    // Antes de cargar, un error del estilo o de sus fuentes manda al respaldo; un mosaico suelto que falle, no
    glMap.on("error", (event) => {
      if (!event.tile) fallBack();
    });
  }).catch(fallBack);
}

// Colores y estilos de las parcelas

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
  let style = { ...base, fillColor };
  // Con una capa municipal, la parcela solo lleva contorno: el color lo ponen los municipios de abajo
  if (isMunicipalMode()) {
    style = { ...base, fillColor: BORDER, fillOpacity: 0 };
  } else if (fillColor === null) {
    // Sin valor en este modo: gris con borde punteado, para no depender solo del color
    style = { ...base, fillColor: NO_DATA.color, color: NO_DATA.border, opacity: 1, fillOpacity: 0.6, dashArray: "3 3" };
  }
  if (p.id === selectedId) {
    style = { ...style, weight: SELECTED_WEIGHT, color: BORDER_HOVER, opacity: 1, dashArray: null };
  }
  return style;
}

function pointStyle(feature) {
  // Con una capa municipal no hay «sin dato»: el círculo va oscuro con anillo blanco, como las parcelas en contorno
  const noData = !isMunicipalMode() && fillColorOf(feature.properties) === null;
  // Anillo blanco para separar los círculos que se enciman; punteado gris si no hay valor
  const style = {
    ...featureStyle(feature),
    radius: POINT_RADIUS,
    weight: 1.5,
    color: noData ? NO_DATA.border : "#ffffff",
    opacity: 1,
    dashArray: noData ? "2 2" : null,
    fillOpacity: noData ? 0.7 : 0.95,
  };
  // La elegida: círculo más grande con anillo negro
  if (feature.properties.id === selectedId) {
    return { ...style, radius: POINT_RADIUS + 3, weight: 3, color: BORDER_HOVER, dashArray: null };
  }
  return style;
}

// Textos

function formatNumber(value, digits) {
  return value.toLocaleString("es-MX", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function formatPercent(probability) {
  return `${formatNumber(probability * 100, 0)} %`;
}

function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Fila etiqueta–valor de la mini tarjeta del tooltip
function tipRow(label, value) {
  return `<div class="tip__row"><dt>${label}</dt><dd>${value}</dd></div>`;
}

// Fila de un riesgo: probabilidad y, si la API trae el semáforo, su nivel con texto (bajo, medio o alto)
function riskRow(label, probability, light) {
  const level = RISK_LEVELS.get(light);
  const badge = level ? ` <span class="badge ${level.badge}">Riesgo ${level.text}</span>` : "";
  return tipRow(label, `${formatPercent(probability)}${badge}`);
}

// Mini tarjeta del tooltip: ID y conjunto, la cifra principal grande y filas etiqueta–valor
function tooltipHtml(p) {
  const training = p.set === "ENTRENAMIENTO";
  const dot = training ? "dot--entrenamiento" : "dot--prediccion";
  const rows = [tipRow("Municipio", `${p.municipality}, ${p.state}`)];
  if (!training) {
    rows.push(tipRow("Intervalo p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
    rows.push(tipRow("Probabilidad bajo 2.5 t/ha", formatPercent(p.prob_below)));
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
    // Siempre es la última línea: avisa que el clic abre el resumen en el panel
    + '<p class="tip__hint">Clic para ver el resumen</p>'
    + "</div>";
}

// Filtros, contador e indicadores

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
  if (municipalFailed && isMunicipalMode()) text += ". No se pudo cargar el modelo municipal.";
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

// Leyenda

// Fila de la leyenda: muestra de color, rótulo y número de parcelas mostradas en esa clase
function legendRow(color, label, count, extraClass = "") {
  return `<div class="legend-row"><span class="legend-swatch ${extraClass}" style="background:${color}"></span>`
    + `<span class="legend-label">${label}</span><span class="legend-count">${count}</span></div>`;
}

// Leyenda plegable: el título (con el rótulo de la columna de conteos) abre y cierra las filas
function legendHtml(title, rows, note = "", countTitle = "Parcelas") {
  return `<details class="legend-details"${legendOpen ? " open" : ""}>`
    + `<summary class="legend-head"><strong>${title}</strong><span class="legend-count-title">${countTitle}</span></summary>`
    + `<div class="legend-body">${rows.join("")}${note ? `<p class="legend-note">${note}</p>` : ""}</div></details>`;
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
let legendOpen = !mobileQuery.matches;
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
  if (MUN_LAYERS.has(mode)) {
    div.innerHTML = municipalLegendHtml(mode);
  } else if (mode === "set") {
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
    ], riskNote(counts));
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

// Capas de parcelas

function bindInteractions(feature, layer, reset) {
  layer.bindTooltip(tooltipHtml(feature.properties), { sticky: true, className: "parcel-tip", opacity: 1 });
  layer.on({
    mouseover: () => {
      const weight = feature.properties.id === selectedId ? SELECTED_WEIGHT : 3;
      layer.setStyle({ weight, color: BORDER_HOVER, opacity: 1 });
      layer.bringToFront();
    },
    mouseout: reset,
    // Clic: elige la parcela y abre su resumen en el panel. El tooltip se cierra para no tapar el mapa
    click: () => {
      layer.closeTooltip();
      openParcel(feature.properties.id);
    },
  });
}

// La parcela elegida va encima de sus vecinas
function raiseSelected() {
  const entry = layersById.get(selectedId);
  if (!entry) return;
  if (map.hasLayer(entry.polygon)) entry.polygon.bringToFront();
  if (map.hasLayer(entry.marker)) entry.marker.bringToFront();
}

function showByZoom() {
  if (!polygonsLayer) return;
  const usePoints = map.getZoom() < POINT_ZOOM;
  const show = usePoints ? pointsLayer : polygonsLayer;
  const hide = usePoints ? polygonsLayer : pointsLayer;
  if (map.hasLayer(hide)) hide.remove();
  if (!map.hasLayer(show)) show.addTo(map);
  raiseSelected();
}

function draw(fit) {
  if (polygonsLayer) polygonsLayer.remove();
  if (pointsLayer) pointsLayer.remove();
  layersById.clear();
  const selected = parcels.filter((f) => matchesFilters(f.properties));
  shown = selected;

  polygonsLayer = L.geoJSON(selected, {
    style: featureStyle,
    onEachFeature: (feature, layer) => {
      bindInteractions(feature, layer, () => polygonsLayer.resetStyle(layer));
      layersById.set(feature.properties.id, { feature, polygon: layer, marker: null });
    },
  });
  pointsLayer = L.featureGroup(selected.map((feature) => {
    const center = L.geoJSON(feature).getBounds().getCenter();
    const marker = L.circleMarker(center, pointStyle(feature));
    bindInteractions(feature, marker, () => marker.setStyle(pointStyle(feature)));
    layersById.get(feature.properties.id).marker = marker;
    return marker;
  }));

  updateCount(selected);
  updateStats(selected);
  updateLegend(selected);
  updateActiveFilters();
  // Si los filtros dejan fuera a la parcela elegida, el panel vuelve a la lista
  if (selectedId !== null && !layersById.has(selectedId)) {
    const focusWasInSummary = parcelView.contains(document.activeElement);
    selectedId = null;
    renderPanel();
    if (focusWasInSummary) listTitle.focus();
  }
  renderList();
  if (fit && selected.length) map.fitBounds(polygonsLayer.getBounds(), { padding: [20, 20] });
  drawMunicipal(fit);
  showByZoom();
}

// Cambia la parcela elegida y vuelve a pintar la anterior y la nueva
function setSelected(id) {
  const previous = selectedId;
  selectedId = id;
  for (const pid of [previous, id]) {
    const entry = layersById.get(pid);
    if (!entry) continue;
    entry.polygon.setStyle(featureStyle(entry.feature));
    entry.marker.setStyle(pointStyle(entry.feature));
  }
  raiseSelected();
}

// Modelo municipal

// Verdadero si la capa elegida es una del modelo municipal
function isMunicipalMode() {
  return MUN_LAYERS.has(layerSelect.value);
}

// Índice del nivel del semáforo para una probabilidad de 0 a 1: menos de 10 % bajo, de 10 a menos de 30 % medio, lo demás alto
function probabilityIndex(probability) {
  if (probability < 0.1) return 0;
  return probability < 0.3 ? 1 : 2;
}

// Clase de un municipio en la capa activa (rótulo y color); null si no tiene estimación
function municipalClassOf(mode, p) {
  if (typeof p.esperado !== "number") return null;
  if (mode === "mun-esperado") return MUN_YIELD_CLASSES.find((c) => p.esperado < c.to);
  if (mode === "mun-riesgo") return MUN_RISK_CLASSES[probabilityIndex(p.prob_bajo_2)];
  return MUN_CONFIDENCE_CLASSES.find((c) => c.key === p.confianza) ?? null;
}

// Municipio elegido en el filtro (dentro del estado elegido, si hay): se resalta y, al elegirlo, el mapa se centra en él
function isChosenMunicipality(p) {
  return Boolean(municipalitySelect.value) && p.municipio === municipalitySelect.value
    && (!stateSelect.value || p.estado === stateSelect.value);
}

// Pide el modelo municipal la primera vez que se elige una de sus capas; si falló, se vuelve a pedir al volver a elegirla
function requestMunicipal() {
  if (!isMunicipalMode() || municipalFeatures || municipalRequest) return;
  municipalFailed = false;
  municipalRequest = fetchJson(mapElement.dataset.municipalUrl)
    .then((geojson) => {
      municipalFeatures = geojson.features;
    })
    .catch(() => {
      // Sin el modelo, el mapa sigue igual; el aviso va en el contador y en la leyenda
      municipalFailed = true;
    })
    .then(() => {
      municipalRequest = null;
      // Al llegar (o fallar), se redibuja con la capa elegida; si ya se eligió un municipio, el mapa se centra en él
      if (isMunicipalMode()) draw(Boolean(municipalitySelect.value));
    });
}

// Mini tarjeta del tooltip de un municipio: nombre y estado, la cifra esperada o, sin estimación, el aviso y la distancia al SIAP
function municipalTooltipHtml(p) {
  const rows = [];
  let value = '<p class="tip__caption">Fuera del rango ambiental del modelo: sin estimación</p>';
  if (typeof p.esperado === "number") {
    const confidence = CONFIDENCE_LEVELS.get(p.confianza);
    value = `<p class="tip__value">${formatNumber(p.esperado, 2)} <span class="tip__unit">t/ha</span></p>`
      + '<p class="tip__caption">Rendimiento esperado</p>';
    rows.push(tipRow("Intervalo p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
    rows.push(tipRow("Probabilidad bajo 2 t/ha", formatPercent(p.prob_bajo_2)));
    rows.push(tipRow("Confianza", confidence ? `<span class="badge ${confidence.badge}">${confidence.text}</span>` : "Sin dato"));
  } else if (typeof p.dist_siap_km === "number") {
    rows.push(tipRow("Distancia al SIAP más cercano", `${formatNumber(p.dist_siap_km, 1)} km`));
  }
  // Historial de la estadística SIAP del municipio, si lo tiene
  if (p.con_siap) {
    rows.push(tipRow("Historial SIAP", `${formatNumber(p.siap_media, 2)} t/ha en ${p.siap_anios} años`));
    rows.push(tipRow("Años bajo 2 t/ha", formatPercent(p.siap_frac_bajo_2)));
  }
  return '<div class="tip">'
    + `<div class="tip__head"><strong class="tip__id">${p.municipio}</strong><span class="tip__set">${p.estado}</span></div>`
    + value
    + `<dl class="tip__rows">${rows.join("")}</dl>`
    + "</div>";
}

// Color y borde de cada municipio: en gris punteado si no tiene estimación; el municipio elegido, con borde negro grueso
function municipalStyle(feature) {
  const p = feature.properties;
  const cls = municipalClassOf(layerSelect.value, p);
  let style = { weight: 0.6, color: "#ffffff", opacity: 1, fillColor: cls ? cls.color : MUN_NO_ESTIMATE.color, fillOpacity: 0.85, dashArray: null };
  if (!cls) style = { ...style, weight: 1, color: MUN_NO_ESTIMATE.border, fillOpacity: 0.6, dashArray: "4 3" };
  if (isChosenMunicipality(p)) style = { ...style, weight: 3, color: BORDER_HOVER, opacity: 1 };
  return style;
}

// Dibuja los municipios del estado elegido (o de todo el país) en su panel; si hay municipio elegido y se pide, centra el mapa en él
function drawMunicipal(fit) {
  if (municipalLayer) municipalLayer.remove();
  municipalLayer = null;
  if (!isMunicipalMode() || !municipalFeatures) return;
  const features = municipalFeatures.filter((f) => !stateSelect.value || f.properties.estado === stateSelect.value);
  municipalLayer = L.geoJSON(features, {
    pane: "municipal",
    style: municipalStyle,
    onEachFeature: (feature, layer) => {
      layer.bindTooltip(municipalTooltipHtml(feature.properties), { sticky: true, className: "parcel-tip", opacity: 1 });
      layer.on({
        mouseover: () => {
          layer.setStyle({ weight: 3, color: BORDER_HOVER, opacity: 1 });
          layer.bringToFront();
        },
        mouseout: () => {
          if (municipalLayer) municipalLayer.resetStyle(layer);
        },
      });
    },
  }).addTo(map);
  const chosen = municipalLayer.getLayers().filter((layer) => isChosenMunicipality(layer.feature.properties));
  if (fit && chosen.length) map.fitBounds(L.featureGroup(chosen).getBounds(), { padding: [20, 20] });
}

// Leyenda de la capa municipal: sus clases con el número de municipios del estado elegido, y la nota del modelo
function municipalLegendHtml(mode) {
  const { title, classes } = MUN_LAYERS.get(mode);
  if (municipalFailed) return legendHtml(title, [], "No se pudo cargar el modelo municipal.");
  if (!municipalFeatures) return legendHtml(title, [], "Cargando el modelo municipal…");
  const inState = municipalFeatures.filter((f) => !stateSelect.value || f.properties.estado === stateSelect.value);
  const counts = countBy(inState, (p) => municipalClassOf(mode, p));
  const rows = [
    ...classes.map((c) => legendRow(c.color, c.label, counts.get(c) ?? 0)),
    legendRow(MUN_NO_ESTIMATE.color, "Sin estimación (fuera del rango del modelo)", counts.get(null) ?? 0, "legend-swatch--no-data"),
  ];
  // El modelo y su año de referencia vienen en cada municipio
  const meta = municipalFeatures[0]?.properties;
  const note = meta ? `Modelo municipal (${meta.modelo}); año de referencia ${meta.anio_referencia}` : "";
  return legendHtml(title, rows, note, "Municipios");
}

// Lista de parcelas por predecir

// Número para ordenar: los que faltan van al final de la lista
function sortValue(value, descending) {
  if (typeof value !== "number") return descending ? -Infinity : Infinity;
  return value;
}

function compareParcels(key) {
  const desc = (field) => (a, b) => sortValue(b[field], true) - sortValue(a[field], true);
  const asc = (field) => (a, b) => sortValue(a[field], false) - sortValue(b[field], false);
  // Criterio principal y desempates; al final, el ID para que el orden sea estable
  const criteria = {
    credit: [desc("prob_not_pay_credit"), desc("prob_not_cover_costs"), asc("pred")],
    costs: [desc("prob_not_cover_costs"), desc("prob_not_pay_credit"), asc("pred")],
    pred: [asc("pred"), desc("prob_not_pay_credit")],
  }[key];
  return (a, b) => {
    for (const compare of criteria) {
      const result = compare(a, b);
      if (result) return result;
    }
    return a.id.localeCompare(b.id);
  };
}

// Badge del riesgo de una fila, con el nivel y la probabilidad en texto
function listRiskHtml(p, sort) {
  const level = RISK_LEVELS.get(p[sort.light]);
  if (!level || typeof p[sort.prob] !== "number") return '<span class="plist__risk muted">Sin dato</span>';
  return `<span class="plist__risk badge ${level.badge}"><span class="visually-hidden">Riesgo de ${sort.column.toLowerCase()}: </span>`
    + `${capitalize(level.text)} · ${formatPercent(p[sort.prob])}</span>`;
}

function listRowHtml(p, sort) {
  const pred = typeof p.pred === "number" ? `${formatNumber(p.pred, 2)} <span class="plist__unit">t/ha</span>` : "—";
  return `<li><button type="button" class="plist__row" data-id="${p.id}">`
    + `<span class="plist__name"><strong>${p.id}</strong><span class="plist__muni">${p.municipality}</span></span>`
    + `<span class="plist__pred"><span class="visually-hidden">Predicción: </span>${pred}</span>`
    + (economicsFailed ? "" : listRiskHtml(p, sort))
    + "</button></li>";
}

// Arma la lista con las parcelas por predecir que pasan los filtros, en el orden elegido
function renderList() {
  const key = economicsFailed ? "pred" : sortSelect.value;
  const sort = SORTS[key];
  const rows = shown.map((f) => f.properties).filter((p) => p.set === "PREDICCION").sort(compareParcels(key));
  const total = rows.length;

  listItems.innerHTML = total
    ? rows.map((p) => listRowHtml(p, sort)).join("")
    : '<li class="plist__empty">No hay parcelas por predecir con estos filtros.</li>';
  listSummary.textContent = total ? `${total} ${total === 1 ? "parcela" : "parcelas"}, ${sort.text}` : "";
  listColumnRisk.textContent = sort.column;
  listView.classList.toggle("plist--no-risk", economicsFailed);
  updateToggleText(total, sort);
}

// Título de la hoja en el celular: cuántas hay y cómo van ordenadas, o qué muestra la hoja
function updateToggleText(total = listItems.querySelectorAll(".plist__row").length, sort = SORTS[sortSelect.value]) {
  if (selectedId !== null) {
    panelToggleText.textContent = `Resumen de ${selectedId}`;
  } else if (!total) {
    panelToggleText.textContent = "Ninguna por predecir con estos filtros";
  } else {
    panelToggleText.textContent = `${total} por predecir · ordenadas por ${economicsFailed ? "rendimiento" : sort.by}`;
  }
}

// Resumen de la parcela elegida

function summaryRow(label, value, attrs = "") {
  return `<div class="psum__row"><dt>${label}</dt><dd${attrs}>${value}</dd></div>`;
}

function summaryRiskRow(label, probability, light) {
  if (typeof probability !== "number") return summaryRow(label, '<span class="muted">Sin dato</span>');
  const level = RISK_LEVELS.get(light);
  const badge = level ? ` <span class="badge ${level.badge}">Riesgo ${level.text}</span>` : "";
  return summaryRow(label, `${formatPercent(probability)}${badge}`);
}

function summaryHtml(p) {
  const training = p.set === "ENTRENAMIENTO";
  const dot = training ? "dot--entrenamiento" : "dot--prediccion";
  const value = training ? p.yield_t_ha : p.pred;
  const rows = [];
  if (training && typeof p.pred === "number") rows.push(summaryRow("Predicción validada", `${formatNumber(p.pred, 2)} t/ha`));
  if (typeof p.p10 === "number") rows.push(summaryRow("Rango p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
  if (typeof p.prob_below === "number") rows.push(summaryRow("Probabilidad bajo 2.5 t/ha", formatPercent(p.prob_below)));
  // La confianza llega aparte, de /api/parcels/<id>
  rows.push(summaryRow("Confianza", '<span class="muted">Cargando…</span>', ' id="psum-conf" aria-busy="true"'));
  rows.push(summaryRow("Área", `${formatNumber(p.area_ha, 2)} ha`));

  const risk = economicsFailed
    ? '<p class="psum__empty">No se pudo cargar la economía.</p>'
    : `<dl class="psum__rows">${summaryRiskRow("No cubrir costos", p.prob_not_cover_costs, p.light_costs)}`
      + `${summaryRiskRow("No pagar el crédito", p.prob_not_pay_credit, p.light_credit)}</dl>`;

  return `<div class="psum__head"><h2 id="psum-id" class="psum__id" tabindex="-1">${p.id}</h2>`
    + `<span class="tip__set"><span class="dot ${dot}"></span>${SET_LABELS[p.set]}</span></div>`
    + `<p class="psum__place">${p.municipality}, ${p.state}</p>`
    + `<p class="psum__value">${typeof value === "number" ? formatNumber(value, 2) : "—"} <span class="psum__unit">t/ha</span></p>`
    + `<p class="psum__caption">${training ? "Rendimiento observado" : "Rendimiento predicho por el modelo"}</p>`
    + `<dl class="psum__rows">${rows.join("")}</dl>`
    + '<p id="psum-conf-reason" class="psum__reason" hidden></p>'
    + (training ? '<p class="psum__reason">Parcela de entrenamiento: la predicción es la validada fuera de entrenamiento.</p>' : "")
    + '<h3 class="psum__subtitle">Riesgo económico</h3>'
    + risk
    + '<details class="help-inline"><summary>¿Qué significan estas cifras?</summary><div class="help-inline__body">'
    + "<p>El rango p10 a p90 es donde se espera que caiga el rendimiento real. El p10 es un rendimiento conservador: "
    + "9 de cada 10 parcelas rinden más que ese valor.</p>"
    + "<p>La confianza depende de las parcelas medidas cercanas: alta, al menos una a 400 m o menos; media, ninguna a 400 m, "
    + "pero la más cercana a 800 m o menos; baja, la más cercana a más de 800 m, o el área queda fuera del rango de su régimen. "
    + "No cambia el intervalo.</p>"
    + "<p>El semáforo de riesgo es bajo con menos de 10 %, medio de 10 a menos de 30 % y alto con 30 % o más. "
    + "Con los costos y precios por defecto, muchas parcelas salen en medio o alto. No significa poca confianza en la "
    + "predicción: el costo total suele pedir más rendimiento del esperado, y en el crédito se suma la pérdida histórica "
    + "del municipio. En la ficha se explica y se pueden cambiar el precio y el punto de equilibrio.</p>"
    + "</div></details>"
    + `<div class="psum__footer"><a class="btn btn--primary psum__cta" href="${detailUrl(p.id)}">Ver ficha completa</a></div>`;
}

// Pide la confianza de la parcela (una vez) y la muestra si la parcela sigue elegida
function loadConfidence(id) {
  if (!confidenceRequests.has(id)) {
    confidenceRequests.set(id, fetchJson(detailApiUrl(id)).then((data) => data.confidence));
  }
  confidenceRequests.get(id).then((confidence) => {
    if (selectedId !== id) return;
    const cell = document.getElementById("psum-conf");
    const reason = document.getElementById("psum-conf-reason");
    const level = CONFIDENCE_LEVELS.get(confidence && confidence.level);
    cell.innerHTML = level ? `<span class="badge ${level.badge}">${level.text}</span>` : "Sin dato de confianza";
    cell.removeAttribute("aria-busy");
    if (confidence && confidence.reason) {
      reason.textContent = `${capitalize(confidence.reason)}.`;
      reason.hidden = false;
    }
  }).catch(() => {
    // Se puede volver a pedir la próxima vez que se elija la parcela
    confidenceRequests.delete(id);
    if (selectedId !== id) return;
    const cell = document.getElementById("psum-conf");
    cell.innerHTML = '<span class="psum__error">No se pudo cargar</span>';
    cell.removeAttribute("aria-busy");
  });
}

// Panel: abrir, cerrar y volver a la lista

// Muestra la vista que toca (lista o resumen) y abre o cierra el panel según el tamaño de la pantalla
function renderPanel() {
  const showParcel = selectedId !== null;
  listView.hidden = showParcel;
  parcelView.hidden = !showParcel;
  if (mobileQuery.matches) {
    panel.hidden = false;
    panelOpenButton.hidden = true;
    panel.classList.toggle("is-collapsed", !panelOpen);
    panelToggle.setAttribute("aria-expanded", String(panelOpen));
  } else {
    panel.hidden = !panelOpen;
    panel.classList.remove("is-collapsed");
    panelOpenButton.hidden = panelOpen;
  }
  updateToggleText();
}

// El mapa cambia de tamaño al abrir o cerrar el panel; sin mover lo que ya se ve
function layoutChanged() {
  map.invalidateSize({ pan: false });
}

function parcelBounds(id) {
  const entry = layersById.get(id);
  return entry ? entry.polygon.getBounds() : null;
}

// Elige una parcela y muestra su resumen. Desde la lista, el mapa además se centra en ella
function openParcel(id, { center = false } = {}) {
  if (!layersById.has(id)) return;
  // El foco vuelve a donde estaba al abrir (una fila de la lista, el mapa); cambiar de parcela no lo mueve
  if (!parcelView.contains(document.activeElement)) returnFocus = document.activeElement;
  const wasOpen = panelOpen;
  if (selectedId === null) closeToList = wasOpen;
  setSelected(id);
  panelOpen = true;
  summaryContent.innerHTML = summaryHtml(layersById.get(id).feature.properties);
  renderPanel();
  if (!wasOpen) layoutChanged();
  const bounds = parcelBounds(id);
  if (center) {
    map.setView(bounds.getCenter(), Math.max(map.getZoom(), FOCUS_ZOOM), { animate: !reducedMotion.matches });
  } else {
    // Si el panel tapó la parcela (la hoja del celular), el mapa se mueve lo justo para verla
    map.panInside(bounds.getCenter(), { padding: [40, 40] });
  }
  document.getElementById("psum-id").focus({ preventScroll: true });
  parcelView.scrollTop = 0;
  loadConfidence(id);
}

// Lleva el foco a un elemento si sigue en la página y se ve; si no, a la alternativa (por omisión, el control
// que vuelve a abrir el panel). Si venía de una parcela del mapa, vuelve al mapa y no al polígono
function restoreFocus(target, fallback = mobileQuery.matches ? panelToggle : panelOpenButton) {
  if (target && target !== mapElement && mapElement.contains(target)) target = mapElement;
  const visible = target && target !== document.body && target.isConnected && target.getClientRects().length > 0;
  (visible ? target : fallback).focus({ preventScroll: true });
}

// Cerrar (botón ×, Esc o el título de la hoja): suelta la parcela y cierra el panel o pliega la hoja
function closePanel() {
  setSelected(null);
  panelOpen = false;
  renderPanel();
  layoutChanged();
  restoreFocus(returnFocus);
  returnFocus = null;
}

// Cerrar el resumen (botón × o Esc): si el panel ya mostraba la lista, vuelve a ella y el foco regresa
// a donde estaba al abrir (la fila o el mapa); si el panel estaba cerrado, se cierra de nuevo
function closeSummary() {
  if (!closeToList) {
    closePanel();
    return;
  }
  setSelected(null);
  renderPanel();
  restoreFocus(returnFocus, listTitle);
  returnFocus = null;
}

// «Volver a la lista»: suelta la parcela y deja el foco en su fila
function backToList() {
  const id = selectedId;
  setSelected(null);
  renderPanel();
  const row = [...listItems.querySelectorAll(".plist__row")].find((el) => el.dataset.id === id);
  (row || listTitle).focus({ preventScroll: true });
  if (row) row.scrollIntoView({ block: "nearest" });
}

// Abre el panel con la lista (botón de escritorio o título de la hoja en el celular)
function openList() {
  panelOpen = true;
  renderPanel();
  layoutChanged();
}

// Carga de datos y URLs

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

// Igual para el JSON de la ficha, de donde sale la confianza
function detailApiUrl(id) {
  return mapElement.dataset.detailApiUrl.replace("__ID__", encodeURIComponent(id));
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

// Sin economía, las capas de riesgo quedan deshabilitadas y la lista se ordena por rendimiento, y lo dice
function disableRiskLayers() {
  for (const option of layerSelect.options) {
    if (RISK_LAYERS.has(option.value)) option.disabled = true;
  }
  for (const option of sortSelect.options) {
    if (option.value !== "pred") option.disabled = true;
  }
  sortSelect.value = "pred";
  listNote.textContent = "No se pudo cargar la economía: la lista se ordena por rendimiento predicho, de menor a mayor.";
  listNote.hidden = false;
}

// Eventos

map.on("zoomend", showByZoom);
// El alto del mapa cambia sin que cambie la ventana (indicadores que se llenan, filtros o la hoja del celular que
// se abren): Leaflet y el mapa base se enteran aquí para no dejar franjas vacías
if (window.ResizeObserver) new ResizeObserver(layoutChanged).observe(mapElement);
layerSelect.addEventListener("change", () => {
  // Una capa municipal pide su GeoJSON la primera vez (o vuelve a pedirlo si antes falló)
  requestMunicipal();
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

// Lista: clic o Enter en una fila elige la parcela y centra el mapa en ella; flechas, Inicio y Fin pasan de fila en fila
listItems.addEventListener("click", (event) => {
  const row = event.target.closest(".plist__row");
  if (row) openParcel(row.dataset.id, { center: true });
});
listItems.addEventListener("keydown", (event) => {
  const rows = [...listItems.querySelectorAll(".plist__row")];
  const index = rows.indexOf(document.activeElement);
  if (index === -1) return;
  const next = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: rows.length - 1 }[event.key];
  if (next === undefined) return;
  event.preventDefault();
  rows[Math.max(0, Math.min(rows.length - 1, next))].focus();
});
sortSelect.addEventListener("change", renderList);

backButton.addEventListener("click", backToList);
// El × de la lista cierra el panel; el del resumen, solo el resumen
listView.querySelector("[data-close]").addEventListener("click", closePanel);
parcelView.querySelector("[data-close]").addEventListener("click", closeSummary);
panelOpenButton.addEventListener("click", () => {
  openList();
  listTitle.focus({ preventScroll: true });
});
// Título de la hoja (celular): la despliega con la lista o la pliega
panelToggle.addEventListener("click", () => {
  if (panelOpen) {
    closePanel();
  } else {
    returnFocus = panelToggle;
    openList();
  }
});

// Esc cierra el resumen (y vuelve a la lista) o el panel, salvo que lo atienda el menú «Descargar» o un selector abierto
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || downloadMenu.contains(event.target) || event.target.tagName === "SELECT") return;
  if (selectedId !== null) {
    closeSummary();
  } else if (panelOpen && (panel.contains(document.activeElement) || mobileQuery.matches)) {
    closePanel();
  }
});

// Al pasar de celular a escritorio (o al revés) el panel toma el estado por defecto de ese tamaño
mobileQuery.addEventListener("change", () => {
  if (selectedId === null) panelOpen = !mobileQuery.matches;
  renderPanel();
  layoutChanged();
});

addBaseMap();
renderPanel();

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
    // Si el hash trae una capa municipal, su modelo se pide ahora; mientras llega, el mapa se dibuja sin él
    requestMunicipal();
    draw(true);
  })
  .catch(() => {
    countLabel.textContent = "No se pudieron cargar las parcelas.";
    listItems.innerHTML = '<li class="plist__empty">No se pudieron cargar las parcelas.</li>';
  });
