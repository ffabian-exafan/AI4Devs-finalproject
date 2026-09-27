"""Desviación por partida con la obra de referencia del handoff (datos ficticios)."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.services.desviaciones import desviacion_partida
from app.services.obra_referencia import APARTADOS, FACTURAS, contratos_iniciales
from app.services.desviaciones import calcular_obra
from app.services.vista_obra import construir_vista, estado_inicial


def _partida(calculo, codigo: str):
    for apartado in calculo.apartados:
        for partida in apartado.partidas:
            if partida.codigo == codigo:
                return partida
    raise AssertionError(codigo)


def _factura(calculo, factura_id: str):
    for factura in calculo.facturas:
        if factura.id == factura_id:
            return factura
    raise AssertionError(factura_id)


def test_formula_precio_y_medicion():
    precio = desviacion_partida(
        precio_presupuesto=Decimal("11.75"),
        precio_facturado=Decimal("14.20"),
        cantidad_facturada=Decimal("480"),
        cantidad_acumulada=Decimal("480"),
        medicion_presupuesto=Decimal("480"),
    )
    assert precio == Decimal("1176.00")

    medicion = desviacion_partida(
        precio_presupuesto=Decimal("39.7"),
        precio_facturado=Decimal("39.7"),
        cantidad_facturada=Decimal("1412"),
        cantidad_acumulada=Decimal("1412"),
        medicion_presupuesto=Decimal("1340"),
    )
    assert medicion == Decimal("2858.40")


def test_acumulado_ignora_el_duplicado():
    calculo = calcular_obra(APARTADOS, FACTURAS, contratos_iniciales())
    assert _partida(calculo, "05.01").desviacion == Decimal("1176.00")
    assert _partida(calculo, "08.01").desviacion == Decimal("2858.40")
    assert _partida(calculo, "02.01").cantidad_facturada == Decimal("33740")
    assert _factura(calculo, "e").kind == "dup"
    assert _factura(calculo, "a").kind == "bad"
    assert _factura(calculo, "h").kind == "ok"
    assert calculo.partidas_con_desvio == 2


def test_validar_duplicado_lo_suma():
    calculo = calcular_obra(APARTADOS, FACTURAS, contratos_iniciales(), {"e"})
    cubierta = _partida(calculo, "02.02")
    assert cubierta.cantidad_facturada == Decimal("3410")
    assert cubierta.exceso_medicion > 0
    assert _factura(calculo, "e").kind == "bad"


def test_vista_inicial_marca_electricidad_y_descuadres():
    vista = construir_vista(estado_inicial())
    assert vista.nav_incidencias == 3
    assert vista.resumen_obras.startswith("5 obras")
    electro = next(f for f in vista.contratos.filas if f.id == 4)
    assert electro.supera is True
    assert "sobre presupuesto" in electro.diferencia
    assert electro.asociado is False
    assert "07 · Alimentación" in vista.contratos.sin_contrato
    tipos = [a.tipo for a in vista.control.alertas]
    assert "Medición excedida" in tipos
    assert "Posible duplicado" in tipos
    slat = next(a for a in vista.control.alertas if a.tipo == "Medición excedida")
    assert slat.importe.startswith("+")
    assert "2.858" in slat.importe or "2.859" in slat.importe


def test_api_vista_obra_recalcula():
    client = TestClient(app)
    alta = client.get("/vista/obra")
    assert alta.status_code == 200, alta.text
    estado = alta.json()["estado"]
    estado["resueltas"] = {"a": "Reclamada", "b": "Desviación aprobada", "e": "Descartada"}
    baja = client.post("/vista/obra", json=estado)
    assert baja.status_code == 200, baja.text
    cuerpo = baja.json()
    assert cuerpo["nav_incidencias"] == 0
    assert cuerpo["obras"][0]["estado"] == "Cuadra"
    assert cuerpo["control"]["alertas"]
    assert all(a["destino"] == "contratos" for a in cuerpo["control"]["alertas"])
