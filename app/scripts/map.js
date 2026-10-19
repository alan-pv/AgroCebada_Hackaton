// Mapa de la página inicial, con dos modelos que no se mezclan:
// - Modelo de parcelas (datos de FIRA): las 197 parcelas coloreadas por conjunto, régimen, rendimiento, predicción o riesgo
//   de no pagar el crédito. La lista del panel son las parcelas por predecir.
// - Modelo municipal (SIAP y clima): los 486 municipios de los cuatro estados coloreados por rendimiento esperado,
//   o confianza del modelo, con contorno en los que tienen parcelas del reto. La lista del panel son los municipios.
// El clic en una parcela o un municipio lo elige y abre su resumen en el panel. En el celular el panel es una hoja
// plegable bajo el mapa

// Colores por conjunto (paleta categórica validada para daltonismo)
const SET_COLORS = {
  ENTRENAMIENTO: "#2a78d6",
  PREDICCION: "#eb6834",
};
const SET_LABELS = {
  ENTRENAMIENTO: "Entrenamiento",
  PREDICCION: "Predicción",
};
// Régimen de registro de las etiquetas: cómo reporta cada municipio sus rendimientos (lo infirió el equipo)
const REGIME_COLORS = {
  A: "#7b4fc4",
  B: "#1f9e89",
};
const REGIME_LABELS = {
  A: "A: con dos decimales",
  B: "B: redondeado a 0.5 o 0.1",
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
// Capa de riesgo económico: la probabilidad de no pagar el crédito y su semáforo
const RISK_LAYER = "risk_credit";
// Semáforo de la API (light_*): texto, rango de probabilidad, color y clase del badge; paleta Okabe-Ito, apta para daltonismo
const RISK_LEVELS = new Map([
  ["verde", { text: "bajo", range: "menos de 10 %", color: "#009E73", badge: "badge--bajo" }],
  ["amarillo", { text: "medio", range: "de 10 a 30 %", color: "#E69F00", badge: "badge--medio" }],
  ["rojo", { text: "alto", range: "30 % o más", color: "#D55E00", badge: "badge--alto" }],
]);
const RISK_KEYS = [...RISK_LEVELS.keys()];
// Nota de la leyenda de riesgo: cuántas de las mostradas salen en medio o alto, y dónde se explica por qué
function riskNote(counts) {
  const withLight = RISK_KEYS.reduce((sum, key) => sum + (counts.get(key) ?? 0), 0);
  if (!withLight) return "";
  const notLow = (counts.get("amarillo") ?? 0) + (counts.get("rojo") ?? 0);
  return `${notLow} de ${withLight} salen en medio o alto, por la pérdida histórica de su municipio o por un precio bajo. `
    + "Ver «¿Cómo se lee el semáforo?».";
}
// Nivel de confianza (de /api/parcels/<id> o del modelo municipal): texto y clase del badge, como en la ficha
const CONFIDENCE_LEVELS = new Map([
  ["alta", { text: "Confianza alta", badge: "badge--bajo" }],
  ["media", { text: "Confianza media", badge: "badge--medio" }],
  ["baja", { text: "Confianza baja", badge: "badge--alto" }],
]);
// Modelo municipal: mapas de calor. Cada escala es una sola gama, de claro (poco) a oscuro (mucho), con paradas
// [valor, color] que se interpolan. Rendimiento esperado en t/ha: azules, de casi blanco en 0 a azul muy oscuro
const MUN_YIELD_SCALE = [
  [0, "#eef4fc"], [0.5, "#cde2fb"], [1, "#9ec5f4"], [1.5, "#6da7ec"], [2, "#3987e5"],
  [2.5, "#256abf"], [3, "#184f95"], [3.3, "#0d366b"],
];
// Confianza: cercanía a datos del SIAP en km (0 = el municipio tiene datos propios), verdes de oscuro (cerca) a claro (lejos).
// Las extrapolaciones toman el extremo claro
const MUN_DISTANCE_SCALE = [[0, "#0b4f2e"], [12, "#1d6b40"], [25, "#2f8553"], [40, "#7cc192"], [60, "#e3f2e7"]];
const MUN_DISTANCE_MAX = 60;
// Confianza del modelo: una sola gama de verdes, más oscuro cuanto más confianza; badge es la clase del mismo verde en map.css
const MUN_CONFIDENCE_CLASSES = [
  { key: "alta", label: "Confianza alta", color: "#0b4f2e", badge: "badge--conf-alta" },
  { key: "media", label: "Confianza media", color: "#2f8553", badge: "badge--conf-media" },
  { key: "baja", label: "Confianza baja", color: "#b4dfbf", badge: "badge--conf-baja" },
];
// Por qué cada municipio tiene su nivel de confianza (criterio de scripts/municipal_capa.py)
const MUN_CONFIDENCE_REASONS = {
  alta: "Tiene historia propia de cebada de temporal en el SIAP.",
  media: "No tiene historia propia en el SIAP, pero tiene agricultura de temporal y un municipio con SIAP a 25 km o menos.",
  baja: "No tiene historia propia en el SIAP, y el municipio con datos más cercano está lejos o casi no hay agricultura de temporal.",
};
// Aviso de los municipios cuyo clima queda fuera del rango de los que tienen SIAP
const MUN_EXTRAPOLATION_NOTE = "Extrapolación: su clima queda fuera del rango de los municipios con SIAP. "
  + "La estimación sale solo de la temperatura, sin la cercanía a datos, y es menos confiable.";
// Cuando la extrapolación da 0 t/ha: el modelo no espera cosecha de temporal ahí
const MUN_NOT_SUITABLE = "Clima no apto para cebada de temporal según el modelo";
// Respaldo si algún municipio llegara sin estimación: gris claro con borde punteado
const MUN_NO_ESTIMATE = { color: "#e7e6e0", border: "#898781" };
// Municipios con parcelas del reto: contorno amarillo claro encima del municipio (no se dibujan las parcelas);
// con el puntero encima o elegido, el amarillo se oscurece
const RETO_OUTLINE = { color: "#ffe14d", weight: 3.5, dashArray: null };
const RETO_OUTLINE_ACTIVE = { color: "#c99400", weight: 4.5, dashArray: null };
const RETO_PANE = "reto";
// Capas del modelo municipal: título de su leyenda y clases
const MUN_LAYERS = new Map([
  ["mun-esperado", { title: "Rendimiento esperado (t/ha)", scale: MUN_YIELD_SCALE, ticks: [0, 1, 2, 3],
                     low: "Menos rendimiento", high: "Más rendimiento" }],
  ["mun-confianza", { title: "Confianza: cercanía a datos del SIAP", scale: MUN_DISTANCE_SCALE, ticks: [0, 20, 40, 60],
                      low: "Datos propios", high: "60 km o más, o extrapolación", reverse: true }],
]);
// Contornos y nombres de los estados, encima de los colores de los municipios
const STATES_PANE = "estados";
const STATE_LABELS_PANE = "estados-nombres";
const STATE_OUTLINE = { color: "#ffffff", weight: 2.5, opacity: 1, fill: false };

// Órdenes de la lista del panel, de cada modelo. by dice cómo van ordenadas en el título de la hoja del celular
const SORTS = {
  credit: { view: "parcels", label: "Riesgo de no pagar el crédito",
            text: "de mayor a menor riesgo de no pagar el crédito", by: "riesgo" },
  pred: { view: "parcels", label: "Rendimiento predicho", text: "de menor a mayor rendimiento predicho", by: "rendimiento" },
  "mun-yield": { view: "municipal", label: "Rendimiento esperado", text: "de mayor a menor rendimiento esperado",
                 by: "rendimiento" },
  "mun-name": { view: "municipal", label: "Nombre", text: "por nombre", by: "nombre" },
};
// Orden elegido en cada modelo; se recuerda al pasar de uno a otro
const sortByView = { parcels: "credit", municipal: "mun-yield" };

// Textos que cambian con el modelo: título de la lista, botón que la abre, columnas e indicadores
const VIEW_TEXT = {
  parcels: {
    listTitle: "Parcelas por predecir",
    open: "Lista de parcelas",
    columns: ["Parcela", "Predicción", "No pagar el crédito"],
    stats: {
      shown: "Parcelas mostradas",
      "to-predict": "Parcelas por predecir",
      "pred-mean": "Rendimiento predicho medio",
      risk: "Parcelas con riesgo alto de no pagar el crédito",
    },
  },
  municipal: {
    listTitle: "Municipios",
    open: "Lista de municipios",
    columns: ["Municipio", "Esperado", "Confianza"],
    stats: {
      shown: "Municipios mostrados",
      "to-predict": "Con historia en el SIAP",
      "pred-mean": "Rendimiento esperado medio",
      risk: "Municipios con confianza alta",
    },
  },
};

// Borde de las parcelas: gris oscuro semitransparente, para que lean sobre el mapa base gris claro
const BORDER = "#3d3c38";
const BORDER_OPACITY = 0.7;
const BORDER_HOVER = "#0b0b0b";
// Parcela o municipio elegido: borde negro más grueso, que se queda al quitar el puntero
const SELECTED_WEIGHT = 4;

// Por debajo de este zoom las parcelas miden pocos píxeles y se dibujan como círculos en su centro
const POINT_ZOOM = 13;
const POINT_RADIUS = 6;
// Zoom mínimo al centrar el mapa en una parcela elegida en la lista: ya se ve su polígono
const FOCUS_ZOOM = 15;
// Zoom máximo al centrar el mapa en un municipio elegido en la lista
const MUN_FOCUS_MAX_ZOOM = 11;

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
const municipalLink = document.getElementById("download-municipal");
const filtersToggle = document.getElementById("filters-toggle");
const filtersActive = document.getElementById("filters-active");
const downloadMenu = document.querySelector(".download-menu");
// Indicadores sobre el mapa: rótulo, cifra y nota de cada uno
const stats = Object.fromEntries(["shown", "to-predict", "pred-mean", "risk"].map((key) => [key, {
  label: document.getElementById(`stat-${key}-label`),
  value: document.getElementById(`stat-${key}`),
  note: document.getElementById(`stat-${key}-note`),
}]));
// Panel: lista de parcelas por predecir (o de municipios) y resumen de la elegida
const panel = document.getElementById("map-panel");
const panelToggle = document.getElementById("panel-toggle");
const panelToggleText = document.getElementById("panel-toggle-text");
const panelOpenButton = document.getElementById("panel-open");
const listView = document.getElementById("panel-list");
const listTitle = document.getElementById("plist-title");
const listSummary = document.getElementById("plist-summary");
const listNote = document.getElementById("plist-note");
const listColumns = ["name", "value", "risk"].map((key) => document.getElementById(`plist-col-${key}`));
const listItems = document.getElementById("plist-items");
const sortSelect = document.getElementById("plist-sort");
const helpParcels = document.getElementById("help-parcels");
const helpMunicipal = document.getElementById("help-municipal");
const parcelView = document.getElementById("panel-parcel");
const summaryContent = document.getElementById("psum-content");
const backButton = document.getElementById("psum-back");

// En el celular (hasta 600 px) el panel es una hoja inferior; en escritorio, una columna a la derecha
const mobileQuery = window.matchMedia("(max-width: 600px)");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Vista inicial sobre la zona de estudio; se ajusta al cargar las parcelas
const map = L.map(mapElement).setView([19.8, -98.4], 10);

let parcels = [];
// Parcelas o municipios que pasan los filtros, en el último dibujo, y de qué modelo son
let shown = [];
let shownView = null;
let polygonsLayer = null;
let pointsLayer = null;
// Polígono (y círculo, en las parcelas) de cada elemento mostrado, por ID: sirven para resaltar el elegido y centrar el
// mapa en él. Los municipios usan su CVEGEO como ID y no tienen círculo (marker es null)
const layersById = new Map();
// Verdadero si la carga de economía falló; entonces la capa de riesgo está deshabilitada
let economicsFailed = false;
// Modelo municipal: municipios (GeoJSON), pedido solo la primera vez que se elige una de sus capas; capa de Leaflet
let municipalFeatures = null;
let municipalRequest = null;
let municipalFailed = false;
let municipalLayer = null;
let retoLayer = null;
// Estados (GeoJSON con su punto para el nombre) y su capa
let statesFeatures = null;
let statesLayer = null;
// Estado y municipio que se quieren mostrar cuando llegue el modelo municipal (del hash o del modelo de parcelas)
let pendingFilters = null;

// Estado del panel: elemento elegido (o null), si está abierto (en el celular, si la hoja está desplegada)
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

// Modelo activo

// Verdadero si la capa elegida es una del modelo municipal
function isMunicipalMode() {
  return MUN_LAYERS.has(layerSelect.value);
}

function currentView() {
  return isMunicipalMode() ? "municipal" : "parcels";
}

// Elementos del modelo activo: parcelas o municipios (vacío mientras el modelo municipal no llega)
function viewFeatures() {
  return isMunicipalMode() ? (municipalFeatures ?? []) : parcels;
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
  if (mode === "regime") return REGIME_COLORS[p.regime] ?? null;
  if (mode === RISK_LAYER) {
    const level = RISK_LEVELS.get(p.light_credit);
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
  if (fillColor === null) {
    // Sin valor en este modo: gris con borde punteado, para no depender solo del color
    style = { ...base, fillColor: NO_DATA.color, color: NO_DATA.border, opacity: 1, fillOpacity: 0.6, dashArray: "3 3" };
  }
  if (p.id === selectedId) {
    style = { ...style, weight: SELECTED_WEIGHT, color: BORDER_HOVER, opacity: 1, dashArray: null };
  }
  return style;
}

function pointStyle(feature) {
  const noData = fillColorOf(feature.properties) === null;
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

// Probabilidad de un modelo: sin 0 % ni 100 %, que sugerirían certeza
function formatProbability(probability) {
  if (probability < 0.01) return "<1 %";
  if (probability > 0.99) return ">99 %";
  return formatPercent(probability);
}

function capitalize(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Fila etiqueta–valor de la mini tarjeta del tooltip
function tipRow(label, value) {
  return `<div class="tip__row"><dt>${label}</dt><dd>${value}</dd></div>`;
}

// Nivel del semáforo para una probabilidad de 0 a 1: menos de 10 % bajo, de 10 a menos de 30 % medio, lo demás alto
function probabilityLevel(probability) {
  if (probability < 0.1) return RISK_KEYS[0];
  return probability < 0.3 ? RISK_KEYS[1] : RISK_KEYS[2];
}

// Probabilidad y, si hay semáforo, su nivel con texto (bajo, medio o alto)
function riskValueHtml(probability, light) {
  const level = RISK_LEVELS.get(light);
  const badge = level ? ` <span class="badge ${level.badge}">Riesgo ${level.text}</span>` : "";
  return `${formatProbability(probability)}${badge}`;
}

// Badge de confianza del modelo municipal, con la misma escala de verdes de la leyenda
function municipalConfidenceBadge(key) {
  const level = MUN_CONFIDENCE_CLASSES.find((c) => c.key === key);
  return level ? `<span class="badge ${level.badge}">${level.label}</span>` : "Sin dato";
}

function confidenceBadge(key) {
  const level = CONFIDENCE_LEVELS.get(key);
  return level ? `<span class="badge ${level.badge}">${level.text}</span>` : "Sin dato";
}

// Mini tarjeta del tooltip de una parcela: ID y conjunto, la cifra principal grande y filas etiqueta–valor
function tooltipHtml(p) {
  const training = p.set === "ENTRENAMIENTO";
  const dot = training ? "dot--entrenamiento" : "dot--prediccion";
  const rows = [tipRow("Municipio", `${p.municipality}, ${p.state}`)];
  if (p.regime) rows.push(tipRow("Régimen", REGIME_LABELS[p.regime] ?? p.regime));
  if (!training) {
    rows.push(tipRow("Intervalo p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
  }
  rows.push(tipRow("Área", `${formatNumber(p.area_ha, 2)} ha`));
  // Riesgo económico, solo si se cargó la economía
  if (typeof p.prob_not_pay_credit === "number") {
    rows.push(tipRow("No pagar el crédito", riskValueHtml(p.prob_not_pay_credit, p.light_credit)));
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
  const inState = viewFeatures().filter((f) => !stateSelect.value || f.properties.state === stateSelect.value);
  fillSelect(municipalitySelect, inState.map((f) => f.properties.municipality));
}

// Llena los filtros con los estados y municipios del modelo activo y deja los valores pedidos si existen en él
function refreshFilters(state = stateSelect.value, municipality = municipalitySelect.value) {
  fillSelect(stateSelect, viewFeatures().map((f) => f.properties.state));
  stateSelect.value = enabledValue(stateSelect, state) ?? "";
  updateMunicipalities();
  municipalitySelect.value = enabledValue(municipalitySelect, municipality) ?? "";
}

function hasEstimate(p) {
  return typeof p.esperado === "number";
}

function updateCount(selected) {
  const total = selected.length;
  let text;
  if (isMunicipalMode()) {
    const withEstimate = selected.filter((f) => hasEstimate(f.properties)).length;
    text = `${total} ${total === 1 ? "municipio" : "municipios"}`;
    if (withEstimate < total) text += `: ${withEstimate} con estimación y ${total - withEstimate} sin estimación`;
    if (municipalFailed) text = "No se pudo cargar el modelo municipal.";
    else if (!municipalFeatures) text = "Cargando el modelo municipal…";
  } else {
    const training = selected.filter((f) => f.properties.set === "ENTRENAMIENTO").length;
    text = `${total} ${total === 1 ? "parcela" : "parcelas"}: ${training} de entrenamiento y ${total - training} por predecir`;
    // Sin economía, el aviso va en el contador (aria-live polite)
    if (economicsFailed) text += ". No se pudo cargar la economía; la capa de riesgo no está disponible.";
  }
  countLabel.textContent = text;
}

// Muestra la cifra (con su unidad, si la tiene) y la nota de un indicador
function setStat(key, value, unit, note) {
  stats[key].value.innerHTML = unit ? `${value} <span class="stat__unit">${unit}</span>` : value;
  stats[key].note.textContent = note;
}

function mean(values) {
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

// Indicadores de las parcelas mostradas: se recalculan con cada cambio de estado o municipio
function updateParcelStats(selected) {
  const toPredict = selected.filter((f) => f.properties.set === "PREDICCION");
  setStat("shown", selected.length, "", `${selected.length - toPredict.length} de entrenamiento`);
  setStat("to-predict", toPredict.length, "", "Sin rendimiento observado");

  // Promedio simple de la predicción de las parcelas por predecir
  const preds = toPredict.map((f) => f.properties.pred).filter((v) => typeof v === "number");
  if (preds.length) {
    setStat("pred-mean", formatNumber(mean(preds), 2), "t/ha",
      preds.length === 1 ? "De la única parcela por predecir" : `Promedio simple de ${preds.length} parcelas por predecir`);
  } else {
    setStat("pred-mean", "—", "", "No hay parcelas por predecir en la selección");
  }

  // Parte de las parcelas mostradas con semáforo rojo en el crédito (probabilidad de 30 % o más)
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

// Indicadores de los municipios mostrados
function updateMunicipalStats(selected) {
  if (!municipalFeatures) {
    const note = municipalFailed ? "No se pudo cargar el modelo municipal" : "Cargando el modelo municipal…";
    for (const key of Object.keys(stats)) setStat(key, "—", "", note);
    return;
  }
  const props = selected.map((f) => f.properties);
  const estimated = props.filter(hasEstimate);
  const inRange = estimated.filter((p) => !isExtrapolation(p));
  setStat("shown", props.length, "", `${estimated.length - inRange.length} son extrapolaciones del clima`);
  setStat("to-predict", props.filter((p) => p.con_siap).length, "", "Los demás se estiman con la temperatura y los vecinos");
  if (!estimated.length) {
    setStat("pred-mean", "—", "", "Ningún municipio con estimación en la selección");
    setStat("risk", "—", "", "Ningún municipio con estimación en la selección");
    return;
  }
  // Las extrapolaciones (muchas en 0 t/ha) no entran al promedio: lo jalarían hacia abajo
  if (inRange.length) {
    setStat("pred-mean", formatNumber(mean(inRange.map((p) => p.esperado)), 2), "t/ha",
      inRange.length === 1 ? "Del único municipio sin extrapolación" : `Promedio simple de ${inRange.length} municipios, sin extrapolaciones`);
  } else {
    setStat("pred-mean", "—", "", "Solo hay extrapolaciones en la selección");
  }
  const high = estimated.filter((p) => p.confianza === "alta").length;
  setStat("risk", formatNumber((high / estimated.length) * 100, 0), "%", `${high} de ${estimated.length} municipios`);
}

// Leyenda

// Fila de la leyenda: muestra de color, rótulo y número de elementos mostrados en esa clase
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

// Cuenta cuántos elementos caen en cada clave; null agrupa los que no tienen valor
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

// Leyenda de la capa activa, con el número de elementos mostrados en cada clase
function updateLegend(selected) {
  const div = legend.getContainer();
  const mode = layerSelect.value;
  if (MUN_LAYERS.has(mode)) {
    div.innerHTML = municipalLegendHtml(mode, selected);
  } else if (mode === "set") {
    const counts = countBy(selected, (p) => p.set);
    div.innerHTML = legendHtml("Conjunto",
      Object.keys(SET_COLORS).map((k) => legendRow(SET_COLORS[k], SET_LABELS[k], counts.get(k) ?? 0)));
  } else if (mode === "regime") {
    const counts = countBy(selected, (p) => p.regime);
    div.innerHTML = legendHtml("Régimen de registro",
      Object.keys(REGIME_COLORS).map((k) => legendRow(REGIME_COLORS[k], REGIME_LABELS[k], counts.get(k) ?? 0)),
      "Cómo reporta cada municipio los rendimientos de sus parcelas. El A da cifras más altas que el B. "
      + "Lo infirió el equipo de los datos; FIRA no lo ha confirmado.");
  } else if (mode === RISK_LAYER) {
    // Los tres niveles del semáforo con su rango de probabilidad, y la entrada de sin dato
    const counts = countBy(selected, (p) => (RISK_LEVELS.has(p.light_credit) ? p.light_credit : null));
    div.innerHTML = legendHtml("Riesgo de no pagar el crédito", [
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

// Capas del mapa

// Tooltip, resaltado al pasar el puntero y clic que abre el resumen; sirve para parcelas y municipios
function bindInteractions(feature, layer, reset, tooltip) {
  layer.bindTooltip(tooltip(feature.properties), { sticky: true, className: "parcel-tip", opacity: 1 });
  layer.on({
    mouseover: () => {
      const weight = feature.properties.id === selectedId ? SELECTED_WEIGHT : 3;
      layer.setStyle({ weight, color: BORDER_HOVER, opacity: 1 });
      layer.bringToFront();
      const outline = retoOutlineOf(feature);
      if (outline) {
        outline.setStyle(retoOutlineStyle(feature, true));
        outline.bringToFront();
      }
    },
    mouseout: () => {
      reset();
      retoOutlineOf(feature)?.setStyle(retoOutlineStyle(feature));
    },
    // Clic: elige el elemento y abre su resumen en el panel. El tooltip se cierra para no tapar el mapa
    click: () => {
      layer.closeTooltip();
      openItem(feature.properties.id);
    },
  });
}

// Contorno del reto de un municipio, si lo tiene
function retoOutlineOf(feature) {
  return layersById.get(feature.properties.id)?.outline ?? null;
}

// El elemento elegido va encima de sus vecinos
function raiseSelected() {
  const entry = layersById.get(selectedId);
  if (!entry) return;
  if (map.hasLayer(entry.polygon)) entry.polygon.bringToFront();
  if (entry.marker && map.hasLayer(entry.marker)) entry.marker.bringToFront();
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

function drawParcels(selected) {
  polygonsLayer = L.geoJSON(selected, {
    style: featureStyle,
    onEachFeature: (feature, layer) => {
      bindInteractions(feature, layer, () => polygonsLayer.resetStyle(layer), tooltipHtml);
      layersById.set(feature.properties.id, { feature, polygon: layer, marker: null });
    },
  });
  pointsLayer = L.featureGroup(selected.map((feature) => {
    const center = L.geoJSON(feature).getBounds().getCenter();
    const marker = L.circleMarker(center, pointStyle(feature));
    bindInteractions(feature, marker, () => marker.setStyle(pointStyle(feature)), tooltipHtml);
    layersById.get(feature.properties.id).marker = marker;
    return marker;
  }));
}

function drawMunicipal(selected) {
  markRetoMunicipalities();
  municipalLayer = L.geoJSON(selected, {
    style: municipalStyle,
    onEachFeature: (feature, layer) => {
      bindInteractions(feature, layer, () => municipalLayer.resetStyle(layer), municipalTooltipHtml);
      layersById.set(feature.properties.id, { feature, polygon: layer, marker: null, municipal: true });
    },
  }).addTo(map);
  // Contorno de los municipios con parcelas del reto, en un panel propio encima de los polígonos y sin recibir el puntero
  if (!map.getPane(RETO_PANE)) {
    map.createPane(RETO_PANE).style.zIndex = 450;
    map.getPane(RETO_PANE).style.pointerEvents = "none";
  }
  drawStates();
  retoLayer = L.layerGroup().addTo(map);
  for (const feature of selected.filter((f) => f.properties.reto)) {
    const outline = L.geoJSON(feature, { pane: RETO_PANE, interactive: false, fill: false, style: () => retoOutlineStyle(feature) });
    outline.addTo(retoLayer);
    layersById.get(feature.properties.id).outline = outline;
  }
}

// Contorno blanco y nombre de cada estado, en paneles propios encima de los municipios y sin recibir el puntero
function drawStates() {
  if (!statesFeatures) return;
  for (const [name, z] of [[STATES_PANE, 440], [STATE_LABELS_PANE, 460]]) {
    if (map.getPane(name)) continue;
    map.createPane(name).style.zIndex = z;
    map.getPane(name).style.pointerEvents = "none";
  }
  statesLayer = L.layerGroup().addTo(map);
  L.geoJSON(statesFeatures, { pane: STATES_PANE, interactive: false, style: () => STATE_OUTLINE }).addTo(statesLayer);
  for (const f of statesFeatures) {
    const { estado, label_lat: lat, label_lon: lon } = f.properties;
    L.marker([lat, lon], {
      pane: STATE_LABELS_PANE, interactive: false, keyboard: false,
      icon: L.divIcon({ className: "state-label", html: `<span>${estado}</span>`, iconSize: null }),
    }).addTo(statesLayer);
  }
}

// Texto normalizado para comparar nombres de estado y municipio (sin acentos ni mayúsculas)
function nameKey(text) {
  return String(text ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
}

// Marca (p.reto) los municipios donde hay parcelas del reto: los pares estado y municipio de las parcelas cargadas
function markRetoMunicipalities() {
  const keys = new Set(parcels.map((f) => `${nameKey(f.properties.state)}|${nameKey(f.properties.municipality)}`));
  for (const f of municipalFeatures ?? []) {
    f.properties.reto = keys.has(`${nameKey(f.properties.estado)}|${nameKey(f.properties.municipio)}`);
  }
}

// Contorno del reto: amarillo claro; más oscuro si el municipio está elegido o tiene el puntero encima
function retoOutlineStyle(feature, hover = false) {
  const base = hover || feature.properties.id === selectedId ? RETO_OUTLINE_ACTIVE : RETO_OUTLINE;
  return { ...base, opacity: 1, fill: false };
}

// Rótulos que dependen del modelo: indicadores, título y columnas de la lista, ayuda y botón que abre la lista
function updateViewTexts() {
  const view = currentView();
  const text = VIEW_TEXT[view];
  for (const [key, stat] of Object.entries(stats)) stat.label.textContent = text.stats[key];
  listTitle.textContent = text.listTitle;
  listColumns.forEach((el, i) => {
    el.textContent = text.columns[i];
  });
  panelOpenButton.textContent = text.open;
  helpParcels.hidden = view === "municipal";
  helpMunicipal.hidden = view !== "municipal";
}

// Opciones de «Ordenar por» del modelo activo, con el orden que se eligió la última vez en él
function updateSortOptions() {
  const view = currentView();
  sortSelect.length = 0;
  for (const [key, sort] of Object.entries(SORTS)) {
    if (sort.view !== view) continue;
    const option = new Option(sort.label, key);
    // Sin economía, en las parcelas solo se puede ordenar por rendimiento
    option.disabled = view === "parcels" && economicsFailed && key !== "pred";
    sortSelect.add(option);
  }
  sortSelect.value = sortByView[view];
}

function draw(fit) {
  for (const layer of [polygonsLayer, pointsLayer, municipalLayer, retoLayer, statesLayer]) {
    if (layer) layer.remove();
  }
  retoLayer = null;
  statesLayer = null;
  polygonsLayer = null;
  pointsLayer = null;
  municipalLayer = null;
  layersById.clear();
  // Al cambiar de modelo cambian los rótulos y las opciones de orden
  if (shownView !== currentView()) {
    shownView = currentView();
    updateViewTexts();
    updateSortOptions();
  }
  const selected = viewFeatures().filter((f) => matchesFilters(f.properties));
  shown = selected;
  if (isMunicipalMode()) {
    drawMunicipal(selected);
    updateMunicipalStats(selected);
  } else {
    drawParcels(selected);
    updateParcelStats(selected);
  }

  updateCount(selected);
  updateLegend(selected);
  updateActiveFilters();
  // Si los filtros (o el cambio de modelo) dejan fuera al elemento elegido, el panel vuelve a la lista
  if (selectedId !== null && !layersById.has(selectedId)) {
    const focusWasInSummary = parcelView.contains(document.activeElement);
    selectedId = null;
    renderPanel();
    if (focusWasInSummary) listTitle.focus();
  }
  renderList();
  const fitLayer = municipalLayer ?? polygonsLayer;
  if (fit && selected.length) map.fitBounds(fitLayer.getBounds(), { padding: [20, 20] });
  showByZoom();
}

// Cambia el elemento elegido y vuelve a pintar el anterior y el nuevo
function setSelected(id) {
  const previous = selectedId;
  selectedId = id;
  for (const pid of [previous, id]) {
    const entry = layersById.get(pid);
    if (!entry) continue;
    if (entry.municipal) {
      entry.polygon.setStyle(municipalStyle(entry.feature));
      if (entry.outline) {
        entry.outline.setStyle(() => retoOutlineStyle(entry.feature));
        if (pid === id) entry.outline.bringToFront();
      }
    } else {
      entry.polygon.setStyle(featureStyle(entry.feature));
      entry.marker.setStyle(pointStyle(entry.feature));
    }
  }
  raiseSelected();
}

// Modelo municipal

// Verdadero si la estimación es una extrapolación: el clima del municipio queda fuera del rango de los que tienen SIAP
function isExtrapolation(p) {
  return p.dentro_rango_ambiental === false;
}

// Color de una escala continua en el valor dado: interpola entre las dos paradas que lo rodean
function scaleColor(scale, value) {
  const v = Math.min(Math.max(value, scale[0][0]), scale[scale.length - 1][0]);
  const i = Math.max(1, scale.findIndex(([stop]) => stop >= v));
  const [v0, c0] = scale[i - 1];
  const [v1, c1] = scale[i];
  const t = v1 === v0 ? 0 : (v - v0) / (v1 - v0);
  const rgb = (hex) => [1, 3, 5].map((k) => parseInt(hex.slice(k, k + 2), 16));
  const [a, b] = [rgb(c0), rgb(c1)];
  return `#${a.map((x, k) => Math.round(x + (b[k] - x) * t).toString(16).padStart(2, "0")).join("")}`;
}

// Cercanía a datos del SIAP en km, como la mide la confianza: 0 si el municipio tiene datos propios; en confianza baja,
// al menos 25 km (aunque esté cerca, le falta agricultura de temporal); las extrapolaciones, al máximo de la escala
function dataDistance(p) {
  if (p.con_siap) return 0;
  if (isExtrapolation(p)) return MUN_DISTANCE_MAX;
  const km = typeof p.dist_siap_km === "number" ? p.dist_siap_km : MUN_DISTANCE_MAX;
  return p.confianza === "baja" ? Math.max(km, 25) : km;
}

// Color de un municipio en la capa activa; null si no tiene estimación
function municipalColor(mode, p) {
  if (!hasEstimate(p)) return null;
  if (mode === "mun-esperado") return scaleColor(MUN_YIELD_SCALE, p.esperado);
  return scaleColor(MUN_DISTANCE_SCALE, dataDistance(p));
}

// Pide el modelo municipal la primera vez que se elige una de sus capas; si falló, se vuelve a pedir al volver a elegirla
function requestMunicipal() {
  if (!isMunicipalMode() || municipalFeatures || municipalRequest) return;
  municipalFailed = false;
  // Los estados son un adorno: si fallan, el mapa municipal sigue sin ellos
  const statesRequest = fetchJson(mapElement.dataset.statesUrl).then((g) => g.features).catch(() => null);
  municipalRequest = Promise.all([fetchJson(mapElement.dataset.municipalUrl), statesRequest])
    .then(([geojson, states]) => {
      statesFeatures = states;
      // Mismos nombres de ID, estado y municipio que las parcelas: así sirven los filtros, la lista y el panel
      for (const f of geojson.features) {
        const p = f.properties;
        Object.assign(p, { id: p.CVEGEO, state: p.estado, municipality: p.municipio });
      }
      municipalFeatures = geojson.features;
    })
    .catch(() => {
      // Sin el modelo, el aviso va en el contador, los indicadores, la leyenda y la lista
      municipalFailed = true;
    })
    .then(() => {
      municipalRequest = null;
      // Al llegar (o fallar), se llenan los filtros y se redibuja con la capa elegida
      if (!isMunicipalMode()) return;
      refreshFilters(pendingFilters?.state, pendingFilters?.municipality);
      pendingFilters = null;
      draw(true);
    });
}

// Mini tarjeta del tooltip de un municipio: nombre y estado, la cifra esperada o, sin estimación, el aviso
function municipalTooltipHtml(p) {
  const rows = [];
  let value = '<p class="tip__caption">Fuera del rango de clima del modelo: sin estimación</p>';
  if (hasEstimate(p)) {
    value = `<p class="tip__value">${formatNumber(p.esperado, 2)} <span class="tip__unit">t/ha</span></p>`
      + `<p class="tip__caption">${p.esperado === 0 ? MUN_NOT_SUITABLE : "Rendimiento esperado (escala del SIAP)"}</p>`;
    if (p.p90 > 0) rows.push(tipRow("Intervalo p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
    rows.push(tipRow("Confianza", municipalConfidenceBadge(p.confianza)));
  }
  if (p.con_siap) rows.push(tipRow("Media del SIAP", `${formatNumber(p.siap_media, 2)} t/ha en ${p.siap_anios} años`));
  if (p.reto) rows.push(tipRow("Parcelas del reto", "Tiene parcelas del reto"));
  return '<div class="tip">'
    + `<div class="tip__head"><strong class="tip__id">${p.municipio}</strong><span class="tip__set">${p.estado}</span></div>`
    + value
    + `<dl class="tip__rows">${rows.join("")}</dl>`
    + (isExtrapolation(p) ? `<p class="tip__caption">${MUN_EXTRAPOLATION_NOTE}</p>` : "")
    + '<p class="tip__hint">Clic para ver el resumen</p>'
    + "</div>";
}

// Color y borde de cada municipio: en gris punteado si no tiene estimación; el elegido, con borde negro grueso
function municipalStyle(feature) {
  const p = feature.properties;
  const fill = municipalColor(layerSelect.value, p);
  let style = { weight: 0.5, color: "#ffffff", opacity: 0.8, fillColor: fill ?? MUN_NO_ESTIMATE.color, fillOpacity: 0.9, dashArray: null };
  if (!fill) style = { ...style, weight: 1, color: MUN_NO_ESTIMATE.border, fillOpacity: 0.6, dashArray: "4 3" };
  if (p.id === selectedId) style = { ...style, weight: SELECTED_WEIGHT - 1, color: BORDER_HOVER, opacity: 1, dashArray: null };
  return style;
}

// Leyenda de la capa municipal: sus clases con el número de municipios mostrados, y la nota del modelo
function municipalLegendHtml(mode, selected) {
  const layer = MUN_LAYERS.get(mode);
  const { title } = layer;
  if (municipalFailed) return legendHtml(title, [], "No se pudo cargar el modelo municipal.", "Municipios");
  if (!municipalFeatures) return legendHtml(title, [], "Cargando el modelo municipal…", "Municipios");
  const counts = countBy(selected, (p) => (hasEstimate(p) ? "con" : null));
  const rows = [gradientHtml(layer)];
  // Solo si algún municipio llega sin estimación
  if (counts.get(null)) rows.push(legendRow(MUN_NO_ESTIMATE.color, "Sin estimación", counts.get(null), "legend-swatch--no-data"));
  rows.push(legendRow("transparent", "Con parcelas del reto", selected.filter((f) => f.properties.reto).length, "legend-swatch--reto"));
  const year = municipalFeatures[0]?.properties.anio_referencia;
  const note = `Escala del SIAP${year ? `, año de referencia ${year}` : ""}. No se compara con la predicción de las parcelas.`
    + (selected.some((f) => isExtrapolation(f.properties)) ? " Los municipios con clima fuera del rango del SIAP son extrapolaciones." : "");
  return legendHtml(title, rows, note, "Municipios");
}

// Barra de degradado de una escala continua, con sus marcas y qué significa cada extremo
function gradientHtml({ scale, ticks, low, high, reverse }) {
  const min = scale[0][0];
  const max = scale[scale.length - 1][0];
  const at = (v) => ((v - min) / (max - min)) * 100;
  const stops = scale.map(([v, c]) => `${c} ${at(v)}%`).join(", ");
  const tickText = (t, i) => (reverse ? `${t}${i === ticks.length - 1 ? "+" : ""} km` : formatNumber(t, 0));
  const marks = ticks.map((t, i) => `<span style="left:${at(t)}%">${tickText(t, i)}</span>`).join("");
  return `<div class="legend-gradient"><div class="legend-gradient__bar" style="background:linear-gradient(to right, ${stops})"></div>`
    + `<div class="legend-gradient__ticks">${marks}</div>`
    + `<div class="legend-gradient__ends"><span>${low}</span><span>${high}</span></div></div>`;
}

// Gráficas del resumen de un municipio (SVG en línea, con el texto en la tinta de la página)

// Escala lineal de un dominio a un rango de píxeles
function linear([d0, d1], [r0, r1]) {
  return (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
}

// Cascada: de dónde sale el rendimiento esperado. Promedio regional, efecto de la temperatura, corrección por los
// vecinos con SIAP y el total. Lo que suma va en azul y lo que resta en rojo; el texto dice el signo, no solo el color
function municipalBreakdownSvg(p) {
  const steps = [
    { label: "Promedio regional", value: p.parte_media, from: 0, kind: "base" },
    { label: `Temperatura (${formatNumber(p.tmax_jul_ago, 1)} °C)`, value: p.parte_tmax, from: p.parte_media },
    { label: isExtrapolation(p) ? "Vecinos con SIAP (no se usa)" : "Vecinos con SIAP", value: p.parte_vecinos,
      from: p.parte_media + p.parte_tmax },
  ];
  const total = p.esperado_sin_corte;
  const ends = [0, total, ...steps.map((st) => st.from), ...steps.map((st) => st.from + st.value)];
  const lo = Math.min(...ends);
  const hi = Math.max(...ends, 0.5);
  const W = 320;
  const labelW = 132;
  const row = 30;
  const x = linear([lo, hi], [labelW + 4, W - 46]);
  const bar = (y, a, b, color, title) => {
    const [x0, x1] = [x(Math.min(a, b)), x(Math.max(a, b))];
    return `<rect x="${x0}" y="${y + 7}" width="${Math.max(x1 - x0, 2)}" height="14" rx="3" fill="${color}"><title>${title}</title></rect>`;
  };
  const text = (y, label, value, signed) => {
    const shown = signed ? `${value >= 0 ? "+" : "−"}${formatNumber(Math.abs(value), 2)}` : formatNumber(value, 2);
    return `<text x="0" y="${y + 18}" class="mchart__label">${label}</text>`
      + `<text x="${W}" y="${y + 18}" class="mchart__value" text-anchor="end">${shown}</text>`;
  };
  let body = "";
  steps.forEach((st, i) => {
    const y = i * row;
    const color = st.kind === "base" ? "#9ec5f4" : (st.value >= 0 ? "#2a78d6" : "#d03b3b");
    body += bar(y, st.from, st.from + st.value, color, `${st.label}: ${formatNumber(st.value, 2)} t/ha`)
      + text(y, st.label, st.value, st.kind !== "base");
  });
  const yt = steps.length * row + 6;
  body += `<line x1="${labelW}" x2="${W}" y1="${yt - 3}" y2="${yt - 3}" class="mchart__rule"/>`;
  body += bar(yt, 0, Math.max(total, 0), "#0d366b", `Esperado: ${formatNumber(p.esperado, 2)} t/ha`)
    + text(yt, "Esperado", p.esperado, false);
  body += `<line x1="${x(0)}" x2="${x(0)}" y1="0" y2="${yt + row}" class="mchart__zero"/>`;
  const h = yt + row;
  const note = total < 0
    ? `<p class="mchart__note">La suma da −${formatNumber(Math.abs(total), 2)} t/ha. Un rendimiento no puede ser negativo, así que se muestra 0.</p>` : "";
  return `<figure class="mchart"><figcaption class="mchart__title">¿De dónde sale el número? (t/ha)</figcaption>`
    + `<svg viewBox="0 0 ${W} ${h}" width="100%" role="img" aria-label="Promedio regional ${formatNumber(p.parte_media, 2)}, `
    + `temperatura ${formatNumber(p.parte_tmax, 2)}, vecinos con SIAP ${formatNumber(p.parte_vecinos, 2)}, esperado ${formatNumber(p.esperado, 2)} t/ha">`
    + `${body}</svg>${note}</figure>`;
}

// Dispersión: temperatura máxima de julio y agosto contra rendimiento esperado de todos los municipios, con la recta
// del modelo, la franja de temperaturas que tienen los municipios con SIAP y el municipio elegido resaltado
function municipalTmaxSvg(p) {
  const all = (municipalFeatures ?? []).map((f) => f.properties).filter((q) => typeof q.tmax_jul_ago === "number");
  const siap = all.filter((q) => q.con_siap).map((q) => q.tmax_jul_ago);
  const t0 = Math.floor(Math.min(...all.map((q) => q.tmax_jul_ago)));
  const t1 = Math.ceil(Math.max(...all.map((q) => q.tmax_jul_ago)));
  const W = 320;
  const H = 170;
  const m = { l: 30, r: 8, t: 8, b: 30 };
  const x = linear([t0, t1], [m.l, W - m.r]);
  const y = linear([0, 3.5], [H - m.b, m.t]);
  const fit = (t) => Math.max(p.parte_media + p.pendiente_tmax * (t - p.tmax_media), 0);
  let body = "";
  if (siap.length) {
    const [s0, s1] = [Math.min(...siap), Math.max(...siap)];
    body += `<rect x="${x(s0)}" y="${m.t}" width="${x(s1) - x(s0)}" height="${H - m.t - m.b}" class="mchart__band"><title>Temperaturas de los municipios con SIAP: ${formatNumber(s0, 1)} a ${formatNumber(s1, 1)} °C</title></rect>`
      + `<text x="${x(s1) + 4}" y="${m.t + 10}" class="mchart__tick">Con SIAP</text>`;
  }
  for (const v of [0, 1, 2, 3]) {
    body += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}" class="mchart__grid"/>`
      + `<text x="${m.l - 6}" y="${y(v) + 4}" class="mchart__tick" text-anchor="end">${v}</text>`;
  }
  for (let t = t0; t <= t1; t += 2) {
    body += `<text x="${x(t)}" y="${H - m.b + 14}" class="mchart__tick" text-anchor="middle">${t}</text>`;
  }
  body += `<text x="${(m.l + W - m.r) / 2}" y="${H - 3}" class="mchart__tick" text-anchor="middle">Temperatura máxima de julio y agosto (°C)</text>`;
  for (const q of all) {
    if (q.id === p.id) continue;
    body += `<circle cx="${x(q.tmax_jul_ago)}" cy="${y(Math.min(q.esperado, 3.5))}" r="2.2" class="mchart__dot"/>`;
  }
  const line = [];
  for (let t = t0; t <= t1; t += 0.25) line.push(`${x(t).toFixed(1)},${y(fit(t)).toFixed(1)}`);
  body += `<polyline points="${line.join(" ")}" class="mchart__fit"/>`;
  body += `<circle cx="${x(p.tmax_jul_ago)}" cy="${y(Math.min(p.esperado, 3.5))}" r="6" class="mchart__me">`
    + `<title>${p.municipio}: ${formatNumber(p.tmax_jul_ago, 1)} °C, ${formatNumber(p.esperado, 2)} t/ha</title></circle>`;
  return `<figure class="mchart"><figcaption class="mchart__title">Temperatura y rendimiento esperado (t/ha)</figcaption>`
    + `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Cada punto es un municipio. ${p.municipio} tiene `
    + `${formatNumber(p.tmax_jul_ago, 1)} °C y ${formatNumber(p.esperado, 2)} t/ha. La recta del modelo baja `
    + `${formatNumber(Math.abs(p.pendiente_tmax), 2)} t/ha por cada grado más.">${body}</svg>`
    + `<p class="mchart__note">Cada punto es un municipio; el grande es ${p.municipio}. La línea es el modelo: cada grado más resta `
    + `${formatNumber(Math.abs(p.pendiente_tmax), 2)} t/ha. Fuera de la franja gris no hay municipios con SIAP y el modelo extrapola.</p></figure>`;
}

// Lista del panel

// Número para ordenar: los que faltan van al final de la lista
function sortValue(value, descending) {
  if (typeof value !== "number") return descending ? -Infinity : Infinity;
  return value;
}

function compareItems(key) {
  const desc = (field) => (a, b) => sortValue(b[field], true) - sortValue(a[field], true);
  const asc = (field) => (a, b) => sortValue(a[field], false) - sortValue(b[field], false);
  // Criterio principal y desempates; al final, el ID (o el nombre del municipio) para que el orden sea estable
  const criteria = {
    credit: [desc("prob_not_pay_credit"), asc("pred")],
    pred: [asc("pred"), desc("prob_not_pay_credit")],
    "mun-yield": [desc("esperado")],
    "mun-name": [],
  }[key];
  const municipal = SORTS[key].view === "municipal";
  return (a, b) => {
    for (const compare of criteria) {
      const result = compare(a, b);
      if (result) return result;
    }
    if (municipal) return a.municipality.localeCompare(b.municipality, "es") || a.id.localeCompare(b.id);
    return a.id.localeCompare(b.id);
  };
}

// Badge del riesgo de no pagar el crédito de una fila, con el nivel y la probabilidad en texto
function listRiskHtml(p) {
  const level = RISK_LEVELS.get(p.light_credit);
  if (!level || typeof p.prob_not_pay_credit !== "number") return '<span class="plist__risk muted">Sin dato</span>';
  return `<span class="plist__risk badge ${level.badge}"><span class="visually-hidden">Riesgo de no pagar el crédito: </span>`
    + `${capitalize(level.text)} · ${formatProbability(p.prob_not_pay_credit)}</span>`;
}

function listRowHtml(p) {
  const pred = typeof p.pred === "number" ? `${formatNumber(p.pred, 2)} <span class="plist__unit">t/ha</span>` : "—";
  return `<li><button type="button" class="plist__row" data-id="${p.id}">`
    + `<span class="plist__name"><strong>${p.id}</strong><span class="plist__muni">${p.municipality}</span></span>`
    + `<span class="plist__pred"><span class="visually-hidden">Predicción: </span>${pred}</span>`
    + (economicsFailed ? "" : listRiskHtml(p))
    + "</button></li>";
}

// Fila de un municipio: nombre y estado, rendimiento esperado y badge de confianza
function municipalRowHtml(p) {
  let value = "—";
  let risk = '<span class="plist__risk muted">Sin estimación</span>';
  const level = MUN_CONFIDENCE_CLASSES.find((c) => c.key === p.confianza);
  if (hasEstimate(p)) {
    value = `${formatNumber(p.esperado, 2)} <span class="plist__unit">t/ha</span>`;
    if (level) risk = `<span class="plist__risk badge ${level.badge}">${level.label}</span>`;
  }
  return `<li><button type="button" class="plist__row" data-id="${p.id}">`
    + `<span class="plist__name"><strong>${p.municipio}</strong><span class="plist__muni">${p.estado}</span></span>`
    + `<span class="plist__pred"><span class="visually-hidden">Rendimiento esperado: </span>${value}</span>`
    + risk
    + "</button></li>";
}

// Arma la lista con los elementos del modelo activo que pasan los filtros, en el orden elegido
function renderList() {
  const municipal = isMunicipalMode();
  const key = municipal ? sortByView.municipal : (economicsFailed ? "pred" : sortByView.parcels);
  const sort = SORTS[key];
  const rows = shown.map((f) => f.properties).filter((p) => municipal || p.set === "PREDICCION").sort(compareItems(key));
  const total = rows.length;

  let empty = municipal ? "No hay municipios con estos filtros." : "No hay parcelas por predecir con estos filtros.";
  if (municipal && municipalFailed) empty = "No se pudo cargar el modelo municipal.";
  else if (municipal && !municipalFeatures) empty = "Cargando el modelo municipal…";
  listItems.innerHTML = total
    ? rows.map((p) => (municipal ? municipalRowHtml(p) : listRowHtml(p))).join("")
    : `<li class="plist__empty">${empty}</li>`;
  const noun = municipal ? (total === 1 ? "municipio" : "municipios") : (total === 1 ? "parcela" : "parcelas");
  listSummary.textContent = total ? `${total} ${noun}, ${sort.text}` : "";
  listView.classList.toggle("plist--no-risk", !municipal && economicsFailed);
  listNote.hidden = municipal || !economicsFailed;
  updateToggleText(total, sort);
}

// Título de la hoja en el celular: cuántas hay y cómo van ordenadas, o qué muestra la hoja
function updateToggleText(total = listItems.querySelectorAll(".plist__row").length, sort = SORTS[sortSelect.value]) {
  const municipal = isMunicipalMode();
  const entry = layersById.get(selectedId);
  if (entry) {
    panelToggleText.textContent = `Resumen de ${entry.municipal ? entry.feature.properties.municipio : selectedId}`;
  } else if (!total) {
    panelToggleText.textContent = municipal ? "Ningún municipio con estos filtros" : "Ninguna por predecir con estos filtros";
  } else if (municipal) {
    panelToggleText.textContent = `${total} municipios · ordenados por ${sort ? sort.by : "rendimiento"}`;
  } else {
    panelToggleText.textContent = `${total} por predecir · ordenadas por ${economicsFailed || !sort ? "rendimiento" : sort.by}`;
  }
}

// Resumen del elemento elegido

function summaryRow(label, value, attrs = "") {
  return `<div class="psum__row"><dt>${label}</dt><dd${attrs}>${value}</dd></div>`;
}

function summaryHtml(p) {
  const training = p.set === "ENTRENAMIENTO";
  const dot = training ? "dot--entrenamiento" : "dot--prediccion";
  const value = training ? p.yield_t_ha : p.pred;
  const rows = [];
  if (training && typeof p.pred === "number") rows.push(summaryRow("Predicción validada", `${formatNumber(p.pred, 2)} t/ha`));
  if (typeof p.p10 === "number") rows.push(summaryRow("Rango p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
  // La confianza llega aparte, de /api/parcels/<id>
  rows.push(summaryRow("Confianza", '<span class="muted">Cargando…</span>', ' id="psum-conf" aria-busy="true"'));
  if (p.regime) rows.push(summaryRow("Régimen", REGIME_LABELS[p.regime] ?? p.regime));
  rows.push(summaryRow("Área", `${formatNumber(p.area_ha, 2)} ha`));

  let risk = '<p class="psum__empty">No se pudo cargar la economía.</p>';
  if (!economicsFailed) {
    const credit = typeof p.prob_not_pay_credit === "number"
      ? riskValueHtml(p.prob_not_pay_credit, p.light_credit) : '<span class="muted">Sin dato</span>';
    risk = `<dl class="psum__rows">${summaryRow("No pagar el crédito", credit)}</dl>`;
  }

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
    + "<p>El régimen es la forma en que el municipio reporta los rendimientos: el A con dos decimales, el B redondeado. "
    + "El modelo lo usa porque el A da cifras más altas.</p>"
    + "<p>El riesgo de no pagar el crédito es la probabilidad de que la cosecha no alcance para pagar lo financiado más "
    + "sus intereses. Junta la pérdida histórica de la cosecha en el municipio y el error del modelo. Bajo: menos de 10 %. "
    + "Medio: de 10 a menos de 30 %. Alto: 30 % o más.</p>"
    + "</div></details>"
    + `<div class="psum__footer"><a class="btn btn--primary psum__cta" href="${detailUrl(p.id)}">Ver ficha completa</a></div>`;
}

// Resumen de un municipio: rendimiento esperado, intervalo, confianza e historia del SIAP
function municipalSummaryHtml(p) {
  const rows = [];
  let value = "—";
  let caption = "Sin estimación para este municipio.";
  let reason = "";
  if (hasEstimate(p)) {
    value = formatNumber(p.esperado, 2);
    caption = p.esperado === 0 ? `${MUN_NOT_SUITABLE}.`
      : `Rendimiento esperado en ${p.anio_referencia ?? "2025"}, en la escala del SIAP`;
    if (p.p90 > 0) rows.push(summaryRow("Rango p10 a p90", `${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`));
    rows.push(summaryRow("Confianza", municipalConfidenceBadge(p.confianza)));
    if (typeof p.tmax_jul_ago === "number") {
      const diff = p.tmax_jul_ago - p.tmax_media;
      rows.push(summaryRow("Tmax jul-ago",
        `${formatNumber(p.tmax_jul_ago, 1)} °C <span class="muted">(${diff >= 0 ? "+" : "−"}${formatNumber(Math.abs(diff), 1)} del promedio)</span>`));
    }
    // En una extrapolación el aviso ya explica la confianza baja
    reason = isExtrapolation(p) ? "" : (MUN_CONFIDENCE_REASONS[p.confianza] ?? "");
  }
  if (p.con_siap) {
    rows.push(summaryRow("Media del SIAP", `${formatNumber(p.siap_media, 2)} t/ha en ${p.siap_anios} años`));
    rows.push(summaryRow(`Años bajo 2 t/ha en el SIAP`, formatPercent(p.siap_frac_bajo_2)));
  } else if (typeof p.dist_siap_km === "number") {
    rows.push(summaryRow("Municipio con SIAP más cercano", `a ${formatNumber(p.dist_siap_km, 1)} km`));
  }
  if (typeof p.agricola_ha === "number") rows.push(summaryRow("Agricultura de temporal", `${formatNumber(p.agricola_ha, 0)} ha`));
  if (p.reto) rows.push(summaryRow("Parcelas del reto", "Tiene parcelas del reto"));

  return `<div class="psum__head"><h2 id="psum-id" class="psum__id" tabindex="-1">${p.municipio}</h2>`
    + `<span class="tip__set">Municipio</span></div>`
    + `<p class="psum__place">${p.estado}</p>`
    + `<p class="psum__value">${value} <span class="psum__unit">t/ha</span></p>`
    + `<p class="psum__caption">${caption}</p>`
    + `<dl class="psum__rows">${rows.join("")}</dl>`
    + (reason ? `<p class="psum__reason">${reason}</p>` : "")
    + (isExtrapolation(p) ? `<p class="psum__reason">${MUN_EXTRAPOLATION_NOTE}</p>` : "")
    + (typeof p.parte_media === "number" ? municipalBreakdownSvg(p) + municipalTmaxSvg(p) : "")
    + '<details class="help-inline"><summary>¿Qué significan estas cifras?</summary><div class="help-inline__body">'
    + "<p>El número sale de tres partes. El promedio regional es el rendimiento medio de los municipios con SIAP, llevado a "
    + "2025. La temperatura lo sube o lo baja según qué tan caliente es el municipio en julio y agosto frente a ese promedio. "
    + "Los vecinos con SIAP corrigen lo que la temperatura no explica: si los municipios cercanos rinden más de lo que su "
    + "temperatura predice, el número sube. Lejos de los datos esa corrección se acerca a cero.</p>"
    + "<p>El modelo municipal estima lo que se puede esperar en un año como 2025 en todo el municipio, con la estadística "
    + "del SIAP de 2003 a 2025 y la temperatura máxima de julio y agosto. No distingue una parcela de otra.</p>"
    + "<p>Las cifras son toneladas por hectárea cosechada del SIAP, más bajas que las de las parcelas del reto. "
    + "No se comparan con la predicción de una parcela.</p>"
    + "<p>El rango p10 a p90 contiene el rendimiento real del municipio en unos 8 de cada 10 casos.</p>"
    + "<p>Los municipios con parcelas del reto llevan un contorno amarillo en el mapa; el modelo municipal no usa esas parcelas.</p>"
    + "</div></details>";
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
  const showItem = selectedId !== null;
  listView.hidden = showItem;
  parcelView.hidden = !showItem;
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

// Elige una parcela o un municipio y muestra su resumen. Desde la lista, el mapa además se centra en él
function openItem(id, { center = false } = {}) {
  const entry = layersById.get(id);
  if (!entry) return;
  // El foco vuelve a donde estaba al abrir (una fila de la lista, el mapa); cambiar de elemento no lo mueve
  if (!parcelView.contains(document.activeElement)) returnFocus = document.activeElement;
  const wasOpen = panelOpen;
  if (selectedId === null) closeToList = wasOpen;
  setSelected(id);
  panelOpen = true;
  const p = entry.feature.properties;
  summaryContent.innerHTML = entry.municipal ? municipalSummaryHtml(p) : summaryHtml(p);
  renderPanel();
  if (!wasOpen) layoutChanged();
  const bounds = entry.polygon.getBounds();
  const animate = !reducedMotion.matches;
  if (center && entry.municipal) {
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: MUN_FOCUS_MAX_ZOOM, animate });
  } else if (center) {
    map.setView(bounds.getCenter(), Math.max(map.getZoom(), FOCUS_ZOOM), { animate });
  } else {
    // Si el panel tapó el elemento (la hoja del celular), el mapa se mueve lo justo para verlo
    map.panInside(bounds.getCenter(), { padding: [40, 40] });
  }
  document.getElementById("psum-id").focus({ preventScroll: true });
  parcelView.scrollTop = 0;
  if (!entry.municipal) loadConfidence(id);
}

// Lleva el foco a un elemento si sigue en la página y se ve; si no, a la alternativa (por omisión, el control
// que vuelve a abrir el panel). Si venía de un elemento del mapa, vuelve al mapa y no al polígono
function restoreFocus(target, fallback = mobileQuery.matches ? panelToggle : panelOpenButton) {
  if (target && target !== mapElement && mapElement.contains(target)) target = mapElement;
  const visible = target && target !== document.body && target.isConnected && target.getClientRects().length > 0;
  (visible ? target : fallback).focus({ preventScroll: true });
}

// Cerrar (botón ×, Esc o el título de la hoja): suelta el elemento y cierra el panel o pliega la hoja
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

// «Volver a la lista»: suelta el elemento y deja el foco en su fila
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
  // Los filtros solo se pasan a las predicciones cuando se ven las parcelas: sus estados y municipios son los de ellas
  const filtered = !isMunicipalMode();
  predictionsLink.href = csvUrl(mapElement.dataset.predictionsUrl, {
    state: filtered && stateSelect.value,
    municipality: filtered && municipalitySelect.value,
  });
  economicsLink.href = csvUrl(mapElement.dataset.economicsUrl, {});
  municipalLink.href = csvUrl(mapElement.dataset.municipalUrl, {});
}

// Capa y filtros en location.hash, p. ej. #layer=risk_credit&state=Puebla&municipality=Chignahuapan
function saveState() {
  const params = new URLSearchParams({ layer: layerSelect.value });
  // Mientras llega el modelo municipal, los filtros pedidos todavía no están en los selectores
  const state = pendingFilters ? pendingFilters.state : stateSelect.value;
  const municipality = pendingFilters ? pendingFilters.municipality : municipalitySelect.value;
  if (state) params.set("state", state);
  if (municipality) params.set("municipality", municipality);
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

// Pasa los filtros al modelo activo; si es el municipal y aún no llega, quedan pendientes hasta que llegue
function applyFilters(state, municipality) {
  pendingFilters = isMunicipalMode() && !municipalFeatures ? { state, municipality } : null;
  refreshFilters(state, municipality);
}

// Aplica la capa y los filtros del hash; lo que no exista o no esté habilitado se ignora
function restoreState() {
  const params = new URLSearchParams(location.hash.slice(1));
  layerSelect.value = enabledValue(layerSelect, params.get("layer")) ?? "set";
  applyFilters(params.get("state") ?? "", params.get("municipality") ?? "");
}

// Texto del botón «Capa y filtros» (celular): cuántos filtros de estado o municipio están activos
function updateActiveFilters() {
  const active = [stateSelect.value, municipalitySelect.value].filter(Boolean).length;
  filtersActive.textContent = active ? ` · ${active} ${active === 1 ? "filtro" : "filtros"}` : "";
}

// Sin economía, la capa de riesgo queda deshabilitada y la lista se ordena por rendimiento, y lo dice
function disableRiskLayers() {
  for (const option of layerSelect.options) {
    if (option.value === RISK_LAYER) option.disabled = true;
  }
  sortByView.parcels = "pred";
  listNote.textContent = "No se pudo cargar la economía: la lista se ordena por rendimiento predicho, de menor a mayor.";
}

// Eventos

map.on("zoomend", showByZoom);
// El alto del mapa cambia sin que cambie la ventana (indicadores que se llenan, filtros o la hoja del celular que
// se abren): Leaflet y el mapa base se enteran aquí para no dejar franjas vacías
if (window.ResizeObserver) new ResizeObserver(layoutChanged).observe(mapElement);
layerSelect.addEventListener("change", () => {
  const switched = currentView() !== shownView;
  // Al pasar de un modelo al otro, los filtros toman los estados y municipios del nuevo (y se conservan si existen en él)
  if (switched) applyFilters(stateSelect.value, municipalitySelect.value);
  // Una capa municipal pide su GeoJSON la primera vez (o vuelve a pedirlo si antes falló)
  requestMunicipal();
  draw(switched);
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
for (const link of [predictionsLink, economicsLink, municipalLink]) {
  link.addEventListener("click", () => {
    downloadMenu.open = false;
  });
}

// Lista: clic o Enter en una fila elige el elemento y centra el mapa en él; flechas, Inicio y Fin pasan de fila en fila
listItems.addEventListener("click", (event) => {
  const row = event.target.closest(".plist__row");
  if (row) openItem(row.dataset.id, { center: true });
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
sortSelect.addEventListener("change", () => {
  sortByView[currentView()] = sortSelect.value;
  renderList();
});

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

// La economía se pide a la par; si falla, el mapa se dibuja igual, sin la capa de riesgo
const economicsRequest = fetchJson(mapElement.dataset.economicsUrl).catch(() => null);

Promise.all([fetchJson(mapElement.dataset.parcelsUrl), fetchJson(mapElement.dataset.predictionsUrl), economicsRequest])
  .then(([geojson, predictions, economics]) => {
    // Une a cada parcela su predicción, intervalo y régimen
    const byId = new Map(predictions.map((r) => [r.id, r]));
    parcels = geojson.features;
    for (const f of parcels) {
      const r = byId.get(f.properties.id);
      if (r) Object.assign(f.properties, { pred: r.pred, p10: r.p10, p90: r.p90, regime: r.regime });
    }
    // Y a cada una su riesgo de no pagar el crédito y su semáforo; sin economía, su capa queda deshabilitada
    economicsFailed = !Array.isArray(economics);
    if (economicsFailed) {
      disableRiskLayers();
    } else {
      const economyById = new Map(economics.map((r) => [r.id, r]));
      for (const f of parcels) {
        const e = economyById.get(f.properties.id);
        if (e) Object.assign(f.properties, { prob_not_pay_credit: e.prob_not_pay_credit, light_credit: e.light_credit });
      }
    }
    // La capa y los filtros vienen del hash si son válidos; luego se dibuja
    restoreState();
    updateDownloadLinks();
    // Si el hash trae una capa municipal, su modelo se pide ahora; mientras llega, el mapa avisa que está cargando
    requestMunicipal();
    draw(true);
  })
  .catch(() => {
    countLabel.textContent = "No se pudieron cargar las parcelas.";
    listItems.innerHTML = '<li class="plist__empty">No se pudieron cargar las parcelas.</li>';
  });
