"""Tipos compartidos para schemas (solo forma/tipos)."""

from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Serializa como number en JSON (como en docs/readme.md §4), no como string
Money = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v), return_type=float, when_used="json"),
]
