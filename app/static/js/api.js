/** Helpers HTTP compartidos (sin build). */
window.GestorApi = {
  async getJson(url) {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(await this._detalleError(res));
    }
    return res.json();
  },

  async copiarFichero(fichero) {
    // Hay que leer los bytes antes de vaciar el <input type="file">.
    // Si no, Chrome invalida el File y el fetch falla con "Failed to fetch".
    try {
      const datos = await fichero.arrayBuffer();
      return new File([datos], fichero.name, {
        type: fichero.type || "application/octet-stream",
      });
    } catch {
      const nombre = fichero && fichero.name ? fichero.name : "el fichero";
      throw new Error(
        "No se ha podido leer «" +
          nombre +
          "». Si lo tienes abierto, ciérralo y vuelve a elegirlo."
      );
    }
  },

  async postForm(url, formData) {
    let res;
    try {
      res = await fetch(url, { method: "POST", body: formData });
    } catch (err) {
      if (err && err.message === "Failed to fetch") {
        throw new Error(
          "El navegador no ha podido enviar el fichero. Ciérralo si lo tienes abierto y vuelve a elegirlo."
        );
      }
      throw err;
    }
    if (!res.ok) {
      throw new Error(await this._detalleError(res));
    }
    return res.json();
  },

  async borrar(url) {
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) {
      throw new Error(await this._detalleError(res));
    }
    return null;
  },

  async patchJson(url, body) {
    const res = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(await this._detalleError(res));
    }
    return res.json();
  },

  async postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(await this._detalleError(res));
    }
    return res.json();
  },

  async _detalleError(res) {
    const texto = await res.text();
    try {
      const body = JSON.parse(texto);
      if (typeof body.detail === "string") return body.detail;
      if (Array.isArray(body.detail)) {
        return body.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      }
      return texto || res.statusText;
    } catch {
      return texto || res.statusText;
    }
  },

  euro(valor) {
    const n = Number(valor);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString("es-ES", {
      style: "currency",
      currency: "EUR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      useGrouping: "always",
    });
  },
};
