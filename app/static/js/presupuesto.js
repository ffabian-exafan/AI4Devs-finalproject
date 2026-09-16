function presupuestoApp() {
  return {
    fichero: null,
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
