function proyectoApp() {
  return {
    proyectoId: null,
    proyecto: null,
    cargando: true,
    error: "",
    fichero: null,
    verPagina: false,
    naveId: "",
    subiendo: false,
    errSubida: "",
    okSubida: "",
    enlazando: false,
    msgEnlace: "",
    errEnlace: "",
    manualApartado: {},
    euro: (v) => GestorApi.euro(v),
    porcentaje: (v) => Number(v).toLocaleString("es-ES", {
      maximumFractionDigits: 2,
    }) + "%",
    anchoProgreso(v) {
      return Math.max(0, Math.min(100, Number(v) || 0));
    },
    get apartadosEnlazables() {
      if (!this.proyecto) return [];
      return (this.proyecto.apartados || []).filter(
        (ap) => !String(ap.codigo || "").startsWith("descuento.")
      );
    },

    textoPendiente(v) {
      const importe = Number(v);
      return importe < 0
        ? "Excedido en " + this.euro(Math.abs(importe))
        : "Pendiente de facturar " + this.euro(importe);
    },

    async init() {
      const params = new URLSearchParams(window.location.search);
      const id = params.get("id") || params.get("proyecto_id");
      if (!id) {
        this.cargando = false;
        this.error = "Falta el id del proyecto en la URL (?id=).";
        return;
      }
      this.proyectoId = Number(id);
      await this.cargar();
    },

    async cargar() {
      this.cargando = true;
      this.error = "";
      try {
        this.proyecto = await GestorApi.getJson("/proyectos/" + this.proyectoId);
        this.manualApartado = {};
        for (const c of this.proyecto.contratos || []) {
          const primera = (c.sugerencias || [])[0];
          this.manualApartado[c.id] = primera ? [String(primera.tarea_id)] : [];
        }
      } catch (err) {
        this.error = err.message;
        this.proyecto = null;
      } finally {
        this.cargando = false;
      }
    },

    onFile(event) {
      this.fichero = event.target.files[0] || null;
      this.errSubida = "";
      this.okSubida = "";
    },

    async subirContrato() {
      if (!this.fichero) {
        this.errSubida = "Selecciona un fichero";
        return;
      }
      this.subiendo = true;
      this.errSubida = "";
      this.okSubida = "";
      try {
        const fd = new FormData();
        fd.append("fichero", this.fichero, this.fichero.name);
        if (this.naveId) {
          fd.append("nave_id", this.naveId);
        }
        if (this.verPagina) {
          fd.append("ver_pagina", "1");
        }
        const res = await GestorApi.postForm(
          "/proyectos/" + this.proyectoId + "/importar-contrato",
          fd
        );
        const nSug = (res.sugerencias_apartado || []).length;
        this.okSubida =
          "Contrato #" +
          res.contrato_id +
          " importado (pendiente de revisión)." +
          (nSug ? " " + nSug + " sugerencia(s) de apartado." : "");
        this.fichero = null;
        await this.cargar();
      } catch (err) {
        this.errSubida = err.message;
      } finally {
        this.subiendo = false;
      }
    },

    sugerenciaDe(contrato, tareaId) {
      const sugerencia = (contrato.sugerencias || []).find(
        (s) => s.tarea_id === Number(tareaId)
      );
      if (!sugerencia) return "";
      return (
        Math.round(Number(sugerencia.confianza) * 100) +
        "% · " +
        sugerencia.motivo
      );
    },

    toggleManual(contratoId, tareaId, marcado) {
      const actual = (this.manualApartado[contratoId] || []).map(String);
      const id = String(tareaId);
      const siguiente = actual.filter((valor) => valor !== id);
      if (marcado) siguiente.push(id);
      this.manualApartado[contratoId] = siguiente;
    },

    async enlazar(contratoId) {
      const ids = (this.manualApartado[contratoId] || [])
        .map(Number)
        .filter((n) => n > 0);
      if (!ids.length) return;
      this.enlazando = true;
      this.msgEnlace = "";
      this.errEnlace = "";
      try {
        const out = await GestorApi.postJson(
          "/proyectos/" +
            this.proyectoId +
            "/contratos/" +
            contratoId +
            "/enlazar-apartado",
          { tarea_apartado_ids: ids, tarea_apartado_id: ids[0] }
        );
        const nombres = (out.apartados || [])
          .map((ap) => ap.codigo_apartado)
          .join(", ");
        this.msgEnlace =
          "Enlace confirmado: contrato #" +
          out.contrato_id +
          " → " +
          (nombres || out.codigo_apartado + " " + out.descripcion_apartado);
        await this.cargar();
      } catch (err) {
        this.errEnlace = err.message;
      } finally {
        this.enlazando = false;
      }
    },
  };
}
