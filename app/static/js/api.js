/** Helpers HTTP compartidos (sin build). */
window.GestorApi = {
  async getJson(url) {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(await this._detalleError(res));
    }
    return res.json();
  },

  async postForm(url, formData) {
    const res = await fetch(url, { method: "POST", body: formData });
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
    if (Number.isNaN(n)) return "—";
    return n.toLocaleString("es-ES", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 2,
    });
  },
};
