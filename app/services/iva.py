"""IVA del contrato de proveedor frente a las líneas del pedido.

El precio cerrado del contrato lo trae con el 21 %. Las líneas del pedido van
sin IVA. Para compararlos se quita ese 21 %. En una obra marcada como
inversión del sujeto pasivo el precio ya se lee como base y no se toca.
"""

from decimal import Decimal, ROUND_HALF_UP

TIPO_IVA = Decimal("0.21")
_CENTIMO = Decimal("0.01")


def sin_iva(importe: Decimal) -> Decimal:
    """Base de un importe que incluye el 21 %."""
    return (Decimal(importe) / (Decimal(1) + TIPO_IVA)).quantize(
        _CENTIMO, rounding=ROUND_HALF_UP
    )
