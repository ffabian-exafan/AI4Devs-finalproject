function facturasApp() {
  return {
    proyectos: [],
    proyectoId: "",
    facturas: [],
    fichero: null,
    seleccionada: null,
    edicion: { lineas: [] },
    subiendo: false,
    cargandoLista: false,
    confirmando: false,
    error: "",
    mensaje: "",
    euro: (v) => GestorApi.euro(v),

    async init() {
      try {
        this.proyectos = await GestorApi.getJson("/proyectos");
        const preseleccionado = new URLSearchParams(window.location.search).get(
          "proyecto_id"
        );
        if (preseleccionado) {
          this.proyectoId = String(preseleccionado);
          await this.cargarLista();
        }
      } catch (err) {
        this.error = "No se pudieron cargar los proyectos: " + err.message;
      }
    },

    async cargarLista() {
      this.seleccionada = null;
      this.edicion = { lineas: [] };
      if (!this.proyectoId) {
        this.facturas = [];
        return;
      }
      this.cargandoLista = true;
      this.error = "";
      try {
        this.facturas = await GestorApi.getJson(
          "/facturas?proyecto_id=" + encodeURIComponent(this.proyectoId)
        );
      } catch (err) {
        this.error = err.message;
      } finally {
        this.cargandoLista = false;
      }
    },

    async subir() {
      if (!this.proyectoId || !this.fichero) return;
      this.subiendo = true;
      this.error = "";
      this.mensaje = "";
      try {
        const form = new FormData();
        form.append("proyecto_id", this.proyectoId);
        form.append("fichero", this.fichero, this.fichero.name);
        const resultado = await GestorApi.postForm("/facturas", form);
        this.mensaje =
          "Factura #" + resultado.factura_id + " leída. Revisa y confirma sus datos.";
        await this.cargarLista();
        await this.abrir(resultado.factura_id);
      } catch (err) {
        this.error = err.message;
      } finally {
        this.subiendo = false;
      }
    },

    async abrir(id) {
      this.error = "";
      try {
        this.seleccionada = await GestorApi.getJson("/facturas/" + id);
        this.edicion = {
          numero: this.seleccionada.numero,
          fecha_emision: this.seleccionada.fecha_emision || "",
          base_imponible: this.seleccionada.base_imponible,
          iva: this.seleccionada.iva,
          irpf: this.seleccionada.irpf,
          retencion_garantia: this.seleccionada.retencion_garantia,
          total: this.seleccionada.total,
          tipo: this.seleccionada.tipo,
          contrato_id: this.seleccionada.contrato_id
            ? String(this.seleccionada.contrato_id)
            : "",
          lineas: (this.seleccionada.lineas || []).map((linea) => ({
            id: linea.id,
            descripcion: linea.descripcion,
            importe: linea.importe,
          })),
        };
      } catch (err) {
        this.error = err.message;
      }
    },

    async confirmar() {
      if (!this.seleccionada) return;
      this.confirmando = true;
      this.error = "";
      this.mensaje = "";
      try {
        const payload = {
          ...this.edicion,
          contrato_id: this.edicion.contrato_id
            ? Number(this.edicion.contrato_id)
            : null,
          lineas: this.edicion.lineas.map((linea) => ({
            id: linea.id || null,
            descripcion: linea.descripcion,
            importe: linea.importe,
          })),
        };
        await GestorApi.postJson(
          "/facturas/" + this.seleccionada.id + "/confirmar",
          payload
        );
        const id = this.seleccionada.id;
        this.mensaje = "Factura confirmada. Ya cuenta en el seguimiento económico.";
        await this.cargarLista();
        await this.abrir(id);
      } catch (err) {
        this.error = err.message;
      } finally {
        this.confirmando = false;
      }
    },
  };
}
