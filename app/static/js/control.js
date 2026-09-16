function controlApp() {
  return {
    proyectos: [],
    proyectoId: "",
    datos: null,
    cargando: false,
    error: "",
    chartContratista: null,
    chartContrato: null,
    chartNave: null,
    euro: (v) => GestorApi.euro(v),

    async init() {
      try {
        this.proyectos = await GestorApi.getJson("/proyectos");
      } catch (err) {
        this.error = "No se pudieron cargar proyectos: " + err.message;
        return;
      }
      const params = new URLSearchParams(window.location.search);
      const pre = params.get("proyecto_id");
      if (pre) {
        this.proyectoId = String(pre);
        await this.cargar();
      }
    },

    async cargar() {
      if (!this.proyectoId) return;
      this.cargando = true;
      this.error = "";
      this.datos = null;
      try {
        this.datos = await GestorApi.getJson(
          "/proyectos/" + this.proyectoId + "/control-economico"
        );
        this.$nextTick(() => this.pintarCharts());
      } catch (err) {
        this.error = err.message;
      } finally {
        this.cargando = false;
      }
    },

    pintarCharts() {
      if (!this.datos || typeof Chart === "undefined") return;

      if (this.chartContratista) this.chartContratista.destroy();
      if (this.chartContrato) this.chartContrato.destroy();
      if (this.chartNave) this.chartNave.destroy();

      const c1 = document.getElementById("chartContratista");
      const c2 = document.getElementById("chartContrato");
      const c3 = document.getElementById("chartNave");
      if (!c1 || !c2 || !c3) return;

      const porC = this.datos.por_contratista || [];
      this.chartContratista = new Chart(c1, {
        type: "bar",
        data: {
          labels: porC.map((r) => r.nif),
          datasets: [
            {
              label: "Presupuestado",
              data: porC.map((r) => Number(r.presupuestado)),
              backgroundColor: "#2f6b3a",
            },
            {
              label: "Facturado",
              data: porC.map((r) => Number(r.facturado)),
              backgroundColor: "#3b6ea5",
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { title: { display: true, text: "Por contratista" } },
        },
      });

      const porContrato = this.datos.por_contrato || [];
      this.chartContrato = new Chart(c2, {
        type: "bar",
        data: {
          labels: porContrato.map((r) => "Contrato #" + r.contrato_id),
          datasets: [
            {
              label: "Contratado",
              data: porContrato.map((r) => Number(r.contratado)),
              backgroundColor: "#2f6b3a",
            },
            {
              label: "Facturado confirmado",
              data: porContrato.map((r) => Number(r.facturado)),
              backgroundColor: "#3b6ea5",
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { title: { display: true, text: "Por contrato" } },
        },
      });

      const porN = this.datos.por_nave || [];
      this.chartNave = new Chart(c3, {
        type: "bar",
        data: {
          labels: porN.map((r) => r.nave),
          datasets: [
            {
              label: "Presupuestado",
              data: porN.map((r) => Number(r.presupuestado)),
              backgroundColor: "#2f6b3a",
            },
            {
              label: "Gasto (estim.)",
              data: porN.map((r) => Number(r.gasto_estimado)),
              backgroundColor: "#d35400",
            },
          ],
        },
        options: {
          responsive: true,
          plugins: { title: { display: true, text: "Por nave" } },
        },
      });
    },
  };
}
