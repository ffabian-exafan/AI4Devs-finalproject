/** Consulta de solo lectura del registro. Sin alta, edición ni borrado. */
function consultaRegistro() {
  const acciones = [
    ["confirmar_revision", "Confirmó la revisión"],
    ["confirmar_factura", "Confirmó la factura"],
    ["certificar_montaje", "Certificó el montaje"],
    ["omitir_certificacion_montaje", "Marcó que el montaje no necesita sello"],
    ["confirmar_importe_cliente", "Confirmó el importe de cliente"],
    ["confirmar_importes_cliente", "Confirmó los importes de cliente"],
    ["confirmar_solo_gestion", "Confirmó el apartado de solo gestión"],
    ["borrar_proyecto", "Borró el proyecto"],
    ["borrar_contrato", "Borró el contrato"],
    ["borrar_factura", "Borró la factura"],
    ["borrar_linea", "Borró la línea"],
    ["inicio_sesion", "Entró"],
    ["marcar_isp", "Marcó la inversión del sujeto pasivo"],
    ["quitar_isp", "Quitó la inversión del sujeto pasivo"],
    ["guardar_precio_hora", "Guardó el precio por hora"],
    ["borrar_linea_mano_obra", "Borró la línea de mano de obra"],
    ["confirmar_parte", "Confirmó el parte"],
    ["borrar_parte", "Borró el parte"],
    ["confirmar_pedido", "Confirmó el pedido"],
  ];
  const tipos = [
    ["presupuesto", "Presupuesto"],
    ["contrato", "Contrato"],
    ["factura", "Factura"],
    ["proyecto", "Proyecto"],
    ["tarea", "Tarea"],
    ["pedido", "Pedido"],
  ];

  return {
    ...sesionLateral(),
    menuCompacto: false,
    cargando: true,
    error: "",
    prohibido: false,
    items: [],
    personas: [],
    acciones: acciones,
    tipos: tipos,
    page: 1,
    pageSize: 0,
    total: 0,
    filtro: {
      usuario_id: "",
      accion: "",
      tipo_documento: "",
      dia: "",
    },

    init() {
      try {
        this.menuCompacto = localStorage.getItem("obrix-menu") === "1";
      } catch {
        this.menuCompacto = false;
      }
      this.abrir();
    },

    toggleMenu() {
      this.menuCompacto = !this.menuCompacto;
      try {
        localStorage.setItem("obrix-menu", this.menuCompacto ? "1" : "0");
      } catch {
        /* sin almacenamiento local, el menú solo cambia en esta visita */
      }
    },

    async abrir() {
      const dentro = await this.cargarYo();
      if (!dentro) return;
      await this.cargarPersonas();
      await this.cargar();
    },

    async cargarPersonas() {
      try {
        this.personas = await GestorApi.getJson("/usuarios");
      } catch {
        this.personas = [];
      }
    },

    cambiarFiltro() {
      this.page = 1;
      this.cargar();
    },

    paginaAnterior() {
      if (this.page <= 1) return;
      this.page -= 1;
      this.cargar();
    },

    paginaSiguiente() {
      if (!this.pageSize || this.page * this.pageSize >= this.total) return;
      this.page += 1;
      this.cargar();
    },

    async cargar() {
      this.cargando = true;
      this.error = "";
      const params = new URLSearchParams();
      params.set("page", String(this.page));
      if (this.filtro.usuario_id) params.set("usuario_id", this.filtro.usuario_id);
      if (this.filtro.accion) params.set("accion", this.filtro.accion);
      if (this.filtro.tipo_documento) params.set("tipo_documento", this.filtro.tipo_documento);
      if (this.filtro.dia) params.set("dia", this.filtro.dia);
      try {
        const res = await fetch("/registro?" + params.toString(), {
          credentials: "same-origin",
        });
        let cuerpo = {};
        try {
          cuerpo = await res.json();
        } catch {
          cuerpo = {};
        }
        if (res.status === 403) {
          this.prohibido = true;
          this.items = [];
          this.total = 0;
          this.error =
            typeof cuerpo.detail === "string"
              ? cuerpo.detail
              : "No se ha podido consultar el registro.";
          return;
        }
        this.prohibido = false;
        if (!res.ok) {
          this.items = [];
          this.total = 0;
          this.error =
            typeof cuerpo.detail === "string"
              ? cuerpo.detail
              : "No se ha podido consultar el registro.";
          return;
        }
        this.items = Array.isArray(cuerpo.items) ? cuerpo.items : [];
        this.page = cuerpo.page || this.page;
        this.pageSize = cuerpo.page_size || 0;
        this.total = typeof cuerpo.total === "number" ? cuerpo.total : 0;
      } catch {
        this.prohibido = false;
        this.items = [];
        this.total = 0;
        this.error = "No se ha podido consultar el registro.";
      } finally {
        this.cargando = false;
      }
    },
  };
}
