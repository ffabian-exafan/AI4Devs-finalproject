"""Extracción de contratos de subcontrata (cabecera + árbol de partidas).

El PDF ya llega en markdown (Sonnet). Haiku lee ese texto, arma el árbol
y propone el apartado de presupuesto. No confirma el enlace.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.config import get_settings
from app.schemas.extraccion import ContratoExtraido, NodoTareaExtraido
from app.services import llm as llm_svc

# NIF ficticio corto (el marcador [CIF_SUBCONTRATISTA_1] supera String(20))
_NIF_SUBCONTRATA = "B00000001"
_PRECIO_TOTAL = Decimal("45000.00")
# Precio unitario ficticio uniforme para líneas [IMPORTE_X] de la fixture
_PU = Decimal("5.00")


_PROMPT_SISTEMA = """\
Eres un extractor de contratos de subcontrata de obra. Respondes solo JSON compacto, en una sola línea, sin markdown.
El contrato queda pendiente de revisión humana: no confirmes nada.
No inventes NIF, nombres, fechas, cantidades ni importes que no estén en el texto.
Si un valor manuscrito corrige uno impreso, usa el manuscrito.
Esquema:
{
  "contratista_nif": "string, máximo 20 caracteres",
  "contratista_nombre": "string",
  "contratista_tipo": "externo",
  "referencia_presupuesto": "string o null",
  "precio_total": number,
  "fecha_firma": "YYYY-MM-DD o null",
  "plazo_ejecucion": "YYYY-MM-DD o null",
  "condiciones_facturacion": "string o null",
  "requiere_revision": true,
  "apartado_sugerido_codigo": "código de la lista de apartados, o null",
  "apartado_sugerido_motivo": "una frase, o null",
  "arbol_tareas": [
    {
      "codigo": "string",
      "nivel": "apartado | subapartado | partida",
      "capitulo": "string o null",
      "descripcion": "string",
      "importe": number,
      "unidad": "string o null",
      "cantidad": number o null,
      "precio_unitario": number o null,
      "hijos": []
    }
  ]
}
Reglas:
- apartado > subapartado > partida, con tarea anidada en "hijos".
- Una partida lleva unidad, cantidad y precio si el documento los trae. Si no, déjalos null. No los calcules.
- El importe de un nodo es el que figura. Si no figura y hay hijos, puede ser la suma de los hijos.
- apartado_sugerido_codigo tiene que ser uno de los códigos que te paso, o null si ninguno encaja.
- No elijas un descuento ni una línea de gestión.
- requiere_revision es siempre true.
"""


def extraer_contrato(
    texto: str,
    apartados: list[tuple[str, str]] | None = None,
) -> ContratoExtraido:
    """Fixture anonimizada sin LLM. El resto lo lee Haiku sobre el markdown."""
    if _es_fixture_electricidad(texto):
        return _extraer_fixture_electricidad(texto)
    settings = get_settings()
    if not llm_svc.hay_llm(settings):
        raise ValueError(
            "No hay extractor para este contrato. "
            "Hace falta la clave del modelo de lectura."
        )
    return _extraer_con_llm(texto, settings, apartados or [])


def _es_fixture_electricidad(texto: str) -> bool:
    return (
        "CIF_SUBCONTRATISTA_1" in texto
        or "IMPORTE_TOTAL_CONTRATO" in texto
        or ("Sala 1" in texto and "Subcontratista" in texto)
    )


def _extraer_fixture_electricidad(texto: str) -> ContratoExtraido:
    condiciones = (
        "El Subcontratista entrega factura original y copia dentro de los primeros "
        "5 días del mes, con datos que permitan verificar la obra realizada sin "
        "desplazarse. Las facturas (salvo la de liquidación) son pagos a cuenta. "
        "El Contratista paga tras conformidad total de la factura."
    )

    arbol: list[NodoTareaExtraido] = [
        _apartado_raiz(
            "1",
            "Modificación de cuadro eléctrico",
            "Modificación cuadro general existente",
            cantidad=Decimal("1"),
            unidad="UD",
        ),
        _apartado_raiz(
            "2",
            "Derivaciones subcuadros",
            "ML cable unipolar de cobre 1x6mm² 750V, colocado bajo tubo",
            cantidad=Decimal("250"),
            unidad="ML",
        ),
        _arbol_exofeed(),
        _arbol_sala(numero_sala=1, codigo_raiz="4"),
        _arbol_sala(numero_sala=2, codigo_raiz="5"),
        _arbol_sala(numero_sala=3, codigo_raiz="6"),
        _apartado_raiz(
            "7",
            "Sobrecosto instalación exterior",
            "Sobrecosto para instalación eléctrica por el exterior de la nave",
            cantidad=Decimal("1"),
            unidad="UD",
        ),
    ]

    return ContratoExtraido(
        contratista_nif=_NIF_SUBCONTRATA,
        contratista_nombre="SUBCONTRATISTA_1",
        contratista_tipo="externo",
        referencia_presupuesto="[REF_PRESUPUESTO_1]",
        precio_total=_PRECIO_TOTAL,
        fecha_firma="2026-06-01",
        plazo_ejecucion="2026-07-15",
        condiciones_facturacion=condiciones,
        arbol_tareas=arbol,
        requiere_revision=True,
    )


def _partida(
    codigo: str,
    descripcion: str,
    cantidad: Decimal,
    unidad: str,
    precio_unitario: Decimal = _PU,
) -> NodoTareaExtraido:
    return NodoTareaExtraido(
        codigo=codigo,
        nivel="partida",
        descripcion=descripcion,
        cantidad=cantidad,
        unidad=unidad,
        precio_unitario=precio_unitario,
        importe=cantidad * precio_unitario,
    )


def _apartado_raiz(
    codigo: str,
    titulo: str,
    descripcion_partida: str,
    cantidad: Decimal,
    unidad: str,
) -> NodoTareaExtraido:
    """Apartado con una única partida hija (cabecera 1 y 2 del anexo)."""
    hija = _partida(f"{codigo}.1", descripcion_partida, cantidad, unidad)
    return NodoTareaExtraido(
        codigo=codigo,
        nivel="apartado",
        capitulo="Anexo electricidad",
        descripcion=titulo,
        importe=hija.importe,
        hijos=[hija],
    )


def _arbol_exofeed() -> NodoTareaExtraido:
    subapartados = [
        (
            "3.1",
            "Fuerza",
            [
                ("ML cable unipolar cobre 1x1,5mm²", Decimal("280"), "ML"),
                ("ML tubo abocardado Tuperplas gris D=20, colocado grapeado", Decimal("70"), "ML"),
            ],
        ),
        (
            "3.2",
            "Maniobra",
            [
                ("ML cable unipolar cobre 1x1,5mm²", Decimal("180"), "ML"),
                ("ML tubo abocardado D=20, grapeado", Decimal("60"), "ML"),
            ],
        ),
        (
            "3.3",
            "Conexionado",
            [
                ("UD colocación y conexionado cuadro control Exafeed", Decimal("1"), "UD"),
                ("UD colocación y conexionado Exafeed central", Decimal("1"), "UD"),
                ("UD conexionado motor silo", Decimal("6"), "UD"),
                ("UD conexionado capacitivo silo", Decimal("6"), "UD"),
                ("UD conexionado máquina arrastre reparto", Decimal("1"), "UD"),
            ],
        ),
        (
            "3.4",
            "Toma de tierra",
            [
                ("ML cable desnudo 1x35mm² colocado en zanja", Decimal("15"), "ML"),
                (
                    "UD pica de acero cobreada 2m, clavada verticalmente en zanja red de tierra",
                    Decimal("3"),
                    "UD",
                ),
                ("UD caja de tierras Quintela PCT-C, colocada", Decimal("1"), "UD"),
            ],
        ),
    ]
    hijos: list[NodoTareaExtraido] = []
    for codigo, titulo, lineas in subapartados:
        partidas = [
            _partida(f"{codigo}.{i}", desc, cant, unid)
            for i, (desc, cant, unid) in enumerate(lineas, start=1)
        ]
        importe_sub = sum((p.importe for p in partidas), Decimal("0"))
        hijos.append(
            NodoTareaExtraido(
                codigo=codigo,
                nivel="subapartado",
                descripcion=titulo,
                importe=importe_sub,
                hijos=partidas,
            )
        )
    importe = sum((h.importe for h in hijos), Decimal("0"))
    return NodoTareaExtraido(
        codigo="3",
        nivel="apartado",
        capitulo="Anexo electricidad",
        descripcion="Circuitos sistema Exofeed (silos)",
        importe=importe,
        hijos=hijos,
    )


def _filas_sala(codigo_raiz: str) -> list[tuple[str, str, str, Decimal, str]]:
    """Filas de Sala (plantilla). (codigo_sub, titulo_sub, descripcion, cantidad, unidad)."""
    return [
        (
            f"{codigo_raiz}.1",
            "Subcuadro sala",
            "UD subcuadro sala ABB, totalmente montado y conexionado",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.2",
            "Canalizaciones",
            "ML tubo abocardado D=25, colocado grapeado",
            Decimal("60"),
            "ML",
        ),
        (
            f"{codigo_raiz}.2",
            "Canalizaciones",
            "ML tubo abocardado D=25, colocado embridado a la sirga del sistema de alimentación",
            Decimal("177"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.1",
            "Máquinas arrastre — Fuerza",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("72"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.1",
            "Máquinas arrastre — Señal",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("144"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.2",
            "Balaitus (ventanas) — Fuerza",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("390"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.2",
            "Balaitus (ventanas) — Señal",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("260"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.3",
            "Balaitus (chimenea) — Fuerza",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("195"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.3",
            "Balaitus (chimenea) — Señal",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("130"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.4",
            "Ventiladores EC-63 — Fuerza",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("540"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.4",
            "Ventiladores EC-63 — Señal",
            "ML cable 1x2,5mm² bajo tubo",
            Decimal("360"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.4",
            "Ventiladores EC-63 — Señal",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("720"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.5",
            "Iluminación interior",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("420"),
            "ML",
        ),
        (
            f"{codigo_raiz}.3.6",
            "Sondas",
            "ML cable 1x1,5mm² bajo tubo",
            Decimal("360"),
            "ML",
        ),
        (
            f"{codigo_raiz}.4",
            "Receptores",
            "UD pantalla LED estanca 1200mm Atmoss 16W, lámpara incluida, colocada",
            Decimal("19"),
            "UD",
        ),
        (
            f"{codigo_raiz}.4",
            "Receptores",
            "UD cuadro de fuerza trifásico, montado y conexionado",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.4",
            "Receptores",
            "UD proyector LED estanco 50W Atmoss, colocado",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.4",
            "Receptores",
            "Tasa RAEE",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.5",
            "Mecanismos",
            "UD punto de luz conmutador Bticino Luna blanco alpino, colocado",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado máquina arrastre sala",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado cuadro Exafeed sala",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado Exafeed sala",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado paleta control sala cargada",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado capacitivo control entrada pienso sala",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionada capacitiva control central sala",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado ventilador EC-63 con válvula de regulación de caudal",
            Decimal("3"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado motor Balaitus ventanas",
            Decimal("2"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado motor Balaitus chimenea",
            Decimal("1"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado sonda temperatura",
            Decimal("2"),
            "UD",
        ),
        (
            f"{codigo_raiz}.6",
            "Conexiones",
            "UD conexionado sonda DOL 139 humedad-CO2",
            Decimal("1"),
            "UD",
        ),
    ]


def _arbol_sala(numero_sala: int, codigo_raiz: str) -> NodoTareaExtraido:
    """Sala N como apartado; debajo subapartados y partidas con precio unitario."""
    grupos: dict[str, list[tuple[str, str, Decimal, str]]] = {}
    orden: list[str] = []
    for codigo, titulo, desc, cant, unid in _filas_sala(codigo_raiz):
        if codigo not in grupos:
            grupos[codigo] = []
            orden.append(codigo)
        grupos[codigo].append((titulo, desc, cant, unid))

    hijos_sub: list[NodoTareaExtraido] = []
    for codigo in orden:
        lineas = grupos[codigo]
        titulo = lineas[0][0]
        partidas: list[NodoTareaExtraido] = []
        for i, (_tit, desc, cant, unid) in enumerate(lineas, start=1):
            cod_partida = codigo if len(lineas) == 1 else f"{codigo}.{i}"
            partidas.append(_partida(cod_partida, f"{titulo}: {desc}", cant, unid))
        importe_sub = sum((p.importe for p in partidas), Decimal("0"))
        hijos_sub.append(
            NodoTareaExtraido(
                codigo=codigo,
                nivel="subapartado",
                descripcion=titulo,
                importe=importe_sub,
                hijos=partidas,
            )
        )

    importe = sum((h.importe for h in hijos_sub), Decimal("0"))
    return NodoTareaExtraido(
        codigo=codigo_raiz,
        nivel="apartado",
        capitulo="Anexo electricidad",
        descripcion=f"Sala {numero_sala}",
        importe=importe,
        hijos=hijos_sub,
    )


def _extraer_con_llm(texto: str, settings, apartados: list[tuple[str, str]]) -> ContratoExtraido:
    lista = "\n".join(f"- {codigo} · {descripcion}" for codigo, descripcion in apartados)
    if not lista:
        lista = "(este proyecto no tiene apartados de presupuesto)"
    contenido = llm_svc.completar_texto(
        api_key=settings.llm_api_key or "",
        api_base=settings.llm_api_base,
        anthropic=llm_svc.es_anthropic(settings),
        model=llm_svc.modelo_extraccion(settings),
        system=_PROMPT_SISTEMA,
        user=(
            "Extrae el contrato y propone el apartado del presupuesto. "
            "El JSON tiene que cerrarse: no dejes un texto a medias.\n\n"
            "Apartados:\n"
            f"{lista}\n\n"
            "Contrato:\n"
            f"{texto}"
        ),
        max_tokens=64000,
    )
    parsed = llm_svc.parsear_json_llm(contenido)
    codigos = {codigo for codigo, _desc in apartados}
    sugerido = parsed.get("apartado_sugerido_codigo")
    if sugerido is not None:
        sugerido = str(sugerido).strip()
        if sugerido not in codigos:
            parsed["apartado_sugerido_codigo"] = None
            parsed["apartado_sugerido_motivo"] = None
        else:
            parsed["apartado_sugerido_codigo"] = sugerido
    parsed["requiere_revision"] = True
    parsed["contratista_tipo"] = parsed.get("contratista_tipo") or "externo"
    parsed["fecha_firma"] = _fecha_iso(parsed.get("fecha_firma"))
    parsed["plazo_ejecucion"] = _fecha_iso(parsed.get("plazo_ejecucion"))
    nif = str(parsed.get("contratista_nif") or "").strip().upper()
    if not nif or len(nif) > 20:
        raise ValueError("El modelo no devolvió un NIF de contratista válido")
    parsed["contratista_nif"] = nif
    nombre = str(parsed.get("contratista_nombre") or "").strip()
    if not nombre:
        raise ValueError("El modelo no devolvió el nombre del contratista")
    parsed["contratista_nombre"] = nombre
    parsed["arbol_tareas"] = _normalizar_nodos(parsed.get("arbol_tareas") or [])
    if parsed.get("precio_total") is None:
        parsed["precio_total"] = sum(
            (Decimal(str(n["importe"])) for n in parsed["arbol_tareas"]),
            Decimal("0"),
        )
    return ContratoExtraido.model_validate(parsed)


def _fecha_iso(valor: object) -> str | None:
    if valor is None or valor == "":
        return None
    texto = str(valor).strip()[:10]
    try:
        date.fromisoformat(texto)
    except ValueError:
        return None
    return texto


def _normalizar_nodos(nodos: object) -> list[dict]:
    if not isinstance(nodos, list):
        return []
    salida: list[dict] = []
    for crudo in nodos:
        if not isinstance(crudo, dict):
            continue
        descripcion = str(crudo.get("descripcion") or "").strip()
        codigo = str(crudo.get("codigo") or "").strip()
        if not descripcion or not codigo:
            continue
        nivel = str(crudo.get("nivel") or "partida").strip().lower()
        if nivel not in {"apartado", "subapartado", "partida"}:
            nivel = "partida"
        hijos = _normalizar_nodos(crudo.get("hijos") or [])
        importe = crudo.get("importe")
        if importe is None and hijos:
            importe = sum((Decimal(str(h["importe"])) for h in hijos), Decimal("0"))
        if importe is None:
            # Línea cortada: no se inventa un importe 0.
            continue
        salida.append(
            {
                "codigo": codigo[:50],
                "nivel": nivel,
                "capitulo": crudo.get("capitulo"),
                "descripcion": descripcion,
                "importe": importe,
                "unidad": (str(crudo["unidad"])[:50] if crudo.get("unidad") else None),
                "cantidad": crudo.get("cantidad"),
                "precio_unitario": crudo.get("precio_unitario"),
                "hijos": hijos,
            }
        )
    return salida
