function gestionObras() {
  return {
    screen: "obras",
    up: "done",
    open: 0,
    ctrlOpen: 7,
    sel: null,
    filter: "all",
    vista: null,
    estado: null,
    error: "",
    lectura: null,
    altaLectura: false,
    ficheroNombre: "",
    sobreDrop: false,
    lineasDoc: ["60%", "90%", "85%", "40%", "95%", "70%", "88%", "55%", "92%", "80%", "35%", "75%"],

    async init() {
      try {
        const data = await GestorApi.getJson("/vista/obra");
        this.vista = data;
        this.estado = data.estado;
      } catch (err) {
        this.error = err.message || "No se ha podido cargar la obra";
      }
    },

    async sincronizar() {
      this.error = "";
      try {
        const data = await GestorApi.postJson("/vista/obra", this.estado);
        this.vista = data;
        this.estado = data.estado;
      } catch (err) {
        this.error = err.message || "No se ha podido recalcular";
      }
    },

    get enObra() {
      return this.screen !== "obras";
    },

    navActivo(id) {
      if (id === "facturas") return this.screen === "facturas";
      if (id === "obras") return ["obras", "presupuesto", "contratos", "control"].includes(this.screen);
      return false;
    },

    ir(screen) {
      this.screen = screen;
    },

    async nuevaObra() {
      this.lectura = null;
      this.altaLectura = true;
      this.ficheroNombre = "";
      this.estado.revisados = this.estado.revisados.map(() => false);
      this.screen = "presupuesto";
      this.up = "empty";
      this.open = 0;
      await this.sincronizar();
    },

    async abrirObra(obra) {
      if (obra.destino === "presupuesto-parcial") {
        this.lectura = null;
        this.altaLectura = false;
        this.estado.revisados = [true, true, true, false, false, false, false, false];
        this.screen = "presupuesto";
        this.up = "done";
        this.open = 3;
        await this.sincronizar();
        return;
      }
      this.altaLectura = false;
      this.screen = "control";
      this.ctrlOpen = 7;
    },

    elegirPresupuesto(event) {
      const fichero = event.target.files && event.target.files[0];
      event.target.value = "";
      if (fichero) this.leerPresupuesto(fichero);
    },

    soltarPresupuesto(event) {
      this.sobreDrop = false;
      const fichero = event.dataTransfer.files && event.dataTransfer.files[0];
      if (fichero) this.leerPresupuesto(fichero);
    },

    async leerPresupuesto(fichero) {
      this.screen = "presupuesto";
      this.up = "reading";
      this.ficheroNombre = fichero.name;
      this.lectura = null;
      this.error = "";
      const fd = new FormData();
      fd.append("fichero", fichero, fichero.name);
      try {
        const alta = await GestorApi.postForm("/proyectos/importar-presupuesto", fd);
        const doc = await GestorApi.getJson(
          "/revisiones/documento?tipo=presupuesto&documento_id=" + alta.presupuesto_id
        );
        this.lectura = this._armarLectura(alta, doc, fichero.name);
        this.open = 0;
        this.up = "done";
      } catch (err) {
        this.error = err.message || "No se ha podido leer el presupuesto";
        this.up = "empty";
      }
    },

    _armarLectura(alta, doc, nombre) {
      const apartados = (doc.arbol || []).map((nodo) => this._apartadoLeido(nodo));
      const avisos = [];
      if (alta.es_escaneado) {
        avisos.push(
          "El documento es un escaneo: ha pasado por OCR y la lectura es poco fiable. Revisa cada apartado."
        );
      }
      if (alta.anotaciones_manuscritas_detectadas) {
        avisos.push(
          "Hay anotaciones manuscritas. El valor escrito a mano prevalece sobre el impreso; confírmalo al revisar."
        );
      }
      if (!alta.sumas_cuadran) {
        avisos.push("Las sumas de los apartados no cuadran con el total del documento.");
      }
      if (!alta.es_escaneado && !alta.anotaciones_manuscritas_detectadas && alta.sumas_cuadran) {
        avisos.push("Revisa los apartados antes de confirmar. Hasta entonces el presupuesto sigue pendiente.");
      }
      return {
        proyectoId: alta.proyecto_id,
        presupuestoId: alta.presupuesto_id,
        nombre: doc.proyecto_nombre,
        fichero: nombre,
        esEscaneado: alta.es_escaneado,
        total: alta.total_leido,
        arbol: doc.arbol || [],
        apartados,
        avisos,
      };
    },

    _apartadoLeido(nodo) {
      const hijos = nodo.hijos || [];
      const filas = hijos.length ? hijos : [nodo];
      const manuscrito = filas.some((fila) => fila.tiene_anotacion_manual) || nodo.tiene_anotacion_manual;
      const partidas = filas.map((fila) => ({
        codigo: fila.codigo,
        descripcion: fila.descripcion,
        unidad: fila.unidad || "—",
        medicion: fila.cantidad == null ? "—" : String(fila.cantidad),
        precio: fila.precio_unitario == null ? "—" : GestorApi.euro(fila.precio_unitario),
        importe: GestorApi.euro(fila.importe_presupuestado),
        duda: fila.tiene_anotacion_manual ? "Anotación manuscrita" : null,
      }));
      let resumen = hijos.length
        ? hijos.length + " partidas"
        : "Cierra por apartado, sin precio unitario";
      if (manuscrito) resumen += " · anotación manuscrita";
      return {
        id: nodo.id,
        codigo: nodo.codigo,
        nombre: nodo.descripcion,
        importe: GestorApi.euro(nodo.importe_presupuestado),
        resumen,
        hay_dudas: manuscrito,
        revisado: false,
        partidas,
      };
    },

    get panelPresupuesto() {
      if (this.lectura) return this._panelLectura();
      if (!this.vista) return null;
      const p = this.vista.presupuesto;
      return {
        ...p,
        fichero: "Presupuesto_Lacasa_firmado.pdf",
        metaFichero: "Ejemplo de maqueta · 18 págs.",
        aviso:
          p.n_dudas +
          " partidas con unidad o medición poco clara en el documento. Compruébalas antes de confirmar.",
        ayudaBoton: "Se activa al revisar los 8 apartados",
        etiquetaBoton: "Crear proyecto",
      };
    },

    _panelLectura() {
      const apartados = this.lectura.apartados;
      const n = apartados.length;
      const nRev = apartados.filter((ap) => ap.revisado).length;
      const nPartidas = apartados.reduce((suma, ap) => suma + ap.partidas.length, 0);
      return {
        revisados: nRev + "/" + n,
        revisados_pct: n ? Math.round((nRev / n) * 100) + "%" : "0%",
        n_partidas: nPartidas,
        total: this.lectura.total == null ? "—" : GestorApi.euro(this.lectura.total),
        falta_revisar: nRev < n || n === 0,
        apartados,
        fichero: this.lectura.fichero,
        metaFichero: this.lectura.esEscaneado
          ? "Escaneado · pendiente de revisión"
          : "Pendiente de revisión",
        aviso: this.lectura.avisos.join(" "),
        ayudaBoton: "Se activa al revisar todos los apartados",
        etiquetaBoton: "Confirmar presupuesto",
      };
    },

    async revisar(indice) {
      if (this.lectura) {
        const ap = this.lectura.apartados[indice];
        ap.revisado = !ap.revisado;
        this.open = ap.revisado
          ? this.lectura.apartados.findIndex((fila) => !fila.revisado)
          : indice;
        return;
      }
      const marcas = this.estado.revisados.slice();
      marcas[indice] = !marcas[indice];
      this.estado.revisados = marcas;
      if (marcas[indice]) {
        this.open = marcas.findIndex((marca) => !marca);
      } else {
        this.open = indice;
      }
      await this.sincronizar();
    },

    async confirmarPresupuesto() {
      if (!this.lectura) {
        this.ir("contratos");
        return;
      }
      if (this.panelPresupuesto.falta_revisar) return;
      const tareas = [];
      const visitar = (nodo) => {
        tareas.push({
          id: nodo.id,
          codigo: nodo.codigo,
          descripcion: nodo.descripcion,
          capitulo: nodo.capitulo,
          unidad: nodo.unidad,
          cantidad: nodo.cantidad,
          precio_unitario: nodo.precio_unitario,
          importe_presupuestado: nodo.importe_presupuestado,
          estado_revision: nodo.tiene_anotacion_manual ? "confirmada" : "revisada",
          anotacion_confirmada: Boolean(nodo.tiene_anotacion_manual),
        });
        (nodo.hijos || []).forEach(visitar);
      };
      this.lectura.arbol.forEach(visitar);
      this.error = "";
      try {
        await GestorApi.postJson("/revisiones/confirmar", {
          tipo: "presupuesto",
          documento_id: this.lectura.presupuestoId,
          tareas,
        });
        this.up = "confirmado";
        this.altaLectura = false;
      } catch (err) {
        this.error = err.message || "No se ha podido confirmar la lectura";
      }
    },

    async cambiarApartado(id, valor) {
      const fila = this.estado.contratos.find((c) => c.id === id);
      fila.apartado_idx = Number(valor);
      await this.sincronizar();
    },

    async asociar(id, asociado) {
      const fila = this.estado.contratos.find((c) => c.id === id);
      fila.asociado = asociado;
      await this.sincronizar();
    },

    bordeContrato(fila) {
      if (fila.asociado) return "hecho";
      if (fila.confianza < 90) return "baja";
      return "";
    },

    colorConfianza(fila) {
      return fila.confianza >= 90 ? "#1e7a34" : "#b56a00";
    },

    get filtros() {
      const todas = this.vista.facturas;
      return [
        { id: "all", etiqueta: "Todas", n: todas.length },
        { id: "bad", etiqueta: "Con incidencia", n: todas.filter((f) => f.kind !== "ok").length },
        { id: "ok", etiqueta: "Cuadran", n: todas.filter((f) => f.kind === "ok").length },
      ];
    },

    get facturasVisibles() {
      const todas = this.vista.facturas;
      if (this.filter === "bad") return todas.filter((f) => f.kind !== "ok");
      if (this.filter === "ok") return todas.filter((f) => f.kind === "ok");
      return todas;
    },

    get seleccion() {
      if (!this.sel) return null;
      return this.vista.facturas.find((f) => f.id === this.sel) || null;
    },

    async resolver(id, resolucion) {
      this.estado.resueltas = { ...this.estado.resueltas, [id]: resolucion };
      this.sel = null;
      await this.sincronizar();
    },

    irAlerta(alerta) {
      if (alerta.destino === "contratos") {
        this.screen = "contratos";
        return;
      }
      this.screen = "facturas";
      this.sel = alerta.factura_id;
      this.filter = "all";
    },
  };
}
