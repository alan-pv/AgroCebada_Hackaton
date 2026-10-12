// Mapa de la página inicial: parcelas coloreadas por conjunto, rendimiento observado o predicción

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

// Vista inicial sobre la zona de estudio; se ajusta al cargar las parcelas
const map = L.map(mapElement).setView([19.8, -98.4], 10);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

let parcels = [];
let polygonsLayer = null;
let pointsLayer = null;

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

function featureStyle(feature) {
  const p = feature.properties;
  const base = { weight: 1, color: BORDER, opacity: 1, fillOpacity: 0.8, dashArray: null };
  if (layerSelect.value === "set") {
    return { ...base, fillColor: SET_COLORS[p.set] };
  }
  const value = colorValue(p);
  if (value === null || value === undefined) {
    // Sin valor en este modo: gris con borde punteado, para no depender solo del color
    return { ...base, fillColor: NO_DATA.color, color: NO_DATA.border, fillOpacity: 0.5, dashArray: "3 3" };
  }
  return { ...base, fillColor: yieldColor(value) };
}

function pointStyle(feature) {
  const value = layerSelect.value === "set" ? 0 : colorValue(feature.properties);
  const noData = value === null || value === undefined;
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
  countLabel.textContent = `${total} ${noun}: ${training} de entrenamiento y ${total - training} por predecir`;
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

map.on("zoomend", showByZoom);
layerSelect.addEventListener("change", () => {
  updateLegend();
  draw(false);
});
stateSelect.addEventListener("change", () => {
  // Al cambiar de estado, el municipio vuelve a "Todos"
  updateMunicipalities();
  draw(true);
});
municipalitySelect.addEventListener("change", () => draw(true));

Promise.all([fetchJson(mapElement.dataset.parcelsUrl), fetchJson(mapElement.dataset.predictionsUrl)])
  .then(([geojson, predictions]) => {
    // Une a cada parcela su predicción e intervalo
    const byId = new Map(predictions.map((r) => [r.id, r]));
    parcels = geojson.features;
    for (const f of parcels) {
      const r = byId.get(f.properties.id);
      if (r) Object.assign(f.properties, { pred: r.pred, p10: r.p10, p90: r.p90, prob_below: r.prob_below });
    }
    fillSelect(stateSelect, parcels.map((f) => f.properties.state));
    updateMunicipalities();
    updateLegend();
    draw(true);
  })
  .catch(() => {
    countLabel.textContent = "No se pudieron cargar las parcelas.";
  });
