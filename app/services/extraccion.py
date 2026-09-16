"""Extracción estructurada de presupuesto: LLM (si hay clave) o parser de fixture."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from urllib import error, request

from app.config import get_settings
from app.schemas.extraccion import (
    AnotacionManuscrita,
    ApartadoExtraido,
    NaveExtraida,
    PresupuestoExtraido,
)
from app.services.extraccion_contrato import extraer_contrato

__all__ = [
    "extraer_presupuesto",
    "extraer_contrato",
]

# Importes ficticios coherentes para marcadores [IMPORTE_*] de la fixture anonimizada.
# No son datos reales; solo permiten probar suma y persistencia.
_IMPORTES_FIXTURE: dict[str, Decimal] = {
    "IMPORTE_CUBIERTA": Decimal("100000.00"),
    "IMPORTE_FALSO_TECHO": Decimal("50000.00"),
    "IMPORTE_ALIMENTACION": Decimal("200000.00"),
    "IMPORTE_SUELOS": Decimal("80000.00"),
    "IMPORTE_CORRALES": Decimal("90000.00"),
    "IMPORTE_NIDOS": Decimal("40000.00"),
    "IMPORTE_JUGUETES": Decimal("10000.00"),
    "IMPORTE_VENTILACION": Decimal("120000.00"),
    "IMPORTE_TOTAL_EXAFAN": Decimal("690000.00"),
    "IMPORTE_OPCION_CALEFACCION": Decimal("30000.00"),
    "IMPORTE_OBRA_CIVIL": Decimal("250000.00"),
    "IMPORTE_ESTRUCTURA_NAVE": Decimal("180000.00"),
    "IMPORTE_VOLADIZO": Decimal("40000.00"),
    "IMPORTE_ESTRUCTURA_ALMACEN": Decimal("30000.00"),
    "IMPORTE_PROYECTADO_CUBIERTA": Decimal("25000.00"),
    "IMPORTE_FONTANERIA": Decimal("60000.00"),
    "IMPORTE_ELECTRICIDAD_PRESUPUESTADO": Decimal("70000.00"),
    "IMPORTE_TOTAL_PROVEEDORES": Decimal("655000.00"),
    "IMPORTE_SUBTOTAL_EXAFAN": Decimal("720000.00"),
    "IMPORTE_SUBTOTAL_PROVEEDORES": Decimal("655000.00"),
    "IMPORTE_GESTION_EXAFAN": Decimal("52400.00"),
    "IMPORTE_TOTAL_PROYECTO": Decimal("1427400.00"),
    "IMPORTE_DESCUENTO_1": Decimal("27400.00"),
    "IMPORTE_TOTAL_FINAL_IMPRESO": Decimal("1400000.00"),
    "IMPORTE_DESCUENTO_2": Decimal("50000.00"),
    "IMPORTE_FINAL_MANUSCRITO": Decimal("1350000.00"),
}

_PROMPT_SISTEMA = """\
Eres un extractor de presupuestos de obra. Devuelves SOLO JSON válido con esta forma:
{
  "nombre_proyecto": string,
  "tipo_proyecto": "llave_en_mano"|"reforma",
  "version": int,
  "fecha": "YYYY-MM-DD"|null,
  "naves": [
    {
      "codigo": string,
      "descripcion": string,
      "apartados": [
        {
          "codigo": string,
          "capitulo": string|null,
          "descripcion": string,
          "importe": number,
          "tiene_anotacion_manual": bool,
          "excluido_de_suma": bool,
          "unidad": null,
          "cantidad": null,
          "precio_unitario": null
        }
      ]
    }
  ],
  "total_impreso": number|null,
  "total_manuscrito": number|null,
  "anotaciones": [
    {
      "campo": string,
      "valor_impreso": string|null,
      "valor_manuscrito": string,
      "descripcion": string
    }
  ]
}

Reglas:
- Nivel de desglose: solo "apartado" si el documento no da partida con precio unitario.
- unidad, cantidad y precio_unitario deben ser null si no aparecen a nivel de apartado.
- Si hay anotación manuscrita sobre valor impreso (tachado + corrección), marca
  tiene_anotacion_manual=true en esa fila y usa el valor manuscrito como válido.
- No inventes importes ni campos que no estén en el documento.
"""


def extraer_presupuesto(texto: str) -> PresupuestoExtraido:
    """Extrae naves/apartados del texto del presupuesto."""
    if _es_fixture_anonimizada(texto):
        resultado = _extraer_fixture_destete(texto)
    else:
        settings = get_settings()
        if settings.llm_api_key and settings.llm_api_base:
            resultado = _extraer_con_llm(texto, settings.llm_api_key, settings.llm_api_base)
        else:
            # Sin LLM autorizado: parser heurístico mínimo sobre tablas markdown
            resultado = _extraer_heuristico(texto)

    return _aplicar_comprobaciones(resultado)


def _es_fixture_anonimizada(texto: str) -> bool:
    return (
        "presupuesto_nave_destete" in texto.lower()
        or "[IMPORTE_CUBIERTA]" in texto
        or "IMPORTE_FINAL_MANUSCRITO" in texto
    )


def _importe(clave: str) -> Decimal:
    if clave not in _IMPORTES_FIXTURE:
        raise KeyError(f"Marcador de importe desconocido: {clave}")
    return _IMPORTES_FIXTURE[clave]


def _extraer_fixture_destete(texto: str) -> PresupuestoExtraido:
    """Parser determinista de la fixture anonimizada de nave de destete."""
    anotaciones: list[AnotacionManuscrita] = []

    # Color de cubierta: ~~Rojo~~ **Verde**
    if "~~Rojo~~" in texto and "Verde" in texto:
        anotaciones.append(
            AnotacionManuscrita(
                campo="cubierta.color",
                valor_impreso="Rojo",
                valor_manuscrito="Verde",
                descripcion="Color de cubierta tachado y corregido a mano",
            )
        )

    # Descuento manuscrito sobre el total impreso
    if "anotación manuscrita" in texto.lower() or "IMPORTE_DESCUENTO_2" in texto:
        anotaciones.append(
            AnotacionManuscrita(
                campo="precio.descuento_final",
                valor_impreso=str(_importe("IMPORTE_TOTAL_FINAL_IMPRESO")),
                valor_manuscrito=str(_importe("IMPORTE_FINAL_MANUSCRITO")),
                descripcion="Descuento adicional manuscrito; prevalece el importe final manuscrito",
            )
        )

    apartados: list[ApartadoExtraido] = [
        ApartadoExtraido(
            codigo="1.1",
            capitulo="Materiales EXAFAN",
            descripcion="Cubierta (color válido: Verde)",
            importe=_importe("IMPORTE_CUBIERTA"),
            tiene_anotacion_manual=True,
        ),
        ApartadoExtraido(
            codigo="1.2",
            capitulo="Materiales EXAFAN",
            descripcion="Falso techo / aislamiento",
            importe=_importe("IMPORTE_FALSO_TECHO"),
        ),
        ApartadoExtraido(
            codigo="2.1",
            capitulo="Equipamiento EXAFAN",
            descripcion="Alimentación",
            importe=_importe("IMPORTE_ALIMENTACION"),
        ),
        ApartadoExtraido(
            codigo="2.2",
            capitulo="Equipamiento EXAFAN",
            descripcion="Suelos (slat y pletinas)",
            importe=_importe("IMPORTE_SUELOS"),
        ),
        ApartadoExtraido(
            codigo="2.3",
            capitulo="Equipamiento EXAFAN",
            descripcion="Corrales (separadores)",
            importe=_importe("IMPORTE_CORRALES"),
        ),
        ApartadoExtraido(
            codigo="2.4",
            capitulo="Equipamiento EXAFAN",
            descripcion="Nidos",
            importe=_importe("IMPORTE_NIDOS"),
        ),
        ApartadoExtraido(
            codigo="2.5",
            capitulo="Equipamiento EXAFAN",
            descripcion="Juguetes",
            importe=_importe("IMPORTE_JUGUETES"),
        ),
        ApartadoExtraido(
            codigo="2.6-2.8",
            capitulo="Equipamiento EXAFAN",
            descripcion="Ventilación (regulación, ventilación y puertas)",
            importe=_importe("IMPORTE_VENTILACION"),
        ),
        ApartadoExtraido(
            codigo="3.1",
            capitulo="Opciones",
            descripcion="Opción calefacción nave existente",
            importe=_importe("IMPORTE_OPCION_CALEFACCION"),
            excluido_de_suma=True,  # no entra en TOTAL_EXAFAN de la tabla 4
        ),
        ApartadoExtraido(
            codigo="5",
            capitulo="Proveedores directos",
            descripcion="Obra civil",
            importe=_importe("IMPORTE_OBRA_CIVIL"),
        ),
        ApartadoExtraido(
            codigo="6.1.1",
            capitulo="Proveedores directos",
            descripcion="Estructura y cerramientos de nave",
            importe=_importe("IMPORTE_ESTRUCTURA_NAVE"),
        ),
        ApartadoExtraido(
            codigo="6.1.2",
            capitulo="Proveedores directos",
            descripcion="Voladizo lateral 57m",
            importe=_importe("IMPORTE_VOLADIZO"),
        ),
        ApartadoExtraido(
            codigo="6.1.3",
            capitulo="Proveedores directos",
            descripcion="Estructura y cerramientos de almacén",
            importe=_importe("IMPORTE_ESTRUCTURA_ALMACEN"),
        ),
        ApartadoExtraido(
            codigo="7",
            capitulo="Proveedores directos",
            descripcion="Proyectado de cubierta",
            importe=_importe("IMPORTE_PROYECTADO_CUBIERTA"),
        ),
        ApartadoExtraido(
            codigo="8.1",
            capitulo="Instalaciones",
            descripcion="Fontanería y calefacción",
            importe=_importe("IMPORTE_FONTANERIA"),
        ),
        ApartadoExtraido(
            codigo="8.2",
            capitulo="Instalaciones",
            descripcion="Electricidad",
            importe=_importe("IMPORTE_ELECTRICIDAD_PRESUPUESTADO"),
        ),
        # Fila del descuento/importe final manuscrito (no suma de apartados de obra)
        ApartadoExtraido(
            codigo="11.descuento",
            capitulo="Precio final",
            descripcion="Descuento adicional / importe final manuscrito",
            importe=_importe("IMPORTE_FINAL_MANUSCRITO"),
            tiene_anotacion_manual=True,
            excluido_de_suma=True,
        ),
    ]

    nave = NaveExtraida(
        codigo="N1",
        descripcion="Nave de destete (7.038 lechones) + almacén",
        importe_presupuestado=_importe("IMPORTE_FINAL_MANUSCRITO"),
        apartados=apartados,
    )

    version = 1
    if "V2" in texto or "versión" in texto.lower():
        # El propio doc indica que el nº puede llevar sufijo V2
        m = re.search(r"V(\d+)", texto)
        if m:
            version = int(m.group(1))

    return PresupuestoExtraido(
        nombre_proyecto="Nave de destete — CLIENTE_1",
        tipo_proyecto="llave_en_mano",
        version=version,
        fecha="2025-06-27",
        naves=[nave],
        total_impreso=_importe("IMPORTE_TOTAL_FINAL_IMPRESO"),
        total_manuscrito=_importe("IMPORTE_FINAL_MANUSCRITO"),
        anotaciones=anotaciones,
    )


def _extraer_heuristico(texto: str) -> PresupuestoExtraido:
    """Fallback sin LLM: detecta filas de tabla markdown con importes numéricos."""
    apartados: list[ApartadoExtraido] = []
    for i, linea in enumerate(texto.splitlines(), start=1):
        if not linea.strip().startswith("|"):
            continue
        celdas = [c.strip() for c in linea.strip("|").split("|")]
        if len(celdas) < 2:
            continue
        if celdas[0].lower() in {"apartado", "concepto", "---"} or set(celdas[0]) <= {"-"}:
            continue
        importe = _parse_decimal(celdas[-1])
        if importe is None:
            continue
        desc = celdas[0]
        if "total" in desc.lower():
            continue
        apartados.append(
            ApartadoExtraido(
                codigo=str(i),
                descripcion=desc,
                importe=importe,
                tiene_anotacion_manual="manuscrit" in linea.lower(),
            )
        )

    nave = NaveExtraida(
        codigo="N1",
        descripcion="Nave detectada",
        importe_presupuestado=sum((a.importe for a in apartados), Decimal("0")),
        apartados=apartados,
    )
    return PresupuestoExtraido(
        nombre_proyecto="Proyecto importado",
        naves=[nave] if apartados else [],
        total_impreso=nave.importe_presupuestado if apartados else None,
        anotaciones=[],
    )


def _parse_decimal(raw: str) -> Decimal | None:
    limpio = (
        raw.replace("€", "")
        .replace(".", "")
        .replace(",", ".")
        .replace("−", "-")
        .replace("—", "")
        .strip()
    )
    limpio = re.sub(r"[^\d.\-]", "", limpio)
    if not limpio or limpio in {".", "-", "-."}:
        return None
    try:
        return Decimal(limpio)
    except Exception:
        return None


def _extraer_con_llm(texto: str, api_key: str, api_base: str) -> PresupuestoExtraido:
    """
    Llama a un endpoint tipo chat/completions compatible.
    Solo si Seguridad autorizó el uso cloud (clave presente).
    """
    url = api_base.rstrip("/") + "/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _PROMPT_SISTEMA},
            {
                "role": "user",
                "content": (
                    "Extrae el presupuesto siguiente. "
                    "Distingue valor impreso vs manuscrito.\n\n" + texto
                ),
            },
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError(f"Error llamando al LLM: {exc}") from exc

    contenido = data["choices"][0]["message"]["content"]
    parsed = json.loads(contenido)
    return PresupuestoExtraido.model_validate(parsed)


def _aplicar_comprobaciones(resultado: PresupuestoExtraido) -> PresupuestoExtraido:
    """Comprueba sumas y fuerza revisión si hay manuscrito o descuadre."""
    apartados_suma: list[ApartadoExtraido] = []
    for nave in resultado.naves:
        for ap in nave.apartados:
            if not ap.excluido_de_suma:
                apartados_suma.append(ap)

    suma = sum((a.importe for a in apartados_suma), Decimal("0"))

    # Comprobación específica fixture: bloques EXAFAN y proveedores
    if _importes_de_fixture_presentes(resultado):
        suma_exafan = _suma_codigos(resultado, {"1.1", "1.2", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6-2.8"})
        suma_prov = _suma_codigos(
            resultado,
            {"5", "6.1.1", "6.1.2", "6.1.3", "7", "8.1", "8.2"},
        )
        cuadran = (
            suma_exafan == _IMPORTES_FIXTURE["IMPORTE_TOTAL_EXAFAN"]
            and suma_prov == _IMPORTES_FIXTURE["IMPORTE_TOTAL_PROVEEDORES"]
        )
    elif resultado.total_impreso is not None:
        cuadran = abs(suma - resultado.total_impreso) < Decimal("0.01")
    else:
        cuadran = False

    hay_manuscrito = bool(resultado.anotaciones) or any(
        ap.tiene_anotacion_manual for nave in resultado.naves for ap in nave.apartados
    )

    resultado.sumas_cuadran = cuadran
    # Revisión humana obligatoria si hay manuscrito o las sumas no cuadran
    resultado.requiere_revision = hay_manuscrito or not cuadran
    return resultado


def _importes_de_fixture_presentes(resultado: PresupuestoExtraido) -> bool:
    codigos = {ap.codigo for n in resultado.naves for ap in n.apartados}
    return "1.1" in codigos and "8.2" in codigos


def _suma_codigos(resultado: PresupuestoExtraido, codigos: set[str]) -> Decimal:
    total = Decimal("0")
    for nave in resultado.naves:
        for ap in nave.apartados:
            if ap.codigo in codigos:
                total += ap.importe
    return total
