function esNombrePdf(nombre) {
  return typeof nombre === "string" && /\.pdf$/i.test(nombre.trim());
}

function urlVerPdf(url) {
  if (!url) return "";
  return url + (url.indexOf("?") >= 0 ? "&" : "?") + "ver=1";
}

/** Safari no entiende closedby. El clic fuera se mide por coordenadas, no por event.target. */
function prepararCierreVisor(dialogo) {
  if (!(dialogo instanceof HTMLDialogElement) || dialogo.dataset.cierreListo === "1") return;
  dialogo.dataset.cierreListo = "1";
  if ("closedBy" in HTMLDialogElement.prototype) return;
  const fuera = (evento, nodo) => {
    const caja = nodo.getBoundingClientRect();
    return (
      evento.clientX < caja.left ||
      evento.clientX > caja.right ||
      evento.clientY < caja.top ||
      evento.clientY > caja.bottom
    );
  };
  let pulsadoFuera = false;
  dialogo.addEventListener("pointerdown", (evento) => {
    pulsadoFuera = fuera(evento, dialogo);
  });
  dialogo.addEventListener("pointerup", (evento) => {
    if (pulsadoFuera && fuera(evento, dialogo)) dialogo.close();
  });
}
