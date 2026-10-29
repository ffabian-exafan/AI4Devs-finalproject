function gestionObras() {
  return {
    screen: "obras",
    up: "done",
    open: 0,
    ctrlOpen: 7,
    subOpen: {},
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
    leyendoFactura: false,
    sobreDrop: false,
    nombreObra: "",
    contraste: null,
    contrasteIndice: 0,
    menuCompacto: false,
    lineasDoc: ["60%", "90%", "85%", "40%", "95%", "70%", "88%", "55%", "92%", "80%", "35%", "75%"],

    async init() {
      try {
        this.menuCompacto = localStorage.getItem("obrix-menu") === "1";
      } catch (_) {
        this.menuCompacto = false;
      }
      await this.cargarObras();
    },

    toggleMenu() {
      this.menuCompacto = !this.menuCompacto;
      try {
        localStorage.setItem("obrix-menu", this.menuCompacto ? "1" : "0");
      } catch (_) { }
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
        return "Sube los presupuestos Excel para crear la obra";
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
      if (id === "obras") {
        return ["obras", "presupuestos", "presupuesto", "contratos", "control"].includes(this.screen);
      }
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
        this.contraste = null;
        this.contrasteIndice = 0;
        this.up = "done";
        this.cargarObras();
        return;
      }
      if (screen === "presupuesto") this.asegurarContrasteCliente();
    },

    nuevaObra() {
      this.lectura = null;
      this.proyecto = null;
      this.proyectoId = null;
      this.vista = null;
      this.altaLectura = true;
      this.ficheroNombre = "";
      this.nombreObra = "";
      this.contraste = null;
      this.screen = "presupuestos";
      this.up = "empty";
      this.open = 0;
      this.error = "";
    },

    async abrirObra(obra) {
      this.error = "";
      this.altaLectura = false;
      this.lectura = null;
      this.contraste = null;
      this.contrasteIndice = 0;
      this.proyectoId = obra.id;
      this.screen = "presupuestos";
      this.up = "done";
      this.open = 0;
      this.cargando = true;
      try {
        await this._cargarVistaProyecto(obra.id);
        await this._cargarLecturaPresupuestos(obra.id);
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

    async elegirPresupuesto(event) {
      const lista = await this._ficherosDeInput(event);
      if (lista.length) this.leerPresupuesto(lista[0]);
    },

    async soltarPresupuesto(event) {
      this.sobreDrop = false;
      const lista = await this._ficherosSoltados(event);
      if (lista.length) this.leerPresupuesto(lista[0]);
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

    async elegirExcel(event) {
      const lista = await this._ficherosDeInput(event);
      if (lista.length) this.leerExcel(lista);
    },

    async soltarExcel(event) {
      this.sobreDrop = false;
      const lista = await this._ficherosSoltados(event);
      if (lista.length) this.leerExcel(lista);
    },

    async leerExcel(lista) {
      if (this.up === "reading") return;
      const nombre = (this.nombreObra || "").trim();
      if (!this.proyectoId && !nombre) {
        this.error = "Escribe el nombre de la obra antes de subir los Excel.";
        return;
      }
      this.screen = "presupuestos";
      this.up = "reading";
      this.ficheroNombre = lista.map((fichero) => fichero.name).join(", ");
      this.lectura = null;
      this.error = "";
      const fd = new FormData();
      try {
        let alta;
        if (this.proyectoId) {
          for (const fichero of lista) {
            const uno = new FormData();
            uno.append("fichero", fichero, fichero.name);
            alta = await GestorApi.postForm(
              "/proyectos/" + this.proyectoId + "/presupuestos-excel",
              uno
            );
          }
        } else {
          fd.append("nombre", nombre);
          lista.forEach((fichero) => fd.append("ficheros", fichero, fichero.name));
          alta = await GestorApi.postForm("/proyectos/importar-presupuestos-excel", fd);
        }
        this.proyectoId = alta.proyecto_id;
        this.altaLectura = true;
        this.open = 0;
        this.up = "done";
        await this._cargarVistaProyecto(alta.proyecto_id);
        await this._cargarLecturaPresupuestos(alta.proyecto_id);
        if (this.lectura && alta.avisos && alta.avisos.length) {
          alta.avisos.forEach((aviso) => {
            this.lectura.avisos.push(
              "«" +
              aviso.bloque +
              "» no cuadra: las líneas suman " +
              GestorApi.euro(aviso.suma_lineas) +
              " y el Excel marca " +
              GestorApi.euro(aviso.total_documento) +
              "."
            );
          });
        }
      } catch (err) {
        this.error = err.message || "No se ha podido leer el Excel";
        this.up = this.proyecto ? "done" : "empty";
        if (this.proyectoId) await this._cargarVistaProyecto(this.proyectoId);
      }
    },

    async _cargarLecturaPresupuestos(proyectoId) {
      const pendientes = await GestorApi.getJson("/revisiones/pendientes");
      const docs = pendientes.filter(
        (item) => item.proyecto_id === proyectoId && item.tipo === "presupuesto"
      );
      if (!docs.length) {
        this.lectura = null;
        return;
      }
      const bloques = [];
      for (const doc of docs) {
        const cuerpo = await GestorApi.getJson(
          "/revisiones/documento?tipo=presupuesto&documento_id=" + doc.documento_id
        );
        bloques.push({
          presupuestoId: doc.documento_id,
          fichero: doc.fichero_origen,
          arbol: cuerpo.arbol || [],
          proyecto_nombre: cuerpo.proyecto_nombre,
        });
      }
      const conLineas = bloques.filter((bloque) => (bloque.arbol || []).length);
      if (!conLineas.length) {
        this.lectura = null;
        return;
      }
      this.lectura = this._armarLectura(
        {
          proyecto_id: proyectoId,
          presupuesto_id: conLineas[0].presupuestoId,
          es_escaneado: false,
          anotaciones_manuscritas_detectadas: 0,
          sumas_cuadran: true,
          total_leido: this.proyecto ? this.proyecto.presupuestado : null,
        },
        {
          arbol: conLineas.flatMap((bloque) => bloque.arbol),
          proyecto_nombre: conLineas[0].proyecto_nombre,
        },
        conLineas.map((bloque) => bloque.fichero).join(", ")
      );
      this.lectura.bloques = conLineas;
    },

    async elegirContratoCliente(event) {
      const lista = await this._ficherosDeInput(event);
      if (lista.length) this.leerContratoCliente(lista[0]);
    },

    async soltarContratoCliente(event) {
      this.sobreDrop = false;
      const lista = await this._ficherosSoltados(event);
      if (lista.length) this.leerContratoCliente(lista[0]);
    },

    async leerContratoCliente(fichero) {
      if (this.up === "reading") return;
      if (!this.proyectoId) {
        this.error = "Primero sube los presupuestos Excel.";
        this.screen = "presupuestos";
        this.up = "empty";
        return;
      }
      this.screen = "presupuesto";
      this.up = "reading";
      this.ficheroNombre = fichero.name;
      this.error = "";
      const fd = new FormData();
      fd.append("fichero", fichero, fichero.name);
      try {
        const contraste = await GestorApi.postForm(
          "/proyectos/" + this.proyectoId + "/contrastar-presupuesto-cliente",
          fd
        );
        this.contraste = this._contrasteDesdeApi(contraste);
        this.contrasteIndice = 0;
        this.up = "done";
      } catch (err) {
        this.error = err.message || "No se ha podido contrastar el PDF";
        this.up = "done";
      }
    },

    _sumaCliente(nodo) {
      const visitar = (actual, esRaiz) => {
        if (
          !esRaiz &&
          actual.nivel === "subapartado" &&
          actual.importe_contrato_cliente != null
        ) {
          return Number(actual.importe_contrato_cliente);
        }
        let suma = 0;
        let hay = false;
        (actual.subapartados || []).forEach((hijo) => {
          const parte = visitar(hijo, false);
          if (parte != null) {
            suma += parte;
            hay = true;
          }
        });
        return hay ? suma : null;
      };
      return visitar(nodo, true);
    },

    _contarContrastados(apartados) {
      const subs = [];
      const visitar = (nodo, cubierto) => {
        (nodo.subapartados || []).forEach((hijo) => {
          const propio =
            hijo.nivel === "subapartado" && hijo.importe_contrato_cliente != null;
          const este = cubierto || propio;
          if (hijo.nivel === "subapartado") subs.push(este);
          visitar(hijo, este);
        });
      };
      (apartados || []).forEach((apartado) => visitar(apartado, false));
      const hechos = subs.filter(Boolean).length;
      return {
        hechos,
        total: subs.length,
        completo: subs.length > 0 && hechos === subs.length,
      };
    },

    seccionesContraste() {
      const apartados = ((this.proyecto && this.proyecto.apartados) || []).filter(
        (apartado) => !this._esDescuento(apartado) && !this._esGestion(apartado)
      );
      const rama = (nodo) => ({
        valor: String(nodo.id),
        etiqueta: nodo.descripcion,
        cuantia: GestorApi.euro(nodo.importe_presupuestado),
        hijos: (nodo.subapartados || [])
          .filter((hijo) => hijo.nivel === "subapartado")
          .map(rama),
      });
      return apartados
        .map((apartado) => ({
          clave: String(apartado.id),
          codigo: apartado.codigo || "Apartado",
          etiqueta: apartado.descripcion,
          hijos: (apartado.subapartados || [])
            .filter((hijo) => hijo.nivel === "subapartado")
            .map(rama),
        }))
        .filter((sec) => sec.hijos.length);
    },

    contrasteElegido(fila, valor) {
      return (fila.elegidos || []).map(String).includes(String(valor));
    },

    filaContraste() {
      const filas = (this.contraste && this.contraste.sugerencias) || [];
      if (!filas.length) return null;
      const indice = Math.min(Math.max(this.contrasteIndice || 0, 0), filas.length - 1);
      return filas[indice];
    },

    _contrasteDesdeApi(contraste) {
      const sugerencias = (contraste.sugerencias || []).map((fila) =>
        this._aplicarCruce({
          id: fila.id,
          descripcion_pdf: fila.descripcion_pdf,
          codigo_pdf: fila.codigo_pdf,
          importe_pdf: fila.importe_pdf,
          importe_bruto: fila.importe_bruto,
          elegidos: (fila.tarea_ids || []).map(String),
          confirmada: Boolean(fila.confirmada),
          sugerida: Boolean(fila.sugerida) && !fila.confirmada,
        })
      );
      const pendiente = sugerencias.findIndex((fila) => !fila.confirmada);
      return {
        presupuesto_id: contraste.presupuesto_id,
        descuentos: contraste.descuentos || [],
        sugerencias,
        indicePendiente: pendiente >= 0 ? pendiente : 0,
      };
    },

    _hidratarContraste(proyecto) {
      const guardado = proyecto && proyecto.contraste_cliente;
      if (!guardado || !(guardado.sugerencias || []).length) return;
      if (
        this.contraste &&
        this.contraste.presupuesto_id === guardado.presupuesto_id &&
        (this.contraste.sugerencias || []).length
      ) {
        const porId = new Map((guardado.sugerencias || []).map((fila) => [fila.id, fila]));
        this.contraste.sugerencias.forEach((fila) => {
          const remoto = porId.get(fila.id);
          if (!remoto || !remoto.confirmada) return;
          fila.elegidos = (remoto.tarea_ids || []).map(String);
          fila.confirmada = true;
          fila.sugerida = false;
          this._aplicarCruce(fila);
        });
        this.contraste.descuentos = guardado.descuentos || this.contraste.descuentos;
        return;
      }
      const leido = this._contrasteDesdeApi(guardado);
      this.contrasteIndice = leido.indicePendiente;
      this.contraste = leido;
    },

    async asegurarContrasteCliente() {
      if (this.contraste && (this.contraste.sugerencias || []).length) return;
      if (!this.proyectoId || this.up === "reading") return;
      const docs = ((this.proyecto && this.proyecto.documentos) || []).filter(
        (doc) => doc.formato === "pdf_cliente" && doc.tiene_fichero
      );
      if (!docs.length) return;
      const doc = docs[docs.length - 1];
      this.up = "reading";
      this.ficheroNombre = doc.fichero_origen || doc.nombre || "";
      this.error = "";
      try {
        const contraste = await GestorApi.getJson(
          "/proyectos/" + this.proyectoId + "/contraste-cliente"
        );
        const leido = this._contrasteDesdeApi(contraste);
        this.contrasteIndice = leido.indicePendiente;
        this.contraste = leido;
        this.up = "done";
      } catch (err) {
        this.error = err.message || "No se ha podido leer el PDF guardado";
        this.up = "done";
      }
    },

    progresoContraste() {
      const filas = (this.contraste && this.contraste.sugerencias) || [];
      const hechas = filas.filter((fila) => fila.confirmada).length;
      if (!filas.length) return "Sin importes";
      return hechas + " de " + filas.length + " confirmados";
    },

    estadoContraste(fila) {
      if (fila.confirmada) return "hecho";
      if ((fila.elegidos || []).length) return "listo";
      return "sin";
    },

    etiquetaEstadoContraste(fila) {
      if (fila.confirmada) return "Confirmado";
      if (fila.sugerida && (fila.elegidos || []).length) return "Propuesta";
      if ((fila.elegidos || []).length) return "Por confirmar";
      return "Sin bloque";
    },

    etiquetaMarcados(n) {
      return n === 1 ? "1 bloque marcado" : n + " bloques marcados";
    },

    _palabrasContraste(texto) {
      return String(texto || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .split(/[^a-z0-9]+/)
        .filter((palabra) => palabra.length > 3);
    },

    _pistaContraste(fila) {
      const palabras = this._palabrasContraste(fila.descripcion_pdf);
      if (!palabras.length) return null;
      let mejor = null;
      let puntos = 0;
      this.seccionesContraste().forEach((sec) => {
        const texto = this._palabrasContraste(sec.codigo + " " + sec.etiqueta);
        const n = palabras.filter((palabra) => texto.includes(palabra)).length;
        if (n > puntos) {
          puntos = n;
          mejor = sec.clave;
        }
      });
      return puntos > 0 ? mejor : null;
    },

    _cuentaMarcados(fila, sec) {
      const ids = new Set((fila.elegidos || []).map(String));
      const contar = (nodos) =>
        (nodos || []).reduce(
          (suma, nodo) => suma + (ids.has(nodo.valor) ? 1 : 0) + contar(nodo.hijos),
          0
        );
      return contar(sec.hijos);
    },

    _abiertosContraste(fila) {
      if (Array.isArray(fila.abiertos)) return fila.abiertos.map(String);
      const abiertos = new Set(
        this.seccionesContraste()
          .filter((sec) => this.ramaMarcada(fila, sec.clave))
          .map((sec) => sec.clave)
      );
      (fila.elegidos || []).forEach((id) => {
        this._ancestrosSubapartado(id).forEach((anc) => abiertos.add(String(anc)));
      });
      if (abiertos.size) return Array.from(abiertos);
      const pista = this._pistaContraste(fila);
      if (pista) return [pista];
      const secciones = this.seccionesContraste();
      return secciones.length ? [secciones[0].clave] : [];
    },

    gruposContraste(fila) {
      if (!fila) return [];
      const abiertos = new Set(this._abiertosContraste(fila));
      const pista = this._pistaContraste(fila);
      return this.seccionesContraste().map((sec) => ({
        clave: sec.clave,
        codigo: sec.codigo,
        etiqueta: sec.etiqueta,
        abierto: abiertos.has(sec.clave),
        pista: pista === sec.clave,
        marcados: this._cuentaMarcados(fila, sec),
        nodos: abiertos.has(sec.clave) ? this._nodosContraste(fila, sec.hijos, 1) : [],
      }));
    },

    _nodosContraste(fila, nodos, nivel) {
      const abiertos = new Set(this._abiertosContraste(fila));
      const filas = [];
      (nodos || []).forEach((nodo) => {
        const abierto = abiertos.has(nodo.valor);
        filas.push({
          valor: nodo.valor,
          etiqueta: nodo.etiqueta,
          cuantia: nodo.cuantia,
          nivel,
          abierto,
          tieneHijos: nodo.hijos.length > 0,
          elegido: this.contrasteElegido(fila, nodo.valor),
          parcial: this.marcaParcial(fila, { tipo: "nodo", valor: nodo.valor }),
        });
        if (abierto) filas.push(...this._nodosContraste(fila, nodo.hijos, nivel + 1));
      });
      return filas;
    },

    toggleArbol(fila, valor) {
      const id = String(valor);
      const abiertos = new Set(this._abiertosContraste(fila));
      if (abiertos.has(id)) abiertos.delete(id);
      else abiertos.add(id);
      fila.abiertos = Array.from(abiertos);
    },

    ramaMarcada(fila, valor) {
      const nodo = this._buscarTarea(valor, (this.proyecto && this.proyecto.apartados) || []);
      if (!nodo) return false;
      const ids = new Set((fila.elegidos || []).map(String));
      return this._idsSubapartados(nodo).some((item) => ids.has(item));
    },

    marcaParcial(fila, nodo) {
      if (nodo.tipo === "nodo" && this.contrasteElegido(fila, nodo.valor)) return false;
      return this.ramaMarcada(fila, nodo.valor);
    },

    _buscarTarea(id, nodos) {
      for (const nodo of nodos || []) {
        if (String(nodo.id) === String(id)) return nodo;
        const hallado = this._buscarTarea(id, nodo.subapartados);
        if (hallado) return hallado;
      }
      return null;
    },

    alternarContraste(fila, valor, marcado) {
      const ids = new Set((fila.elegidos || []).map(String));
      const id = String(valor);
      if (marcado) {
        ids.add(id);
        const nodos = (this.proyecto && this.proyecto.apartados) || [];
        const nodo = this._buscarTarea(id, nodos);
        const descendientes = new Set(this._idsSubapartados(nodo));
        descendientes.forEach((desc) => ids.delete(desc));
        this._ancestrosSubapartado(id).forEach((anc) => ids.delete(anc));
      } else {
        ids.delete(id);
      }
      fila.elegidos = Array.from(ids);
      fila.sugerida = false;
      this._aplicarCruce(fila);
    },

    _idsSubapartados(nodo) {
      const ids = [];
      const visitar = (actual) => {
        (actual.subapartados || []).forEach((hijo) => {
          if (hijo.nivel === "subapartado") ids.push(String(hijo.id));
          visitar(hijo);
        });
      };
      if (nodo) visitar(nodo);
      return ids;
    },

    _ancestrosSubapartado(id) {
      const camino = [];
      const buscar = (nodos, pila) => {
        for (const nodo of nodos || []) {
          if (String(nodo.id) === String(id)) {
            camino.push(...pila);
            return true;
          }
          const siguiente =
            nodo.nivel === "subapartado" ? pila.concat(String(nodo.id)) : pila;
          if (buscar(nodo.subapartados, siguiente)) return true;
        }
        return false;
      };
      buscar((this.proyecto && this.proyecto.apartados) || [], []);
      return camino;
    },

    _aplicarCruce(fila) {
      const ids = fila.elegidos || [];
      const nodos = (this.proyecto && this.proyecto.apartados) || [];
      const elegidos = ids
        .map((id) => this._buscarTarea(id, nodos))
        .filter(Boolean);
      if (!elegidos.length) {
        fila.excel = "—";
        fila.diferencia = "—";
        fila.supera = false;
        fila.hay_cruce = false;
        return fila;
      }
      const base = elegidos.reduce(
        (suma, apartado) => suma + (Number(apartado.importe_presupuestado) || 0),
        0
      );
      const cliente = Number(fila.importe_pdf) || 0;
      const diff = cliente - base;
      fila.excel = GestorApi.euro(base);
      fila.diferencia = GestorApi.euro(diff);
      fila.supera = diff > 0.5;
      fila.hay_cruce = true;
      return fila;
    },

    async confirmarImporteCliente(fila) {
      const ids = (fila.elegidos || []).map((id) => Number(id)).filter((id) => id);
      if (!ids.length) {
        this.error = "Elige al menos un subapartado del Excel.";
        return;
      }
      this.error = "";
      try {
        await GestorApi.postJson(
          "/proyectos/" + this.proyectoId + "/importe-cliente",
          { tarea_ids: ids, importe: fila.importe_pdf, linea_id: fila.id }
        );
        fila.confirmada = true;
        await this._cargarVistaProyecto(this.proyectoId);
        const filas = (this.contraste && this.contraste.sugerencias) || [];
        const desde = filas.indexOf(fila);
        const siguiente = filas.findIndex((item, i) => i > desde && !item.confirmada);
        if (siguiente >= 0) this.contrasteIndice = siguiente;
        else {
          const pendiente = filas.findIndex((item) => !item.confirmada);
          if (pendiente >= 0) this.contrasteIndice = pendiente;
        }
      } catch (err) {
        this.error = err.message || "No se ha podido guardar el importe del cliente";
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
      this._hidratarContraste(proyecto);
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
        const montaje = apartado ? Number(apartado.importe_montaje) || 0 : 0;
        const base = apartado
          ? montaje > 0
            ? montaje
            : Number(apartado.importe_presupuestado) || 0
          : 0;
        const contratado = Number(contrato.precio_total) || 0;
        const diff = contratado - base;
        return {
          id: contrato.id,
          gremio: contrato.contratista_nombre,
          archivo: contrato.fichero_origen || contrato.contratista_nif,
          tiene_fichero: Boolean(contrato.tiene_fichero),
          url_fichero: contrato.tiene_fichero
            ? "/proyectos/" + proyecto.id + "/contratos/" + contrato.id + "/fichero"
            : null,
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
          etiqueta_base: montaje > 0 ? "Montaje del apartado" : "Presupuestado en el apartado",
          presupuestado: apartado ? euro(base) : "—",
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
        tiene_fichero: Boolean(factura.tiene_fichero),
        url_fichero: factura.tiene_fichero
          ? "/proyectos/" + proyecto.id + "/facturas/" + factura.id + "/fichero"
          : null,
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
      let desvioTotal = 0;
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
        const montaje = Number(ap.importe_montaje) || 0;
        const cliente = this._sumaCliente(ap);
        const escala = Math.max(pres, montaje, contratado, facturado, 1);
        const pct = (valor) => Math.round((valor / escala) * 100) + "%";
        const base = montaje > 0 ? montaje : pres;
        const hayCifra = contratado > 0 || facturado > 0;
        const desvio = hayCifra ? Math.max(contratado, facturado) - base : 0;
        if (hayCifra) desvioTotal += desvio;
        const detalle = [
          euro(pres) + " presupuestado",
          euro(montaje) + " montaje",
          cliente == null ? null : euro(cliente) + " contrato cliente",
          euro(contratado) + " contratado",
          euro(facturado) + " facturado",
        ]
          .filter(Boolean)
          .join(" · ");
        return {
          codigo: ap.codigo,
          nombre: ap.descripcion,
          facturado: euro(facturado),
          presupuestado: euro(pres),
          detalle,
          ancho_presupuesto: pct(pres),
          ancho_contratado: pct(contratado),
          ancho_facturado: pct(facturado),
          desviacion: hayCifra && Math.abs(desvio) >= 0.5 ? euro(desvio) : "—",
          alerta: desvio > 0.5 || (contratado > 0 && facturado > contratado + 0.5),
          partidas: this._filasControl(ap),
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
      const contrasteCliente = this._contarContrastados(apartados);
      return {
        pasos: [
          {
            id: "presupuestos",
            etiqueta: "Presupuestos",
            detalle: apartados.length + " apartados",
            completo: proyecto.estado !== "pendiente_revision" && apartados.length > 0,
          },
          {
            id: "presupuesto",
            etiqueta: "Contrato cliente",
            detalle:
              contrasteCliente.hechos +
              "/" +
              contrasteCliente.total +
              " contrastados",
            completo: contrasteCliente.completo,
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
          n_partidas: apartados.reduce((suma, ap) => suma + this._filasPartida(ap).length, 0),
          total: euro(presTotal),
          falta_revisar: false,
          apartados: apartados.map((ap) =>
            this._vistaApartado(ap, {
              importe: euro(ap.importe_presupuestado),
              hay_dudas: ap.estado_revision === "pendiente",
              revisado: ap.estado_revision !== "pendiente",
            })
          ),
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
          aviso: "Revisa los apartados del Excel. Las líneas de montaje son las que luego presupuesta y factura la subcontrata.",
          ayudaBoton: "Después se contrasta el PDF firmado con el cliente",
          etiquetaBoton: "Seguir con el contrato del cliente",
          documentos: (proyecto.documentos || [])
            .filter((doc) => doc.tiene_fichero)
            .map((doc) => ({
              id: doc.id,
              nombre: doc.fichero_origen,
              formato: doc.formato === "excel_expertis" ? "Excel" : "PDF cliente",
              url: "/proyectos/" + proyecto.id + "/presupuestos/" + doc.id + "/fichero",
            })),
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
              detalle: "Apartados del Excel",
              color: "#111111",
            },
            {
              etiqueta: "Montaje",
              valor: euro(
                apartados.reduce((suma, ap) => suma + (Number(ap.importe_montaje) || 0), 0)
              ),
              detalle: "Base de la subcontrata",
              color: "#111111",
            },
            {
              etiqueta: "Contratado",
              valor: euro(contrTotal),
              detalle: (proyecto.contratos || []).length + " contratos",
              color: "#111111",
            },
            {
              etiqueta: "Facturado",
              valor: euro(factTotal),
              detalle: "Solo facturas confirmadas",
              color: "#111111",
            },
            {
              etiqueta: "Desviación",
              valor: Math.abs(desvioTotal) < 0.5 ? euro(0) : euro(desvioTotal),
              detalle: "Contratado o facturado frente a presupuesto",
              color: desvioTotal > 0.5 ? "#a52a17" : "#1e7a34",
            },
          ],
          filas: filasControl,
          alertas,
        },
      };
    },

    _conMontajeArriba(filas) {
      return filas.filter((fila) => fila.montaje).concat(filas.filter((fila) => !fila.montaje));
    },

    _hijos(nodo) {
      if (nodo.hijos && nodo.hijos.length) return nodo.hijos;
      if (nodo.subapartados && nodo.subapartados.length) return nodo.subapartados;
      return [];
    },

    _tieneUnidades(nodo) {
      if (nodo.nivel && nodo.nivel !== "partida") return false;
      const n = Number(nodo.cantidad);
      return Number.isFinite(n) && n > 0;
    },

    _textoDescuento(valor) {
      if (valor == null || valor === "") return "—";
      return String(valor) + " %";
    },

    _filasPartida(nodo) {
      const hijos = this._hijos(nodo);
      if (!hijos.length) return this._tieneUnidades(nodo) ? [this._filaPartida(nodo)] : [];
      return hijos.flatMap((hijo) => this._filasPartida(hijo));
    },

    _filaPartida(fila) {
      const importe =
        fila.importe_presupuestado != null ? fila.importe_presupuestado : null;
      return {
        id: fila.id,
        codigo: fila.codigo,
        descripcion: fila.descripcion,
        unidad: String(fila.cantidad),
        medicion: this._textoDescuento(fila.descuento_pct),
        precio: fila.precio_unitario == null ? "—" : GestorApi.euro(fila.precio_unitario),
        importe: Number(importe) ? GestorApi.euro(importe) : "—",
        duda: fila.tiene_anotacion_manual
          ? "Anotación manuscrita"
          : fila.estado_revision === "pendiente"
            ? "Pendiente"
            : null,
        montaje: Boolean(fila.es_montaje),
        apartado: fila.es_montaje ? fila.capitulo || "" : "",
      };
    },

    _filasControl(ap) {
      const filas = this._conMontajeArriba(this._filasPartida(ap));
      return filas.map((fila) => ({
        codigo: fila.codigo,
        descripcion: fila.descripcion,
        presupuesto: fila.importe,
        medicion: fila.montaje ? "Montaje" : "—",
        facturado: "—",
        medicion_facturada: "—",
        desviacion: "—",
        alerta: false,
      }));
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
      const vista = this._vistaApartado(nodo, {
        importe: GestorApi.euro(nodo.importe_presupuestado),
        revisado: false,
      });
      const manuscrito =
        vista.partidas.some((fila) => fila.duda === "Anotación manuscrita") ||
        this._grupoConDuda(vista.grupos) ||
        nodo.tiene_anotacion_manual;
      if (manuscrito && !vista.resumen.includes("anotación")) {
        vista.resumen += " · anotación manuscrita";
      }
      vista.hay_dudas = manuscrito;
      return vista;
    },

    toggleSub(clave) {
      this.subOpen = Object.assign({}, this.subOpen, { [clave]: !this.subOpen[clave] });
    },

    subAbierto(clave) {
      return Boolean(this.subOpen[clave]);
    },

    _vistaApartado(nodo, extra) {
      const arbol = this._arbolPartidas(nodo);
      const grupos = this._marcarGrupos(arbol.grupos);
      const nPartidas = arbol.partidas.length + this._nPartidasGrupos(grupos);
      const nMontaje =
        arbol.partidas.filter((fila) => fila.montaje).length + this._nMontajeGrupos(grupos);
      let resumen = grupos.length
        ? grupos.length + " subapartados · " + nPartidas + " partidas"
        : nPartidas
          ? nPartidas + " partidas"
          : "Sin líneas con unidades";
      if (nMontaje) resumen += " · " + nMontaje + " de montaje";
      return Object.assign(
        {
          id: nodo.id,
          codigo: nodo.codigo,
          nombre: nodo.descripcion,
          resumen,
          hay_dudas: false,
          partidas: arbol.partidas,
          grupos,
        },
        extra
      );
    },

    _arbolPartidas(nodo) {
      const grupos = [];
      const partidas = [];
      for (const hijo of this._hijos(nodo)) {
        const anidados = this._hijos(hijo);
        const esGrupo =
          hijo.nivel === "subapartado" || (anidados.length > 0 && !this._tieneUnidades(hijo));
        if (esGrupo) {
          const dentro = this._arbolPartidas(hijo);
          if (!dentro.grupos.length && !dentro.partidas.length) continue;
          grupos.push({
            id: hijo.id,
            codigo: hijo.codigo,
            nombre: hijo.descripcion,
            importe:
              hijo.importe_presupuestado == null
                ? hijo.importe == null
                  ? "—"
                  : GestorApi.euro(hijo.importe)
                : GestorApi.euro(hijo.importe_presupuestado),
            partidas: dentro.partidas,
            grupos: dentro.grupos,
          });
          continue;
        }
        if (this._tieneUnidades(hijo)) partidas.push(this._filaPartida(hijo));
      }
      return { grupos, partidas: this._conMontajeArriba(partidas) };
    },

    _marcarGrupos(grupos, prefijo) {
      return (grupos || []).map((grupo, indice) => {
        const clave = String(grupo.id != null ? grupo.id : (prefijo || "g") + "-" + indice);
        return {
          clave,
          codigo: grupo.codigo,
          nombre: grupo.nombre,
          importe: grupo.importe,
          partidas: grupo.partidas,
          grupos: this._marcarGrupos(grupo.grupos, clave),
        };
      });
    },

    _nPartidasGrupos(grupos) {
      return (grupos || []).reduce(
        (suma, grupo) => suma + grupo.partidas.length + this._nPartidasGrupos(grupo.grupos),
        0
      );
    },

    _nMontajeGrupos(grupos) {
      return (grupos || []).reduce(
        (suma, grupo) =>
          suma +
          grupo.partidas.filter((fila) => fila.montaje).length +
          this._nMontajeGrupos(grupo.grupos),
        0
      );
    },

    _grupoConDuda(grupos) {
      return (grupos || []).some(
        (grupo) =>
          grupo.partidas.some((fila) => fila.duda === "Anotación manuscrita") ||
          this._grupoConDuda(grupo.grupos)
      );
    },

    resumenGrupo(grupo) {
      if (grupo.grupos && grupo.grupos.length) {
        return grupo.grupos.length + (grupo.grupos.length === 1 ? " bloque" : " bloques");
      }
      return grupo.partidas.length + (grupo.partidas.length === 1 ? " partida" : " partidas");
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
      const nPartidas = apartados.reduce(
        (suma, ap) =>
          suma +
          ap.partidas.length +
          this._nPartidasGrupos(ap.grupos),
        0
      );
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
        documentos: this._documentosPresupuesto(),
        ayudaBoton: "Se activa al revisar todos los apartados",
        etiquetaBoton: "Confirmar presupuesto",
      };
    },

    _documentosPresupuesto() {
      if (this.vista && this.vista.presupuesto && this.vista.presupuesto.documentos) {
        return this.vista.presupuesto.documentos;
      }
      const proyectoId = this.proyectoId || (this.lectura && this.lectura.proyectoId);
      const bloques = (this.lectura && this.lectura.bloques) || [];
      if (!proyectoId || !bloques.length) return [];
      return bloques.map((bloque) => ({
        id: bloque.presupuestoId,
        nombre: bloque.fichero,
        formato: "Excel",
        url: "/proyectos/" + proyectoId + "/presupuestos/" + bloque.presupuestoId + "/fichero",
      }));
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
      const enLectura = Boolean(this.lectura);
      const revisados = new Set(
        ((this.lectura && this.lectura.apartados) || [])
          .filter((ap) => ap.revisado)
          .map((ap) => ap.id)
      );
      const esEscaneado = Boolean(this.lectura && this.lectura.esEscaneado);
      const abierto = this.open;
      await this._cargarVistaProyecto(id);
      const pendientes = await GestorApi.getJson("/revisiones/pendientes");
      this.nPendientes = pendientes.length;
      if (!enLectura) return;
      await this._cargarLecturaPresupuestos(id);
      if (!this.lectura) return;
      if (esEscaneado) this.lectura.esEscaneado = true;
      this.lectura.apartados.forEach((ap) => {
        if (revisados.has(ap.id)) ap.revisado = true;
      });
      this.open = abierto;
    },

    async confirmarPresupuesto() {
      if (!this.lectura) {
        this.screen = "presupuesto";
        this.up = "done";
        this.asegurarContrasteCliente();
        return;
      }
      if (this.panelPresupuesto.falta_revisar) return;
      const visitar = (nodo, destino) => {
        destino.push({
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
        (nodo.hijos || []).forEach((hijo) => visitar(hijo, destino));
      };
      const bloques = this.lectura.bloques && this.lectura.bloques.length
        ? this.lectura.bloques
        : [{ presupuestoId: this.lectura.presupuestoId, arbol: this.lectura.arbol }];
      this.error = "";
      try {
        for (const bloque of bloques) {
          const tareasBloque = [];
          (bloque.arbol || []).forEach((nodo) => visitar(nodo, tareasBloque));
          if (!tareasBloque.length) continue;
          await GestorApi.postJson("/revisiones/confirmar", {
            tipo: "presupuesto",
            documento_id: bloque.presupuestoId,
            tareas: tareasBloque,
          });
        }
        const proyectoId = this.lectura.proyectoId;
        await this._cargarVistaProyecto(proyectoId);
        this.lectura = null;
        this.altaLectura = false;
        this.up = "done";
        this.screen = "presupuesto";
        this.asegurarContrasteCliente();
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

    async elegirContrato(event) {
      const lista = await this._ficherosDeInput(event);
      if (lista.length) this.leerContrato(lista[0]);
    },

    async elegirFactura(event) {
      const lista = await this._ficherosDeInput(event);
      if (lista.length) this.leerFactura(lista[0]);
    },

    async _ficherosDeInput(event) {
      const input = event.target;
      const lista = input.files ? Array.from(input.files) : [];
      if (!lista.length) return [];
      try {
        return await Promise.all(lista.map((fichero) => GestorApi.copiarFichero(fichero)));
      } catch (err) {
        this.error = err.message || "No se ha podido leer el fichero";
        return [];
      } finally {
        input.value = "";
      }
    },

    async _ficherosSoltados(event) {
      const lista = event.dataTransfer.files ? Array.from(event.dataTransfer.files) : [];
      if (!lista.length) return [];
      try {
        return await Promise.all(lista.map((fichero) => GestorApi.copiarFichero(fichero)));
      } catch (err) {
        this.error = err.message || "No se ha podido leer el fichero";
        return [];
      }
    },

    async leerContrato(fichero) {
      if (this.leyendoContrato) return;
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
      if (this.leyendoFactura) return;
      if (!this.proyectoId) {
        this.error = "Abre una obra antes de subir facturas.";
        return;
      }
      this.error = "";
      this.leyendoFactura = true;
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
      } finally {
        this.leyendoFactura = false;
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
