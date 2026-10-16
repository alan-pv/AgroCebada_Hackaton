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
// Semáforo de la API (light_*): texto, rango de probabilidad y color; paleta Okabe-Ito, apta para daltonismo
const RISK_LEVELS = new Map([
  ["verde", { text: "bajo", range: "menos de 10 %", color: "#009E73" }],
  ["amarillo", { text: "medio", range: "de 10 a 30 %", color: "#E69F00" }],
  ["rojo", { text: "alto", range: "30 % o más", color: "#D55E00" }],
]);

const BORDER = "#52514e";
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

// Vista inicial sobre la zona de estudio; se ajusta al cargar las parcelas
const map = L.map(mapElement).setView([19.8, -98.4], 10);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

let parcels = [];
let polygonsLayer = null;
let pointsLayer = null;
// Verdadero si la carga de economía falló; entonces las capas de riesgo están deshabilitadas
let economicsFailed = false;

function yieldColor(value) {
  for (const c of YIELD_CLASSES) {
    if (value < c.to) return c.color;
  }
  // 5.6 o más cae en la última clase
  return YIELD_CLASSES[YIELD_CLASSES.length - 1].color;
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
  const base = { weight: 1, color: BORDER, opacity: 1, fillOpacity: 0.8, dashArray: null };
  const fillColor = fillColorOf(p);
  if (fillColor === null) {
    // Sin valor en este modo: gris con borde punteado, para no depender solo del color
    return { ...base, fillColor: NO_DATA.color, color: NO_DATA.border, fillOpacity: 0.5, dashArray: "3 3" };
  }
  return { ...base, fillColor };
}

function pointStyle(feature) {
  const noData = fillColorOf(feature.properties) === null;
  // Anillo blanco para separar los círculos que se enciman; punteado gris si no hay valor
  return {
    ...featureStyle(feature),
    radius: POINT_RADIUS,
    weight: 1,
    color: noData ? NO_DATA.border : "#ffffff",
    dashArray: noData ? "2 2" : null,
    fillOpacity: noData ? 0.6 : 0.9,
  };
}

function formatNumber(value, digits) {
  return value.toLocaleString("es-MX", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// Línea del tooltip con la probabilidad de un riesgo y, si la API la trae, su nivel (bajo, medio o alto)
function riskLine(label, probability, light) {
  const level = RISK_LEVELS.get(light);
  const suffix = level ? ` (riesgo ${level.text})` : "";
  return `${label}: ${formatNumber(probability * 100, 0)} %${suffix}`;
}

function tooltipHtml(p) {
  const lines = [`<strong>${p.id}</strong>`, `${p.municipality}, ${p.state}`];
  if (p.set === "ENTRENAMIENTO") {
    lines.push(`Entrenamiento · ${formatNumber(p.yield_t_ha, 2)} t/ha observadas`);
  } else {
    lines.push(`Predicción · ${formatNumber(p.pred, 2)} t/ha`);
    lines.push(`Intervalo p10 a p90: ${formatNumber(p.p10, 2)} a ${formatNumber(p.p90, 2)} t/ha`);
    lines.push(`Probabilidad bajo 2.5 t/ha: ${formatNumber(p.prob_below * 100, 0)} %`);
  }
  lines.push(`${formatNumber(p.area_ha, 2)} ha`);
  // Riesgo económico, solo si se cargó la economía
  if (typeof p.prob_not_cover_costs === "number") {
    lines.push(riskLine("Probabilidad de no cubrir costos", p.prob_not_cover_costs, p.light_costs));
  }
  if (typeof p.prob_not_pay_credit === "number") {
    lines.push(riskLine("Probabilidad de no pagar el crédito", p.prob_not_pay_credit, p.light_credit));
  }
  // Siempre es la última línea: avisa que el clic abre la ficha
  lines.push("Clic para ver la ficha");
  return lines.join("<br>");
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

function legendRow(color, label, extraClass = "") {
  return `<div class="legend-row"><span class="legend-swatch ${extraClass}" style="background:${color}"></span>${label}</div>`;
}

const legend = L.control({ position: "bottomright" });
legend.onAdd = () => L.DomUtil.create("div", "legend");
legend.addTo(map);

function updateLegend() {
  const div = legend.getContainer();
  const mode = layerSelect.value;
  if (mode === "set") {
    div.innerHTML = "<strong>Conjunto</strong>"
      + Object.keys(SET_COLORS).map((k) => legendRow(SET_COLORS[k], SET_LABELS[k])).join("");
  } else if (RISK_LAYERS.has(mode)) {
    // Los tres niveles del semáforo con su rango de probabilidad, y la entrada de sin dato
    div.innerHTML = `<strong>${RISK_LAYERS.get(mode).title}</strong>`
      + [...RISK_LEVELS.values()].map((level) => legendRow(level.color, `Riesgo ${level.text}: ${level.range}`)).join("")
      + legendRow(NO_DATA.color, "Sin dato", "legend-swatch--no-data");
  } else {
    div.innerHTML = `<strong>${LEGEND_TITLES[mode]}</strong>`
      + YIELD_CLASSES.map((c) => legendRow(c.color, `${c.from.toFixed(1)} a ${c.to.toFixed(1)}`)).join("")
      + legendRow(NO_DATA.color, NO_DATA_LABELS[mode], "legend-swatch--no-data");
  }
}

function bindInteractions(feature, layer, reset) {
  layer.bindTooltip(tooltipHtml(feature.properties), { sticky: true });
  layer.on({
    mouseover: () => {
      layer.setStyle({ weight: 3, color: BORDER_HOVER });
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

// Sin economía, las capas de riesgo quedan deshabilitadas y el resto del mapa sigue igual
function disableRiskLayers() {
  for (const option of layerSelect.options) {
    if (RISK_LAYERS.has(option.value)) option.disabled = true;
  }
}

map.on("zoomend", showByZoom);
layerSelect.addEventListener("change", () => {
  updateLegend();
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
    updateLegend();
    updateDownloadLinks();
    draw(true);
  })
  .catch(() => {
    countLabel.textContent = "No se pudieron cargar las parcelas.";
  });
