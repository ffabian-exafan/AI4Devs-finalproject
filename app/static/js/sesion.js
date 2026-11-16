/** Nombre de la sesión y salida, compartido por las pantallas con barra lateral. */
function sesionLateral() {
  return {
    yo: null,

    async cargarYo() {
      try {
        this.yo = await GestorApi.getJson("/auth/yo");
        return true;
      } catch {
        const destino = location.pathname && location.pathname !== "/" ? location.pathname : "/";
        location.replace("/login.html?next=" + encodeURIComponent(destino));
        return false;
      }
    },

    inicialSesion() {
      const nombre = this.yo && this.yo.nombre ? this.yo.nombre.trim() : "";
      return nombre ? nombre.charAt(0).toUpperCase() : "";
    },

    async salir() {
      try {
        await GestorApi.postVacio("/auth/logout");
      } finally {
        location.assign("/login.html");
      }
    },
  };
}
