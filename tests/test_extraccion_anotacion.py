"""El LLM puede devolver valor_manuscrito null si no lee la cifra."""

from app.schemas.extraccion import PresupuestoExtraido
from app.services.extraccion import _aplicar_comprobaciones


def test_valor_manuscrito_nulo_no_rompe_la_validacion():
    extraido = PresupuestoExtraido.model_validate(
        {
            "nombre_proyecto": "Obra de ejemplo",
            "naves": [
                {
                    "codigo": "N1",
                    "descripcion": "Nave de ejemplo",
                    "apartados": [
                        {
                            "codigo": "1.1",
                            "descripcion": "Cubierta",
                            "importe": 100,
                        }
                    ],
                }
            ],
            "total_impreso": 100,
            "anotaciones": [
                {
                    "campo": f"fila.{i}.importe",
                    "valor_impreso": "100",
                    "valor_manuscrito": None,
                    "descripcion": "Cifra tachada; el valor a mano no se lee",
                }
                for i in range(4)
            ],
        }
    )

    assert len(extraido.anotaciones) == 4
    assert all(a.valor_manuscrito is None for a in extraido.anotaciones)
    revisado = _aplicar_comprobaciones(extraido)
    assert revisado.requiere_revision is True
