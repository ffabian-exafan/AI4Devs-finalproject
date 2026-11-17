/** Pantalla de alta, edición y baja de usuarios. */
function gestionUsuarios() {
  const roles = {
    jefe_obra: "Jefe de obra",
    administracion: "Administración",
    direccion: "Dirección",
    superadministrador: "Superadministrador",
  };

  return {
    ...sesionLateral(),
    menuCompacto: false,
    cargando: true,
    error: "",
    usuarios: [],
    editandoId: null,
    modalAbierto: false,
    form: vacio(),

    init() {
      try {
        this.menuCompacto = localStorage.getItem("obrix-menu") === "1";
      } catch {
        this.menuCompacto = false;
      }
      this.cargar();
    },

    toggleMenu() {
      this.menuCompacto = !this.menuCompacto;
      try {
        localStorage.setItem("obrix-menu", this.menuCompacto ? "1" : "0");
      } catch {
        /* sin almacenamiento local, el menú solo cambia en esta visita */
      }
    },

    etiquetaRol(rol) {
      return roles[rol] || rol;
    },

    async cargar() {
      this.cargando = true;
      this.error = "";
      const dentro = await this.cargarYo();
      if (!dentro) return;
      try {
        this.usuarios = await GestorApi.getJson("/usuarios");
      } catch (err) {
        this.error = err.message || "No se han podido cargar los usuarios.";
      } finally {
        this.cargando = false;
      }
    },

    nuevo() {
      this.error = "";
      this.editandoId = null;
      this.form = vacio();
      this.abrirModal();
    },

    editar(usuario) {
      this.error = "";
      this.editandoId = usuario.id;
      this.form = {
        nombre: usuario.nombre,
        email: usuario.email,
        rol: usuario.rol,
        password: "",
      };
      this.abrirModal();
    },

    abrirModal() {
      this.modalAbierto = true;
      this.$refs.modalUsuario.showModal();
    },

    cerrarModal() {
      if (this.$refs.modalUsuario.open) this.$refs.modalUsuario.close();
    },

    alCerrar() {
      this.modalAbierto = false;
      this.editandoId = null;
      this.form = vacio();
      this.error = "";
    },

    async guardar() {
      this.error = "";
      try {
        if (this.editandoId) {
          const cuerpo = {
            nombre: this.form.nombre,
            email: this.form.email,
            rol: this.form.rol,
          };
          if (this.form.password) cuerpo.password = this.form.password;
          await GestorApi.patchJson("/usuarios/" + this.editandoId, cuerpo);
        } else {
          await GestorApi.postJson("/usuarios", this.form);
        }
        this.cerrarModal();
        this.usuarios = await GestorApi.getJson("/usuarios");
      } catch (err) {
        this.error = err.message || "No se ha podido guardar.";
      }
    },

    async borrar(usuario) {
      if (!window.confirm("¿Borrar a " + usuario.nombre + "?")) return;
      this.error = "";
      try {
        await GestorApi.borrar("/usuarios/" + usuario.id);
        if (this.editandoId === usuario.id) this.cerrarModal();
        this.usuarios = await GestorApi.getJson("/usuarios");
      } catch (err) {
        this.error = err.message || "No se ha podido borrar.";
      }
    },
  };
}

function vacio() {
  return { nombre: "", email: "", rol: "jefe_obra", password: "" };
}
