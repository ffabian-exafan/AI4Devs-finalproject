function fechaMadrid(iso) {
  if (!iso) return "";
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "";
  return new Intl.DateTimeFormat("es-ES", {
    timeZone: "Europe/Madrid",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(fecha);
}

function gestionObras() {
  return {
    ...sesionLateral(),
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
    marcadas: [],
    borrando: false,
    lectura: null,
    lineaForm: null,
    lineaPdfForm: null,
    guardandoLinea: false,
    altaLectura: false,
    ficheroNombre: "",
    verPagina: false,
    leyendoContrato: false,
    leyendoParte: false,
    errorManoObra: "",
    manoObraAbierta: false,
    precioHoraEscrito: "",
    sobreDropParte: false,
    leyendoFactura: false,
    selloFacturaId: null,
    selloAlc: "",
    selloError: "",
    confirmandoSello: false,
    visorPdf: null,
    sobreDrop: false,
    nombreObra: "",
    origenAlta: "excel",
    contraste: null,
    contrasteIndice: 0,
    pdfSinBloque: true,
    menuCompacto: false,
    lineasDoc: ["60%", "90%", "85%", "40%", "95%", "70%", "88%", "55%", "92%", "80%", "35%", "75%"],

    async init() {
      try {
        this.menuCompacto = localStorage.getItem("obrix-menu") === "1";
        this.pdfSinBloque = localStorage.getItem("obrix-pdf-sin-bloque") !== "0";
      } catch (_) {
        this.menuCompacto = false;
      }
      const dentro = await this.cargarYo();
      if (!dentro) return;
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
        const proyectos = await GestorApi.getJson("/proyectos");
        this.proyectos = proyectos;
        const ids = new Set(proyectos.map((p) => p.id));
        this.marcadas = this.marcadas.filter((id) => ids.has(id));
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

    estaMarcada(id) {
      return this.marcadas.includes(id);
    },

    todasMarcadas() {
      return this.proyectos.length > 0 && this.proyectos.every((p) => this.marcadas.includes(p.id));
    },

    algunaMarcada() {
      return this.proyectos.some((p) => this.marcadas.includes(p.id));
    },

    marcarObra(id, marcada) {
      if (marcada) {
        if (!this.marcadas.includes(id)) this.marcadas = this.marcadas.concat(id);
        return;
      }
      this.marcadas = this.marcadas.filter((item) => item !== id);
    },

    marcarTodas(marcada) {
      this.marcadas = marcada ? this.proyectos.map((p) => p.id) : [];
    },

    etiquetaBorrarSeleccion() {
      const n = this.marcadas.length;
      return "Borrar " + n + (n === 1 ? " obra" : " obras");
    },

    async borrarObra(obra) {
      if (!obra || !obra.id) return;
      const nombre = obra.nombre || "#" + obra.id;
      if (!window.confirm("¿Borrar la obra «" + nombre + "»? Se eliminan su presupuesto, contratos y facturas.")) {
        return;
      }
      await this._borrarObras([obra]);
    },

    async borrarSeleccion() {
      if (this.borrando || !this.marcadas.length) return;
      const elegidas = this.proyectos.filter((p) => this.marcadas.includes(p.id));
      if (!elegidas.length) return;
      const n = elegidas.length;
      const texto =
        n === 1
          ? "¿Borrar la obra «" + (elegidas[0].nombre || "#" + elegidas[0].id) + "»? Se eliminan su presupuesto, contratos y facturas."
          : "¿Borrar " + n + " obras? Se eliminan sus presupuestos, contratos y facturas.";
      if (!window.confirm(texto)) return;
      await this._borrarObras(elegidas);
    },

    async _borrarObras(obras) {
      this.borrando = true;
      this.error = "";
      const fallos = [];
      try {
        for (const obra of obras) {
          try {
            await GestorApi.borrar("/proyectos/" + obra.id);
            this.marcadas = this.marcadas.filter((id) => id !== obra.id);
            if (this.proyectoId === obra.id) {
              this.proyecto = null;
              this.proyectoId = null;
              this.vista = null;
              this.lectura = null;
              this.altaLectura = false;
              this.screen = "obras";
              this.up = "done";
            }
          } catch (err) {
            fallos.push((obra.nombre || "#" + obra.id) + ": " + (err.message || "no se ha podido borrar"));
          }
        }
        await this.cargarObras();
        if (fallos.length) this.error = fallos.join(" · ");
      } finally {
        this.borrando = false;
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
      if (!lista.length) return;
      if (this.origenAlta === "pedido") this.leerPedidos(lista);
      else this.leerExcel(lista);
    },

    async soltarExcel(event) {
      this.sobreDrop = false;
      const lista = await this._ficherosSoltados(event);
      if (!lista.length) return;
      if (this.origenAlta === "pedido") this.leerPedidos(lista);
      else this.leerExcel(lista);
    },

    async leerPedidos(lista) {
      if (this.up === "reading") return;
      const nombre = (this.nombreObra || "").trim();
      if (!this.proyectoId && !nombre) {
        this.error = "Escribe el nombre de la obra antes de subir los pedidos.";
        return;
      }
      this.screen = "presupuestos";
      this.up = "reading";
      this.ficheroNombre = lista.map((fichero) => fichero.name).join(", ");
      this.error = "";
      const fd = new FormData();
      try {
        let alta;
        if (this.proyectoId) {
          fd.append("fichero", lista[0], lista[0].name);
          alta = await GestorApi.postForm("/proyectos/" + this.proyectoId + "/pedidos", fd);
        } else {
          fd.append("nombre", nombre);
          lista.forEach((fichero) => fd.append("ficheros", fichero, fichero.name));
          alta = await GestorApi.postForm("/proyectos/importar-pedidos", fd);
        }
        this.proyectoId = alta.proyecto_id;
        await this._cargarVistaProyecto(alta.proyecto_id);
      } catch (err) {
        this.error = err.message || "No se ha podido leer el pedido";
      }
      this.up = "empty";
    },

    async confirmarPedido(pedido) {
      this.error = "";
      try {
        await GestorApi.postJson(
          "/proyectos/" + this.proyectoId + "/pedidos/" + pedido.pedido_id + "/confirmar",
          {}
        );
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido confirmar el pedido";
      }
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
      if (this.verPagina) {
        fd.append("ver_pagina", "1");
      }
      try {
        const contraste = await GestorApi.postForm(
          "/proyectos/" + this.proyectoId + "/contrastar-presupuesto-cliente",
          fd
        );
        this.contraste = this._contrasteDesdeApi(contraste);
        this.contrasteIndice = 0;
        this.verPagina = false;
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

    _nombrePlano(texto) {
      return String(texto || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/\s+/g, " ")
        .trim();
    },

    _esBloqueMontaje(nodo) {
      const nombre = this._nombrePlano(nodo && nodo.descripcion);
      return nombre === "montaje" || nombre.startsWith("montaje ");
    },

    _restoMontaje(nodo) {
      const nombre = this._nombrePlano(nodo && nodo.descripcion);
      return nombre.startsWith("montaje ") ? nombre.slice("montaje ".length).trim() : "";
    },

    _montajeSuelto(nodo, hermanos) {
      const buscado = this._nombrePlano(nodo && nodo.descripcion);
      if (!buscado || this._esBloqueMontaje(nodo)) return null;
      return (
        (hermanos || []).find(
          (otro) => otro.id !== nodo.id && this._restoMontaje(otro) === buscado
        ) || null
      );
    },

    _cuantiaContraste(nodo, hermanos) {
      let base = Number(nodo.importe_presupuestado) || 0;
      const suelto = this._montajeSuelto(nodo, hermanos);
      if (suelto) base += Number(suelto.importe_presupuestado) || 0;
      return base;
    },

    _incluyeMontaje(nodo, hermanos) {
      if (!nodo || this._esBloqueMontaje(nodo)) return false;
      if ((Number(nodo.importe_montaje) || 0) > 0) return true;
      return Boolean(this._montajeSuelto(nodo, hermanos));
    },

    seccionesContraste() {
      const apartados = ((this.proyecto && this.proyecto.apartados) || []).filter(
        (apartado) =>
          !this._esDescuento(apartado) && !apartado.solo_gestion && !this._esRecargo(apartado)
      );
      const rama = (nodo, hermanos) => ({
        valor: String(nodo.id),
        etiqueta: nodo.descripcion,
        cuantia: GestorApi.euro(this._cuantiaContraste(nodo, hermanos)),
        incluyeMontaje: this._incluyeMontaje(nodo, hermanos),
        hijos: (nodo.subapartados || [])
          .filter((hijo) => hijo.nivel === "subapartado" && !this._esBloqueMontaje(hijo))
          .map((hijo, _indice, lista) => rama(hijo, lista)),
      });
      return apartados
        .map((apartado) => {
          const hijos = (apartado.subapartados || []).filter(
            (hijo) => hijo.nivel === "subapartado"
          );
          const visibles = hijos.filter((hijo) => {
            if (!this._esBloqueMontaje(hijo)) return true;
            const resto = this._restoMontaje(hijo);
            if (!resto || resto === "general") return true;
            return !hijos.some(
              (otro) =>
                !this._esBloqueMontaje(otro) && this._nombrePlano(otro.descripcion) === resto
            );
          });
          return {
            clave: String(apartado.id),
            codigo: apartado.codigo || "Apartado",
            etiqueta: apartado.descripcion,
            hijos: visibles.map((hijo) => rama(hijo, hijos)),
          };
        })
        .filter((sec) => sec.hijos.length);
    },

    contrasteElegido(fila, valor) {
      return (fila.elegidos || []).map(String).includes(String(valor));
    },

    abrirLineaPdf() {
      this.error = "";
      this.lineaPdfForm = { id: null, codigo: "", descripcion: "", importe: "" };
    },

    editarLineaPdf(fila, indice) {
      if (!fila || !fila.es_manual) return;
      this.error = "";
      this.contrasteIndice = indice;
      this.lineaPdfForm = {
        id: fila.id,
        codigo: fila.codigo_pdf || "",
        descripcion: fila.descripcion_pdf || "",
        importe: this._importePlano(fila.importe_pdf),
      };
    },

    async guardarLineaPdf() {
      if (!this.lineaPdfForm || !this.proyectoId) return;
      const codigo = (this.lineaPdfForm.codigo || "").trim();
      const descripcion = (this.lineaPdfForm.descripcion || "").trim();
      const importe = Number(this._importePlano(this.lineaPdfForm.importe));
      if (!codigo || descripcion.length < 2 || Number.isNaN(importe) || importe < 0) {
        this.error = "Código, descripción (al menos 2 caracteres) e importe son obligatorios";
        return;
      }
      const body = { codigo, descripcion, importe };
      const idLinea = this.lineaPdfForm.id;
      this.error = "";
      try {
        const contraste = idLinea
          ? await GestorApi.patchJson(
              "/proyectos/" + this.proyectoId + "/lineas-pdf/" + idLinea,
              body
            )
          : await GestorApi.postJson("/proyectos/" + this.proyectoId + "/lineas-pdf", body);
        this._ponerContraste(contraste, idLinea);
        this.lineaPdfForm = null;
      } catch (err) {
        this.error = err.message || "No se ha podido guardar el apartado";
      }
    },

    async borrarLineaPdf(fila) {
      if (!fila || !fila.es_manual || !this.proyectoId) return;
      const nombre = fila.descripcion_pdf || "este apartado";
      if (!window.confirm("¿Borrar el apartado «" + nombre + "»?")) return;
      this.error = "";
      try {
        await GestorApi.borrar(
          "/proyectos/" + this.proyectoId + "/lineas-pdf/" + fila.id
        );
        if (this.lineaPdfForm && this.lineaPdfForm.id === fila.id) this.lineaPdfForm = null;
        const contraste = await GestorApi.getJson(
          "/proyectos/" + this.proyectoId + "/contraste-cliente"
        );
        this._ponerContraste(contraste);
      } catch (err) {
        this.error = err.message || "No se ha podido borrar el apartado";
      }
    },

    _ponerContraste(contraste, idPreferido) {
      const leido = this._contrasteDesdeApi(contraste);
      let indice = leido.indicePendiente;
      if (!idPreferido) {
        const ultima = [...leido.sugerencias].reverse().find((fila) => fila.es_manual);
        if (ultima) {
          const puesto = leido.sugerencias.findIndex((fila) => fila.id === ultima.id);
          if (puesto >= 0) indice = puesto;
        }
      } else {
        const puesto = leido.sugerencias.findIndex((fila) => fila.id === idPreferido);
        if (puesto >= 0) indice = puesto;
      }
      this.contrasteIndice = indice;
      this.contraste = leido;
      this.up = "done";
    },

    metaContraste(fila) {
      const base = (fila.codigo_pdf || "") + " · " + this.etiquetaEstadoContraste(fila);
      return fila.es_manual ? base + " · Añadido a mano" : base;
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
          guardados: fila.confirmada ? (fila.tarea_ids || []).map(String) : [],
          confirmada: Boolean(fila.confirmada),
          sugerida: Boolean(fila.sugerida) && !fila.confirmada,
          solo_gestion: Boolean(fila.solo_gestion),
          apartado_gestion_id: fila.apartado_gestion_id || null,
          es_manual: Boolean(fila.es_manual),
        })
      );
      const pendiente = sugerencias.findIndex(
        (fila) => !fila.confirmada && !fila.solo_gestion
      );
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
          if (!remoto) return;
          fila.solo_gestion = Boolean(remoto.solo_gestion);
          fila.apartado_gestion_id = remoto.apartado_gestion_id || null;
          fila.es_manual = Boolean(remoto.es_manual);
          if (!remoto.confirmada) return;
          fila.elegidos = (remoto.tarea_ids || []).map(String);
          fila.guardados = fila.elegidos.slice();
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
      const hechas = filas.filter((fila) => fila.confirmada || fila.solo_gestion).length;
      if (!filas.length) return "Sin importes";
      return hechas + " de " + filas.length + " confirmados";
    },

    estadoContraste(fila) {
      if (fila.confirmada || fila.solo_gestion) return "hecho";
      if ((fila.elegidos || []).length) return "listo";
      return "sin";
    },

    etiquetaEstadoContraste(fila) {
      if (fila.solo_gestion) {
        return this.gestionPendiente(fila) ? "Pendiente de confirmar" : "Solo gestión";
      }
      if (fila.confirmada) return "Confirmado";
      if (fila.sugerida && (fila.elegidos || []).length) return "Propuesta";
      if ((fila.elegidos || []).length) return "Por confirmar";
      return "Sin bloque";
    },

    apartadoDeGestion(fila) {
      if (!fila || !fila.apartado_gestion_id || !this.proyecto) return null;
      return (
        (this.proyecto.apartados || []).find((ap) => ap.id === fila.apartado_gestion_id) || null
      );
    },

    gestionPendiente(fila) {
      const apartado = this.apartadoDeGestion(fila);
      return Boolean(apartado && apartado.estado_revision === "pendiente");
    },

    async marcarSoloGestion(fila) {
      if (!fila || !fila.id || !this.proyectoId) return;
      this.error = "";
      try {
        await GestorApi.postJson(
          "/proyectos/" + this.proyectoId + "/lineas-pdf/" + fila.id + "/solo-gestion",
          {}
        );
        this.contraste = null;
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido marcar la línea como solo gestión";
      }
    },

    async desmarcarSoloGestion(fila) {
      if (!fila || !fila.id || !this.proyectoId) return;
      this.error = "";
      try {
        await GestorApi.borrar(
          "/proyectos/" + this.proyectoId + "/lineas-pdf/" + fila.id + "/solo-gestion"
        );
        this.contraste = null;
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido quitar la marca de solo gestión";
      }
    },

    async confirmarGestion(fila) {
      const apartado = this.apartadoDeGestion(fila);
      if (!apartado || !this.proyectoId) return;
      this.error = "";
      try {
        await GestorApi.postJson(
          "/proyectos/" + this.proyectoId + "/apartados/" + apartado.id + "/confirmar-gestion",
          {}
        );
        this.contraste = null;
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido confirmar el importe";
      }
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
          incluyeMontaje: Boolean(nodo.incluyeMontaje),
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

    _padreTarea(id) {
      let hallado = null;
      const buscar = (nodos) => {
        for (const nodo of nodos || []) {
          if ((nodo.subapartados || []).some((hijo) => String(hijo.id) === String(id))) {
            hallado = nodo;
            return true;
          }
          if (buscar(nodo.subapartados)) return true;
        }
        return false;
      };
      buscar((this.proyecto && this.proyecto.apartados) || []);
      return hallado;
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
      const base = this._importeDeElegidos(ids);
      const cliente = Number(fila.importe_pdf) || 0;
      // Contrato cliente menos presupuesto. Verde si el contrato es mayor.
      const diff = cliente - base;
      fila.excel = GestorApi.euro(base);
      fila.diferencia = GestorApi.euro(diff);
      fila.supera = diff < -0.005;
      fila.hay_cruce = true;
      return fila;
    },

    _raizApartado(id) {
      let raiz = this._buscarTarea(id, (this.proyecto && this.proyecto.apartados) || []);
      let padre = raiz ? this._padreTarea(raiz.id) : null;
      while (padre) {
        raiz = padre;
        padre = this._padreTarea(raiz.id);
      }
      return raiz;
    },

    _importeDeBloque(id) {
      const nodo = this._buscarTarea(id, (this.proyecto && this.proyecto.apartados) || []);
      if (!nodo) return 0;
      const padre = this._padreTarea(nodo.id);
      const hermanos = (padre && padre.subapartados) || [];
      return this._cuantiaContraste(nodo, hermanos);
    },

    _importeDeElegidos(ids) {
      return (ids || []).reduce((suma, id) => suma + this._importeDeBloque(id), 0);
    },

    _algunBloqueElegido(nodos, elegidos) {
      for (const nodo of nodos || []) {
        if (elegidos.has(String(nodo.valor))) return true;
        if (this._algunBloqueElegido(nodo.hijos, elegidos)) return true;
      }
      return false;
    },

    // Bloques que ninguna línea del PDF tiene marcados. Si el padre ya está
    // marcado, sus hijos no salen: el importe del padre ya los incluye.
    _bloquesSinLinea() {
      const elegidos = new Set();
      ((this.contraste && this.contraste.sugerencias) || []).forEach((fila) => {
        if (fila.solo_gestion) return;
        (fila.elegidos || []).forEach((id) => elegidos.add(String(id)));
      });
      const libres = [];
      const visitar = (nodos) => {
        (nodos || []).forEach((nodo) => {
          if (elegidos.has(String(nodo.valor))) return;
          if (this._algunBloqueElegido(nodo.hijos, elegidos)) {
            visitar(nodo.hijos);
            return;
          }
          libres.push(nodo);
        });
      };
      this.seccionesContraste().forEach((sec) => visitar(sec.hijos));
      return libres;
    },

    resumenContraste() {
      const vacio = {
        filas: [],
        sinAsignar: false,
        pdfSinAsignar: "—",
        excel: "—",
        pdf: "—",
        diferencia: "—",
      };
      const apartados = ((this.proyecto && this.proyecto.apartados) || []).filter(
        (apartado) =>
          !this._esDescuento(apartado) && !apartado.solo_gestion && !this._esRecargo(apartado)
      );
      const filasPdf = (this.contraste && this.contraste.sugerencias) || [];
      if (!apartados.length && !filasPdf.length) return vacio;
      // Una fila por apartado del PDF: el Excel es la suma de sus bloques,
      // la misma cifra del pie de la línea. No se agrupa por fichero.
      const filas = [];
      let excelNum = 0;
      let sinAsignar = 0;
      filasPdf.forEach((fila) => {
        if (fila.solo_gestion) return;
        const importe = Number(fila.importe_pdf) || 0;
        const elegidos = (fila.elegidos || [])
          .map((id) => this._buscarTarea(id, apartados))
          .filter(Boolean);
        if (!elegidos.length) {
          sinAsignar += importe;
          return;
        }
        const excel = this._importeDeElegidos(elegidos.map((nodo) => nodo.id));
        const diff = importe - excel;
        excelNum += excel;
        filas.push({
          id: "pdf-" + fila.id,
          nombre:
            (fila.codigo_pdf ? fila.codigo_pdf + " · " : "") +
            (fila.descripcion_pdf || "Apartado"),
          excel: GestorApi.euro(excel),
          pdf: GestorApi.euro(importe),
          diferencia: GestorApi.euro(diff),
          supera: diff < -0.005,
        });
      });
      this._bloquesSinLinea().forEach((nodo) => {
        const excel = this._importeDeBloque(nodo.valor);
        if (Math.abs(excel) < 0.005) return;
        excelNum += excel;
        const raiz = this._raizApartado(nodo.valor);
        const prefijo = raiz && raiz.codigo ? raiz.codigo + " · " : "";
        filas.push({
          id: "libre-" + nodo.valor,
          nombre: prefijo + (nodo.etiqueta || "Apartado"),
          excel: GestorApi.euro(excel),
          pdf: "—",
          diferencia: "—",
          supera: false,
        });
      });
      filasPdf
        .filter((fila) => fila.solo_gestion)
        .forEach((fila) => {
          filas.push({
            id: "gestion-" + fila.id,
            nombre:
              (fila.codigo_pdf ? fila.codigo_pdf + " · " : "") +
              (fila.descripcion_pdf || "Solo gestión"),
            excel: "—",
            pdf: GestorApi.euro(fila.importe_pdf),
            diferencia: "—",
            supera: false,
          });
        });
      const totalExcel = excelNum;
      const totalLineas = filasPdf.reduce((suma, fila) => suma + (Number(fila.importe_pdf) || 0), 0);
      const descuentos = (this.contraste && this.contraste.descuentos) || [];
      const sumaDescuentos = descuentos.reduce(
        (suma, descuento) => suma + (Number(descuento.importe) || 0),
        0
      );
      const basePdf = this.pdfSinBloque ? totalLineas : totalLineas - sinAsignar;
      const totalPdf = basePdf - sumaDescuentos;
      const diffTotal = totalPdf - totalExcel;
      return {
        filas,
        sinAsignar: Math.abs(sinAsignar) >= 0.005,
        pdfSinAsignar: GestorApi.euro(sinAsignar),
        hayDescuento: Math.abs(sumaDescuentos) >= 0.005,
        descuento: GestorApi.euro(-sumaDescuentos),
        excel: GestorApi.euro(totalExcel),
        pdf: GestorApi.euro(totalPdf),
        diferencia: GestorApi.euro(diffTotal),
        supera: diffTotal < -0.005,
      };
    },

    alternarPdfSinBloque() {
      this.pdfSinBloque = !this.pdfSinBloque;
      try {
        localStorage.setItem("obrix-pdf-sin-bloque", this.pdfSinBloque ? "1" : "0");
      } catch (_) {
        /* la preferencia se pierde al cerrar el navegador */
      }
    },

    contrasteCambiado(fila) {
      if (!fila || !fila.confirmada) return false;
      const firma = (ids) =>
        (ids || [])
          .map(String)
          .filter(Boolean)
          .sort()
          .join(",");
      return firma(fila.elegidos) !== firma(fila.guardados);
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
        fila.guardados = (fila.elegidos || []).slice();
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
      const precioGuardado = proyecto.mano_obra && proyecto.mano_obra.precio_hora;
      this.precioHoraEscrito = precioGuardado ? Number(precioGuardado) : "";
      this.errorManoObra = "";
      const lineasMano = (this.vista.mano_obra && this.vista.mano_obra.lineas) || [];
      lineasMano.forEach((linea) => {
        (linea.partes || []).forEach((parte) => {
          if (parte.horas == null) parte.horas = "";
          if (parte.fecha == null) parte.fecha = "";
        });
      });
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
      const gestiones = todos.filter((ap) => !this._esDescuento(ap) && this._esRecargo(ap));
      const apartados = todos.filter((ap) => !this._esDescuento(ap) && !this._esRecargo(ap));
      const contratables = apartados.filter((ap) => !this._gestionPendiente(ap));
      const opciones = contratables
        .map((ap) => this._coberturaApartado(ap))
        .filter(Boolean);
      const catalogoLineas = [];
      opciones.forEach((grupo) => {
        catalogoLineas.push.apply(catalogoLineas, this._piezasDeGrupo(grupo));
      });
      const filas = (proyecto.contratos || []).map((contrato) => {
        const sugerencia = (contrato.sugerencias || [])[0];
        const confirmados = (contrato.tarea_apartado_ids || []).map(String);
        const legado = contrato.tarea_apartado_id ? [String(contrato.tarea_apartado_id)] : [];
        const apartadoIds = confirmados.length
          ? confirmados
          : legado.length
            ? legado
            : sugerencia
              ? [String(sugerencia.tarea_id)]
              : [];
        const asociado = confirmados.length > 0 || legado.length > 0;
        const fila = {
          id: contrato.id,
          gremio: contrato.contratista_nombre,
          archivo: contrato.fichero_origen || contrato.contratista_nif,
          tiene_fichero: Boolean(contrato.tiene_fichero),
          url_fichero: contrato.tiene_fichero
            ? "/proyectos/" + proyecto.id + "/contratos/" + contrato.id + "/fichero"
            : null,
          importe: euro(contrato.precio_total),
          precio_total: Number(contrato.precio_total) || 0,
          codigo: contrato.codigo || null,
          codigo_escrito: "",
          apartado_ids: apartadoIds,
          confianza: asociado
            ? 100
            : sugerencia
              ? Math.round(Number(sugerencia.confianza) * 100)
              : 0,
          motivo: asociado
            ? apartadoIds.length > 1
              ? "Enlace confirmado · " + apartadoIds.length + " apartados"
              : "Enlace confirmado"
            : sugerencia
              ? sugerencia.motivo
              : "Sin sugerencia automática",
          aviso: contrato.aviso || null,
          hay_aviso: Boolean(contrato.aviso),
          etiqueta_base: null,
          presupuestado: "—",
          diferencia: "—",
        supera: false,
        base: 0,
        asociado,
          pdf_guardados: (contrato.apartados_enlace || [])
            .filter((ap) => ap.linea_pdf_id)
            .map((ap) => ({
              linea_id: ap.linea_pdf_id,
              nombre: ap.descripcion,
              importe: Number(ap.importe) || 0,
              linea_descripcion: ap.linea_pdf_descripcion || "",
              explicacion: ap.explicacion || "",
            })),
          nuevos: [],
          linea_abierta: null,
          nuevo_nombre: "",
          nuevo_importe: "",
          nuevo_explicacion: "",
        };
        return fila;
      });
      filas.forEach((fila) => {
        if (!fila.asociado) return;
        fila.apartado_ids = this._expandirCobertura(fila.apartado_ids, opciones);
      });
      const tomadas = {};
      filas.forEach((fila) => {
        if (!fila.asociado) return;
        fila.apartado_ids.forEach((valor) => {
          if (!tomadas[valor]) tomadas[valor] = { contratoId: fila.id, gremio: fila.gremio };
        });
      });
      filas.forEach((fila) => {
        if (fila.asociado) {
          this._pintarBaseContrato(fila, catalogoLineas);
          return;
        }
        fila.apartado_ids = this._expandirCobertura(fila.apartado_ids, opciones).filter(
          (valor) => !tomadas[valor]
        );
        this._pintarBaseContrato(fila, catalogoLineas);
      });
      const pendientesContrato = filas.filter((fila) => !fila.asociado).length;
      const sinApartado = opciones.filter((grupo) =>
        this._piezasDeGrupo(grupo).some((pieza) => !tomadas[pieza.valor])
      ).length;
      const facturasVista = (facturas || []).map((factura) => ({
        id: factura.id,
        proveedor: factura.contratista_nombre,
        numero: factura.numero,
        fecha: factura.fecha_emision || "—",
        apartado: factura.contrato_etiqueta || "Sin contrato",
        contrato_id: factura.contrato_id,
        codigo_contrato: factura.codigo_contrato || null,
        aviso_codigo: factura.aviso_codigo || null,
        codigo_escrito: "",
        candidatos: [],
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
        fichero: factura.fichero_origen || "",
        url_fichero: factura.tiene_fichero
          ? "/proyectos/" + proyecto.id + "/facturas/" + factura.id + "/fichero"
          : null,
        aviso_isp: factura.aviso_isp || null,
        referencia_alc: factura.referencia_alc || null,
        tiene_sello: Boolean(factura.tiene_sello),
        url_sello: factura.tiene_sello ? "/facturas/" + factura.id + "/sello" : null,
        tiene_certificacion: Boolean(factura.tiene_certificacion_montaje),
        certificacion_por: factura.certificacion_montaje_por || "",
        certificacion_fecha: fechaMadrid(factura.certificacion_montaje_en),
        certificacion_usuario_id: factura.certificacion_montaje_usuario_id || null,
        url_certificacion: factura.tiene_certificacion_montaje
          ? "/facturas/" + factura.id + "/certificacion"
          : null,
        certificacion_omitida: Boolean(factura.certificacion_montaje_omitida),
        falta_otra_persona: Boolean(
          factura.tiene_certificacion_montaje &&
            factura.estado_revision !== "confirmada" &&
            this.yo &&
            factura.certificacion_montaje_usuario_id === this.yo.id
        ),
        acciones: factura.aviso_isp
          ? []
          : factura.estado_revision === "confirmada"
            ? factura.tiene_sello
              ? []
              : [{ etiqueta: "Generar sello", variante: "primary", resolucion: "Validada" }]
            : factura.tiene_certificacion_montaje
              ? this.yo && factura.certificacion_montaje_usuario_id === this.yo.id
                ? []
                : [{ etiqueta: "Confirmar factura", variante: "primary", resolucion: "Validada" }]
              : factura.certificacion_montaje_omitida
                ? [{ etiqueta: "Confirmar factura", variante: "primary", resolucion: "Validada" }]
                : [
                    { etiqueta: "Certificar montaje", variante: "primary", resolucion: "Certificar" },
                    { etiqueta: "No es necesario", variante: "secondary", resolucion: "Omitir" },
                  ],
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
      const filasControl = filas.map((fila) => {
        const presupuestado = Number(fila.base) || 0;
        const facturado = (facturas || [])
          .filter(
            (factura) =>
              factura.estado_revision === "confirmada" &&
              String(factura.contrato_id) === String(fila.id)
          )
          .reduce((suma, factura) => suma + (Number(factura.total) || 0), 0);
        const contratado = Number(fila.precio_total) || 0;
        const escala = contratado > 0 ? contratado : Math.max(presupuestado, facturado, 1);
        const pct = (valor) =>
          Math.min(100, Math.max(0, Math.round((valor / escala) * 100))) + "%";
        const desvio = presupuestado - facturado;
        desvioTotal += desvio;
        return {
          id: fila.id,
          nombre: fila.gremio,
          base: presupuestado,
          contratado: euro(contratado),
          presupuestado: euro(presupuestado),
          facturado: euro(facturado),
          ancho_presupuesto: pct(presupuestado),
          ancho_facturado: pct(facturado),
          alerta: facturado > presupuestado + 0.5,
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
        pedidos: proyecto.pedidos || [],
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
          apartados: apartados.map((ap) => {
            const extra = {
              importe: euro(ap.importe_presupuestado),
              hay_dudas: ap.estado_revision === "pendiente",
              revisado: ap.estado_revision !== "pendiente",
              solo_gestion: Boolean(ap.solo_gestion),
            };
            if (ap.solo_gestion) {
              extra.resumen =
                ap.estado_revision === "pendiente"
                  ? "Solo gestión · pendiente de revisión"
                  : "Solo gestión";
            }
            return this._vistaApartado(ap, extra);
          }),
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
          tomadas,
          apartados_contrato: catalogoLineas,
          filas,
          lineas_pdf_sin_excel: (
            (proyecto.contraste_cliente && proyecto.contraste_cliente.sugerencias) || []
          )
            .filter((fila) => fila.id && !fila.confirmada && !fila.solo_gestion)
            .map((fila) => ({
              id: fila.id,
              descripcion: fila.codigo_pdf
                ? fila.codigo_pdf + " " + fila.descripcion_pdf
                : fila.descripcion_pdf,
              importe: euro(fila.importe_pdf),
            })),
        },
        mano_obra: proyecto.mano_obra || {
          precio_hora: null,
          acumulado_horas: "0.00",
          acumulado: "0,00 €",
          lineas: [],
        },
        facturas: facturasVista,
        control: {
          kpis: [
            {
              etiqueta: "Mano de obra y montaje",
              valor: euro(filasControl.reduce((suma, fila) => suma + fila.base, 0)),
              detalle: "Base de la subcontrata",
              color: "#2a2724",
            },
            {
              etiqueta: "Contratado",
              valor: euro(contrTotal),
              detalle: (proyecto.contratos || []).length + " contratos",
              color: "#2a2724",
            },
            {
              etiqueta: "Facturado",
              valor: euro(factTotal),
              detalle: "Solo facturas confirmadas",
              color: "#2a2724",
            },
            {
              etiqueta: desvioTotal < -0.5 ? "Desviación" : "Por facturar",
              valor: euro(Math.abs(desvioTotal)),
              detalle: desvioTotal < -0.5
                ? "Facturado por encima del presupuesto"
                : "Presupuesto aún sin factura",
              color: desvioTotal < -0.5 ? "#9a1f16" : "#2a2724",
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
      const filas = this._filasPartida(ap).filter((fila) => fila.montaje);
      return filas.map((fila) => ({
        codigo: fila.codigo,
        descripcion: fila.descripcion,
        presupuesto: fila.importe,
        medicion: this._etiquetaMano(fila),
        facturado: "—",
        medicion_facturada: "—",
        desviacion: "—",
        alerta: false,
      }));
    },

    _etiquetaMano(fila) {
      const texto = String(fila.descripcion || "")
        .trim()
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
      if (texto.startsWith("colocacion")) return "Mano de obra";
      return "Montaje";
    },

    _esDescuento(nodo) {
      const texto = ((nodo.codigo || "") + " " + (nodo.descripcion || "")).toLowerCase();
      return texto.includes("descuento");
    },

    _esGestion(nodo) {
      const texto = ((nodo.descripcion || "") + " " + (nodo.nombre || "")).toLowerCase();
      return texto.includes("gestión") || texto.includes("gestion");
    },

    _esRecargo(nodo) {
      return !nodo.solo_gestion && this._esGestion(nodo);
    },

    _gestionPendiente(nodo) {
      return Boolean(nodo.solo_gestion && nodo.estado_revision !== "confirmada");
    },

    _piezaCobertura(nodo, nivel) {
      return {
        tipo: "linea",
        id: String(nodo.id),
        valor: String(nodo.id),
        etiqueta: this._nombreCortoApartado(nodo),
        prefijo: nodo.solo_gestion ? "Solo gestión" : "Montaje",
        cuantia: GestorApi.euro(this._baseContrato(nodo)),
        nivel: nivel,
        solo_gestion: Boolean(nodo.solo_gestion),
        importe_montaje: nodo.importe_montaje,
        importe_presupuestado: nodo.importe_presupuestado,
      };
    },

    _coberturaApartado(ap) {
      const filas = [];
      const volcar = (nodo, nivel) => {
        const salida = [];
        for (const hijo of nodo.subapartados || []) {
          const dentro = volcar(hijo, nivel + 1);
          if (hijo.es_montaje) {
            if (!this._montajeEnCero(hijo)) salida.push(this._piezaCobertura(hijo, nivel));
            salida.push.apply(salida, dentro);
            continue;
          }
          if (!dentro.length) continue;
          salida.push({
            tipo: "titulo",
            valor: "t-" + hijo.id,
            etiqueta: this._nombreCortoApartado(hijo),
            nivel: nivel,
          });
          salida.push.apply(salida, dentro);
        }
        return salida;
      };
      filas.push.apply(filas, volcar(ap, 1));
      if (!filas.some((fila) => fila.tipo === "linea")) {
        if (!ap.solo_gestion && this._montajeEnCero(ap)) return null;
        return {
          id: String(ap.id),
          nombre: this._nombreCortoApartado(ap),
          simple: true,
          filas: [],
          pieza: this._piezaCobertura(ap, 0),
        };
      }
      return {
        id: String(ap.id),
        nombre: this._nombreCortoApartado(ap),
        simple: false,
        filas: filas,
        pieza: null,
      };
    },

    _piezasDeGrupo(grupo) {
      if (!grupo) return [];
      if (grupo.simple) return grupo.pieza ? [grupo.pieza] : [];
      return (grupo.filas || []).filter((fila) => fila.tipo === "linea");
    },

    _expandirCobertura(ids, opciones) {
      const set = new Set((ids || []).map(String));
      const salida = [];
      (opciones || []).forEach((grupo) => {
        const piezas = this._piezasDeGrupo(grupo);
        const entero = set.has(String(grupo.id));
        piezas.forEach((pieza) => {
          if (entero || set.has(pieza.valor)) salida.push(pieza.valor);
        });
      });
      return salida;
    },

    textoDesglose(fila, grupo) {
      const piezas = this._piezasDeGrupo(grupo);
      const ids = new Set(fila.apartado_ids || []);
      const marcadas = piezas.filter((pieza) => ids.has(pieza.valor)).length;
      const n = piezas.length;
      const lineas = n === 1 ? "1 línea" : n + " líneas";
      if (!marcadas) return lineas;
      return marcadas + " de " + n;
    },

    ocupanteLinea(fila, valor) {
      const tomadas = (this.vista && this.vista.contratos && this.vista.contratos.tomadas) || {};
      const toma = tomadas[String(valor)];
      if (!toma || String(toma.contratoId) === String(fila.id)) return "";
      return toma.gremio || "otro contrato";
    },

    _piezasLibres(fila, grupo) {
      return this._piezasDeGrupo(grupo).filter((pieza) => !this.ocupanteLinea(fila, pieza.valor));
    },

    apartadoMarcado(fila, grupo) {
      const libres = this._piezasLibres(fila, grupo);
      if (!libres.length) return false;
      const ids = new Set(fila.apartado_ids || []);
      return libres.every((pieza) => ids.has(pieza.valor));
    },

    apartadoParcial(fila, grupo) {
      const libres = this._piezasLibres(fila, grupo);
      const ids = new Set(fila.apartado_ids || []);
      const marcadas = libres.filter((pieza) => ids.has(pieza.valor)).length;
      return marcadas > 0 && marcadas < libres.length;
    },

    apartadoBloqueado(fila, grupo) {
      const piezas = this._piezasDeGrupo(grupo);
      return piezas.length > 0 && piezas.every((pieza) => this.ocupanteLinea(fila, pieza.valor));
    },

    toggleGrupo(id, grupo, marcado) {
      if (!this.vista) return;
      const fila = this.vista.contratos.filas.find((c) => c.id === id);
      if (!fila || fila.asociado) return;
      const valores = new Set(this._piezasDeGrupo(grupo).map((pieza) => pieza.valor));
      let ids = (fila.apartado_ids || []).filter((item) => !valores.has(item));
      if (marcado) {
        this._piezasDeGrupo(grupo).forEach((pieza) => {
          if (this.ocupanteLinea(fila, pieza.valor)) return;
          ids.push(pieza.valor);
        });
      }
      fila.apartado_ids = ids;
      this._pintarBaseContrato(fila, this.vista.contratos.apartados_contrato || []);
    },

    _baseContrato(apartado) {
      if (!apartado) return 0;
      if (apartado.solo_gestion) {
        return Number(apartado.importe_presupuestado) || 0;
      }
      return Number(apartado.importe_montaje) || 0;
    },

    _montajeEnCero(nodo) {
      return Math.abs(Number(nodo && nodo.importe_montaje) || 0) < 0.005;
    },

    _nombreCortoApartado(ap) {
      const texto = String(ap.descripcion || "").trim();
      if (!texto) return ap.codigo || "Apartado";
      const partes = texto.split(/\s[-–]\s/).map((p) => p.trim()).filter(Boolean);
      const sistema = partes.find((p) => {
        const letras = p.replace(/[^A-Za-zÁÉÍÓÚÜáéíóúü]/g, "");
        if (letras.length < 4) return false;
        const mayus = (letras.match(/[A-ZÁÉÍÓÚÜ]/g) || []).length;
        return mayus / letras.length >= 0.7;
      });
      if (sistema) return sistema;
      return texto.length > 48 ? texto.slice(0, 45) + "…" : texto;
    },

    _textoBase(elegidos) {
      if (!elegidos.length) return null;
      const solo = elegidos.every((ap) => ap.solo_gestion);
      const montaje = elegidos.every((ap) => !ap.solo_gestion);
      if (elegidos.length === 1) {
        return solo ? "Importe del PDF" : "Montaje del apartado";
      }
      if (solo) return "Importe de los apartados";
      if (montaje) return "Montaje de los apartados";
      return "Base de los apartados";
    },

    _pintarBaseContrato(fila, catalogo) {
      const ids = fila.apartado_ids || [];
      const elegidos = (catalogo || []).filter((ap) => ids.includes(String(ap.id)));
      const delPdf = (fila.pdf_guardados || []).concat(fila.nuevos || []);
      if (!elegidos.length && !delPdf.length) {
        fila.etiqueta_base = null;
        fila.presupuestado = "—";
        fila.diferencia = "—";
        fila.supera = false;
        return;
      }
      const base =
        elegidos.reduce((suma, ap) => suma + this._baseContrato(ap), 0) +
        delPdf.reduce((suma, item) => suma + (Number(item.importe) || 0), 0);
      // Base menos contrato. El rojo se queda si el contrato supera la base.
      const diff = base - (Number(fila.precio_total) || 0);
      fila.base = base;
      fila.etiqueta_base = this._textoBaseMixta(elegidos, delPdf.length);
      fila.presupuestado = GestorApi.euro(base);
      fila.diferencia = GestorApi.euro(diff);
      fila.supera = diff < -0.005;
    },

    _textoBaseMixta(elegidos, cuantosContrato) {
      if (!elegidos.length) return "Apartados del contrato";
      if (!cuantosContrato) return this._textoBase(elegidos);
      return "Montaje y apartados del contrato";
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

    puedeAsociar(fila) {
      const ids = fila.apartado_ids || [];
      const nuevos = fila.nuevos || [];
      return ids.length > 0 || nuevos.length > 0;
    },

    lineaEnContrato(fila, lineaId) {
      const enNuevos = (fila.nuevos || []).some((item) => item.linea_id === lineaId);
      const guardada = (fila.pdf_guardados || []).some((item) => item.linea_id === lineaId);
      return enNuevos || guardada;
    },

    anadirApartadoPdf(id, linea) {
      if (!this.vista) return;
      const fila = this.vista.contratos.filas.find((c) => c.id === id);
      if (!fila || fila.asociado || this.lineaEnContrato(fila, linea.id)) return;
      const nombre = (fila.nuevo_nombre || "").trim();
      const explicacion = (fila.nuevo_explicacion || "").trim();
      const importe = Number(String(fila.nuevo_importe || "").replace(",", "."));
      if (nombre.length < 2 || explicacion.length < 5 || !(importe > 0)) {
        this.error = "En el apartado del PDF anota nombre, importe y explicación.";
        return;
      }
      this.error = "";
      fila.nuevos.push({
        linea_id: linea.id,
        nombre,
        importe,
        explicacion,
        linea_descripcion: linea.descripcion,
      });
      fila.nuevo_nombre = "";
      fila.nuevo_importe = "";
      fila.nuevo_explicacion = "";
      fila.linea_abierta = null;
      this._pintarBaseContrato(fila, this.vista.contratos.apartados_contrato || []);
    },

    quitarApartadoManual(id, indice) {
      if (!this.vista) return;
      const fila = this.vista.contratos.filas.find((c) => c.id === id);
      if (!fila || fila.asociado) return;
      fila.nuevos.splice(indice, 1);
      this._pintarBaseContrato(fila, this.vista.contratos.apartados_contrato || []);
    },

    toggleApartado(id, valor, marcado) {
      if (!this.proyectoId || !this.vista) return;
      const fila = this.vista.contratos.filas.find((c) => c.id === id);
      if (!fila || fila.asociado) return;
      const ids = (fila.apartado_ids || []).filter((item) => item !== String(valor));
      if (marcado) ids.push(String(valor));
      fila.apartado_ids = ids;
      this._pintarBaseContrato(fila, this.vista.contratos.apartados_contrato || []);
    },

    async quitarContrato(fila) {
      if (!fila || !fila.id || !this.proyectoId) return;
      const nombre = fila.gremio || fila.archivo || "este proveedor";
      if (
        !window.confirm(
          "¿Quitar el contrato de " +
            nombre +
            "? Las facturas se quedan en la obra y dejan de apuntar a este contrato."
        )
      ) {
        return;
      }
      this.error = "";
      try {
        await GestorApi.borrar(
          "/proyectos/" + this.proyectoId + "/contratos/" + fila.id
        );
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.error = err.message || "No se ha podido quitar el contrato";
      }
    },

    async asociar(id, asociado) {
      if (this.proyectoId && this.vista) {
        const fila = this.vista.contratos.filas.find((c) => c.id === id);
        if (!fila) return;
        if (!asociado) {
          this.error = "";
          try {
            await GestorApi.postJson(
              "/proyectos/" + this.proyectoId + "/contratos/" + id + "/desenlazar-apartado",
              {}
            );
            await this._cargarVistaProyecto(this.proyectoId);
          } catch (err) {
            this.error = err.message || "No se ha podido quitar el enlace";
          }
          return;
        }
        const ids = (fila.apartado_ids || []).map(Number).filter((n) => n > 0);
        const nuevos = fila.nuevos || [];
        if (!ids.length && !nuevos.length) {
          this.error = "Elige al menos un apartado antes de asociar.";
          return;
        }
        this.error = "";
        try {
          await GestorApi.postJson(
            "/proyectos/" + this.proyectoId + "/contratos/" + id + "/enlazar-apartado",
            {
              tarea_apartado_ids: ids,
              tarea_apartado_id: ids[0] || null,
              explicaciones: [],
              apartados_nuevos: nuevos.map((item) => ({
                linea_id: item.linea_id,
                nombre: item.nombre,
                importe: item.importe,
                explicacion: item.explicacion,
              })),
            }
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

    async guardarPrecioHora() {
      if (!this.proyectoId) return;
      this.errorManoObra = "";
      try {
        const precio = Number(this.precioHoraEscrito);
        await GestorApi.patchJson("/proyectos/" + this.proyectoId + "/precio-hora", {
          precio_hora: Number.isFinite(precio) ? precio.toFixed(4) : this.precioHoraEscrito,
        });
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.errorManoObra = err.message || "No se ha podido guardar el precio";
      }
    },

    partesManoObra() {
      const lineas = (this.vista && this.vista.mano_obra && this.vista.mano_obra.lineas) || [];
      return lineas.flatMap((linea) => linea.partes || []);
    },

    async elegirParte(event) {
      const lista = await this._ficherosDeInput(event);
      await this.subirPartes(lista);
    },

    async soltarPartes(event) {
      this.sobreDropParte = false;
      const lista = await this._ficherosSoltados(event);
      await this.subirPartes(lista);
    },

    async subirPartes(lista) {
      if (!lista.length || this.leyendoParte || !this.proyectoId) return;
      this.errorManoObra = "";
      this.leyendoParte = true;
      this.screen = "contratos";
      try {
        for (const fichero of lista) {
          this.ficheroNombre = fichero.name;
          const fd = new FormData();
          fd.append("fichero", fichero, fichero.name);
          await GestorApi.postForm("/proyectos/" + this.proyectoId + "/partes", fd);
        }
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.errorManoObra = err.message || "No se ha podido leer el parte";
        if (this.proyectoId) {
          await this._cargarVistaProyecto(this.proyectoId);
          this.screen = "contratos";
        }
      } finally {
        this.leyendoParte = false;
      }
    },

    async guardarHorasParte(parte) {
      if (!this.proyectoId || !parte) return;
      this.errorManoObra = "";
      try {
        await GestorApi.patchJson("/proyectos/" + this.proyectoId + "/partes/" + parte.id, {
          horas: parte.horas === "" ? null : parte.horas,
          fecha: parte.fecha || null,
        });
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.errorManoObra = err.message || "No se han podido guardar las horas";
      }
    },

    async confirmarParte(parte) {
      if (!this.proyectoId || !parte) return;
      this.errorManoObra = "";
      try {
        await GestorApi.postJson(
          "/proyectos/" + this.proyectoId + "/partes/" + parte.id + "/confirmar",
          {}
        );
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.errorManoObra = err.message || "No se ha podido confirmar el parte";
      }
    },

    async quitarParte(parte) {
      if (!this.proyectoId || !parte) return;
      this.errorManoObra = "";
      try {
        await GestorApi.borrar("/proyectos/" + this.proyectoId + "/partes/" + parte.id);
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.errorManoObra = err.message || "No se ha podido quitar el parte";
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

    async marcarIsp(event) {
      const entrada = event.target;
      const fichero = entrada.files && entrada.files[0];
      entrada.value = "";
      if (!fichero || !this.proyectoId) return;
      this.error = "";
      const fd = new FormData();
      fd.append("fichero", fichero, fichero.name);
      try {
        await GestorApi.postForm(
          "/proyectos/" + this.proyectoId + "/inversion-sujeto-pasivo",
          fd
        );
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido marcar la obra";
      }
    },

    async quitarIsp() {
      if (!this.proyectoId) return;
      if (!window.confirm("¿Volver a facturar esta obra con IVA?")) return;
      this.error = "";
      try {
        await GestorApi.borrar(
          "/proyectos/" + this.proyectoId + "/inversion-sujeto-pasivo"
        );
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido quitar la marca";
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
            contrato_id: detalle.contrato_id,
            codigo_contrato: detalle.codigo_contrato || null,
            aviso_codigo: detalle.aviso_codigo || null,
            apartado: detalle.contrato_etiqueta || "Sin contrato",
            candidatos: (detalle.contratos_candidatos || []).map((contrato) => ({
              id: contrato.id,
              etiqueta:
                (contrato.codigo ? contrato.codigo + " · " : "") +
                contrato.contratista_nombre +
                " · " +
                GestorApi.euro(contrato.precio_total),
            })),
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

    async borrarFactura(factura) {
      if (!factura || !factura.id || !this.proyectoId) return;
      const numero = factura.numero ? " " + factura.numero : "";
      const nombre = (factura.proveedor || "esta factura") + numero;
      if (!window.confirm("¿Borrar la factura " + nombre + "?")) return;
      this.error = "";
      try {
        await GestorApi.borrar("/facturas/" + factura.id);
        if (String(this.sel) === String(factura.id)) this.sel = null;
        await this._cargarVistaProyecto(this.proyectoId);
      } catch (err) {
        this.error = err.message || "No se ha podido borrar la factura";
      }
    },

    async guardarCodigoContrato(fila) {
      const codigo = (fila.codigo_escrito || "").trim();
      if (!codigo || !this.proyectoId) return;
      this.error = "";
      try {
        await GestorApi.postJson(
          "/proyectos/" + this.proyectoId + "/contratos/" + fila.id + "/codigo",
          { codigo }
        );
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "contratos";
      } catch (err) {
        this.error = err.message || "No se ha podido guardar el código";
      }
    },

    async guardarCodigoFactura(factura) {
      const codigo = (factura.codigo_escrito || "").trim();
      if (!codigo || !factura.id) return;
      this.error = "";
      try {
        await GestorApi.postJson("/facturas/" + factura.id + "/codigo", { codigo });
        const abierta = factura.id;
        this.sel = null;
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "facturas";
        await this.seleccionarFactura(abierta);
      } catch (err) {
        this.error = err.message || "No se ha podido guardar el código";
      }
    },

    async enlazarContratoFactura(factura, contratoId) {
      if (!factura || !factura.id || !contratoId) return;
      if (String(factura.contrato_id || "") === String(contratoId)) return;
      this.error = "";
      try {
        await GestorApi.postJson("/facturas/" + factura.id + "/contrato", {
          contrato_id: Number(contratoId),
        });
        const abierta = factura.id;
        this.sel = null;
        await this._cargarVistaProyecto(this.proyectoId);
        await this.seleccionarFactura(abierta);
      } catch (err) {
        this.error = err.message || "No se ha podido enlazar el contrato";
      }
    },

    bordeContrato(fila) {
      if (fila.asociado) return "hecho";
      if (fila.confianza < 90) return "baja";
      return "";
    },

    colorConfianza(fila) {
      return fila.confianza >= 90 ? "#1b6b38" : "#8f5d08";
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

    async certificarMontaje(id) {
      this.error = "";
      try {
        const detalle = await GestorApi.getJson("/facturas/" + id);
        if (!detalle.codigo_contrato) {
          this.error =
            detalle.aviso_codigo || "La factura no trae código de contrato. Indícalo.";
          return;
        }
        await GestorApi.postVacio("/facturas/" + id + "/certificar-montaje");
        this.sel = null;
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "facturas";
        await this.seleccionarFactura(id);
      } catch (err) {
        this.error = err.message || "No se ha podido certificar el montaje";
      }
    },

    async omitirCertificacion(id) {
      this.error = "";
      try {
        await GestorApi.postVacio("/facturas/" + id + "/omitir-certificacion-montaje");
        this.sel = null;
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "facturas";
        await this.seleccionarFactura(id);
      } catch (err) {
        this.error = err.message || "No se ha podido omitir la certificación";
      }
    },

    async resolver(id, resolucion) {
      if (resolucion === "Certificar") {
        await this.certificarMontaje(id);
        return;
      }
      if (resolucion === "Omitir") {
        await this.omitirCertificacion(id);
        return;
      }
      if (this.proyectoId) {
        if (resolucion !== "Validada") {
          this.error = "Para que la factura cuente hay que confirmarla.";
          return;
        }
        this.error = "";
        try {
          const detalle = await GestorApi.getJson("/facturas/" + id);
          if (!detalle.codigo_contrato) {
            this.error =
              detalle.aviso_codigo || "La factura no trae código de contrato. Indícalo.";
            return;
          }
          this.selloFacturaId = id;
          this.selloAlc = "";
          this.selloError = "";
          this.$nextTick(() => {
            const dialogo = this.$refs.dialogoSello;
            if (dialogo && !dialogo.open) dialogo.showModal();
            if (this.$refs.campoAlc) this.$refs.campoAlc.focus();
          });
        } catch (err) {
          this.error = err.message || "No se ha podido abrir la factura";
        }
        return;
      }
      this.estado.resueltas = { ...this.estado.resueltas, [id]: resolucion };
      this.sel = null;
      await this.sincronizar();
    },

    async confirmarConSello() {
      const id = this.selloFacturaId;
      const alc = (this.selloAlc || "").trim();
      if (!id) return;
      if (!alc) {
        this.selloError = "Indica la referencia ALC.";
        if (this.$refs.campoAlc) this.$refs.campoAlc.focus();
        return;
      }
      this.confirmandoSello = true;
      this.selloError = "";
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
          codigo_contrato: detalle.codigo_contrato,
          contrato_id: detalle.contrato_id,
          referencia_alc: alc,
          lineas: (detalle.lineas || []).map((linea) => ({
            id: linea.id,
            descripcion: linea.descripcion,
            importe: linea.importe,
          })),
        });
        if (this.$refs.dialogoSello && this.$refs.dialogoSello.open) {
          this.$refs.dialogoSello.close();
        }
        this.sel = null;
        await this._cargarVistaProyecto(this.proyectoId);
        this.screen = "facturas";
        await this.seleccionarFactura(id);
      } catch (err) {
        this.selloError = err.message || "No se ha podido confirmar la factura";
      } finally {
        this.confirmandoSello = false;
      }
    },

    esPdf(nombre) {
      return esNombrePdf(nombre);
    },

    abrirVisorPdf(url, nombre) {
      if (!url || !esNombrePdf(nombre)) return;
      this.visorPdf = {
        url: urlVerPdf(url),
        nombre: nombre,
        descarga: url,
      };
      this.$nextTick(() => {
        const dialogo = this.$refs.visorPdf;
        if (!(dialogo instanceof HTMLDialogElement)) return;
        prepararCierreVisor(dialogo);
        if (!dialogo.open) dialogo.showModal();
      });
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
