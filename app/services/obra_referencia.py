"""Obra de referencia del handoff. Importes y nombres ficticios, solo para la UI."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.services.desviaciones import (
    ApartadoBase,
    ContratoEntrada,
    FacturaEntrada,
    LineaEntrada,
    PartidaBase,
)

D = Decimal


def _p(
    codigo: str,
    descripcion: str,
    unidad: str,
    medicion: str,
    precio: str,
    marca: str | None = None,
) -> PartidaBase:
    return PartidaBase(
        codigo=codigo,
        descripcion=descripcion,
        unidad=unidad,
        medicion=D(medicion),
        precio=D(precio),
        marca_duda=marca,
    )


APARTADOS: list[ApartadoBase] = [
    ApartadoBase(
        "01",
        "Movimiento de tierras y cimentación",
        [
            _p("01.01", "Desbroce y explanación de parcela", "m²", "6200", "1.9"),
            _p("01.02", "Excavación de zanjas y pozos", "m³", "1480", "14.5"),
            _p("01.03", "Hormigón HA-25 en zapatas y riostras", "m³", "520", "112"),
            _p("01.04", "Solera de hormigón en pasillos", "m²", "1340", "11.47", "Medición"),
        ],
    ),
    ApartadoBase(
        "02",
        "Estructura metálica y cubierta",
        [
            _p("02.01", "Estructura de acero S275 en pórticos", "kg", "48200", "2.35"),
            _p("02.02", "Panel sándwich de cubierta 40 mm", "m²", "3150", "22.9"),
            _p("02.03", "Canalones y bajantes", "ml", "420", "24.3"),
        ],
    ),
    ApartadoBase(
        "03",
        "Cerramientos y aislamiento",
        [
            _p("03.01", "Panel de hormigón prefabricado", "m²", "1650", "38.4"),
            _p("03.02", "Aislamiento de poliuretano proyectado", "m²", "2980", "11.7"),
        ],
    ),
    ApartadoBase(
        "04",
        "Instalación eléctrica",
        [
            _p("04.01", "Cuadro general y protecciones", "ud", "1", "9800"),
            _p("04.02", "Luminarias LED estancas", "ud", "164", "112"),
            _p("04.03", "Cableado y bandejas", "PA", "1", "26732", "Unidad"),
        ],
    ),
    ApartadoBase(
        "05",
        "Fontanería y bebederos",
        [
            _p("05.01", "Bebedero chupete inox", "ud", "480", "11.75"),
            _p("05.02", "Tubería PE 32 mm", "m", "1250", "2.1"),
            _p("05.03", "Depósito de agua 10 m³ y dosificador", "ud", "1", "8389"),
            _p("05.04", "Mano de obra de montaje", "h", "510", "32"),
        ],
    ),
    ApartadoBase(
        "06",
        "Ventilación y climatización",
        [
            _p("06.01", "Ventanas de entrada de aire", "ud", "96", "215"),
            _p("06.02", 'Extractores de 50"', "ud", "12", "1840"),
            _p("06.03", "Panel de refrigeración evaporativa", "m²", "84", "208.5"),
        ],
    ),
    ApartadoBase(
        "07",
        "Alimentación (silos y transporte)",
        [
            _p("07.01", "Silo de chapa galvanizada 25 t", "ud", "4", "7900"),
            _p("07.02", "Transporte de pienso por cadena", "ml", "640", "51.9"),
        ],
    ),
    ApartadoBase(
        "08",
        "Slats y fosos de purines",
        [
            _p("08.01", "Slat de hormigón para engorde", "m²", "1340", "39.7"),
            _p("08.02", "Foso de purines en hormigón armado", "m³", "610", "107"),
            _p("08.03", "Transporte y colocación", "ud", "1", "1970"),
        ],
    ),
]


def _presupuesto(indice: int) -> Decimal:
    total = Decimal(0)
    for partida in APARTADOS[indice].partidas:
        total += (partida.medicion * partida.precio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return total


def _contratado(indice: int, delta: str) -> Decimal:
    return (_presupuesto(indice) + D(delta)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


# delta sobre el presupuesto del apartado de origen (importe cerrado del contrato).
_CONTRATOS_BASE: list[dict] = [
    {
        "id": 1,
        "gremio": "Excavaciones Gállego, S.L.",
        "archivo": "Contrato_movimiento_tierras.pdf",
        "origen": 0,
        "delta": "-1500",
        "confianza": 97,
        "motivo": "Objeto: excavación, explanación y cimentación de naves. Coincide con 4 de 4 partidas.",
        "aviso": None,
        "asociado": True,
    },
    {
        "id": 2,
        "gremio": "Estructuras Metálicas Zuera",
        "archivo": "EMZ_contrato_nave_Lacasa.pdf",
        "origen": 1,
        "delta": "-2950",
        "confianza": 96,
        "motivo": "Suministro y montaje de estructura S275 y panel de cubierta. Coincide con 3 de 3 partidas.",
        "aviso": None,
        "asociado": True,
    },
    {
        "id": 3,
        "gremio": "Aislamientos Ebro",
        "archivo": "Contrato_AE_cerramientos.pdf",
        "origen": 2,
        "delta": "-800",
        "confianza": 94,
        "motivo": "Panel prefabricado y poliuretano proyectado. Coincide con 2 de 2 partidas.",
        "aviso": None,
        "asociado": True,
    },
    {
        "id": 4,
        "gremio": "Electro Monegros",
        "archivo": "Electro_Monegros_firmado.pdf",
        "origen": 3,
        "delta": "1400",
        "confianza": 93,
        "motivo": "Instalación eléctrica completa y alumbrado LED.",
        "aviso": "El importe contratado supera lo presupuestado en el apartado.",
        "asociado": False,
    },
    {
        "id": 5,
        "gremio": "Fontanería Cinco Villas",
        "archivo": "FCV_contrato_2026.pdf",
        "origen": 4,
        "delta": "0",
        "confianza": 91,
        "motivo": "Red de agua, bebederos y depósito con dosificador.",
        "aviso": None,
        "asociado": False,
    },
    {
        "id": 6,
        "gremio": "Montajes Técnicos Ebro",
        "archivo": "MTE_contrato_montajes.pdf",
        "origen": 5,
        "delta": "0",
        "confianza": 72,
        "motivo": "Menciona extractores y ventanas de entrada de aire, pero también «montaje de silos».",
        "aviso": "Revisa el alcance: el contrato podría cubrir parte de 07 · Alimentación.",
        "asociado": False,
    },
    {
        "id": 7,
        "gremio": "Prefabricados Aragón",
        "archivo": "Contrato_slats_fosos.pdf",
        "origen": 7,
        "delta": "-600",
        "confianza": 95,
        "motivo": "Slats de hormigón y fosos de purines. Coincide con 3 de 3 partidas.",
        "aviso": None,
        "asociado": True,
    },
]

IMPORTE_CONTRATO: dict[int, Decimal] = {
    fila["id"]: _contratado(fila["origen"], fila["delta"]) for fila in _CONTRATOS_BASE
}


def contratos_iniciales() -> list[ContratoEntrada]:
    return [
        ContratoEntrada(
            id=fila["id"],
            gremio=fila["gremio"],
            archivo=fila["archivo"],
            importe=IMPORTE_CONTRATO[fila["id"]],
            apartado_idx=fila["origen"],
            confianza=fila["confianza"],
            motivo=fila["motivo"],
            aviso=fila["aviso"],
            asociado=fila["asociado"],
        )
        for fila in _CONTRATOS_BASE
    ]


def ficha_contrato(contrato_id: int) -> dict:
    for fila in _CONTRATOS_BASE:
        if fila["id"] == contrato_id:
            return fila
    raise KeyError(contrato_id)


def _lin(codigo: str, cantidad: str, precio: str) -> LineaEntrada:
    return LineaEntrada(codigo, D(cantidad), D(precio))


# Orden de la bandeja (el cálculo reordena por fecha).
FACTURAS: list[FacturaEntrada] = [
    FacturaEntrada("a", "PA-26-0231", "Prefabricados Aragón", "22/09/2026", "2026-09-22", 7, [
        _lin("08.01", "1412", "39.7"),
        _lin("08.02", "300", "107"),
    ]),
    FacturaEntrada("b", "FCV-2026-066", "Fontanería Cinco Villas", "19/09/2026", "2026-09-19", 4, [
        _lin("05.01", "480", "14.2"),
        _lin("05.02", "1250", "2.1"),
        _lin("05.03", "1", "8389"),
    ]),
    FacturaEntrada("e", "EMZ-26/131", "Estructuras Metálicas Zuera", "18/09/2026", "2026-09-18", 1, [
        _lin("02.01", "13740", "2.35"),
        _lin("02.02", "1205", "22.9"),
    ]),
    FacturaEntrada("d", "EMZ-26/131", "Estructuras Metálicas Zuera", "12/09/2026", "2026-09-12", 1, [
        _lin("02.01", "13740", "2.35"),
        _lin("02.02", "1205", "22.9"),
    ]),
    FacturaEntrada("g", "EM-1044", "Electro Monegros", "10/09/2026", "2026-09-10", 3, [
        _lin("04.01", "1", "9800"),
        _lin("04.02", "60", "112"),
    ]),
    FacturaEntrada("f", "AE-0877", "Aislamientos Ebro", "02/09/2026", "2026-09-02", 2, [
        _lin("03.01", "1100", "38.4"),
    ]),
    FacturaEntrada("c", "EMZ-26/118", "Estructuras Metálicas Zuera", "29/08/2026", "2026-08-29", 1, [
        _lin("02.01", "20000", "2.35"),
        _lin("02.02", "1000", "22.9"),
    ]),
    FacturaEntrada("h", "F-2026-0412", "Excavaciones Gállego, S.L.", "11/07/2026", "2026-07-11", 0, [
        _lin("01.01", "6200", "1.9"),
        _lin("01.02", "1480", "14.5"),
        _lin("01.03", "520", "112"),
        _lin("01.04", "1340", "11.47"),
    ]),
]

PROYECTO = {
    "codigo": "OB-2026-014",
    "nombre": "Granja porcina de engorde · 2.400 plazas",
    "cliente": "Explotaciones Hnos. Lacasa",
    "ubicacion": "Ejea de los Caballeros (Zaragoza)",
    "especie": "porcino",
    "fase": "Ejecución",
}

# Resto del listado: cifras redondas de ejemplo, sin desglose.
OTRAS_OBRAS = [
    {
        "especie": "avicola",
        "nombre": "Nave avícola de puesta · 60.000 gallinas",
        "meta": "OB-2026-011 · Avícola Monegros · Sariñena",
        "presupuestado": "1284000",
        "facturado": "1048300",
        "fase": "Ejecución",
        "estado": "1 descuadre",
        "tono": "warning",
        "destino": "control",
    },
    {
        "especie": "porcino",
        "nombre": "Maternidad 1.200 cerdas",
        "meta": "OB-2026-009 · Agropecuaria del Cinca · Fraga",
        "presupuestado": "2150000",
        "facturado": "2089600",
        "fase": "Cierre",
        "estado": "Cuadra",
        "tono": "success",
        "destino": "control",
    },
    {
        "especie": "bovino",
        "nombre": "Cebadero de terneros · 800 plazas",
        "meta": "OB-2026-017 · Ganados Arbués · Tauste",
        "presupuestado": "612400",
        "facturado": "0",
        "fase": "Contratos",
        "estado": "Contratos 4/6",
        "tono": "info",
        "destino": "control",
    },
    {
        "especie": "avicola",
        "nombre": "Broilers · 2 naves 2.000 m²",
        "meta": "OB-2026-018 · Granja Sanz · Alcañiz",
        "presupuestado": "0",
        "facturado": "0",
        "fase": "Presupuesto",
        "estado": "Revisión IA",
        "tono": "brand",
        "destino": "presupuesto-parcial",
    },
]
