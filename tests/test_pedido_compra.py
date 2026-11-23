"""Lectura del pedido de serie 1. PDF generado en memoria, sin datos reales."""

from decimal import Decimal

from app.services.pedido_compra import leer_pedido
from tests.pdf_pedido import pdf_pedido


def test_entra_montaje_e_instalacion_con_el_importe_neto():
    contenido = pdf_pedido(
        [
            ("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "150,00", "0", "100,00"),
            ("SUST01000001", "INSTALACION SEGUN PRESUPUESTO ZZ000000", "1,00", "80,00", "0", "80,00"),
            ("SER01010001", "TRANSPORTE DE EJEMPLO", "1,00", "20,00", "0", "20,00"),
            ("MAT01010001", "MATERIAL DE EJEMPLO", "1,00", "50,00", "30", "35,00"),
            ("SER02010002", "COLOCACIÓN DE EJEMPLO", "2,00", "10,00", "0", "20,00"),
        ]
    )
    lectura = leer_pedido(contenido)
    assert lectura.cuadra is True
    assert lectura.numero == "1-10001"
    assert lectura.rotulo == "NAVE 1"
    assert lectura.aviso is None
    assert [(linea.descripcion, linea.importe) for linea in lectura.lineas] == [
        ("MONTAJE DE EJEMPLO", Decimal("100.00")),
        ("INSTALACION SEGUN PRESUPUESTO ZZ000000", Decimal("80.00")),
        ("COLOCACIÓN DE EJEMPLO", Decimal("20.00")),
    ]
    assert lectura.lineas[0].cantidad == Decimal("1.00")
    assert lectura.lineas[0].precio_unitario == Decimal("150.00")
    assert lectura.lineas[0].descuento_pct == Decimal("0.00")


def test_sin_cabecera_no_inventa_lineas():
    lectura = leer_pedido(pdf_pedido(
        [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
        cabecera=False,
    ))
    assert lectura.cuadra is False
    assert lectura.lineas == []
    assert lectura.aviso == "El pedido no trae la plantilla de Exafan"


def test_sin_numero_de_cinco_digitos_no_cuadra():
    lectura = leer_pedido(pdf_pedido(
        [("SER02010001", "MONTAJE DE EJEMPLO", "1,00", "10,00", "0", "10,00")],
        numero="SIN-NUMERO",
    ))
    assert lectura.cuadra is False
    assert lectura.lineas == []
