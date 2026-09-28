"""Agrupa códigos de presupuesto: 1.1 es padre de 1.1.1 y 1.1.2."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.tarea import Tarea


def padre_mas_especifico(codigo: str, codigos: set[str]) -> str | None:
    """Devuelve el código existente más largo que sea prefijo estricto de `codigo`.

    1.1.1 cuelga de 1.1 si 1.1 está en el conjunto. 6.1.1 no cuelga de nadie
    si 6.1 no existe: ese código ya es el apartado con importe.
    """
    mejor: str | None = None
    for candidato in codigos:
        if candidato == codigo:
            continue
        if not codigo.startswith(candidato + "."):
            continue
        if mejor is None or len(candidato) > len(mejor):
            mejor = candidato
    return mejor


def mapa_padres(tareas: list[Tarea]) -> dict[int, int | None]:
    """Usa tarea_padre_id si ya está guardado; si no, agrupa por código (1.1 → 1.1.1)."""
    if any(t.tarea_padre_id is not None for t in tareas):
        return {t.id: t.tarea_padre_id for t in tareas}

    id_por_codigo: dict[str, int] = {}
    for t in tareas:
        id_por_codigo.setdefault(t.codigo, t.id)
    codigos = set(id_por_codigo)
    mapa: dict[int, int | None] = {}
    for t in tareas:
        padre = padre_mas_especifico(t.codigo, codigos)
        mapa[t.id] = id_por_codigo[padre] if padre is not None else None
    return mapa


def debe_elevar_grupo(tienen_importe: list[bool]) -> bool:
    """Varias filas bajo el mismo prefijo forman un apartado si el precio no está en cada una.

    1.1.1 (con importe) y 1.1.2 (sin importe) → apartado 1.1.
    6.1.1, 6.1.2 y 6.1.3, cada una con importe → siguen siendo apartados.
    """
    if len(tienen_importe) < 2:
        return False
    return sum(1 for tiene in tienen_importe if tiene) < 2


def descripcion_apartado(codigo: str, descripciones: list[str]) -> str:
    cabezas: list[str] = []
    for texto in descripciones:
        limpio = texto.split("[VERIFICAR]")[0].strip()
        cabeza = limpio.split(" - ")[0].strip()
        if not cabeza:
            continue
        cabezas.append(cabeza.split()[0])
    if cabezas and all(c.casefold() == cabezas[0].casefold() for c in cabezas):
        return cabezas[0]
    return f"Apartado {codigo}"


def _tiene_importe_propio(tarea: Tarea) -> bool:
    return Decimal(tarea.importe_presupuestado) != 0


def asegurar_apartados_padre(db: Session, tareas: list[Tarea]) -> None:
    """Crea apartados que el extractor no trajo (1.1 sobre 1.1.1 y 1.1.2) y sube el importe."""
    if any(t.tarea_padre_id is not None for t in tareas):
        return

    codigos = {t.codigo for t in tareas}
    grupos: dict[str, list[Tarea]] = {}
    for tarea in tareas:
        partes = tarea.codigo.split(".")
        if len(partes) < 2:
            continue
        padre = ".".join(partes[:-1])
        # 2.2 y 2.3 son apartados distintos. Solo se eleva 1.1.1 → 1.1.
        if "." not in padre or padre in codigos:
            continue
        grupos.setdefault(padre, []).append(tarea)

    creados = False
    for codigo, miembros in grupos.items():
        tienen = [_tiene_importe_propio(m) for m in miembros]
        if not debe_elevar_grupo(tienen):
            continue
        con_importe = [m for m in miembros if _tiene_importe_propio(m)]
        importe = (
            Decimal(con_importe[0].importe_presupuestado)
            if len(con_importe) == 1
            else Decimal("0")
        )
        if len(con_importe) == 1:
            con_importe[0].importe_presupuestado = Decimal("0")
        base = miembros[0]
        apartado = Tarea(
            nave_id=base.nave_id,
            presupuesto_id=base.presupuesto_id,
            contrato_id=None,
            tarea_padre_id=None,
            contratista_id=None,
            codigo=codigo,
            nivel="apartado",
            capitulo=base.capitulo,
            descripcion=(
                descripcion_apartado(codigo, [m.descripcion for m in miembros])
                + (
                    ""
                    if importe != 0
                    else " [VERIFICAR] sin importe en el documento"
                )
            ),
            importe_presupuestado=importe,
            tiene_anotacion_manual=any(m.tiene_anotacion_manual for m in miembros),
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
        db.add(apartado)
        db.flush()
        for miembro in miembros:
            miembro.tarea_padre_id = apartado.id
            miembro.nivel = "subapartado"
        tareas.append(apartado)
        creados = True
    if creados:
        db.commit()
