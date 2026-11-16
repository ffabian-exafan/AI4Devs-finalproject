function presupuestoApp() {
  return {
    fichero: null,
    verPagina: false,
    enviando: false,
    error: "",
    resultado: null,
    euro: (v) => GestorApi.euro(v),

    onFile(event) {
      this.fichero = event.target.files[0] || null;
      this.error = "";
      this.resultado = null;
    },

    async enviar() {
      if (!this.fichero) {
        this.error = "Selecciona un fichero";
        return;
      }
      this.enviando = true;
      this.error = "";
      this.resultado = null;
      try {
        const fd = new FormData();
        fd.append("fichero", this.fichero, this.fichero.name);
        if (this.verPagina) {
          fd.append("ver_pagina", "1");
        }
        this.resultado = await GestorApi.postForm(
          "/proyectos/importar-presupuesto",
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
