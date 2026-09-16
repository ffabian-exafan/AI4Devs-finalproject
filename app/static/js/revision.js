function revisionApp() {
  return {
    pendientes: [],
    cargandoLista: true,
    doc: null,
    filasPlanas: [],
    enviando: false,
    mensaje: "",
    mensajeOk: false,
    chart: null,

    async init() {
      await this.cargarPendientes();
    },

    async cargarPendientes() {
      this.cargandoLista = true;
      try {
        const res = await fetch("/revisiones/pendientes");
        if (!res.ok) throw new Error(await res.text());
        this.pendientes = await res.json();
      } catch (err) {
        this.mensaje = "Error cargando pendientes: " + err.message;
        this.mensajeOk = false;
      } finally {
        this.cargandoLista = false;
      }
    },

    async abrir(item) {
      this.mensaje = "";
      const url =
        "/revisiones/documento?tipo=" +
        encodeURIComponent(item.tipo) +
        "&documento_id=" +
        item.documento_id;
      const res = await fetch(url);
      if (!res.ok) {
        this.mensaje = "No se pudo abrir el documento";
        this.mensajeOk = false;
        return;
      }
      this.doc = await res.json();
      this.filasPlanas = this.aplanar(this.doc.arbol, 0);
      this.$nextTick(() => this.pintarChart());
    },

    aplanar(nodos, depth) {
      const out = [];
      for (const n of nodos || []) {
        out.push({
          id: n.id,
          codigo: n.codigo,
          nivel: n.nivel,
          capitulo: n.capitulo,
          descripcion: n.descripcion,
          unidad: n.unidad,
          cantidad: n.cantidad,
          precio_unitario: n.precio_unitario,
          importe_presupuestado: Number(n.importe_presupuestado),
          tiene_anotacion_manual: n.tiene_anotacion_manual,
          estado_revision: n.estado_revision,
          anotacion_confirmada: false,
          _depth: depth,
        });
        out.push(...this.aplanar(n.hijos || [], depth + 1));
      }
      return out;
    },

    contarPendientes() {
      return this.filasPlanas.filter((f) => f.estado_revision === "pendiente").length;
    },

    manuscritosSinConfirmar() {
      return this.filasPlanas.filter(
        (f) => f.tiene_anotacion_manual && !f.anotacion_confirmada
      ).length;
    },

    camposObligatoriosVacios() {
      return this.filasPlanas.some(
        (f) => !String(f.codigo || "").trim() || !String(f.descripcion || "").trim()
      );
    },

    // Comodidad de UI: el backend vuelve a validar con Pydantic.
    puedeConfirmar() {
      if (!this.doc || !this.filasPlanas.length) return false;
      if (this.contarPendientes() > 0) return false;
      if (this.manuscritosSinConfirmar() > 0) return false;
      if (this.camposObligatoriosVacios()) return false;
      return true;
    },

    onEstadoChange(fila) {
      if (fila.tiene_anotacion_manual && fila.estado_revision === "confirmada") {
        fila.anotacion_confirmada = true;
      }
    },

    marcarTodasRevisadas() {
      for (const f of this.filasPlanas) {
        if (!f.tiene_anotacion_manual && f.estado_revision === "pendiente") {
          f.estado_revision = "revisada";
        }
      }
    },

    pintarChart() {
      const canvas = document.getElementById("chartImportes");
      if (!canvas || typeof Chart === "undefined") return;
      const apartados = this.filasPlanas.filter((f) => f.nivel === "apartado");
      const labels = apartados.map((f) => f.codigo);
      const data = apartados.map((f) => Number(f.importe_presupuestado) || 0);
      if (this.chart) this.chart.destroy();
      this.chart = new Chart(canvas, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "Importe por apartado",
              data,
              backgroundColor: "#2f6b3a",
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true },
          },
        },
      });
    },

    async confirmar() {
      if (!this.puedeConfirmar()) return;
      this.enviando = true;
      this.mensaje = "";
      const payload = {
        tipo: this.doc.tipo,
        documento_id: this.doc.documento_id,
        tareas: this.filasPlanas.map((f) => ({
          id: f.id,
          codigo: f.codigo,
          descripcion: f.descripcion,
          capitulo: f.capitulo,
          unidad: f.unidad || null,
          cantidad: f.cantidad,
          precio_unitario: f.precio_unitario,
          importe_presupuestado: f.importe_presupuestado,
          estado_revision: f.tiene_anotacion_manual
            ? "confirmada"
            : f.estado_revision,
          anotacion_confirmada: !!f.anotacion_confirmada,
        })),
      };
      try {
        const res = await fetch("/revisiones/confirmar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail = body.detail;
          this.mensaje =
            typeof detail === "string"
              ? detail
              : Array.isArray(detail)
                ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
                : "Error al confirmar";
          this.mensajeOk = false;
          return;
        }
        this.mensajeOk = true;
        this.mensaje = body.mensaje || "Confirmado";
        this.doc = null;
        this.filasPlanas = [];
        if (this.chart) {
          this.chart.destroy();
          this.chart = null;
        }
        await this.cargarPendientes();
      } catch (err) {
        this.mensaje = String(err);
        this.mensajeOk = false;
      } finally {
        this.enviando = false;
      }
    },
  };
}
