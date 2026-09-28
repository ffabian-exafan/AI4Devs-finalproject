"""1.1 agrupa 1.1.1 y 1.1.2; un código sin padre sigue siendo apartado."""

from decimal import Decimal

from app.models import Tarea
from app.services.revision import _construir_arbol


def _fila(identificador: int, codigo: str) -> Tarea:
    return Tarea(
        id=identificador,
        nave_id=1,
        codigo=codigo,
        nivel="apartado",
        descripcion=codigo,
        importe_presupuestado=Decimal("10"),
        tiene_anotacion_manual=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )


def test_arbol_de_revision_anida_por_codigo():
    arbol = _construir_arbol(
        [
            _fila(1, "1.1"),
            _fila(2, "1.1.1"),
            _fila(3, "1.1.2"),
            _fila(4, "6.1.1"),
        ]
    )

    assert [n.codigo for n in arbol] == ["1.1", "6.1.1"]
    cubierta = arbol[0]
    assert [h.codigo for h in cubierta.hijos] == ["1.1.1", "1.1.2"]
    assert all(h.nivel == "subapartado" for h in cubierta.hijos)
    assert cubierta.hijos[0].tarea_padre_id == cubierta.id
