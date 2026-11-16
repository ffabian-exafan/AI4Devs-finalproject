/** Pantalla de entrada. */
function entrar() {
  return {
    email: "",
    password: "",
    error: "",
    enviando: false,

    destino() {
      const next = new URLSearchParams(location.search).get("next") || "/";
      if (!next.startsWith("/") || next.startsWith("//")) return "/";
      return next;
    },

    async init() {
      try {
        await GestorApi.getJson("/auth/yo");
        location.replace(this.destino());
      } catch {
        /* sin sesión: se queda en el formulario */
      }
    },

    async enviar() {
      this.error = "";
      this.enviando = true;
      try {
        await GestorApi.postJson("/auth/login", {
          email: this.email,
          password: this.password,
        });
        location.assign(this.destino());
      } catch (err) {
        this.error = err.message || "No se ha podido entrar.";
      } finally {
        this.enviando = false;
      }
    },
  };
}
