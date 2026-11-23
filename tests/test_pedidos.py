"""Alta de obra desde pedidos ficticios."""

from pathlib import Path

from app.models.pedido import Pedido


def test_el_modelo_tiene_numero_unico_y_nave():
    assert Pedido.__tablename__ == "pedido"
    columnas = {col.name for col in Pedido.__table__.columns}
    assert {"proyecto_id", "nave_id", "numero", "rotulo", "estado_revision", "ruta_almacen"} <= columnas


def test_el_almacen_acepta_el_tipo_pedido():
    texto = Path("app/services/almacen.py").read_text(encoding="utf-8")
    assert '"pedido"' in texto
