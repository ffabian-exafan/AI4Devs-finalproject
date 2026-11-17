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
    marcadas: [],
    borrando: false,
    page: 1,
    pageSize: 10,
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
        this.podarMarcadas();
        this.ajustarPagina();
      } catch (err) {
        this.error = err.message || "No se han podido cargar los usuarios.";
      } finally {
        this.cargando = false;
      }
    },

    usuariosVisibles() {
      const inicio = (this.page - 1) * this.pageSize;
      return this.usuarios.slice(inicio, inicio + this.pageSize);
    },

    totalPaginas() {
      return Math.max(1, Math.ceil(this.usuarios.length / this.pageSize));
    },

    textoPagina() {
      const total = this.usuarios.length;
      if (!total) return "0 usuarios";
      const inicio = (this.page - 1) * this.pageSize + 1;
      const fin = Math.min(total, this.page * this.pageSize);
      return inicio + "–" + fin + " de " + total;
    },

    ajustarPagina() {
      if (this.page > this.totalPaginas()) this.page = this.totalPaginas();
      if (this.page < 1) this.page = 1;
    },

    paginaAnterior() {
      if (this.page > 1) this.page -= 1;
    },

    paginaSiguiente() {
      if (this.page < this.totalPaginas()) this.page += 1;
    },

    esPropio(id) {
      return !!(this.yo && this.yo.id === id);
    },

    podarMarcadas() {
      const propio = this.yo ? this.yo.id : null;
      const ids = new Set(this.usuarios.map((u) => u.id));
      this.marcadas = this.marcadas.filter((id) => ids.has(id) && id !== propio);
    },

    borrablesVisibles() {
      return this.usuariosVisibles().filter((u) => !this.esPropio(u.id));
    },

    estaMarcado(id) {
      return this.marcadas.includes(id);
    },

    todasMarcadas() {
      const fila = this.borrablesVisibles();
      return fila.length > 0 && fila.every((u) => this.marcadas.includes(u.id));
    },

    algunaMarcada() {
      return this.borrablesVisibles().some((u) => this.marcadas.includes(u.id));
    },

    marcarUsuario(id, marcada) {
      if (this.esPropio(id)) return;
      if (marcada) {
        if (!this.marcadas.includes(id)) this.marcadas = this.marcadas.concat(id);
        return;
      }
      this.marcadas = this.marcadas.filter((item) => item !== id);
    },

    marcarPagina(marcada) {
      const ids = this.borrablesVisibles().map((u) => u.id);
      if (marcada) {
        this.marcadas = [...new Set(this.marcadas.concat(ids))];
        return;
      }
      const quitar = new Set(ids);
      this.marcadas = this.marcadas.filter((id) => !quitar.has(id));
    },

    etiquetaBorrarMarcadas() {
      const n = this.marcadas.length;
      return "Borrar " + n + (n === 1 ? " usuario" : " usuarios");
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
        this.podarMarcadas();
        this.ajustarPagina();
      } catch (err) {
        this.error = err.message || "No se ha podido guardar.";
      }
    },

    async borrar(usuario) {
      if (!usuario || this.esPropio(usuario.id)) return;
      if (!window.confirm("¿Borrar a " + usuario.nombre + "?")) return;
      await this._borrarUsuarios([usuario]);
    },

    async borrarMarcadas() {
      if (this.borrando || !this.marcadas.length) return;
      const elegidas = this.usuarios.filter((u) => this.marcadas.includes(u.id) && !this.esPropio(u.id));
      if (!elegidas.length) return;
      const n = elegidas.length;
      const texto =
        n === 1 ? "¿Borrar a " + elegidas[0].nombre + "?" : "¿Borrar a " + n + " usuarios?";
      if (!window.confirm(texto)) return;
      await this._borrarUsuarios(elegidas);
    },

    async _borrarUsuarios(lista) {
      this.borrando = true;
      this.error = "";
      const fallos = [];
      try {
        for (const usuario of lista) {
          if (this.esPropio(usuario.id)) continue;
          try {
            await GestorApi.borrar("/usuarios/" + usuario.id);
            this.marcadas = this.marcadas.filter((id) => id !== usuario.id);
            if (this.editandoId === usuario.id) this.cerrarModal();
          } catch (err) {
            fallos.push(usuario.nombre + ": " + (err.message || "no se ha podido borrar"));
          }
        }
        this.usuarios = await GestorApi.getJson("/usuarios");
        this.podarMarcadas();
        this.ajustarPagina();
        if (fallos.length) this.error = fallos.join(" · ");
      } catch (err) {
        this.error = err.message || "No se han podido borrar los usuarios.";
      } finally {
        this.borrando = false;
      }
    },
  };
}

function vacio() {
  return { nombre: "", email: "", rol: "jefe_obra", password: "" };
}
