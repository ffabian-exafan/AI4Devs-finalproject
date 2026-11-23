"""Casado contrato ↔ apartado de presupuesto (sugerencias; confirmación humana aparte)."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Contrato,
    ContratoApartado,
    LineaPdfCliente,
    LineaPdfClienteTarea,
    Nave,
    Presupuesto,
    Tarea,
)
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


def ids_apartados_enlazados(contrato: Contrato) -> list[int]:
    """Ids confirmados. Si aún no hay filas en contrato_apartado, vale el FK antiguo."""
    ids = [enlace.tarea_id for enlace in (contrato.enlaces_apartado or [])]
    if ids:
        return ids
    if contrato.tarea_apartado_id is not None:
        return [contrato.tarea_apartado_id]
    return []


def repartir_importe(total: Decimal, pesos: list[Decimal]) -> list[Decimal]:
    """Reparte `total` según `pesos`. El último tramo cierra el céntimo.

    [VERIFICAR] docs/readme.md no define cómo se reparte el precio de un
    contrato entre varios apartados. Se prorratea por la base de cada uno
    (montaje, o el importe del PDF si es solo gestión). Si todas son 0,
    a partes iguales.
    """
    n = len(pesos)
    if n == 0:
        return []
    cifra = Decimal(total).quantize(Decimal("0.01"))
    if n == 1:
        return [cifra]
    bases = [Decimal(peso) if Decimal(peso) > 0 else Decimal("0") for peso in pesos]
    suma = sum(bases, Decimal("0"))
    if suma == 0:
        bases = [Decimal("1")] * n
        suma = Decimal(n)
    partes: list[Decimal] = []
    acumulado = Decimal("0")
    for indice, peso in enumerate(bases):
        if indice == n - 1:
            partes.append((cifra - acumulado).quantize(Decimal("0.01")))
        else:
            trozo = (cifra * peso / suma).quantize(Decimal("0.01"))
            partes.append(trozo)
            acumulado += trozo
    return partes


def enlazar_contrato_apartado(
    db: Session,
    proyecto_id: int,
    contrato_id: int,
    tarea_apartado_ids: list[int],
    explicaciones: dict[int, str] | None = None,
    apartados_nuevos: list[tuple[int, str, Decimal, str]] | None = None,
) -> tuple[Contrato, list[Tarea]]:
    """
    Confirma los apartados que cubre el contrato.
    Sustituye el enlace anterior. Valida cada id en el backend.

    Un apartado escrito a mano cuelga de una línea del PDF del cliente que no
    está en el Excel. Lleva nombre, importe y explicación. El importe entra en
    la base y no se carga como descuadre del Excel.
    """
    textos = {clave: (valor or "").strip() for clave, valor in (explicaciones or {}).items()}
    ids = list(tarea_apartado_ids)

    contrato = (
        db.query(Contrato)
        .filter(Contrato.id == contrato_id, Contrato.proyecto_id == proyecto_id)
        .first()
    )
    if contrato is None:
        raise ValueError(f"Contrato {contrato_id} no encontrado en proyecto {proyecto_id}")

    lineas_vistas: set[int] = set()
    for linea_id, nombre, importe, explicacion in apartados_nuevos or []:
        if linea_id in lineas_vistas:
            raise ValueError("Esa línea del PDF ya está en este enlace")
        lineas_vistas.add(linea_id)
        linea = _linea_pdf_sin_excel(db, proyecto_id, linea_id)
        creado = _crear_apartado_de_contrato(db, contrato, linea, nombre, importe)
        ids.append(creado.id)
        textos[creado.id] = explicacion.strip()

    if not ids:
        raise ValueError("Indica al menos un apartado")

    hermanos = _apartados_y_subapartados(db, proyecto_id)
    padres = mapa_padres(hermanos)
    vistos: list[int] = []
    apartados: list[Tarea] = []
    for tarea_id in ids:
        if tarea_id in vistos:
            continue
        vistos.append(tarea_id)
        apartados.append(
            _validar_enlace(db, proyecto_id, contrato, tarea_id, padres, textos)
        )
    apartados.sort(key=lambda ap: (ap.presupuesto_id is None, ap.codigo, ap.id))
    _rechazar_solape(db, proyecto_id, contrato, apartados, padres)

    contrato.enlaces_apartado.clear()
    db.flush()
    for apartado in apartados:
        contrato.enlaces_apartado.append(
            ContratoApartado(
                tarea_id=apartado.id,
                explicacion=textos.get(apartado.id) if apartado.presupuesto_id is None else None,
            )
        )
    de_excel = [ap for ap in apartados if ap.presupuesto_id is not None]
    contrato.tarea_apartado_id = de_excel[0].id if de_excel else apartados[0].id
    db.add(contrato)
    db.commit()
    db.refresh(contrato)
    return contrato, apartados


def aparece_en_excel(descripcion: str, apartados_excel: list[Tarea]) -> bool:
    """True si el texto del contrato ya está cubierto por un apartado del Excel."""
    propio = _normalizar(descripcion)
    if len(propio) < 4:
        return False
    for apartado in apartados_excel:
        excel = _normalizar(f"{apartado.codigo} {apartado.descripcion}")
        if len(excel) < 4:
            continue
        if propio in excel or excel in propio:
            return True
        for raiz in _RAICES:
            if raiz in propio and raiz in excel:
                return True
    return False


def _linea_pdf_sin_excel(db: Session, proyecto_id: int, linea_id: int) -> LineaPdfCliente:
    """Línea de importe del PDF del cliente que no está contrastada con el Excel."""
    linea = db.get(LineaPdfCliente, linea_id)
    presupuesto = db.get(Presupuesto, linea.presupuesto_id) if linea is not None else None
    if (
        linea is None
        or presupuesto is None
        or presupuesto.proyecto_id != proyecto_id
        or presupuesto.formato != "pdf_cliente"
    ):
        raise ValueError(f"Línea {linea_id} no encontrada")
    if linea.tipo != "importe":
        raise ValueError("Solo se puede relacionar una línea de importe del PDF del cliente")
    if linea.apartado_gestion_id is not None:
        raise ValueError("Esa línea ya es un apartado de solo gestión")
    contrastada = (
        db.query(LineaPdfClienteTarea)
        .filter(
            LineaPdfClienteTarea.linea_id == linea.id,
            LineaPdfClienteTarea.es_sugerencia.is_(False),
        )
        .first()
    )
    if contrastada is not None:
        raise ValueError("Esa línea del PDF ya está en el Excel")
    return linea


def _crear_apartado_de_contrato(
    db: Session,
    contrato: Contrato,
    linea: LineaPdfCliente,
    nombre: str,
    importe: Decimal,
) -> Tarea:
    """Apartado escrito a mano sobre una línea del PDF del cliente. No entra en el Excel."""
    if contrato.nave_id is None:
        raise ValueError("El contrato no tiene nave donde colgar el apartado")
    codigo = f"pdf.{linea.id}"
    usado = (
        db.query(Tarea)
        .filter(Tarea.contrato_id == contrato.id, Tarea.codigo == codigo)
        .first()
    )
    if usado is not None:
        cuantos = (
            db.query(Tarea)
            .filter(Tarea.contrato_id == contrato.id, Tarea.codigo.like(f"pdf.{linea.id}.%"))
            .count()
        )
        codigo = f"pdf.{linea.id}.{cuantos + 1}"
    tarea = Tarea(
        nave_id=contrato.nave_id,
        presupuesto_id=None,
        contrato_id=contrato.id,
        tarea_padre_id=None,
        contratista_id=contrato.contratista_id,
        codigo=codigo,
        nivel="apartado",
        descripcion=nombre.strip(),
        importe_presupuestado=Decimal(importe).quantize(Decimal("0.01")),
        es_montaje=False,
        solo_gestion=False,
        linea_pdf_cliente_id=linea.id,
        tiene_anotacion_manual=False,
        estado_revision="confirmada",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(tarea)
    db.flush()
    return tarea


def _rechazar_solape(
    db: Session,
    proyecto_id: int,
    contrato: Contrato,
    apartados: list[Tarea],
    padres: dict[int, int | None],
) -> None:
    """Una línea de montaje no va en dos contratos, ni junto al bloque que la contiene.

    El apartado de solo gestión sigue entero y lo pueden compartir varios contratos.
    """
    de_excel = [
        ap for ap in apartados if ap.presupuesto_id is not None and not ap.solo_gestion
    ]
    if not de_excel:
        return

    hijos: dict[int, list[int]] = {}
    for hijo_id, padre_id in padres.items():
        if padre_id is not None:
            hijos.setdefault(padre_id, []).append(hijo_id)

    def descendientes(tarea_id: int) -> list[int]:
        pila = list(hijos.get(tarea_id, []))
        vistos: list[int] = []
        while pila:
            nodo = pila.pop()
            vistos.append(nodo)
            pila.extend(hijos.get(nodo, []))
        return vistos

    def ancestros(tarea_id: int) -> list[int]:
        cadena: list[int] = []
        actual = padres.get(tarea_id)
        while actual is not None:
            cadena.append(actual)
            actual = padres.get(actual)
        return cadena

    elegidos = {ap.id for ap in de_excel}
    for ap in de_excel:
        if any(anc in elegidos for anc in ancestros(ap.id)):
            raise ValueError(
                "No se puede enlazar un apartado y una línea que ya cuelga de él"
            )

    ocupados: dict[int, str] = {}
    otros = (
        db.query(Contrato)
        .options(
            joinedload(Contrato.contratista),
            joinedload(Contrato.enlaces_apartado),
        )
        .filter(Contrato.proyecto_id == proyecto_id, Contrato.id != contrato.id)
        .all()
    )
    for otro in otros:
        nombre = otro.contratista.nombre if otro.contratista else "otro contrato"
        for tarea_id in ids_apartados_enlazados(otro):
            tarea = db.get(Tarea, tarea_id)
            if tarea is None or tarea.solo_gestion:
                continue
            ocupados.setdefault(tarea_id, nombre)
            for desc in descendientes(tarea_id):
                ocupados.setdefault(desc, nombre)
    for ap in de_excel:
        if ap.id in ocupados:
            raise ValueError(f"Esa línea ya la cubre {ocupados[ap.id]}")
        for desc in descendientes(ap.id):
            if desc in ocupados:
                raise ValueError(f"Parte de ese apartado ya la cubre {ocupados[desc]}")


def _validar_enlace(
    db: Session,
    proyecto_id: int,
    contrato: Contrato,
    tarea_id: int,
    padres: dict[int, int | None],
    textos: dict[int, str],
) -> Tarea:
    apartado = db.get(Tarea, tarea_id)
    if apartado is None:
        raise ValueError(f"Apartado {tarea_id} no encontrado")
    if apartado.presupuesto_id is not None:
        return _validar_apartado(db, proyecto_id, tarea_id, padres)
    if apartado.pedido_id is not None:
        nave = db.get(Nave, apartado.nave_id)
        if nave is None or nave.proyecto_id != proyecto_id:
            raise ValueError("El apartado no pertenece a este proyecto")
        if apartado.nivel != "apartado" or apartado.tarea_padre_id is not None:
            raise ValueError("Solo se puede enlazar un apartado del pedido")
        if apartado.estado_revision != "confirmada":
            raise ValueError("La línea del pedido sigue pendiente de revisión")
        from app.services.codigo_contrato import pedido_de_codigo

        if pedido_de_codigo(contrato.codigo or "") != nave.codigo and (
            pedido_de_codigo(contrato.codigo_2 or "") != nave.codigo
        ):
            raise ValueError("El contrato no es de esta nave")
        return apartado
    if (
        apartado.contrato_id != contrato.id
        or apartado.tarea_padre_id is not None
        or apartado.nivel != "apartado"
    ):
        raise ValueError("Solo se puede enlazar un apartado raíz de este contrato")
    texto = textos.get(tarea_id, "")
    if len(texto) < 5:
        raise ValueError("La explicación del apartado del contrato es obligatoria")
    nave = db.get(Nave, apartado.nave_id)
    if nave is None or nave.proyecto_id != proyecto_id:
        raise ValueError("El apartado no pertenece a este proyecto")
    return apartado


def _validar_apartado(
    db: Session,
    proyecto_id: int,
    tarea_apartado_id: int,
    padres: dict[int, int | None],
) -> Tarea:
    apartado = db.get(Tarea, tarea_apartado_id)
    if apartado is None:
        raise ValueError(f"Apartado {tarea_apartado_id} no encontrado")
    if apartado.presupuesto_id is None:
        raise ValueError("La tarea indicada no proviene de un presupuesto")
    if apartado.codigo.startswith("descuento."):
        raise ValueError("Un descuento de cierre no es un apartado contratable")
    if apartado.solo_gestion and apartado.estado_revision != "confirmada":
        raise ValueError("El apartado de solo gestión sigue pendiente de revisión")
    if _es_recargo(apartado):
        raise ValueError("Un recargo no es un apartado contratable")

    es_raiz = padres.get(apartado.id) is None and apartado.nivel == "apartado"
    es_subapartado = padres.get(apartado.id) is not None and apartado.nivel in (
        "apartado",
        "subapartado",
    )
    if not (es_raiz or es_subapartado or apartado.es_montaje or apartado.solo_gestion):
        raise ValueError("Solo se puede enlazar un apartado o una línea de montaje")

    nave = db.get(Nave, apartado.nave_id)
    if nave is None or nave.proyecto_id != proyecto_id:
        raise ValueError("El apartado no pertenece a este proyecto")
    return apartado


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
        if padres.get(t.id) is None
        and not t.codigo.startswith("descuento.")
        and not (t.solo_gestion and t.estado_revision != "confirmada")
        and not _es_recargo(t)
    ]


def _es_recargo(tarea: Tarea) -> bool:
    """El recargo «Gestión» del Excel no es un apartado de contratista."""
    if tarea.solo_gestion:
        return False
    texto = (tarea.descripcion or "").lower()
    return "gestión" in texto or "gestion" in texto


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
