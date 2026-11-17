/** Menú de acciones de una fila. El navegador abre el popover; esto cubre teclado y el anclaje antiguo. */
(function () {
  const soportaFocusgroup = "focusGroup" in HTMLElement.prototype;
  const soportaInvoker = "commandForElement" in HTMLButtonElement.prototype;
  const soportaAncla = !!(window.CSS && CSS.supports("position-area: block-end"));
  const entrarAlAbrir = new WeakSet();

  if (!Object.hasOwn(HTMLElement.prototype, "popover")) {
    import("https://unpkg.com/@oddbird/popover-polyfill@latest/dist/popover.min.js");
  }

  function menuDe(trigger) {
    const id = trigger.getAttribute("commandfor");
    return id ? document.getElementById(id) : null;
  }

  function grupoDe(menu) {
    return menu ? menu.querySelector("[focusgroup]") : null;
  }

  function triggerDe(grupo) {
    if (!grupo) return null;
    const id = grupo.getAttribute("aria-labelledby");
    return id ? document.getElementById(id) : null;
  }

  function abierto(menu) {
    if (menu.classList.contains(":popover-open")) return true;
    try {
      return menu.matches(":popover-open");
    } catch {
      return false;
    }
  }

  function opciones(grupo) {
    return [...grupo.querySelectorAll("button")].filter((item) => {
      if (item.closest("[focusgroup]") !== grupo) return false;
      if (item.disabled || item.getAttribute("aria-disabled") === "true") return false;
      return getComputedStyle(item).display !== "none";
    });
  }

  function enfocar(el, visible) {
    if (!el) return;
    try {
      el.focus(visible ? undefined : { focusVisible: false });
    } catch {
      el.focus();
    }
  }

  function preparar(menu) {
    if (soportaFocusgroup) return;
    const grupo = grupoDe(menu);
    if (!grupo) return;
    grupo.setAttribute("role", "menu");
    grupo.querySelectorAll("button:not([role])").forEach((item) => {
      if (item.closest("[focusgroup]") === grupo) item.setAttribute("role", "menuitem");
    });
  }

  function colocar(menu, trigger) {
    if (soportaAncla) {
      menu.style.left = "";
      menu.style.top = "";
      return;
    }
    const margen = 8;
    const hueco = 4;
    const rect = trigger.getBoundingClientRect();
    const ancho = menu.offsetWidth;
    const alto = menu.offsetHeight;
    let left = rect.right - ancho;
    let top = rect.bottom + hueco;
    if (left < margen) left = margen;
    if (left + ancho > window.innerWidth - margen) {
      left = Math.max(margen, window.innerWidth - ancho - margen);
    }
    if (top + alto > window.innerHeight - margen) {
      const arriba = rect.top - alto - hueco;
      top = arriba >= margen ? arriba : Math.max(margen, window.innerHeight - alto - margen);
    }
    menu.style.left = Math.round(left) + "px";
    menu.style.top = Math.round(top) + "px";
  }

  document.addEventListener(
    "pointerdown",
    (event) => {
      const trigger = event.target.closest("button.btn-menu[commandfor]");
      if (!trigger) return;
      event.preventDefault();
      const menu = menuDe(trigger);
      if (menu) preparar(menu);
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      const trigger = event.target.closest("button.btn-menu[commandfor]");
      if (!trigger) return;
      const menu = menuDe(trigger);
      if (!menu) return;
      const teclado = event.detail === 0;
      if (teclado) entrarAlAbrir.add(menu);
      if (soportaInvoker) return;
      event.preventDefault();
      preparar(menu);
      if (abierto(menu)) {
        enfocar(trigger, false);
        menu.hidePopover();
        return;
      }
      if (!teclado) entrarAlAbrir.delete(menu);
      menu.showPopover({ source: trigger });
    },
    true
  );

  document.addEventListener(
    "keydown",
    (event) => {
      const trigger = event.target.closest("button.btn-menu[commandfor]");
      if (trigger && event.key === "ArrowDown") {
        event.preventDefault();
        const menu = menuDe(trigger);
        if (!menu) return;
        preparar(menu);
        entrarAlAbrir.add(menu);
        if (!abierto(menu)) trigger.click();
        else {
          const primera = opciones(grupoDe(menu))[0];
          if (primera) primera.focus();
        }
        return;
      }

      const grupo = event.target.closest("[focusgroup]");
      if (!grupo || !grupo.closest(".menu-popover")) return;
      const teclas = ["ArrowDown", "ArrowUp", "Home", "End"];
      if (!teclas.includes(event.key)) return;
      if (soportaFocusgroup && event.key !== "Home" && event.key !== "End") return;
      const lista = opciones(grupo);
      if (!lista.length) return;
      const actual = lista.indexOf(document.activeElement);
      if (actual < 0 && event.key !== "Home" && event.key !== "End") return;
      const siguiente =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? lista.length - 1
            : (actual + (event.key === "ArrowUp" ? -1 : 1) + lista.length) % lista.length;
      event.preventDefault();
      lista[siguiente].focus({ preventScroll: true });
    },
    true
  );

  document.addEventListener(
    "toggle",
    (event) => {
      const menu = event.target;
      if (!(menu instanceof HTMLElement) || !menu.classList.contains("menu-popover")) return;
      const grupo = grupoDe(menu);
      const trigger = triggerDe(grupo);
      if (trigger) trigger.setAttribute("aria-expanded", event.newState === "open" ? "true" : "false");
      if (event.newState !== "open") {
        entrarAlAbrir.delete(menu);
        return;
      }
      preparar(menu);
      if (trigger) colocar(menu, trigger);
      if (entrarAlAbrir.has(menu)) {
        entrarAlAbrir.delete(menu);
        const primera = grupo ? opciones(grupo)[0] : null;
        if (primera) primera.focus();
        return;
      }
      enfocar(trigger, false);
    },
    true
  );

  document.addEventListener(
    "click",
    (event) => {
      const item = event.target.closest(".menu-popover [focusgroup] > button:not([commandfor])");
      if (!item) return;
      const menu = item.closest(".menu-popover");
      const trigger = triggerDe(grupoDe(menu));
      const desdePuntero = event.detail !== 0;
      queueMicrotask(() => {
        const dialogo = document.querySelector("dialog[open]");
        try {
          if (!dialogo && trigger && document.contains(trigger)) enfocar(trigger, !desdePuntero);
          if (menu && menu.isConnected && abierto(menu)) menu.hidePopover();
        } catch {
          /* la fila se fue al borrar */
        }
      });
    },
    true
  );

  document.addEventListener("pointermove", (event) => {
    const item = event.target.closest(".menu-popover [focusgroup] > button");
    if (!item || item === document.activeElement) return;
    const debajo = document.elementFromPoint(event.clientX, event.clientY);
    if (debajo !== item && !item.contains(debajo)) return;
    enfocar(item, false);
  });

  document.addEventListener("focusin", (event) => {
    document.querySelectorAll(".menu-popover").forEach((menu) => {
      if (!abierto(menu)) return;
      const trigger = triggerDe(grupoDe(menu));
      if (menu.contains(event.target) || event.target === trigger) return;
      menu.hidePopover();
    });
  });
})();
