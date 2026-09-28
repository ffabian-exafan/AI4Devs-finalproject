function gestionObras() {
  return {
    screen: "obras",
    up: "done",
    open: 0,
    ctrlOpen: 7,
    sel: null,
    filter: "all",
    vista: null,
    proyecto: null,
    proyectoId: null,
    estado: null,
    error: "",
    cargando: true,
    proyectos: [],
    nPendientes: 0,
    lectura: null,
    lineaForm: null,
    guardandoLinea: false,
    altaLectura: false,
    ficheroNombre: "",
    leyendoContrato: false,
    sobreDrop: false,
    lineasDoc: ["60%", "90%", "85%", "40%", "95%", "70%", "88%", "55%", "92%", "80%", "35%", "75%"],

    async init() {
      await this.cargarObras();
    },

    async cargarObras() {
      this.cargando = true;
      this.error = "";
      try {
        const [proyectos, pendientes] = await Promise.all([
          GestorApi.getJson("/proyectos"),
          GestorApi.getJson("/revisiones/pendientes"),
        ]);
        this.proyectos = proyectos;
        this.nPendientes = pendientes.length;
      } catch (err) {
        this.error = err.message || "No se han podido cargar las obras";
      } finally {
        this.cargando = false;
      }
    },

    euro(valor) {
      return GestorApi.euro(valor);
    },

    porcentajeObra(obra) {
      const base = Number(obra.presupuestado) || 0;
      if (!base) return "0%";
      const pct = Math.round(((Number(obra.facturado) || 0) / base) * 100);
      return pct + "%";
    },

    tonoEstado(estado) {
      if (estado === "pendiente_revision") return "warning";
      if (estado === "en_curso") return "success";
      return "neutral";
    },

    etiquetaEstado(estado) {
      if (estado === "pendiente_revision") return "Pendiente de revisión";
      if (estado === "en_curso") return "En curso";
      return estado;
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

    get resumenObras() {
      const n = this.proyectos.length;
      const pend = this.proyectos.filter((p) => p.estado === "pendiente_revision").length;
      return n + " obras · " + pend + " pendientes de revisión";
    },

    get navIncidencias() {
      if (this.vista && this.vista.facturas) {
        return this.vista.facturas.filter((f) => f.kind !== "ok").length;
      }
      return this.nPendientes;
    },

    get tituloObra() {
      if (this.proyecto) return this.proyecto.nombre;
      if (this.lectura) return this.lectura.nombre;
      return "Nueva obra";
    },

    get miga() {
      if (this.proyecto) return "#" + this.proyecto.id;
      if (this.lectura) return "Lectura";
      return "Nueva";
    },

    get subtituloObra() {
      if (this.altaLectura && !this.lectura && !this.proyecto) {
        return "Sube el presupuesto para crear la obra";
      }
      if (this.lectura && this.up === "done") {
        return this.lectura.fichero + " · pendiente de revisión";
      }
      if (this.proyecto) {
        return this.proyecto.tipo + " · " + this.etiquetaEstado(this.proyecto.estado);
      }
      return "";
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
      if (screen === "obras") {
        this.lectura = null;
        this.altaLectura = false;
        this.proyecto = null;
        this.proyectoId = null;
        this.vista = null;
        this.up = "done";
        this.cargarObras();
      }
    },

    nuevaObra() {
      this.lectura = null;
      this.proyecto = null;
      this.proyectoId = null;
      this.vista = null;
      this.altaLectura = true;
      this.ficheroNombre = "";
      this.screen = "presupuesto";
      this.up = "empty";
      this.open = 0;
      this.error = "";
    },

    async abrirObra(obra) {
      this.error = "";
      this.altaLectura = false;
      this.lectura = null;
      this.proyectoId = obra.id;
      this.screen = "presupuesto";
      this.up = "done";
      this.open = 0;
      this.cargando = true;
      try {
        await this._cargarVistaProyecto(obra.id);
        const pendientes = await GestorApi.getJson("/revisiones/pendientes");
        const doc = pendientes.find(
          (item) => item.proyecto_id === obra.id && item.tipo === "presupuesto"
        );
        if (doc) {
          const arbol = await GestorApi.getJson(
            "/revisiones/documento?tipo=presupuesto&documento_id=" + doc.documento_id
          );
          this.lectura = this._armarLectura(
            {
              proyecto_id: obra.id,
              presupuesto_id: doc.documento_id,
              es_escaneado: false,
              anotaciones_manuscritas_detectadas: doc.anotaciones_manuales > 0,
              sumas_cuadran: true,
              total_leido: obra.presupuestado,
            },
            arbol,
            doc.fichero_origen
          );
        }
      } catch (err) {
        this.error = err.message || "No se ha podido abrir la obra";
        this.screen = "obras";
      } finally {
        this.cargando = false;
      }
    },

    async borrarObra(obra) {
      if (!obra || !obra.id) return;
      const nombre = obra.nombre || "#" + obra.id;
      if (!window.confirm("¿Borrar la obra «" + nombre + "»? Se eliminan su presupuesto, contratos y facturas.")) {
        return;
      }
      this.error = "";
      try {
        await GestorApi.borrar("/proyectos/" + obra.id);
        if (this.proyectoId === obra.id) {
          this.proyecto = null;
          this.proyectoId = null;
          this.vista = null;
          this.lectura = null;
          this.altaLectura = false;
          this.screen = "obras";
          this.up = "done";
        }
        await this.cargarObras();
      } catch (err) {
        this.error = err.message || "No se ha podido borrar la obra";
      }
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
        this.proyectoId = alta.proyecto_id;
        this.open = 0;
        this.up = "done";
        await this._cargarVistaProyecto(alta.proyecto_id);
      } catch (err) {
        this.error = err.message || "No se ha podido leer el presupuesto";
        this.up = "empty";
      }
    },

    async _cargarVistaProyecto(proyectoId) {
      const [proyecto, facturas, control] = await Promise.all([
        GestorApi.getJson("/proyectos/" + proyectoId),
        GestorApi.getJson("/facturas?proyecto_id=" + proyectoId),
        GestorApi.getJson("/proyectos/" + proyectoId + "/control-economico"),
      ]);
      this.proyecto = proyecto;
      this.proyectoId = proyecto.id;
      this.vista = this._armarVista(proyecto, facturas, control);
      const fila = this.proyectos.find((p) => p.id === proyecto.id);
      if (fila) {
        fila.presupuestado = proyecto.presupuestado;
        fila.facturado = proyecto.facturado;
        fila.estado = proyecto.estado;
      }
    },

    _armarVista(proyecto, facturas, control) {
      const euro = (valor) => GestorApi.euro(valor);
      const todos = proyecto.apartados || [];
      const descuentos = todos.filter((ap) => this._esDescuento(ap));
      const gestiones = todos.filter((ap) => !this._esDescuento(ap) && this._esGestion(ap));
      const apartados = todos.filter((ap) => !this._esDescuento(ap) && !this._esGestion(ap));
      const opciones = [{ valor: "", etiqueta: "Elige apartado" }].concat(
        apartados.map((ap) => ({
          valor: String(ap.id),
          etiqueta: ap.codigo + " · " + ap.descripcion,
        }))
      );
      const filas = (proyecto.contratos || []).map((contrato) => {
        const sugerencia = (contrato.sugerencias || [])[0];
        const apartadoId = contrato.tarea_apartado_id || (sugerencia && sugerencia.tarea_id) || "";
        const apartado = apartados.find((ap) => ap.id === Number(apartadoId));
        const presupuestado = apartado ? Number(apartado.importe_presupuestado) || 0 : 0;
        const contratado = Number(contrato.precio_total) || 0;
        const diff = contratado - presupuestado;
        return {
          id: contrato.id,
          gremio: contrato.contratista_nombre,
          archivo: contrato.contratista_nif,
          importe: euro(contrato.precio_total),
          apartado_idx: apartadoId === "" ? "" : String(apartadoId),
          confianza: contrato.tarea_apartado_id
            ? 100
            : sugerencia
              ? Math.round(Number(sugerencia.confianza) * 100)
              : 0,
          motivo: contrato.tarea_apartado_id
            ? "Enlace confirmado"
            : sugerencia
              ? sugerencia.motivo
              : "Sin sugerencia automática",
          aviso: null,
          hay_aviso: false,
          presupuestado: apartado ? euro(apartado.importe_presupuestado) : "—",
          diferencia: apartado ? euro(diff) : "—",
          supera: apartado ? diff > 0 : false,
          asociado: Boolean(contrato.tarea_apartado_id),
        };
      });
      const pendientesContrato = filas.filter((fila) => !fila.asociado).length;
      const sinApartado = apartados.filter((ap) => !(ap.contratos || []).length).length;
      const facturasVista = (facturas || []).map((factura) => ({
        id: factura.id,
        proveedor: factura.contratista_nombre,
        numero: factura.numero,
        fecha: factura.fecha_emision || "—",
        apartado: factura.contrato_id ? "Contrato #" + factura.contrato_id : "Sin contrato",
        importe: euro(factura.total),
        kind: factura.estado_revision === "confirmada" ? "ok" : "bad",
        estado: factura.estado_revision === "confirmada" ? "Confirmada" : "Pendiente",
        tono: factura.estado_revision === "confirmada" ? "success" : "warning",
        diferencia: "",
        es_duplicado: false,
        aviso_duplicado: null,
        desviacion: factura.estado_revision === "confirmada" ? "Confirmada" : "Pendiente de revisión",
        desviacion_negativa: false,
        acciones:
          factura.estado_revision === "confirmada"
            ? []
            : [{ etiqueta: "Confirmar factura", variante: "primary", resolucion: "Validada" }],
        lineas: [],
      }));
      const incidencias = facturasVista.filter((fila) => fila.kind !== "ok").length;
      const presTotal = todos.reduce(
        (suma, ap) => suma + (Number(ap.importe_presupuestado) || 0),
        0
      );
      const factTotal = (facturas || [])
        .filter((factura) => factura.estado_revision === "confirmada")
        .reduce((suma, factura) => suma + (Number(factura.total) || 0), 0);
      const contrTotal = (proyecto.contratos || []).reduce(
        (suma, contrato) => suma + (Number(contrato.precio_total) || 0),
        0
      );
      const filasControl = apartados.concat(gestiones).map((ap) => {
        const contratado = (ap.contratos || []).reduce(
          (suma, contrato) => suma + (Number(contrato.contratado) || 0),
          0
        );
        const facturado = (ap.contratos || []).reduce(
          (suma, contrato) => suma + (Number(contrato.facturado) || 0),
          0
        );
        const pres = Number(ap.importe_presupuestado) || 0;
        const escala = Math.max(pres, contratado, facturado, 1);
        const pct = (valor) => Math.round((valor / escala) * 100) + "%";
        return {
          codigo: ap.codigo,
          nombre: ap.descripcion,
          facturado: euro(facturado),
          presupuestado: euro(pres),
          ancho_presupuesto: pct(pres),
          ancho_contratado: pct(contratado),
          ancho_facturado: pct(facturado),
          desviacion: euro(facturado - pres),
          alerta: facturado > pres && pres > 0,
          partidas: (ap.subapartados || []).map((sub) => ({
            codigo: sub.codigo,
            descripcion: sub.descripcion,
            presupuesto: Number(sub.importe_presupuestado) ? euro(sub.importe_presupuestado) : "—",
            medicion: "—",
            facturado: "—",
            medicion_facturada: "—",
            desviacion: "—",
            alerta: false,
          })),
        };
      });
      const alertas = [];
      filas
        .filter((fila) => !fila.asociado)
        .forEach((fila) => {
          alertas.push({
            id: "c" + fila.id,
            tipo: "Contrato",
            tono: "warning",
            importe: fila.importe,
            titulo: fila.gremio,
            texto: "Sin apartado asociado",
            destino: "contratos",
            factura_id: null,
          });
        });
      facturasVista
        .filter((fila) => fila.kind !== "ok")
        .forEach((fila) => {
          alertas.push({
            id: "f" + fila.id,
            tipo: "Factura",
            tono: "error",
            importe: fila.importe,
            titulo: fila.proveedor,
            texto: fila.numero + " · pendiente de confirmar",
            destino: "facturas",
            factura_id: fila.id,
          });
        });
      const naves = (control.por_nave || []).length;
      return {
        pasos: [
          {
            id: "presupuesto",
            etiqueta: "Presupuesto",
            detalle: apartados.length + " apartados",
            completo: proyecto.estado !== "pendiente_revision",
          },
          {
            id: "contratos",
            etiqueta: "Contratos",
            detalle: filas.length - pendientesContrato + "/" + filas.length + " asociados",
            completo: filas.length > 0 && pendientesContrato === 0,
          },
          {
            id: "facturas",
            etiqueta: "Facturas",
            detalle: facturasVista.length + " leídas · " + incidencias + " pendientes",
            completo: facturasVista.length > 0 && incidencias === 0,
          },
          {
            id: "control",
            etiqueta: "Control de desviaciones",
            detalle: naves ? naves + " naves" : "Por apartado",
            completo: false,
          },
        ],
        presupuesto: {
          revisados: apartados.length + "/" + apartados.length,
          revisados_pct: "100%",
          n_partidas: apartados.reduce((suma, ap) => suma + 1 + (ap.subapartados || []).length, 0),
          total: euro(presTotal),
          falta_revisar: false,
          apartados: apartados.map((ap) => ({
            id: ap.id,
            codigo: ap.codigo,
            nombre: ap.descripcion,
            importe: euro(ap.importe_presupuestado),
            resumen: (ap.subapartados || []).length
              ? (ap.subapartados || []).length + " subapartados"
              : "Cierra por apartado",
            hay_dudas: ap.estado_revision === "pendiente",
            revisado: ap.estado_revision !== "pendiente",
            partidas: (ap.subapartados || []).length
              ? ap.subapartados.map((sub) => ({
                  id: sub.id,
                  codigo: sub.codigo,
                  descripcion: sub.descripcion,
                  unidad: "—",
                  medicion: "—",
                  precio: "—",
                  importe: Number(sub.importe_presupuestado) ? euro(sub.importe_presupuestado) : "—",
                  duda: sub.estado_revision === "pendiente" ? "Pendiente" : null,
                }))
              : [
                  {
                    id: ap.id,
                    codigo: ap.codigo,
                    descripcion: ap.descripcion,
                    unidad: "—",
                    medicion: "—",
                    precio: "—",
                    importe: euro(ap.importe_presupuestado),
                    duda: null,
                  },
                ],
          })),
          gestiones: gestiones.map((ap) => this._filaGestion(ap)),
          descuentos: descuentos.map((ap) => ({
            id: ap.id,
            codigo: ap.codigo,
            descripcion: ap.descripcion,
            importe: euro(ap.importe_presupuestado),
            manuscrito: false,
          })),
          fichero: "Presupuesto del proyecto",
          metaFichero: this.etiquetaEstado(proyecto.estado),
          aviso: "Revisa apartados, asocia contratos y confirma las facturas. Hasta confirmar, nada cuenta como cerrado.",
          ayudaBoton: "Pasa a contratos cuando el presupuesto esté revisado",
          etiquetaBoton: "Seguir con contratos",
        },
        contratos: {
          pendientes: pendientesContrato,
          sin_contrato: sinApartado + (sinApartado === 1 ? " apartado" : " apartados"),
          hay_sin_contrato: sinApartado > 0,
          opciones,
          filas,
        },
        facturas: facturasVista,
        control: {
          kpis: [
            {
              etiqueta: "Presupuestado",
              valor: euro(presTotal),
              detalle: "Apartados del presupuesto",
              color: "#444242",
            },
            {
              etiqueta: "Contratado",
              valor: euro(contrTotal),
              detalle: (proyecto.contratos || []).length + " contratos",
              color: "#6e2094",
            },
            {
              etiqueta: "Facturado",
              valor: euro(factTotal),
              detalle: "Solo facturas confirmadas",
              color: "#6e2094",
            },
            {
              etiqueta: "Desviación",
              valor: euro(factTotal - presTotal),
              detalle: "Facturado frente a presupuesto",
              color: factTotal > presTotal ? "#a52a17" : "#1e7a34",
            },
          ],
          filas: filasControl,
          alertas,
        },
      };
    },

    _esDescuento(nodo) {
      const texto = ((nodo.codigo || "") + " " + (nodo.descripcion || "")).toLowerCase();
      return texto.includes("descuento");
    },

    _esGestion(nodo) {
      const texto = ((nodo.descripcion || "") + " " + (nodo.nombre || "")).toLowerCase();
      return texto.includes("gestión") || texto.includes("gestion");
    },

    _filaGestion(nodo) {
      const hijos = nodo.hijos || nodo.subapartados || [];
      const nota = hijos
        .map((hijo) => hijo.descripcion)
        .filter(Boolean)
        .join(" ");
      return {
        id: nodo.id,
        codigo: nodo.codigo,
        descripcion: nodo.descripcion || nodo.nombre,
        nota,
        importe: GestorApi.euro(nodo.importe_presupuestado),
      };
    },

    _armarLectura(alta, doc, nombre) {
      const raices = doc.arbol || [];
      const nodosDescuento = raices.filter((nodo) => this._esDescuento(nodo));
      const nodosGestion = raices.filter((nodo) => !this._esDescuento(nodo) && this._esGestion(nodo));
      const apartados = raices
        .filter((nodo) => !this._esDescuento(nodo) && !this._esGestion(nodo))
        .map((nodo) => this._apartadoLeido(nodo));
      const gestiones = nodosGestion.map((nodo) => this._filaGestion(nodo));
      const descuentos = nodosDescuento.map((nodo) => ({
        id: nodo.id,
        codigo: nodo.codigo,
        descripcion: nodo.descripcion,
        importe: GestorApi.euro(nodo.importe_presupuestado),
        manuscrito: !!nodo.tiene_anotacion_manual,
      }));
      const neto = raices.reduce(
        (suma, nodo) => suma + (Number(nodo.importe_presupuestado) || 0),
        0
      );
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
      if (nodosDescuento.some((nodo) => nodo.tiene_anotacion_manual)) {
        avisos.push(
          "Hay un descuento manuscrito al final. Prevalece sobre el impreso; confírmalo al revisar."
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
        total: nodosDescuento.length ? neto : alta.total_leido,
        arbol: doc.arbol || [],
        apartados,
        gestiones,
        descuentos,
        avisos,
      };
    },

    _apartadoLeido(nodo) {
      const hijos = nodo.hijos || [];
      const filas = hijos.length ? hijos : [nodo];
      const manuscrito = filas.some((fila) => fila.tiene_anotacion_manual) || nodo.tiene_anotacion_manual;
      const partidas = filas.map((fila) => ({
        id: fila.id,
        codigo: fila.codigo,
        descripcion: fila.descripcion,
        unidad: fila.unidad || "—",
        medicion: fila.cantidad == null ? "—" : String(fila.cantidad),
        precio: fila.precio_unitario == null ? "—" : GestorApi.euro(fila.precio_unitario),
        importe:
          fila.nivel === "subapartado" && !Number(fila.importe_presupuestado)
            ? "—"
            : GestorApi.euro(fila.importe_presupuestado),
        duda: fila.tiene_anotacion_manual ? "Anotación manuscrita" : null,
      }));
      let resumen = hijos.length
        ? hijos.length + " subapartados"
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
      if (!this.vista || !this.vista.presupuesto) return null;
      return this.vista.presupuesto;
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
        gestiones: this.lectura.gestiones || [],
        descuentos: this.lectura.descuentos || [],
        ayudaBoton: "Se activa al revisar todos los apartados",
        etiquetaBoton: "Confirmar presupuesto",
      };
    },

    async revisar(indice) {
      if (!this.lectura && this.vista && this.vista.presupuesto) {
        const ap = this.vista.presupuesto.apartados[indice];
        if (!ap) return;
        ap.revisado = !ap.revisado;
        return;
      }
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

    nuevaLinea() {
      this.error = "";
      this.lineaForm = { id: null, codigo: "", descripcion: "", importe: "" };
    },

    editarLinea(linea) {
      if (!linea || !linea.id) return;
      this.error = "";
      this.lineaForm = {
        id: linea.id,
        codigo: linea.codigo || "",
        descripcion: linea.nombre || linea.descripcion || "",
        importe: this._importePlano(linea.importe),
      };
    },

    _importePlano(texto) {
      let s = String(texto ?? "").trim();
      if (!s || s === "—") return "";
      const neg = /[-−]/.test(s);
      s = s.replace(/[^\d,.]/g, "");
      if (!s) return "";
      if (s.includes(",")) s = s.replace(/\./g, "").replace(",", ".");
      const n = Number(s);
      if (Number.isNaN(n)) return "";
      return String(neg ? -Math.abs(n) : n);
    },

    async guardarLinea() {
      if (!this.lineaForm || !this.proyectoId || this.guardandoLinea) return;
      const codigo = (this.lineaForm.codigo || "").trim();
      const descripcion = (this.lineaForm.descripcion || "").trim();
      const importe = Number(this._importePlano(this.lineaForm.importe));
      if (!codigo || !descripcion || Number.isNaN(importe)) {
        this.error = "Código, descripción e importe son obligatorios";
        return;
      }
      const body = {
        codigo,
        descripcion,
        importe_presupuestado: importe,
      };
      const url = this.lineaForm.id
        ? "/proyectos/" + this.proyectoId + "/lineas/" + this.lineaForm.id
        : "/proyectos/" + this.proyectoId + "/lineas";
      this.error = "";
      this.guardandoLinea = true;
      try {
        if (this.lineaForm.id) await GestorApi.patchJson(url, body);
        else await GestorApi.postJson(url, body);
        this.lineaForm = null;
        await this._refrescarTrasLinea();
      } catch (err) {
        this.error = err.message || "No se ha podido guardar la línea";
      } finally {
        this.guardandoLinea = false;
      }
    },

    async borrarLinea(linea) {
      if (!linea || !linea.id || !this.proyectoId) return;
      const nombre = linea.nombre || linea.descripcion || linea.codigo;
      if (!window.confirm("¿Borrar la línea «" + nombre + "»?")) return;
      this.error = "";
      try {
        await GestorApi.borrar("/proyectos/" + this.proyectoId + "/lineas/" + linea.id);
        if (this.lineaForm && this.lineaForm.id === linea.id) this.lineaForm = null;
        await this._refrescarTrasLinea();
      } catch (err) {
        this.error = err.message || "No se ha podido borrar la línea";
      }
    },

    async _refrescarTrasLinea() {
      const id = this.proyectoId;
      if (!id) return;
      const revisados = new Set(
        ((this.lectura && this.lectura.apartados) || [])
          .filter((ap) => ap.revisado)
          .map((ap) => ap.id)
      );
      const esEscaneado = Boolean(this.lectura && this.lectura.esEscaneado);
      await this._cargarVistaProyecto(id);
      const pendientes = await GestorApi.getJson("/revisiones/pendientes");
      this.nPendientes = pendientes.length;
      const docPend = pendientes.find(
        (item) => item.proyecto_id === id && item.tipo === "presupuesto"
      );
      if (!docPend) {
        this.lectura = null;
        return;
      }
      const doc = await GestorApi.getJson(
        "/revisiones/documento?tipo=presupuesto&documento_id=" + docPend.documento_id
      );
      this.lectura = this._armarLectura(
        {
          proyecto_id: id,
          presupuesto_id: docPend.documento_id,
          es_escaneado: esEscaneado,
          anotaciones_manuscritas_detectadas: docPend.anotaciones_manuales > 0,
          sumas_cuadran: true,
          total_leido: this.proyecto ? this.proyecto.presupuestado : null,
        },
        doc,
        doc.fichero_origen
      );
      this.lectura.apartados.forEach((ap) => {
        if (revisados.has(ap.id)) ap.revisado = true;
      });
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
        const proyectoId = this.lectura.proyectoId;
        await this._cargarVistaProyecto(proyectoId);
        this.lectura = null;
        this.altaLectura = false;
        this.up = "done";
        this.screen = "contratos";
      } catch (err) {
        this.error = err.message || "No se ha podido confirmar la lectura";
      }
    },

    async cambiarApartado(id, valor) {
      if (this.proyectoId && this.vista) {
        const fila = this.vista.contratos.filas.find((c) => c.id === id);
        if (fila) fila.apartado_idx = String(valor);
        return;
      }
      const fila = this.estado.contratos.find((c) => c.id === id);
      fila.apartado_idx = Number(valor);
      await this.sincronizar();
    },

    async asociar(id, asociado) {
      if (this.proyectoId && this.vista) {
        const fila = this.vista.contratos.filas.find((c) => c.id === id);
        if (!fila) return;
        if (!asociado) {
          this.error = "El enlace confirmado se mantiene. Elige el apartado antes de asociar.";
          return;
        }
        const tareaId = Number(fila.apartado_idx);
        if (!tareaId) {
          this.error = "Elige un apartado antes de asociar.";
          return;
        }
        this.error = "";
        try {
          await GestorApi.postJson(
            "/proyectos/" + this.proyectoId + "/contratos/" + id + "/enlazar-apartado",
            { tarea_apartado_id: tareaId }
          );
          await this._cargarVistaProyecto(this.proyectoId);
        } catch (err) {
          this.error = err.message || "No se ha podido asociar el contrato";
        }
        return;
      }
      const fila = this.estado.contratos.find((c) => c.id === id);
      fila.asociado = asociado;
      await this.sincronizar();
    },

    elegirContrato(event) {
      const fichero = event.target.files && event.target.files[0];
      event.target.value = "";
      if (fichero) this.leerContrato(fichero);
    },

    elegirFactura(event) {
      const fichero = event.target.files && event.target.files[0];
      event.target.value = "";
      if (fichero) this.leerFactura(fichero);
    },

    async leerContrato(fichero) {
      if (!this.proyectoId) {
        this.error = "Abre una obra antes de subir contratos.";
        return;
      }
      this.error = "";
      this.ficheroNombre = fichero.name;
      this.leyendoContrato = true;
      this.screen = "contratos";
      const fd = new FormData();
      fd.append("fichero", fichero, fichero.name);
      try {
        await GestorApi.postForm("/proyectos/" + this.proyectoId + "/importar-contrato", fd);
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.error = err.message || "No se ha podido leer el contrato";
      } finally {
        this.leyendoContrato = false;
      }
    },

    async leerFactura(fichero) {
      if (!this.proyectoId) {
        this.error = "Abre una obra antes de subir facturas.";
        return;
      }
      this.error = "";
      const fd = new FormData();
      fd.append("proyecto_id", String(this.proyectoId));
      fd.append("fichero", fichero, fichero.name);
      try {
        const alta = await GestorApi.postForm("/facturas", fd);
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "facturas";
        await this.seleccionarFactura(alta.factura_id);
      } catch (err) {
        this.error = err.message || "No se ha podido leer la factura";
      }
    },

    async seleccionarFactura(id) {
      if (this.sel === id) {
        this.sel = null;
        return;
      }
      this.sel = id;
      if (!this.vista) return;
      try {
        const detalle = await GestorApi.getJson("/facturas/" + id);
        this.vista.facturas = this.vista.facturas.map((fila) => {
          if (String(fila.id) !== String(id)) return fila;
          return {
            ...fila,
            lineas: (detalle.lineas || []).map((linea) => ({
              codigo: String(linea.id),
              descripcion: linea.descripcion,
              importe: GestorApi.euro(linea.importe),
              facturado: GestorApi.euro(linea.importe),
              presupuesto: "—",
              acumulado: "—",
              mala: false,
              nota: null,
            })),
          };
        });
      } catch (err) {
        this.error = err.message || "No se ha podido abrir la factura";
      }
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
      if (this.proyectoId) {
        if (resolucion !== "Validada") {
          this.error = "Para que la factura cuente hay que confirmarla.";
          return;
        }
        this.error = "";
        try {
          const detalle = await GestorApi.getJson("/facturas/" + id);
          await GestorApi.postJson("/facturas/" + id + "/confirmar", {
            numero: detalle.numero,
            fecha_emision: detalle.fecha_emision,
            base_imponible: detalle.base_imponible,
            iva: detalle.iva,
            irpf: detalle.irpf,
            retencion_garantia: detalle.retencion_garantia,
            total: detalle.total,
            tipo: detalle.tipo,
            contrato_id: detalle.contrato_id,
            lineas: (detalle.lineas || []).map((linea) => ({
              id: linea.id,
              descripcion: linea.descripcion,
              importe: linea.importe,
            })),
          });
          this.sel = null;
          await this._cargarVistaProyecto(this.proyectoId);
        } catch (err) {
          this.error = err.message || "No se ha podido confirmar la factura";
        }
        return;
      }
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
