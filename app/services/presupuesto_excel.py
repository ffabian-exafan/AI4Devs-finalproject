"""Alta de obra desde Excel Expertis y contraste con el PDF del cliente."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LineaPdfCliente, LineaPdfClienteTarea, Nave, Presupuesto, Proyecto, Tarea
from app.schemas.presupuesto import (
    ApartadoExcelOut,
    AvisoCuadreOut,
    ContrastarClienteOut,
    DescuentoContrasteOut,
    ImporteClienteOut,
    ImportarExcelOut,
    ImportesClienteOut,
    SugerenciaContrasteOut,
)
from app.services import almacen as almacen_svc
from app.services import extraccion as extraccion_svc
from app.services import llm as llm_svc
from app.services.casado import _apartados_presupuesto
from app.services.excel_expertis import (
    ExcelLeido,
    NodoExcel,
    _normalizar,
    _titulo_montaje,
    aplicar_relacion_montaje,
    asignar_montaje_por_nombre,
    leer_excel_expertis,
    lineas_y_productos_montaje,
)
from app.services.ingesta import leer_presupuesto
from app.services.jerarquia import mapa_padres

# [VERIFICAR] el Excel no dice si la obra es llave en mano o reforma.
_TIPO_OBRA = "llave_en_mano"
_EXTENSIONES = (".xlsx", ".xlsm")


def importar_presupuestos_excel(
    db: Session,
    nombre: str,
    ficheros: list[tuple[str, bytes]],
) -> ImportarExcelOut:
    """Crea la obra a partir de uno o varios Excel. Cada fichero es un apartado."""
    nombre_obra = nombre.strip()
    if not nombre_obra:
        raise ValueError("Falta el nombre de la obra")
    if not ficheros:
        raise ValueError("Falta el fichero")
    almacen_svc.exigir_lote_distinto(ficheros)

    preparados = [
        (*_preparar(nombre_f, contenido), contenido) for nombre_f, contenido in ficheros
    ]

    proyecto = Proyecto(
        nombre=nombre_obra[:255],
        tipo=_TIPO_OBRA,
        estado="pendiente_revision",
        fase="Presupuesto",
    )
    db.add(proyecto)
    db.flush()

    nave = Nave(
        proyecto_id=proyecto.id,
        codigo="01",
        descripcion=nombre_obra[:255],
        importe_presupuestado=Decimal("0"),
    )
    db.add(nave)
    db.flush()

    apartados: list[ApartadoExcelOut] = []
    presupuesto_ids: list[int] = []
    avisos: list[AvisoCuadreOut] = []
    partidas = 0
    montaje = 0
    for indice, (nombre_f, leido, contenido) in enumerate(preparados, start=1):
        salida = _persistir_fichero(
            db,
            proyecto,
            nave,
            nombre_f,
            leido,
            contenido,
            codigo_apartado=f"{indice:02d}",
        )
        apartados.append(salida)
        presupuesto_ids.append(salida.presupuesto_id)
        partidas += salida.partidas
        montaje += salida.lineas_montaje
        avisos.extend(_avisos(leido))

    nave.importe_presupuestado = sum((a.importe for a in apartados), Decimal("0"))
    db.commit()
    return _respuesta(
        proyecto.id,
        presupuesto_ids,
        apartados,
        partidas,
        montaje,
        avisos,
    )


def anadir_presupuesto_excel(
    db: Session,
    proyecto_id: int,
    nombre_fichero: str,
    contenido: bytes,
) -> ImportarExcelOut:
    """Añade otro Excel a una obra ya creada."""
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    _exigir_fichero_nuevo(db, proyecto_id, "excel_expertis", nombre_fichero, contenido)

    nombre_f, leido = _preparar(nombre_fichero, contenido)
    nave = (
        db.query(Nave)
        .filter(Nave.proyecto_id == proyecto.id)
        .order_by(Nave.id)
        .first()
    )
    if nave is None:
        nave = Nave(
            proyecto_id=proyecto.id,
            codigo="01",
            descripcion=proyecto.nombre,
            importe_presupuestado=Decimal("0"),
        )
        db.add(nave)
        db.flush()

    codigo = f"{len(_apartados_presupuesto(db, proyecto.id)) + 1:02d}"
    salida = _persistir_fichero(
        db,
        proyecto,
        nave,
        nombre_f,
        leido,
        contenido,
        codigo_apartado=codigo,
    )
    proyecto.estado = "pendiente_revision"
    nave.importe_presupuestado = _suma_raices(db, nave.id)
    db.commit()
    return _respuesta(
        proyecto.id,
        [salida.presupuesto_id],
        [salida],
        salida.partidas,
        salida.lineas_montaje,
        _avisos(leido),
    )


def contrastar_presupuesto_cliente(
    db: Session,
    proyecto_id: int,
    contenido: bytes,
    nombre_fichero: str,
) -> ContrastarClienteOut:
    """Lee el PDF del cliente y deja cada importe para contrastarlo a mano. No crea partidas."""
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    subapartados = _subapartados_excel(db, proyecto_id)
    if not subapartados:
        raise ValueError("La obra no tiene subapartados de Excel con los que contrastar")
    _exigir_fichero_nuevo(db, proyecto_id, "pdf_cliente", nombre_fichero, contenido)

    leido = leer_presupuesto(contenido, nombre_fichero)
    extraido = extraccion_svc.extraer_presupuesto(leido.texto)
    version = (
        db.query(Presupuesto)
        .filter(Presupuesto.proyecto_id == proyecto_id, Presupuesto.formato == "pdf_cliente")
        .count()
        + 1
    )
    presupuesto = Presupuesto(
        proyecto_id=proyecto_id,
        version=version,
        fichero_origen=nombre_fichero[:512],
        estado_extraccion="extraido",
        es_escaneado=leido.es_escaneado,
        formato="pdf_cliente",
    )
    db.add(presupuesto)
    db.flush()
    presupuesto.ruta_almacen = almacen_svc.guardar(
        proyecto_id,
        "presupuesto",
        presupuesto.id,
        nombre_fichero,
        contenido,
    )

    sugerencias, descuentos = _construir_sugerencias(extraido)
    _persistir_lineas(db, presupuesto.id, sugerencias, descuentos)
    _proponer_relaciones(db, proyecto_id, presupuesto.id)
    db.commit()
    return _salida_contraste(db, presupuesto)


def obtener_contraste_cliente(db: Session, proyecto_id: int) -> ContrastarClienteOut:
    """Devuelve el último PDF del cliente. Si aún no hay líneas, las lee del fichero guardado."""
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    presupuesto = _ultimo_pdf_cliente(db, proyecto_id)
    if presupuesto is None:
        raise ValueError("Esta obra no tiene PDF del cliente")
    cambio = False
    if not _hay_lineas_importe(db, presupuesto.id):
        ruta = almacen_svc.abrir_si_existe(presupuesto.ruta_almacen)
        if ruta is None:
            raise ValueError("El PDF del cliente no está guardado")
        contenido = ruta.read_bytes()
        leido = leer_presupuesto(contenido, presupuesto.fichero_origen)
        extraido = extraccion_svc.extraer_presupuesto(leido.texto)
        sugerencias, descuentos = _construir_sugerencias(extraido)
        _persistir_lineas(db, presupuesto.id, sugerencias, descuentos)
        cambio = True
    if _proponer_relaciones(db, proyecto_id, presupuesto.id):
        cambio = True
    if cambio:
        db.commit()
    return _salida_contraste(db, presupuesto)


def contraste_guardado(db: Session, proyecto_id: int) -> ContrastarClienteOut | None:
    """Líneas ya guardadas. No vuelve a leer el PDF."""
    presupuesto = _ultimo_pdf_cliente(db, proyecto_id)
    if presupuesto is None or not _hay_lineas_importe(db, presupuesto.id):
        return None
    return _salida_contraste(db, presupuesto)


def confirmar_importe_cliente(
    db: Session,
    proyecto_id: int,
    tarea_id: int,
    importe: Decimal,
) -> ImporteClienteOut:
    """Guarda el importe del contrato con el cliente en un subapartado Excel."""
    salida = confirmar_importes_cliente(db, proyecto_id, [tarea_id], importe)
    return salida.asignaciones[0]


def confirmar_importes_cliente(
    db: Session,
    proyecto_id: int,
    tarea_ids: list[int],
    importe: Decimal,
    linea_id: int | None = None,
) -> ImportesClienteOut:
    """Un importe del PDF puede cubrir varios subapartados. La cifra se reparte según su presupuesto."""
    if not tarea_ids:
        raise ValueError("Elige al menos un subapartado")
    vistos: list[int] = []
    for tarea_id in tarea_ids:
        if tarea_id not in vistos:
            vistos.append(tarea_id)
    tareas = [_exigir_subapartado(db, proyecto_id, tarea_id) for tarea_id in vistos]
    _rechazar_solape(db, tareas)
    partes = _repartir_importe(
        Decimal(importe),
        [Decimal(tarea.importe_presupuestado or 0) for tarea in tareas],
    )
    for tarea, parte in zip(tareas, partes):
        tarea.importe_contrato_cliente = parte
    if linea_id is not None:
        _enlazar_linea(db, proyecto_id, linea_id, vistos)
    db.commit()
    for tarea in tareas:
        db.refresh(tarea)
    return ImportesClienteOut(
        asignaciones=[
            ImporteClienteOut(
                tarea_id=tarea.id,
                importe_contrato_cliente=tarea.importe_contrato_cliente,
            )
            for tarea in tareas
        ]
    )


def _exigir_fichero_nuevo(
    db: Session,
    proyecto_id: int,
    formato: str,
    nombre: str,
    contenido: bytes,
) -> None:
    rutas = [
        fila.ruta_almacen
        for fila in db.query(Presupuesto)
        .filter(Presupuesto.proyecto_id == proyecto_id, Presupuesto.formato == formato)
        .all()
    ]
    almacen_svc.exigir_distinto(contenido, nombre, rutas)


def _ultimo_pdf_cliente(db: Session, proyecto_id: int) -> Presupuesto | None:
    return (
        db.query(Presupuesto)
        .filter(
            Presupuesto.proyecto_id == proyecto_id,
            Presupuesto.formato == "pdf_cliente",
        )
        .order_by(Presupuesto.id.desc())
        .first()
    )


def _hay_lineas_importe(db: Session, presupuesto_id: int) -> bool:
    return (
        db.query(LineaPdfCliente.id)
        .filter(
            LineaPdfCliente.presupuesto_id == presupuesto_id,
            LineaPdfCliente.tipo == "importe",
        )
        .first()
        is not None
    )


def _construir_sugerencias(extraido) -> tuple[list[SugerenciaContrasteOut], list[DescuentoContrasteOut]]:
    lineas = [
        apartado
        for nave in extraido.naves
        for apartado in nave.apartados
        if apartado.importe is not None
        and not apartado.excluido_de_suma
        and not apartado.codigo.startswith("descuento")
    ]
    lineas_pdf = [
        SugerenciaContrasteOut(
            descripcion_pdf=apartado.descripcion,
            codigo_pdf=apartado.codigo,
            importe_pdf=apartado.importe or Decimal("0"),
        )
        for apartado in lineas
    ]
    sugerencias = _repartir_cierre(lineas_pdf, extraido)
    descuentos = [
        DescuentoContrasteOut(
            descripcion=descuento.descripcion,
            importe=descuento.importe,
            es_manuscrito=descuento.es_manuscrito,
        )
        for descuento in extraido.descuentos
    ]
    return sugerencias, descuentos


def _persistir_lineas(
    db: Session,
    presupuesto_id: int,
    sugerencias: list[SugerenciaContrasteOut],
    descuentos: list[DescuentoContrasteOut],
) -> None:
    ids = [
        fila.id
        for fila in db.query(LineaPdfCliente)
        .filter(LineaPdfCliente.presupuesto_id == presupuesto_id)
        .all()
    ]
    if ids:
        db.execute(delete(LineaPdfClienteTarea).where(LineaPdfClienteTarea.linea_id.in_(ids)))
        db.execute(delete(LineaPdfCliente).where(LineaPdfCliente.presupuesto_id == presupuesto_id))
    orden = 0
    for sugerencia in sugerencias:
        db.add(
            LineaPdfCliente(
                presupuesto_id=presupuesto_id,
                orden=orden,
                tipo="importe",
                codigo=(sugerencia.codigo_pdf or "")[:128],
                descripcion=(sugerencia.descripcion_pdf or "Importe")[:512],
                importe=Decimal(sugerencia.importe_pdf),
                importe_bruto=(
                    Decimal(sugerencia.importe_bruto)
                    if sugerencia.importe_bruto is not None
                    else None
                ),
                es_manuscrito=False,
            )
        )
        orden += 1
    for descuento in descuentos:
        db.add(
            LineaPdfCliente(
                presupuesto_id=presupuesto_id,
                orden=orden,
                tipo="descuento",
                codigo="",
                descripcion=(descuento.descripcion or "Descuento")[:512],
                importe=Decimal(descuento.importe),
                importe_bruto=None,
                es_manuscrito=bool(descuento.es_manuscrito),
            )
        )
        orden += 1
    db.flush()


def _salida_contraste(db: Session, presupuesto: Presupuesto) -> ContrastarClienteOut:
    filas = (
        db.query(LineaPdfCliente)
        .filter(LineaPdfCliente.presupuesto_id == presupuesto.id)
        .order_by(LineaPdfCliente.orden, LineaPdfCliente.id)
        .all()
    )
    ids = [fila.id for fila in filas if fila.tipo == "importe"]
    pares = (
        db.query(LineaPdfClienteTarea)
        .filter(LineaPdfClienteTarea.linea_id.in_(ids))
        .all()
        if ids
        else []
    )
    confirmados: dict[int, list[int]] = {}
    propuestos: dict[int, list[int]] = {}
    for par in pares:
        destino = propuestos if par.es_sugerencia else confirmados
        destino.setdefault(par.linea_id, []).append(par.tarea_id)
    sugerencias: list[SugerenciaContrasteOut] = []
    descuentos: list[DescuentoContrasteOut] = []
    for fila in filas:
        if fila.tipo == "descuento":
            descuentos.append(
                DescuentoContrasteOut(
                    descripcion=fila.descripcion,
                    importe=fila.importe,
                    es_manuscrito=fila.es_manuscrito,
                )
            )
            continue
        cerrados = confirmados.get(fila.id, [])
        propuestas = propuestos.get(fila.id, [])
        if cerrados:
            tareas = cerrados
            confirmada = True
            sugerida = False
        else:
            tareas = propuestas
            confirmada = False
            sugerida = bool(propuestas)
        sugerencias.append(
            SugerenciaContrasteOut(
                id=fila.id,
                descripcion_pdf=fila.descripcion,
                codigo_pdf=fila.codigo,
                importe_pdf=fila.importe,
                importe_bruto=fila.importe_bruto,
                tarea_ids=tareas,
                confirmada=confirmada,
                sugerida=sugerida,
            )
        )
    return ContrastarClienteOut(
        presupuesto_id=presupuesto.id,
        sugerencias=sugerencias,
        descuentos=descuentos,
    )


def _enlazar_linea(db: Session, proyecto_id: int, linea_id: int, tarea_ids: list[int]) -> None:
    linea = db.get(LineaPdfCliente, linea_id)
    if linea is None or linea.tipo != "importe":
        raise ValueError("Línea del PDF no encontrada")
    presupuesto = db.get(Presupuesto, linea.presupuesto_id)
    if (
        presupuesto is None
        or presupuesto.proyecto_id != proyecto_id
        or presupuesto.formato != "pdf_cliente"
    ):
        raise ValueError("La línea no pertenece a este proyecto")
    hermanas = [
        fila.id
        for fila in db.query(LineaPdfCliente)
        .filter(LineaPdfCliente.presupuesto_id == presupuesto.id)
        .all()
    ]
    db.execute(delete(LineaPdfClienteTarea).where(LineaPdfClienteTarea.linea_id == linea.id))
    if hermanas and tarea_ids:
        db.execute(
            delete(LineaPdfClienteTarea).where(
                LineaPdfClienteTarea.linea_id.in_(hermanas),
                LineaPdfClienteTarea.tarea_id.in_(tarea_ids),
            )
        )
    for tarea_id in tarea_ids:
        db.add(
            LineaPdfClienteTarea(
                linea_id=linea.id,
                tarea_id=tarea_id,
                es_sugerencia=False,
            )
        )


@dataclass(frozen=True)
class _BloqueContraste:
    id: int
    padre_id: int | None
    ruta: str


_PROMPT_CONTRASTE = (
    "Relaciona cada línea del PDF del cliente con los bloques del Excel que cubre. "
    'Responde solo JSON: {"relaciones": [{"linea": 0, "bloques": [1]}]}. '
    "linea y bloques son índices de las listas. "
    "Un bloque solo puede ir en una línea. "
    "No marques un bloque y lo que cuelga de él: el bloque ya incluye a los hijos. "
    "Si la línea habla del conjunto, marca el padre. Si habla de una parte, marca solo esa parte. "
    "Varios hermanos sí, cuando la línea cubre esas partes y no el padre. "
    "Guíate por el nombre. El importe no tiene que coincidir. "
    "Si no hay un bloque claro, devuelve bloques vacío. No inventes índices."
)


def _proponer_relaciones(db: Session, proyecto_id: int, presupuesto_id: int) -> bool:
    """Marca una primera relación. No escribe el importe ni da la línea por confirmada.

    Si no hay modelo, o no responde, se usa el nombre. No se repite si la línea
    ya tiene bloques o ya se intentó.
    """
    lineas = (
        db.query(LineaPdfCliente)
        .filter(
            LineaPdfCliente.presupuesto_id == presupuesto_id,
            LineaPdfCliente.tipo == "importe",
        )
        .order_by(LineaPdfCliente.orden, LineaPdfCliente.id)
        .all()
    )
    if not lineas:
        return False
    ids = [linea.id for linea in lineas]
    enlazadas = {
        fila.linea_id
        for fila in db.query(LineaPdfClienteTarea.linea_id)
        .filter(LineaPdfClienteTarea.linea_id.in_(ids))
        .all()
    }
    pendientes = [
        linea for linea in lineas if not linea.relacion_intentada and linea.id not in enlazadas
    ]
    if not pendientes:
        return False
    ocupados = {
        fila.tarea_id
        for fila in db.query(LineaPdfClienteTarea.tarea_id)
        .filter(LineaPdfClienteTarea.linea_id.in_(ids))
        .all()
    }
    libres = [bloque for bloque in _bloques_contraste(db, proyecto_id) if bloque.id not in ocupados]
    textos = [linea.descripcion for linea in pendientes]
    asignadas: dict[int, list[int]] = {}
    if libres and textos:
        relaciones = _relacionar_pdf_llm(textos, libres)
        if relaciones is None:
            relaciones = _relacionar_por_nombre(textos, libres)
        asignadas = _depurar_asignaciones(relaciones, textos, libres)
    for indice, linea in enumerate(pendientes):
        for tarea_id in asignadas.get(indice, []):
            db.add(
                LineaPdfClienteTarea(
                    linea_id=linea.id,
                    tarea_id=tarea_id,
                    es_sugerencia=True,
                )
            )
        linea.relacion_intentada = True
    db.flush()
    return True


def _bloques_contraste(db: Session, proyecto_id: int) -> list[_BloqueContraste]:
    nodos = _subapartados_excel(db, proyecto_id)
    if not nodos:
        return []
    presupuesto_ids = {nodo.presupuesto_id for nodo in nodos if nodo.presupuesto_id is not None}
    todas = (
        db.query(Tarea).filter(Tarea.presupuesto_id.in_(presupuesto_ids)).all()
        if presupuesto_ids
        else []
    )
    por_id = {tarea.id: tarea for tarea in todas}

    def ruta(nodo: Tarea) -> str:
        partes: list[str] = []
        actual: Tarea | None = nodo
        vistos: set[int] = set()
        while actual is not None and actual.id not in vistos:
            vistos.add(actual.id)
            texto = " ".join((actual.descripcion or "").split())
            if texto:
                partes.append(texto[:80])
            padre_id = actual.tarea_padre_id
            actual = por_id.get(padre_id) if padre_id else None
        return " / ".join(reversed(partes))[:240]

    return [
        _BloqueContraste(id=nodo.id, padre_id=nodo.tarea_padre_id, ruta=ruta(nodo))
        for nodo in nodos
    ]


def _relacionar_pdf_llm(
    lineas: list[str],
    bloques: list[_BloqueContraste],
) -> dict[int, list[int]] | None:
    """Índice de línea → índices de bloque. None si no hay modelo o la respuesta no vale."""
    settings = get_settings()
    if not llm_svc.hay_llm(settings):
        return None
    lista_bloques = "\n".join(f"{i}. {bloque.ruta}" for i, bloque in enumerate(bloques))
    lista_lineas = "\n".join(f"{i}. {nombre}" for i, nombre in enumerate(lineas))
    try:
        contenido = llm_svc.completar_texto(
            api_key=settings.llm_api_key or "",
            api_base=settings.llm_api_base,
            anthropic=llm_svc.es_anthropic(settings),
            model=llm_svc.modelo_extraccion(settings),
            system=_PROMPT_CONTRASTE,
            user=f"Bloques:\n{lista_bloques}\n\nLíneas:\n{lista_lineas}",
            max_tokens=4000,
        )
        parsed = llm_svc.parsear_json_llm(contenido)
    except (OSError, ValueError, TimeoutError):
        return None
    crudas = parsed.get("relaciones")
    if not isinstance(crudas, list):
        return None
    return _interpretar_relaciones(crudas, len(lineas), len(bloques))


def _interpretar_relaciones(crudas: list, n_lineas: int, n_bloques: int) -> dict[int, list[int]]:
    resultado: dict[int, list[int]] = {}
    for item in crudas:
        if not isinstance(item, dict):
            continue
        linea = _como_indice(item.get("linea"), n_lineas)
        if linea is None:
            continue
        vistos: list[int] = []
        for valor in _valores_bloque(item.get("bloques")):
            indice = _como_indice(valor, n_bloques)
            if indice is not None and indice not in vistos:
                vistos.append(indice)
        if vistos:
            resultado[linea] = vistos
    return resultado


def _valores_bloque(valor: object) -> list:
    if isinstance(valor, list):
        return valor
    if valor is None:
        return []
    return [valor]


def _como_indice(valor: object, tope: int) -> int | None:
    if isinstance(valor, bool) or valor is None or isinstance(valor, float):
        return None
    if isinstance(valor, int) or (isinstance(valor, str) and valor.strip().lstrip("-").isdigit()):
        indice = int(valor)
        if 0 <= indice < tope:
            return indice
    return None


def _relacionar_por_nombre(
    lineas: list[str],
    bloques: list[_BloqueContraste],
) -> dict[int, list[int]]:
    """Un bloque por línea, el de más palabras en común. Sin modelo no se confirma nada."""
    candidatos: list[tuple[int, int, int]] = []
    for i, linea in enumerate(lineas):
        for j, bloque in enumerate(bloques):
            puntos = _solape_nombre(linea, bloque.ruta)
            if puntos > 0:
                candidatos.append((puntos, i, j))
    candidatos.sort(key=lambda item: (item[0], -item[1], -item[2]), reverse=True)
    lineas_usadas: set[int] = set()
    bloques_usados: set[int] = set()
    salida: dict[int, list[int]] = {}
    for _puntos, i, j in candidatos:
        if i in lineas_usadas or j in bloques_usados:
            continue
        salida[i] = [j]
        lineas_usadas.add(i)
        bloques_usados.add(j)
    return salida


def _depurar_asignaciones(
    cruda: dict[int, list[int]],
    lineas: list[str],
    bloques: list[_BloqueContraste],
) -> dict[int, list[int]]:
    """Pasa índices de bloque a ids. Quita el hijo si el padre ya está, y no repite bloque."""
    por_linea: dict[int, list[int]] = {}
    for linea, indices in cruda.items():
        if not isinstance(linea, int) or not 0 <= linea < len(lineas):
            continue
        ids: list[int] = []
        for indice in indices:
            if not isinstance(indice, int) or not 0 <= indice < len(bloques):
                continue
            bloque_id = bloques[indice].id
            if bloque_id not in ids:
                ids.append(bloque_id)
        if ids:
            por_linea[linea] = _sin_hijos(ids, bloques)
    mejor: dict[int, tuple[int, int]] = {}
    rutas = {bloque.id: bloque.ruta for bloque in bloques}
    for linea, ids in por_linea.items():
        for bloque_id in ids:
            puntos = _solape_nombre(lineas[linea], rutas.get(bloque_id, ""))
            actual = mejor.get(bloque_id)
            if actual is None or puntos > actual[0] or (puntos == actual[0] and linea < actual[1]):
                mejor[bloque_id] = (puntos, linea)
    salida: dict[int, list[int]] = {}
    for linea, ids in por_linea.items():
        quedaron = [bloque_id for bloque_id in ids if mejor.get(bloque_id, (0, -1))[1] == linea]
        if quedaron:
            salida[linea] = quedaron
    return salida


def _sin_hijos(ids: list[int], bloques: list[_BloqueContraste]) -> list[int]:
    elegidos = set(ids)
    quitar: set[int] = set()
    for bloque_id in elegidos:
        for descendiente in _descendientes(bloque_id, bloques):
            if descendiente in elegidos:
                quitar.add(descendiente)
    return [bloque_id for bloque_id in ids if bloque_id not in quitar]


def _descendientes(bloque_id: int, bloques: list[_BloqueContraste]) -> set[int]:
    hijos: dict[int, list[int]] = {}
    for bloque in bloques:
        if bloque.padre_id is not None:
            hijos.setdefault(bloque.padre_id, []).append(bloque.id)
    salida: set[int] = set()
    pila = list(hijos.get(bloque_id, []))
    while pila:
        actual = pila.pop()
        if actual in salida:
            continue
        salida.add(actual)
        pila.extend(hijos.get(actual, []))
    return salida


def _solape_nombre(linea: str, ruta: str) -> int:
    palabras = _palabras_contraste(linea)
    otras = _palabras_contraste(ruta)
    if not palabras or not otras:
        return 0
    return len(palabras & otras)


def _palabras_contraste(texto: str) -> set[str]:
    normal = _normalizar(texto or "")
    return {palabra for palabra in re.split(r"[^a-z0-9]+", normal) if len(palabra) > 3}


def _exigir_subapartado(db: Session, proyecto_id: int, tarea_id: int) -> Tarea:
    apartado = db.get(Tarea, tarea_id)
    if apartado is None or apartado.presupuesto_id is None:
        raise ValueError(f"Subapartado {tarea_id} no encontrado")
    if apartado.nivel != "subapartado":
        raise ValueError("Solo se puede contrastar un subapartado")
    nave = db.get(Nave, apartado.nave_id)
    if nave is None or nave.proyecto_id != proyecto_id:
        raise ValueError("El apartado no pertenece a este proyecto")
    presupuesto = db.get(Presupuesto, apartado.presupuesto_id)
    if presupuesto is None or presupuesto.formato != "excel_expertis":
        raise ValueError("El apartado no viene de un presupuesto Excel")
    return apartado


def _rechazar_solape(db: Session, tareas: list[Tarea]) -> None:
    """El importe de un bloque ya incluye sus subapartados: no se contrastan los dos."""
    elegidos = {tarea.id for tarea in tareas}
    cache: dict[int, Tarea] = {tarea.id: tarea for tarea in tareas}
    for tarea in tareas:
        padre_id = tarea.tarea_padre_id
        while padre_id is not None:
            if padre_id in elegidos:
                raise ValueError(
                    "No contrastes un bloque y sus subapartados a la vez: "
                    "el importe del bloque ya los incluye"
                )
            padre = cache.get(padre_id)
            if padre is None:
                padre = db.get(Tarea, padre_id)
                if padre is not None:
                    cache[padre.id] = padre
            padre_id = padre.tarea_padre_id if padre is not None else None


def _repartir_importe(importe: Decimal, bases: list[Decimal]) -> list[Decimal]:
    """Reparte un importe. El peso es el presupuesto de cada subapartado; el último ajusta los céntimos."""
    importe = Decimal(importe).quantize(Decimal("0.01"))
    if not bases:
        return []
    total = sum(bases, Decimal("0"))
    pesos = bases if total > 0 else [Decimal("1")] * len(bases)
    total = sum(pesos, Decimal("0"))
    acumulado = Decimal("0")
    partes: list[Decimal] = []
    for indice, peso in enumerate(pesos):
        if indice == len(pesos) - 1:
            partes.append((importe - acumulado).quantize(Decimal("0.01")))
        else:
            parte = (importe * peso / total).quantize(Decimal("0.01"))
            acumulado += parte
            partes.append(parte)
    return partes


def _repartir_cierre(
    sugerencias: list[SugerenciaContrasteOut],
    extraido,
) -> list[SugerenciaContrasteOut]:
    """Reparte el descuento de cierre. El importe manuscrito, si existe, es el que vale."""
    if not sugerencias:
        return sugerencias
    suma = sum((fila.importe_pdf for fila in sugerencias), Decimal("0"))
    if suma <= 0:
        return sugerencias
    neto = _neto_firmado(extraido, suma)
    if neto >= suma - Decimal("0.01"):
        return sugerencias

    factor = neto / suma
    acumulado = Decimal("0")
    salida: list[SugerenciaContrasteOut] = []
    for indice, fila in enumerate(sugerencias):
        bruto = fila.importe_pdf
        if indice == len(sugerencias) - 1:
            neto_linea = (neto - acumulado).quantize(Decimal("0.01"))
        else:
            neto_linea = (bruto * factor).quantize(Decimal("0.01"))
            acumulado += neto_linea
        salida.append(fila.model_copy(update={"importe_pdf": neto_linea, "importe_bruto": bruto}))
    return salida


def _neto_firmado(extraido, suma: Decimal) -> Decimal:
    manuscritos = sum(
        (descuento.importe for descuento in extraido.descuentos if descuento.es_manuscrito),
        Decimal("0"),
    )
    if extraido.total_manuscrito is not None:
        return Decimal(extraido.total_manuscrito)
    if extraido.total_impreso is not None and manuscritos == 0:
        return Decimal(extraido.total_impreso)
    if extraido.total_impreso is not None:
        return Decimal(extraido.total_impreso) - manuscritos
    resta = sum((descuento.importe for descuento in extraido.descuentos), Decimal("0"))
    return suma - resta


def _subapartados_excel(db: Session, proyecto_id: int) -> list[Tarea]:
    """Bloques del Excel (negrita o cursiva), no el fichero entero."""
    raices = [
        ap
        for ap in _apartados_presupuesto(db, proyecto_id)
        if ap.presupuesto is not None and ap.presupuesto.formato == "excel_expertis"
    ]
    if not raices:
        return []
    presupuesto_ids = {ap.presupuesto_id for ap in raices}
    return (
        db.query(Tarea)
        .filter(
            Tarea.presupuesto_id.in_(presupuesto_ids),
            Tarea.nivel == "subapartado",
        )
        .order_by(Tarea.codigo, Tarea.id)
        .all()
    )


def _preparar(nombre_fichero: str, contenido: bytes) -> tuple[str, ExcelLeido]:
    nombre = (nombre_fichero or "").strip()
    if not nombre:
        raise ValueError("Falta el nombre del fichero")
    if not nombre.lower().endswith(_EXTENSIONES):
        raise ValueError("El presupuesto tiene que ser un Excel .xlsx o .xlsm")
    if not contenido:
        raise ValueError("El fichero está vacío")
    leido = leer_excel_expertis(contenido)
    leido.nombre_apartado = _titulo_fichero(nombre)
    relacionar_montaje_general(leido)
    return nombre, leido


_PROMPT_MONTAJE = (
    "Relaciona cada línea de montaje con un solo producto del presupuesto. "
    'Responde solo JSON: {"asignaciones": [{"linea": 0, "producto": 1}]}. '
    "producto es el índice de la lista, o null si la línea es general "
    "(dietas, transporte, puesta en marcha, varios productos o ninguno). "
    "No inventes productos ni incluyas importes."
)


def relacionar_montaje_general(leido: ExcelLeido) -> None:
    """Reparte el montaje del bloque GENERAL entre los productos.

    Con LLM se mandan solo los nombres. Si no hay modelo, o no responde,
    se usa el nombre del producto cuando aparece en la línea. El documento
    sigue pendiente de revisión.
    """
    lineas, productos = lineas_y_productos_montaje(leido.nodos)
    if not lineas or not productos:
        return
    desc_lineas = [nodo.descripcion for nodo in lineas]
    desc_productos = [nodo.descripcion for nodo in productos]
    asignaciones = _asignar_montaje_llm(desc_lineas, desc_productos)
    if asignaciones is None:
        asignaciones = asignar_montaje_por_nombre(desc_lineas, desc_productos)
    leido.importe = aplicar_relacion_montaje(leido.nodos, asignaciones)


def _asignar_montaje_llm(lineas: list[str], productos: list[str]) -> list[int | None] | None:
    settings = get_settings()
    if not llm_svc.hay_llm(settings):
        return None
    lista_productos = "\n".join(f"{i}. {nombre}" for i, nombre in enumerate(productos))
    lista_lineas = "\n".join(f"{i}. {nombre}" for i, nombre in enumerate(lineas))
    try:
        contenido = llm_svc.completar_texto(
            api_key=settings.llm_api_key or "",
            api_base=settings.llm_api_base,
            anthropic=llm_svc.es_anthropic(settings),
            model=llm_svc.modelo_extraccion(settings),
            system=_PROMPT_MONTAJE,
            user=f"Productos:\n{lista_productos}\n\nLíneas:\n{lista_lineas}",
            max_tokens=4000,
        )
        parsed = llm_svc.parsear_json_llm(contenido)
    except (OSError, ValueError, TimeoutError):
        return None
    crudas = parsed.get("asignaciones")
    if not isinstance(crudas, list):
        return None
    return _interpretar_asignaciones(crudas, len(lineas), productos)


def _interpretar_asignaciones(
    crudas: list,
    n_lineas: int,
    productos: list[str],
) -> list[int | None]:
    resultado: list[int | None] = [None] * n_lineas
    for item in crudas:
        if not isinstance(item, dict):
            continue
        indice = item.get("linea")
        if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < n_lineas:
            continue
        resultado[indice] = _indice_producto(item.get("producto"), productos)
    return resultado


def _indice_producto(valor: object, productos: list[str]) -> int | None:
    if valor is None or valor == "" or isinstance(valor, bool):
        return None
    if isinstance(valor, int) or (isinstance(valor, str) and valor.strip().lstrip("-").isdigit()):
        indice = int(valor)
        if 0 <= indice < len(productos):
            return indice
        return None
    texto = _normalizar(str(valor))
    iguales = [i for i, nombre in enumerate(productos) if _normalizar(nombre) == texto]
    if len(iguales) == 1:
        return iguales[0]
    return None


def _persistir_fichero(
    db: Session,
    proyecto: Proyecto,
    nave: Nave,
    nombre_fichero: str,
    leido: ExcelLeido,
    contenido: bytes,
    *,
    codigo_apartado: str,
) -> ApartadoExcelOut:
    version = _version_fichero(nombre_fichero)
    presupuesto = Presupuesto(
        proyecto_id=proyecto.id,
        version=version,
        fichero_origen=nombre_fichero[:512],
        estado_extraccion="pendiente_revision",
        es_escaneado=False,
        formato="excel_expertis",
    )
    db.add(presupuesto)
    db.flush()
    presupuesto.ruta_almacen = almacen_svc.guardar(
        proyecto.id,
        "presupuesto",
        presupuesto.id,
        nombre_fichero,
        contenido,
    )

    apartado = Tarea(
        nave_id=nave.id,
        presupuesto_id=presupuesto.id,
        codigo=codigo_apartado,
        nivel="apartado",
        descripcion=leido.nombre_apartado,
        importe_presupuestado=leido.importe,
        tiene_anotacion_manual=False,
        es_montaje=False,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(apartado)
    db.flush()
    for nodo in leido.nodos:
        _guardar_nodo(db, nave.id, presupuesto.id, apartado.id, nodo)
    return ApartadoExcelOut(
        tarea_id=apartado.id,
        presupuesto_id=presupuesto.id,
        codigo=apartado.codigo,
        descripcion=apartado.descripcion,
        importe=apartado.importe_presupuestado,
        partidas=leido.partidas,
        lineas_montaje=leido.lineas_montaje,
    )


def _guardar_nodo(
    db: Session,
    nave_id: int,
    presupuesto_id: int,
    padre_id: int,
    nodo: NodoExcel,
) -> None:
    tarea = Tarea(
        nave_id=nave_id,
        presupuesto_id=presupuesto_id,
        tarea_padre_id=padre_id,
        codigo=nodo.codigo[:50],
        nivel=nodo.nivel,
        capitulo=(nodo.capitulo or None),
        descripcion=nodo.descripcion,
        unidad=None,
        cantidad=nodo.cantidad,
        precio_unitario=nodo.precio_unitario,
        descuento_pct=nodo.descuento_pct,
        referencia=(nodo.referencia or None),
        referencia_alt=(nodo.referencia_alt or None),
        importe_presupuestado=nodo.importe,
        tiene_anotacion_manual=False,
        es_montaje=nodo.es_montaje,
        estado_revision="pendiente",
        estado="no_iniciada",
        avance_fisico_pct=Decimal("0"),
    )
    db.add(tarea)
    db.flush()
    for hijo in nodo.hijos:
        _guardar_nodo(db, nave_id, presupuesto_id, tarea.id, hijo)


def _avisos(leido: ExcelLeido) -> list[AvisoCuadreOut]:
    return [
        AvisoCuadreOut(
            bloque=aviso.bloque,
            suma_lineas=aviso.suma_lineas,
            total_documento=aviso.total_documento,
        )
        for aviso in leido.avisos
    ]


def _respuesta(
    proyecto_id: int,
    presupuesto_ids: list[int],
    apartados: list[ApartadoExcelOut],
    partidas: int,
    montaje: int,
    avisos: list[AvisoCuadreOut],
) -> ImportarExcelOut:
    return ImportarExcelOut(
        proyecto_id=proyecto_id,
        presupuesto_ids=presupuesto_ids,
        apartados=apartados,
        partidas_detectadas=partidas,
        lineas_montaje=montaje,
        requiere_revision=True,
        sumas_cuadran=not avisos,
        avisos=avisos,
    )


def devolver_elementos_de_montaje(db: Session, presupuesto_id: int) -> None:
    """Saca ELEMENTOS DE MONTAJE de un bloque de montaje y lo devuelve a su subbloque.

    Las obras importadas antes de esta regla lo tenían dentro de Montaje.
    """
    tareas = (
        db.query(Tarea)
        .filter(Tarea.presupuesto_id == presupuesto_id)
        .order_by(Tarea.id)
        .all()
    )
    if not tareas:
        return
    por_id = {tarea.id: tarea for tarea in tareas}
    cambio = False
    for linea in tareas:
        if linea.nivel != "partida" or not _es_elementos_de_montaje(linea.descripcion):
            continue
        padre = por_id.get(linea.tarea_padre_id or 0)
        if padre is None or not _es_bloque_montaje(padre.descripcion):
            if linea.es_montaje:
                linea.es_montaje = False
                linea.capitulo = None
                cambio = True
            continue
        destino = _bloque_de_capitulo(linea, padre, por_id)
        if destino is None:
            continue
        importe = Decimal(linea.importe_presupuestado or 0)
        for nodo in _hasta_la_raiz(padre, por_id):
            nodo.importe_presupuestado = _dinero(Decimal(nodo.importe_presupuestado) - importe)
        linea.tarea_padre_id = destino.id
        linea.es_montaje = False
        linea.capitulo = None
        for nodo in _hasta_la_raiz(destino, por_id):
            nodo.importe_presupuestado = _dinero(Decimal(nodo.importe_presupuestado) + importe)
        cambio = True
    if cambio:
        db.commit()


def _es_elementos_de_montaje(descripcion: str) -> bool:
    return _normalizar(descripcion).startswith("elementos de montaje")


def _es_bloque_montaje(descripcion: str) -> bool:
    """Bloque generado: «Montaje», «Montaje general» o «Montaje {subapartado}»."""
    nombre = _normalizar(descripcion)
    return nombre == "montaje" or nombre.startswith("montaje ")


def repartir_montaje_por_subapartado(db: Session, presupuesto_id: int) -> None:
    """Parte el bloque único «Montaje» de una obra ya importada.

    Cada grupo de líneas vuelve al subapartado de su capítulo, en un bloque
    «Montaje {nombre}». Las que no son de uno solo quedan en «Montaje general».
    """
    tareas = (
        db.query(Tarea)
        .filter(Tarea.presupuesto_id == presupuesto_id)
        .order_by(Tarea.id)
        .all()
    )
    if not tareas:
        return
    por_id = {tarea.id: tarea for tarea in tareas}
    cambio = False
    for bloque in list(tareas):
        if bloque.nivel != "subapartado" or _normalizar(bloque.descripcion) != "montaje":
            continue
        lineas = [
            linea
            for linea in tareas
            if linea.tarea_padre_id == bloque.id and linea.nivel == "partida" and linea.es_montaje
        ]
        if not lineas:
            continue
        propios, sueltos = _emparejar_montaje(lineas, bloque, por_id)
        for destino, grupo in propios.items():
            _mover_grupo_montaje(db, bloque, destino, grupo, por_id, tareas, _titulo_montaje(destino.descripcion))
            cambio = True
        if sueltos:
            destino, titulo = _destino_montaje_suelto(sueltos, bloque, por_id)
            _mover_grupo_montaje(db, bloque, destino, sueltos, por_id, tareas, titulo)
            cambio = True
        db.flush()
        if _montaje_vacio(db, bloque, tareas):
            db.delete(bloque)
            cambio = True
    if cambio:
        db.commit()


def _emparejar_montaje(
    lineas: list[Tarea],
    bloque: Tarea,
    por_id: dict[int, Tarea],
) -> tuple[dict[Tarea, list[Tarea]], list[Tarea]]:
    propios: dict[Tarea, list[Tarea]] = {}
    sueltos: list[Tarea] = []
    for linea in lineas:
        destino = _destino_de_capitulo(linea.capitulo or "", bloque, por_id)
        if destino is None:
            sueltos.append(linea)
            continue
        propios.setdefault(destino, []).append(linea)
    return propios, sueltos


def _destino_de_capitulo(
    capitulo: str,
    bloque: Tarea,
    por_id: dict[int, Tarea],
) -> Tarea | None:
    buscado = _normalizar(capitulo)
    if not buscado:
        return None
    raiz = _raiz_id(bloque, por_id)
    for nodo in por_id.values():
        if nodo.nivel != "subapartado" or nodo.id == bloque.id:
            continue
        if _es_bloque_montaje(nodo.descripcion):
            continue
        if _raiz_id(nodo, por_id) != raiz:
            continue
        if _normalizar(_etiqueta_tarea(nodo)) == buscado or _normalizar(nodo.descripcion) == buscado:
            return nodo
    return None


def _destino_montaje_suelto(
    lineas: list[Tarea],
    bloque: Tarea,
    por_id: dict[int, Tarea],
) -> tuple[Tarea, str]:
    """Un subapartado recibe las líneas; si hay varios, el bloque es general."""
    candidatos = _subapartados_del_apartado(bloque, por_id)
    padre = por_id.get(bloque.tarea_padre_id or 0)
    if len(candidatos) == 1:
        destino = candidatos[0]
        etiqueta = _etiqueta_tarea(destino)[:255]
        for linea in lineas:
            linea.capitulo = etiqueta
        return destino, _titulo_montaje(destino.descripcion)
    anfitrion = padre or bloque
    return anfitrion, "Montaje general"


def _subapartados_del_apartado(bloque: Tarea, por_id: dict[int, Tarea]) -> list[Tarea]:
    raiz = _raiz_id(bloque, por_id)
    return [
        nodo
        for nodo in por_id.values()
        if nodo.nivel == "subapartado"
        and nodo.id != bloque.id
        and not _es_bloque_montaje(nodo.descripcion)
        and _raiz_id(nodo, por_id) == raiz
    ]


def _mover_grupo_montaje(
    db: Session,
    bloque: Tarea,
    destino: Tarea,
    grupo: list[Tarea],
    por_id: dict[int, Tarea],
    tareas: list[Tarea],
    titulo: str,
) -> None:
    receptor = _bloque_hijo(destino.id, titulo, por_id)
    if receptor is None:
        receptor = Tarea(
            nave_id=bloque.nave_id,
            presupuesto_id=bloque.presupuesto_id,
            tarea_padre_id=destino.id,
            codigo="0",
            nivel="subapartado",
            descripcion=titulo[:255],
            importe_presupuestado=Decimal("0"),
            tiene_anotacion_manual=False,
            es_montaje=False,
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
        db.add(receptor)
        db.flush()
        por_id[receptor.id] = receptor
        tareas.append(receptor)
    for linea in grupo:
        importe = Decimal(linea.importe_presupuestado or 0)
        for nodo in _hasta_la_raiz(bloque, por_id):
            nodo.importe_presupuestado = _dinero(Decimal(nodo.importe_presupuestado) - importe)
        linea.padre = receptor
        for nodo in _hasta_la_raiz(receptor, por_id):
            nodo.importe_presupuestado = _dinero(Decimal(nodo.importe_presupuestado) + importe)


def _bloque_hijo(padre_id: int, titulo: str, por_id: dict[int, Tarea]) -> Tarea | None:
    buscado = _normalizar(titulo)
    for nodo in por_id.values():
        if (
            nodo.tarea_padre_id == padre_id
            and nodo.nivel == "subapartado"
            and _normalizar(nodo.descripcion) == buscado
        ):
            return nodo
    return None


def _montaje_vacio(db: Session, bloque: Tarea, tareas: list[Tarea]) -> bool:
    if any(tarea.tarea_padre_id == bloque.id for tarea in tareas):
        return False
    if bloque.importe_contrato_cliente is not None:
        return False
    from app.models import Asignacion, Contrato, LineaFactura

    if db.query(Contrato.id).filter(Contrato.tarea_apartado_id == bloque.id).first():
        return False
    if db.query(Asignacion.id).filter(Asignacion.tarea_id == bloque.id).first():
        return False
    if db.query(LineaFactura.id).filter(LineaFactura.tarea_id == bloque.id).first():
        return False
    return True


def _bloque_de_capitulo(
    linea: Tarea,
    montaje: Tarea,
    por_id: dict[int, Tarea],
) -> Tarea | None:
    buscado = _normalizar(linea.capitulo or "")
    if not buscado:
        return None
    apartado_id = montaje.tarea_padre_id
    for nodo in por_id.values():
        if nodo.id == montaje.id or nodo.nivel == "partida":
            continue
        if nodo.tarea_padre_id is None:
            continue
        if _raiz_id(nodo, por_id) != apartado_id and nodo.tarea_padre_id != apartado_id:
            continue
        if _normalizar(_etiqueta_tarea(nodo)) == buscado:
            return nodo
    return None


def _raiz_id(nodo: Tarea, por_id: dict[int, Tarea]) -> int | None:
    actual: Tarea | None = nodo
    while actual is not None and actual.tarea_padre_id is not None:
        actual = por_id.get(actual.tarea_padre_id)
    return actual.id if actual is not None else None


def _hasta_la_raiz(nodo: Tarea, por_id: dict[int, Tarea]) -> list[Tarea]:
    """Del bloque hacia arriba, sin el apartado raíz: su total no cambia."""
    cadena: list[Tarea] = []
    actual: Tarea | None = nodo
    while actual is not None and actual.tarea_padre_id is not None:
        cadena.append(actual)
        actual = por_id.get(actual.tarea_padre_id)
    return cadena


def _etiqueta_tarea(nodo: Tarea) -> str:
    codigo = (nodo.codigo or "").strip()
    nombre = (nodo.descripcion or "").strip()
    if codigo and codigo != "0" and not re.fullmatch(r"b\d+", codigo):
        return f"{codigo} {nombre}".strip()
    return nombre or codigo


def _dinero(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"))


def rellenar_origen_montaje(db: Session, presupuesto: Presupuesto) -> None:
    """Anota en cada montaje ya guardado el bloque del Excel del que salió."""
    if presupuesto.formato != "excel_expertis":
        return
    tareas = (
        db.query(Tarea)
        .filter(Tarea.presupuesto_id == presupuesto.id, Tarea.es_montaje.is_(True))
        .order_by(Tarea.id)
        .all()
    )
    if not tareas or all(tarea.capitulo for tarea in tareas):
        return
    ruta = almacen_svc.abrir_si_existe(presupuesto.ruta_almacen)
    if ruta is None:
        return
    try:
        leido = leer_excel_expertis(ruta.read_bytes())
    except ValueError:
        return
    origenes = _partidas_montaje(leido.nodos)
    if len(origenes) != len(tareas):
        return
    for tarea, nodo in zip(tareas, origenes, strict=True):
        if tarea.codigo != nodo.codigo or tarea.descripcion != nodo.descripcion:
            return
    cambio = False
    for tarea, nodo in zip(tareas, origenes, strict=True):
        if nodo.capitulo and tarea.capitulo != nodo.capitulo:
            tarea.capitulo = nodo.capitulo[:255]
            cambio = True
    if cambio:
        db.commit()


def _partidas_montaje(nodos: list[NodoExcel]) -> list[NodoExcel]:
    lineas: list[NodoExcel] = []
    for nodo in nodos:
        if nodo.nivel == "partida" and nodo.es_montaje:
            lineas.append(nodo)
        lineas.extend(_partidas_montaje(nodo.hijos))
    return lineas


def _suma_raices(db: Session, nave_id: int) -> Decimal:
    tareas = db.query(Tarea).filter(Tarea.nave_id == nave_id, Tarea.presupuesto_id.isnot(None)).all()
    padres = mapa_padres(tareas)
    return sum(
        (t.importe_presupuestado for t in tareas if padres.get(t.id) is None),
        Decimal("0"),
    )


def _titulo_fichero(nombre: str) -> str:
    """El título del apartado es el nombre del Excel, sin carpeta ni extensión."""
    base = Path(nombre.replace("\\", "/")).name
    titulo = Path(base).stem.strip()
    return (titulo or "Apartado")[:512]


def _version_fichero(nombre: str) -> int:
    hallado = re.search(r"\bV(\d+)\b", nombre, flags=re.IGNORECASE)
    if hallado is None:
        return 1
    return max(1, int(hallado.group(1)))
