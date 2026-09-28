"""Casado contrato ↔ apartado de presupuesto (sugerencias; confirmación humana aparte)."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models import Contrato, Nave, Tarea
from app.schemas.casado import SugerenciaApartadoOut
from app.services.jerarquia import mapa_padres

# Umbral mínimo para devolver un candidato (0–1)
_CONFIANZA_MIN = Decimal("0.25")
_MAX_SUGERENCIAS = 3

# Raíces semánticas frecuentes en obra (MVP sin embeddings)
_RAICES = (
    "electr",
    "fontan",
    "calefacc",
    "ventil",
    "estructur",
    "cubiert",
    "aliment",
    "corral",
    "suel",
    "obra civil",
    "instalac",
)


def apartados_de_presupuesto(db: Session, proyecto_id: int) -> list[Tarea]:
    """Apartados raíz del presupuesto. Los descuentos de cierre no se ofrecen."""
    return _apartados_presupuesto(db, proyecto_id)


def sugerir_apartados_para_contrato(
    db: Session,
    contrato: Contrato,
    *,
    max_resultados: int = _MAX_SUGERENCIAS,
) -> list[SugerenciaApartadoOut]:
    """Propone apartados de presupuesto del mismo proyecto. No persiste el enlace."""
    apartados = _apartados_presupuesto(db, contrato.proyecto_id)
    if not apartados:
        return []

    texto = _texto_consulta_contrato(db, contrato)
    if not texto.strip():
        return []

    puntuados: list[tuple[Decimal, Tarea, str]] = []
    for ap in apartados:
        conf, motivo = _puntuar(texto, ap)
        if conf >= _CONFIANZA_MIN:
            puntuados.append((conf, ap, motivo))

    puntuados.sort(key=lambda x: (-x[0], x[1].codigo))
    salida: list[SugerenciaApartadoOut] = []
    modelo = _sugerencia_guardada(contrato, apartados)
    if modelo is not None:
        salida.append(modelo)
    for conf, ap, motivo in puntuados:
        if modelo is not None and ap.id == modelo.tarea_id:
            continue
        salida.append(
            SugerenciaApartadoOut(
                tarea_id=ap.id,
                codigo=ap.codigo,
                descripcion=ap.descripcion,
                confianza=conf,
                motivo=motivo,
            )
        )
        if len(salida) >= max_resultados:
            break
    return salida[:max_resultados]


def _sugerencia_guardada(
    contrato: Contrato,
    apartados: list[Tarea],
) -> SugerenciaApartadoOut | None:
    """La propuesta de la lectura queda en motivo_sugerencia como «codigo\\nmotivo»."""
    raw = (contrato.motivo_sugerencia or "").strip()
    if "\n" not in raw:
        return None
    codigo, motivo = raw.split("\n", 1)
    codigo = codigo.strip()
    apartado = next((ap for ap in apartados if ap.codigo == codigo), None)
    if apartado is None:
        return None
    puntos = contrato.confianza if contrato.confianza is not None else 75
    confianza = Decimal(puntos) / Decimal(100)
    if confianza > 1:
        confianza = Decimal(1)
    if confianza < 0:
        confianza = Decimal(0)
    return SugerenciaApartadoOut(
        tarea_id=apartado.id,
        codigo=apartado.codigo,
        descripcion=apartado.descripcion,
        confianza=confianza,
        motivo=motivo.strip() or "Propuesto al leer el contrato",
    )


def enlazar_contrato_apartado(
    db: Session,
    proyecto_id: int,
    contrato_id: int,
    tarea_apartado_id: int,
) -> tuple[Contrato, Tarea]:
    """
    Confirma el enlace contrato → apartado de presupuesto.
    Valida pertenencia al proyecto y que la tarea sea apartado de presupuesto.
    """
    contrato = (
        db.query(Contrato)
        .filter(Contrato.id == contrato_id, Contrato.proyecto_id == proyecto_id)
        .first()
    )
    if contrato is None:
        raise ValueError(f"Contrato {contrato_id} no encontrado en proyecto {proyecto_id}")

    apartado = db.get(Tarea, tarea_apartado_id)
    if apartado is None:
        raise ValueError(f"Apartado {tarea_apartado_id} no encontrado")
    if apartado.presupuesto_id is None:
        raise ValueError("La tarea indicada no proviene de un presupuesto")
    if apartado.nivel != "apartado" or apartado.tarea_padre_id is not None:
        raise ValueError("Solo se puede enlazar a una tarea de nivel 'apartado'")
    hermanos = _apartados_y_subapartados(db, proyecto_id)
    if mapa_padres(hermanos).get(apartado.id) is not None:
        raise ValueError("Solo se puede enlazar a un apartado, no a un subapartado")
    if apartado.codigo.startswith("descuento."):
        raise ValueError("Un descuento de cierre no es un apartado contratable")

    nave = db.get(Nave, apartado.nave_id)
    if nave is None or nave.proyecto_id != proyecto_id:
        raise ValueError("El apartado no pertenece a este proyecto")

    contrato.tarea_apartado_id = apartado.id
    db.add(contrato)
    db.commit()
    db.refresh(contrato)
    return contrato, apartado


def _apartados_y_subapartados(db: Session, proyecto_id: int) -> list[Tarea]:
    nave_ids = [
        n.id for n in db.query(Nave).filter(Nave.proyecto_id == proyecto_id).all()
    ]
    if not nave_ids:
        return []
    return (
        db.query(Tarea)
        .filter(
            Tarea.nave_id.in_(nave_ids),
            Tarea.presupuesto_id.isnot(None),
        )
        .order_by(Tarea.codigo, Tarea.id)
        .all()
    )


def _apartados_presupuesto(db: Session, proyecto_id: int) -> list[Tarea]:
    tareas = _apartados_y_subapartados(db, proyecto_id)
    padres = mapa_padres(tareas)
    return [
        t
        for t in tareas
        if padres.get(t.id) is None and not t.codigo.startswith("descuento.")
    ]


def _texto_consulta_contrato(db: Session, contrato: Contrato) -> str:
    contrato_full = (
        db.query(Contrato)
        .options(
            joinedload(Contrato.contratista),
            joinedload(Contrato.tareas),
        )
        .filter(Contrato.id == contrato.id)
        .first()
    )
    if contrato_full is None:
        return ""

    partes: list[str] = []
    if contrato_full.referencia_presupuesto:
        partes.append(contrato_full.referencia_presupuesto)
    if contrato_full.contratista is not None:
        partes.append(contrato_full.contratista.nombre)
    if contrato_full.condiciones_facturacion:
        partes.append(contrato_full.condiciones_facturacion[:200])

    for t in contrato_full.tareas or []:
        if t.tarea_padre_id is None:
            partes.append(t.descripcion)
            if t.capitulo:
                partes.append(t.capitulo)

    return " ".join(partes)


def _puntuar(texto_contrato: str, apartado: Tarea) -> tuple[Decimal, str]:
    tc = _normalizar(texto_contrato)
    etiqueta = f"{apartado.codigo} {apartado.descripcion}"
    if apartado.capitulo:
        etiqueta = f"{etiqueta} {apartado.capitulo}"
    ta = _normalizar(etiqueta)
    desc = _normalizar(apartado.descripcion)

    if not ta:
        return Decimal("0"), ""

    if desc and len(desc) >= 4 and desc in tc:
        return Decimal("0.92"), f"Coincide la descripción «{apartado.descripcion}»"

    for raiz in _RAICES:
        if raiz in ta and raiz in tc:
            return Decimal("0.85"), f"Misma familia de concepto («{raiz}…»)"

    tokens_c = _tokens(tc)
    tokens_a = _tokens(ta)
    if not tokens_a or not tokens_c:
        return Decimal("0"), ""

    inter = tokens_a & tokens_c
    if not inter:
        for a in tokens_a:
            for c in tokens_c:
                if len(a) >= 6 and len(c) >= 6 and (a[:6] == c[:6]):
                    return Decimal("0.55"), f"Tokens cercanos («{a}» ≈ «{c}»)"
        return Decimal("0"), ""

    jaccard = Decimal(len(inter)) / Decimal(len(tokens_a | tokens_c))
    conf = min(Decimal("0.80"), (jaccard * Decimal("1.5")).quantize(Decimal("0.01")))
    motivo = "Solape de términos: " + ", ".join(sorted(inter)[:4])
    return conf, motivo


def _normalizar(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9.\s]+", " ", sin_tildes)


def _tokens(texto: str) -> set[str]:
    return {t for t in texto.split() if len(t) >= 3}
