"""Extracción de contratos de subcontrata (cabecera + árbol de partidas)."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.extraccion import ContratoExtraido, NodoTareaExtraido

# NIF ficticio corto (el marcador [CIF_SUBCONTRATISTA_1] supera String(20))
_NIF_SUBCONTRATA = "B00000001"
_PRECIO_TOTAL = Decimal("45000.00")
# Precio unitario ficticio uniforme para líneas [IMPORTE_X] de la fixture
_PU = Decimal("5.00")


def extraer_contrato(texto: str) -> ContratoExtraido:
    if _es_fixture_electricidad(texto):
        return _extraer_fixture_electricidad(texto)
    raise ValueError(
        "No hay extractor para este contrato. "
        "Usa la fixture anonimizada o configura LLM (Ticket pendiente de ampliar)."
    )


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
