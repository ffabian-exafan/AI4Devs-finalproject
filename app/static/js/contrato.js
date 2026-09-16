function contratoApp() {
  return {
    proyectos: [],
    naves: [],
    proyectoId: "",
    naveId: "",
    fichero: null,
    cargandoNaves: false,
    enviando: false,
    error: "",
    resultado: null,
    euro: (v) => GestorApi.euro(v),

    async init() {
      try {
        this.proyectos = await GestorApi.getJson("/proyectos");
      } catch (err) {
        this.error = "No se pudieron cargar proyectos: " + err.message;
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const pre = params.get("proyecto_id");
      if (pre) {
        this.proyectoId = String(pre);
        await this.cargarNaves();
      }
    },

    async cargarNaves() {
      this.naves = [];
      this.naveId = "";
      if (!this.proyectoId) return;
      this.cargandoNaves = true;
      try {
        const det = await GestorApi.getJson("/proyectos/" + this.proyectoId);
        this.naves = det.naves || [];
      } catch (err) {
        this.error = "No se pudo cargar el proyecto: " + err.message;
      } finally {
        this.cargandoNaves = false;
      }
    },

    onFile(event) {
      this.fichero = event.target.files[0] || null;
      this.error = "";
      this.resultado = null;
    },

    async enviar() {
      if (!this.proyectoId || !this.fichero) {
        this.error = "Proyecto y fichero son obligatorios";
        return;
      }
      this.enviando = true;
      this.error = "";
      this.resultado = null;
      try {
        const fd = new FormData();
        fd.append("fichero", this.fichero, this.fichero.name);
        if (this.naveId) {
          fd.append("nave_id", this.naveId);
        }
        this.resultado = await GestorApi.postForm(
          "/proyectos/" + this.proyectoId + "/importar-contrato",
          fd
        );
      } catch (err) {
        this.error = err.message;
      } finally {
        this.enviando = false;
      }
    },
  };
}
