// Pestañas compartidas. El HTML trae las secciones apiladas, cada una legible sin JavaScript:
//
//   <div class="tabs" data-tabs aria-label="Secciones de la ficha">
//     <section class="tabs__panel" id="economia" data-tab-label="Economía">...</section>
//   </div>
//
// Este script arma la fila de pestañas con los data-tab-label, deja visible una sección y oculta las demás.
// Sigue el patrón de pestañas de WAI-ARIA: flechas, Inicio y Fin mueven entre pestañas y activan la elegida.
// La pestaña activa va en location.hash (#economia); un enlace a un elemento dentro de otra sección la abre.
// Con data-tabs-hash="false" el contenedor no toca la URL. Cada cambio dispara «tabs:change» con detail.id.

(function () {
  function setupTabs(container) {
    const panels = [...container.children].filter((el) => el.classList.contains("tabs__panel"));
    if (!panels.length) return;
    const useHash = container.dataset.tabsHash !== "false";

    const list = document.createElement("div");
    list.className = "tabs__list";
    list.setAttribute("role", "tablist");
    if (container.hasAttribute("aria-label")) list.setAttribute("aria-label", container.getAttribute("aria-label"));

    const tabs = panels.map((panel) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = "tabs__tab";
      tab.id = `tab-${panel.id}`;
      tab.textContent = panel.dataset.tabLabel || panel.id;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", panel.id);
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-labelledby", tab.id);
      list.append(tab);
      return tab;
    });
    container.prepend(list);
    container.classList.add("tabs--ready");

    function select(index, { focus = false, updateHash = true } = {}) {
      tabs.forEach((tab, i) => {
        const active = i === index;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        panels[i].hidden = !active;
      });
      if (focus) tabs[index].focus();
      if (useHash && updateHash) {
        history.replaceState(null, "", `${location.pathname}${location.search}#${panels[index].id}`);
      }
      container.dispatchEvent(new CustomEvent("tabs:change", { detail: { id: panels[index].id } }));
    }

    // Índice de la sección que contiene el destino del hash, o -1 si no está en este contenedor
    function indexFromHash() {
      const id = decodeURIComponent(location.hash.slice(1));
      if (!id) return -1;
      const target = document.getElementById(id);
      return target ? panels.findIndex((panel) => panel.contains(target)) : -1;
    }

    tabs.forEach((tab, i) => {
      tab.addEventListener("click", () => select(i));
      tab.addEventListener("keydown", (event) => {
        const last = tabs.length - 1;
        const current = tabs.indexOf(event.target);
        const next = {
          ArrowRight: current === last ? 0 : current + 1,
          ArrowLeft: current === 0 ? last : current - 1,
          Home: 0,
          End: last,
        }[event.key];
        if (next === undefined) return;
        event.preventDefault();
        select(next, { focus: true });
      });
    });

    // Lleva al destino del hash; si es un <details> plegado, lo abre
    function revealTarget() {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (target.tagName === "DETAILS") target.open = true;
      target.scrollIntoView();
    }

    // Un enlace a un elemento dentro de otra sección (p. ej. #desglose) abre esa sección y lleva al elemento
    window.addEventListener("hashchange", () => {
      const index = indexFromHash();
      if (index < 0) return;
      select(index, { updateHash: false });
      revealTarget();
    });

    const initial = useHash ? indexFromHash() : -1;
    select(initial < 0 ? 0 : initial, { updateHash: false });
    // Al cargar con un hash a un elemento dentro de una sección, el navegador ya intentó llevar a él
    // mientras estaba oculto; se lleva de nuevo ahora que se ve
    if (initial >= 0 && location.hash.slice(1) !== panels[initial].id) revealTarget();

    // Las secciones entran al orden de tabulación después de cargar: si fueran enfocables antes,
    // el navegador enfocaría la del hash al abrir la página y dibujaría el marco de foco alrededor
    window.addEventListener("load", () => {
      setTimeout(() => panels.forEach((panel) => { panel.tabIndex = 0; }));
    }, { once: true });

    // Si las pestañas no caben (celular), un desvanecido en el borde avisa que hay más hacia ese lado
    function updateOverflow() {
      const more = list.scrollWidth - list.clientWidth;
      list.classList.toggle("tabs__list--more-right", more > 1 && list.scrollLeft < more - 1);
      list.classList.toggle("tabs__list--more-left", more > 1 && list.scrollLeft > 1);
    }
    list.addEventListener("scroll", updateOverflow, { passive: true });
    window.addEventListener("resize", updateOverflow);
    // La pestaña elegida entra a la vista si quedó fuera; solo se desplaza la fila, nunca la página
    // (offsetLeft se mide desde la fila porque .tabs__list lleva position: relative)
    function revealSelected() {
      const tab = list.querySelector('[aria-selected="true"]');
      if (tab.offsetLeft < list.scrollLeft) {
        list.scrollLeft = tab.offsetLeft;
      } else if (tab.offsetLeft + tab.offsetWidth > list.scrollLeft + list.clientWidth) {
        list.scrollLeft = tab.offsetLeft + tab.offsetWidth - list.clientWidth;
      }
      updateOverflow();
    }
    container.addEventListener("tabs:change", revealSelected);
    revealSelected();
  }

  document.querySelectorAll("[data-tabs]").forEach(setupTabs);
})();
