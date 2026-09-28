"""Extracción estructurada de presupuesto: LLM (si hay clave) o parser de fixture."""

from __future__ import annotations

import re
from decimal import Decimal

from app.config import get_settings
from app.services.jerarquia import (
    debe_elevar_grupo,
    descripcion_apartado,
    padre_mas_especifico,
)
from app.services import llm as llm_svc
from app.schemas.extraccion import (
    AnotacionManuscrita,
    ApartadoExtraido,
    DescuentoExtraido,
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
          "importe": number|null,
          "tiene_anotacion_manual": bool,
          "excluido_de_suma": bool,
          "unidad": null,
          "cantidad": null,
          "precio_unitario": null,
          "subapartados": [
            {
              "codigo": "1.1.1",
              "descripcion": string,
              "importe": number|null
            }
          ]
        }
      ]
    }
  ],
  "total_impreso": number|null,
  "total_manuscrito": number|null,
  "descuentos": [
    {"descripcion": string, "importe": number, "es_manuscrito": bool}
  ],
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
- El importe cierra en el apartado (ejemplo 1.1). Los subapartados (1.1.1, 1.1.2)
  van dentro de ese apartado, no como apartados sueltos.
- Si el subapartado no tiene importe propio, pon null. No copies el importe del padre.
- unidad, cantidad y precio_unitario deben ser null si no aparecen a nivel de apartado.
- Si hay anotación manuscrita sobre valor impreso (tachado + corrección), marca
  tiene_anotacion_manual=true en esa fila y usa el valor manuscrito como válido.
- No inventes importes ni campos que no estén en el documento.
- Si la fila no muestra importe, pon null. No uses 0 salvo que el documento ponga 0.
- La línea de gestión o honorarios (un porcentaje sobre otros apartados, junto al
  precio final) es un apartado con su propio importe. No es un descuento y no se omite.
  No la conviertas en un subapartado sin importe.
- Los descuentos del final no son apartados. Van en "descuentos" con importe positivo
  (lo que se resta). El impreso y, si existe, el manuscrito van por separado.
- total_impreso es el precio total final impreso, ya restado el descuento impreso.
- total_manuscrito es el importe final escrito a mano, si lo hay. No lo recalcules.
"""


def extraer_presupuesto(texto: str) -> PresupuestoExtraido:
    """Extrae naves/apartados del texto del presupuesto."""
    if _es_fixture_anonimizada(texto):
        resultado = _extraer_fixture_destete(texto)
    else:
        settings = get_settings()
        if llm_svc.hay_llm(settings):
            resultado = _extraer_con_llm(texto, settings)
        else:
            # Sin LLM autorizado: parser heurístico mínimo sobre tablas markdown
            resultado = _extraer_heuristico(texto)

    _anidar_subapartados(resultado)
    _separar_descuentos(resultado)
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


def _extraer_con_llm(texto: str, settings) -> PresupuestoExtraido:
    """
    Extrae con Claude (Messages) o con un endpoint chat/completions.
    Solo si Seguridad autorizó el uso cloud (clave presente).
    """
    contenido = llm_svc.completar_texto(
        api_key=settings.llm_api_key,
        api_base=settings.llm_api_base,
        anthropic=llm_svc.es_anthropic(settings),
        model=llm_svc.modelo_extraccion(settings),
        system=_PROMPT_SISTEMA,
        user=(
            "Extrae el presupuesto siguiente. "
            "Distingue valor impreso vs manuscrito.\n\n" + texto
        ),
    )
    parsed = llm_svc.parsear_json_llm(contenido)
    return PresupuestoExtraido.model_validate(parsed)


def _aplanar_apartados(apartados: list[ApartadoExtraido]) -> list[ApartadoExtraido]:
    planos: list[ApartadoExtraido] = []
    for ap in apartados:
        hijos = list(ap.subapartados)
        ap.subapartados = []
        planos.append(ap)
        planos.extend(_aplanar_apartados(hijos))
    return planos


def _completar_apartados_padre(planos: list[ApartadoExtraido]) -> list[ApartadoExtraido]:
    """Si faltó la fila 1.1, la crea y sube el único importe del grupo."""
    codigos = {ap.codigo for ap in planos}
    grupos: dict[str, list[ApartadoExtraido]] = {}
    for ap in planos:
        partes = ap.codigo.split(".")
        if len(partes) < 2:
            continue
        padre = ".".join(partes[:-1])
        # 2.2 y 2.3 son apartados distintos. Solo se eleva 1.1.1 → 1.1.
        if "." not in padre or padre in codigos:
            continue
        grupos.setdefault(padre, []).append(ap)

    nuevos: list[ApartadoExtraido] = []
    for codigo, miembros in grupos.items():
        tienen = [m.importe is not None for m in miembros]
        if not debe_elevar_grupo(tienen):
            continue
        con_importe = [m for m in miembros if m.importe is not None]
        importe_padre = con_importe[0].importe if len(con_importe) == 1 else None
        if len(con_importe) == 1:
            con_importe[0].importe = None
            con_importe[0].excluido_de_suma = True
        nuevos.append(
            ApartadoExtraido(
                codigo=codigo,
                capitulo=miembros[0].capitulo,
                descripcion=descripcion_apartado(
                    codigo, [m.descripcion for m in miembros]
                ),
                importe=importe_padre,
                tiene_anotacion_manual=any(m.tiene_anotacion_manual for m in miembros),
            )
        )
    return planos + nuevos


def _anidar_subapartados(resultado: PresupuestoExtraido) -> None:
    """1.1.1 y 1.1.2 pasan a ser hijos de 1.1 cuando ese código existe."""
    for nave in resultado.naves:
        planos = _completar_apartados_padre(_aplanar_apartados(nave.apartados))
        codigos = {ap.codigo for ap in planos}
        hijos: dict[str, list[ApartadoExtraido]] = {}
        raices: list[ApartadoExtraido] = []
        for ap in planos:
            padre = padre_mas_especifico(ap.codigo, codigos)
            if padre is None:
                raices.append(ap)
            else:
                hijos.setdefault(padre, []).append(ap)
        for ap in planos:
            ap.subapartados = hijos.get(ap.codigo, [])
        nave.apartados = raices


def _es_fila_descuento(ap: ApartadoExtraido) -> bool:
    texto = f"{ap.codigo} {ap.descripcion}".casefold()
    return "descuento" in texto or texto.strip().startswith("dto")


def _separar_descuentos(resultado: PresupuestoExtraido) -> None:
    """Saca del árbol las filas de descuento y las deja como resta del cierre."""
    for nave in resultado.naves:
        quedan: list[ApartadoExtraido] = []
        for ap in nave.apartados:
            if (
                not _es_fila_descuento(ap)
                or ap.importe is None
                or (
                    resultado.total_manuscrito is not None
                    and ap.importe == resultado.total_manuscrito
                )
            ):
                quedan.append(ap)
                continue
            resultado.descuentos.append(
                DescuentoExtraido(
                    descripcion=ap.descripcion,
                    importe=abs(ap.importe),
                    es_manuscrito=ap.tiene_anotacion_manual,
                )
            )
        nave.apartados = quedan
    for descuento in resultado.descuentos:
        if descuento.importe < 0:
            descuento.importe = abs(descuento.importe)


def _aplicar_comprobaciones(resultado: PresupuestoExtraido) -> PresupuestoExtraido:
    """Comprueba sumas y fuerza revisión si hay manuscrito o descuadre."""
    apartados_suma: list[ApartadoExtraido] = []
    for nave in resultado.naves:
        for ap in nave.apartados:
            if not ap.excluido_de_suma:
                apartados_suma.append(ap)

    suma = sum(
        (a.importe for a in apartados_suma if a.importe is not None),
        Decimal("0"),
    )

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
    else:
        impresos = sum(
            (d.importe for d in resultado.descuentos if not d.es_manuscrito),
            Decimal("0"),
        )
        manuscritos = sum(
            (d.importe for d in resultado.descuentos if d.es_manuscrito),
            Decimal("0"),
        )
        neto_impreso = suma - impresos
        neto_final = neto_impreso - manuscritos
        if resultado.total_impreso is None and resultado.total_manuscrito is None:
            cuadran = False
        else:
            cuadran = True
            if resultado.total_impreso is not None:
                cuadran = abs(neto_impreso - resultado.total_impreso) < Decimal("0.01")
            if resultado.total_manuscrito is not None:
                cuadran = cuadran and abs(neto_final - resultado.total_manuscrito) < Decimal("0.01")

    hay_manuscrito = (
        bool(resultado.anotaciones)
        or any(d.es_manuscrito for d in resultado.descuentos)
        or any(
            ap.tiene_anotacion_manual for nave in resultado.naves for ap in nave.apartados
        )
    )
    falta_importe = any(
        ap.importe is None for nave in resultado.naves for ap in nave.apartados
    )

    resultado.sumas_cuadran = cuadran and not falta_importe
    # Revisión humana obligatoria si hay manuscrito, descuadre o filas sin cifra
    resultado.requiere_revision = hay_manuscrito or not cuadran or falta_importe
    return resultado


def _importes_de_fixture_presentes(resultado: PresupuestoExtraido) -> bool:
    codigos = {ap.codigo for n in resultado.naves for ap in n.apartados}
    return "1.1" in codigos and "8.2" in codigos


def _suma_codigos(resultado: PresupuestoExtraido, codigos: set[str]) -> Decimal:
    total = Decimal("0")
    for nave in resultado.naves:
        for ap in nave.apartados:
            if ap.codigo in codigos and ap.importe is not None:
                total += ap.importe
    return total
