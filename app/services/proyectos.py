"""Consultas de proyectos para listado y detalle de UI."""

from decimal import Decimal

from sqlalchemy import bindparam, func, text
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Contrato,
    ContratoApartado,
    Factura,
    LineaPdfCliente,
    Nave,
    Presupuesto,
    Proyecto,
    Tarea,
    Usuario,
)
from app.services.codigo_contrato import (
    AVISO_REPETIDO,
    AVISO_SIN_CODIGO,
    AVISO_VARIOS,
)
from app.services.registro import registrar
from app.schemas.proyecto import (
    ApartadoContratoOut,
    ApartadoEnlaceOut,
    ApartadoResumenOut,
    ContratoApartadoOut,
    ContratoResumenOut,
    DocumentoProyectoOut,
    NaveResumenOut,
    ProyectoDetalleOut,
    ProyectoRead,
)
from app.services import almacen as almacen_svc
from app.services import casado as casado_svc
from app.services import mano_obra as mano_obra_svc
from app.services.jerarquia import asegurar_apartados_padre, mapa_padres
from app.services.presupuesto_excel import (
    contraste_guardado,
    devolver_elementos_de_montaje,
    rellenar_origen_montaje,
    meter_colocacion_en_montaje,
    repartir_montaje_por_subapartado,
    sumar_dietas_guardadas,
)


def listar_proyectos(db: Session) -> list[ProyectoRead]:
    filas = db.query(Proyecto).order_by(Proyecto.id.desc()).all()
    if not filas:
        return []
    ids = [p.id for p in filas]
    presupuestado = _presupuestado_raices(db, ids)
    facturado = _facturado_confirmado(db, ids)
    return [
        ProyectoRead(
            id=p.id,
            nombre=p.nombre,
            tipo=p.tipo,
            fecha_inicio=p.fecha_inicio,
            estado=p.estado,
            created_at=p.created_at,
            presupuestado=presupuestado.get(p.id, Decimal("0")),
            facturado=facturado.get(p.id, Decimal("0")),
        )
        for p in filas
    ]


def _presupuestado_raices(db: Session, proyecto_ids: list[int]) -> dict[int, Decimal]:
    """Suma solo apartados raíz. Un subapartado no se vuelve a sumar."""
    tareas = (
        db.query(Tarea, Nave.proyecto_id)
        .join(Nave, Tarea.nave_id == Nave.id)
        .filter(
            Nave.proyecto_id.in_(proyecto_ids),
            Tarea.presupuesto_id.isnot(None),
        )
        .all()
    )
    por_proyecto: dict[int, list[Tarea]] = {}
    for tarea, proyecto_id in tareas:
        por_proyecto.setdefault(proyecto_id, []).append(tarea)

    totales: dict[int, Decimal] = {}
    for proyecto_id, grupo in por_proyecto.items():
        padres = mapa_padres(grupo)
        totales[proyecto_id] = sum(
            (t.importe_presupuestado for t in grupo if padres.get(t.id) is None),
            Decimal("0"),
        )
    return totales


def _facturado_confirmado(db: Session, proyecto_ids: list[int]) -> dict[int, Decimal]:
    filas = (
        db.query(Factura.proyecto_id, func.coalesce(func.sum(Factura.total), 0))
        .filter(
            Factura.proyecto_id.in_(proyecto_ids),
            Factura.estado_revision == "confirmada",
        )
        .group_by(Factura.proyecto_id)
        .all()
    )
    return {
        proyecto_id: Decimal(total)
        for proyecto_id, total in filas
        if proyecto_id is not None
    }


def _apartados_del_contrato(contrato: Contrato) -> list[Tarea]:
    enlaces = [
        enlace.tarea
        for enlace in (contrato.enlaces_apartado or [])
        if enlace.tarea is not None
    ]
    if not enlaces and contrato.tarea_apartado is not None:
        enlaces = [contrato.tarea_apartado]
    enlaces.sort(key=lambda ap: (ap.codigo, ap.id))
    return enlaces


def obtener_proyecto(db: Session, proyecto_id: int) -> ProyectoDetalleOut:
    proyecto = (
        db.query(Proyecto)
        .options(joinedload(Proyecto.naves))
        .filter(Proyecto.id == proyecto_id)
        .first()
    )
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    naves = sorted(proyecto.naves, key=lambda n: n.id)
    nave_por_id = {n.id: n for n in naves}
    nave_ids = list(nave_por_id.keys())

    tareas_presupuesto: list[Tarea] = []
    if nave_ids:
        tareas_presupuesto = (
            db.query(Tarea)
            .filter(
                Tarea.nave_id.in_(nave_ids),
                Tarea.presupuesto_id.isnot(None),
            )
            .order_by(Tarea.codigo, Tarea.id)
            .all()
        )
        asegurar_apartados_padre(db, tareas_presupuesto)
        presupuestos = (
            db.query(Presupuesto)
            .filter(Presupuesto.proyecto_id == proyecto_id, Presupuesto.formato == "excel_expertis")
            .all()
        )
        for presupuesto in presupuestos:
            rellenar_origen_montaje(db, presupuesto)
            devolver_elementos_de_montaje(db, presupuesto.id)
            repartir_montaje_por_subapartado(db, presupuesto.id)
            meter_colocacion_en_montaje(db, presupuesto.id)
            sumar_dietas_guardadas(db, presupuesto.id)

    contratos_db = (
        db.query(Contrato)
        .options(
            joinedload(Contrato.contratista),
            joinedload(Contrato.tarea_apartado),
            joinedload(Contrato.enlaces_apartado).joinedload(ContratoApartado.tarea),
        )
        .filter(Contrato.proyecto_id == proyecto_id)
        .order_by(Contrato.id.desc())
        .all()
    )

    facturado_por_contrato = {
        contrato_id: Decimal(total)
        for contrato_id, total in (
            db.query(
                Factura.contrato_id,
                func.coalesce(func.sum(Factura.total), 0),
            )
            .filter(
                Factura.proyecto_id == proyecto_id,
                Factura.contrato_id.isnot(None),
                Factura.estado_revision == "confirmada",
            )
            .group_by(Factura.contrato_id)
            .all()
        )
    }
    contratos_por_apartado: dict[int, list[ContratoApartadoOut]] = {}
    contratos_unicos: dict[int, Contrato] = {}
    for contrato in contratos_db:
        contratos_unicos[contrato.id] = contrato
    contratos_db = list(contratos_unicos.values())

    padres = mapa_padres(tareas_presupuesto)
    hijos_por_id: dict[int, list[Tarea]] = {}
    raices: list[Tarea] = []
    for tarea in tareas_presupuesto:
        padre_id = padres.get(tarea.id)
        if padre_id is None:
            raices.append(tarea)
        else:
            hijos_por_id.setdefault(padre_id, []).append(tarea)

    def importe_montaje_de(tarea: Tarea) -> Decimal:
        """Suma de líneas es_montaje bajo el nodo (y el propio si lo es)."""
        total = (
            Decimal(tarea.importe_presupuestado) if tarea.es_montaje else Decimal("0")
        )
        pila = list(hijos_por_id.get(tarea.id, []))
        while pila:
            nodo = pila.pop()
            if nodo.es_montaje:
                total += Decimal(nodo.importe_presupuestado)
            pila.extend(hijos_por_id.get(nodo.id, []))
        return total

    def base_enlace(tarea: Tarea) -> Decimal:
        if tarea.solo_gestion:
            return Decimal(tarea.importe_presupuestado or 0)
        return importe_montaje_de(tarea)

    def peso_de(tarea: Tarea) -> Decimal:
        if tarea.presupuesto_id is None:
            return Decimal(tarea.importe_presupuestado or 0)
        return base_enlace(tarea)

    por_tarea = {tarea.id: tarea for tarea in tareas_presupuesto}
    for contrato in contratos_db:
        ligados = [
            enlace.tarea
            for enlace in (contrato.enlaces_apartado or [])
            if enlace.tarea is not None
        ]
        if not ligados and contrato.tarea_apartado is not None:
            ligados = [contrato.tarea_apartado]
        ligados.sort(key=lambda tarea: (tarea.presupuesto_id is None, tarea.codigo, tarea.id))
        if not ligados:
            continue
        pesos = [peso_de(tarea) for tarea in ligados]
        contratado = Decimal(contrato.precio_total)
        facturado = facturado_por_contrato.get(contrato.id, Decimal("0"))
        trozos_c = casado_svc.repartir_importe(contratado, pesos)
        trozos_f = casado_svc.repartir_importe(facturado, pesos)
        for tarea, parte_c, parte_f in zip(ligados, trozos_c, trozos_f):
            if tarea.presupuesto_id is None or tarea.id not in por_tarea:
                continue
            destino = tarea.id
            while padres.get(destino) is not None:
                destino = padres[destino]
            if destino not in por_tarea:
                continue
            lista = contratos_por_apartado.setdefault(destino, [])
            previo = next((item for item in lista if item.id == contrato.id), None)
            contratado = parte_c if previo is None else previo.contratado + parte_c
            facturado = parte_f if previo is None else previo.facturado + parte_f
            porcentaje = (
                (facturado / contratado * Decimal("100")) if contratado != 0 else Decimal("0")
            )
            ficha = ContratoApartadoOut(
                id=contrato.id,
                contratista_nombre=(
                    contrato.contratista.nombre if contrato.contratista else "—"
                ),
                contratista_nif=(
                    contrato.contratista.nif if contrato.contratista else "—"
                ),
                contratado=contratado,
                facturado=facturado,
                pendiente=contratado - facturado,
                porcentaje_facturado=porcentaje.quantize(Decimal("0.01")),
            )
            if previo is None:
                lista.append(ficha)
            else:
                lista[lista.index(previo)] = ficha

    def resumen_apartado(ap: Tarea, *, con_contratos: bool) -> ApartadoResumenOut:
        nivel = ap.nivel
        if padres.get(ap.id) is not None and nivel == "apartado":
            nivel = "subapartado"
        hijos = [
            resumen_apartado(hijo, con_contratos=False)
            for hijo in hijos_por_id.get(ap.id, [])
        ]
        return ApartadoResumenOut(
            id=ap.id,
            codigo=ap.codigo,
            descripcion=ap.descripcion,
            nivel=nivel,
            importe_presupuestado=ap.importe_presupuestado,
            unidad=ap.unidad,
            cantidad=ap.cantidad,
            precio_unitario=ap.precio_unitario,
            descuento_pct=ap.descuento_pct,
            es_montaje=bool(ap.es_montaje),
            solo_gestion=bool(ap.solo_gestion),
            importe_montaje=importe_montaje_de(ap),
            capitulo=ap.capitulo,
            importe_contrato_cliente=ap.importe_contrato_cliente,
            nave_id=ap.nave_id,
            nave_codigo=nave_por_id[ap.nave_id].codigo
            if ap.nave_id in nave_por_id
            else "",
            estado_revision=ap.estado_revision,
            contrato_enlazado_id=(
                contratos_por_apartado[ap.id][0].id
                if con_contratos and contratos_por_apartado.get(ap.id)
                else None
            ),
            contratos=contratos_por_apartado.get(ap.id, []) if con_contratos else [],
            subapartados=hijos,
        )

    apartados_out = [resumen_apartado(ap, con_contratos=True) for ap in raices]

    ids_contratos = [c.id for c in contratos_db]
    raices_de_contrato: dict[int, list[Tarea]] = {}
    if ids_contratos:
        for tarea in (
            db.query(Tarea)
            .filter(
                Tarea.contrato_id.in_(ids_contratos),
                Tarea.tarea_padre_id.is_(None),
                Tarea.nivel == "apartado",
            )
            .order_by(Tarea.codigo, Tarea.id)
            .all()
        ):
            raices_de_contrato.setdefault(tarea.contrato_id, []).append(tarea)
    ids_linea = {
        tarea.linea_pdf_cliente_id
        for tareas in raices_de_contrato.values()
        for tarea in tareas
        if tarea.linea_pdf_cliente_id
    }
    lineas_pdf = {
        linea.id: linea
        for linea in (
            db.query(LineaPdfCliente).filter(LineaPdfCliente.id.in_(ids_linea)).all()
            if ids_linea
            else []
        )
    }

    def texto_linea(tarea: Tarea) -> tuple[int | None, str | None]:
        linea = lineas_pdf.get(tarea.linea_pdf_cliente_id or 0)
        if linea is None:
            return None, None
        return linea.id, linea.descripcion

    excel_para_cruce = [
        ap
        for ap in raices
        if not ap.codigo.startswith("descuento.")
        and not (ap.solo_gestion and ap.estado_revision != "confirmada")
    ]

    contratos_out: list[ContratoResumenOut] = []
    for c in contratos_db:
        enlaces = [enlace for enlace in (c.enlaces_apartado or []) if enlace.tarea is not None]
        enlazados = [enlace.tarea for enlace in enlaces] or _apartados_del_contrato(c)
        explicacion_de = {enlace.tarea_id: enlace.explicacion for enlace in enlaces}
        if enlazados:
            sugerencias = []
        else:
            sugerencias = casado_svc.sugerir_apartados_para_contrato(db, c)
        de_excel = [ap for ap in enlazados if ap.presupuesto_id is not None]
        fuera = []
        for tarea in raices_de_contrato.get(c.id, []):
            if tarea.id in explicacion_de or not casado_svc.aparece_en_excel(
                tarea.descripcion, excel_para_cruce
            ):
                fuera.append(tarea)

        def enlace_de(ap: Tarea) -> ApartadoEnlaceOut:
            linea_id, linea_texto = texto_linea(ap)
            return ApartadoEnlaceOut(
                id=ap.id,
                codigo=ap.codigo,
                descripcion=ap.descripcion,
                importe=ap.importe_presupuestado,
                es_de_contrato=ap.presupuesto_id is None,
                explicacion=explicacion_de.get(ap.id),
                linea_pdf_id=linea_id,
                linea_pdf_descripcion=linea_texto,
            )

        contratos_out.append(
            ContratoResumenOut(
                id=c.id,
                contratista_nombre=c.contratista.nombre if c.contratista else "—",
                contratista_nif=c.contratista.nif if c.contratista else "—",
                precio_total=c.precio_total,
                codigo=c.codigo,
                aviso=c.aviso,
                estado_extraccion=c.estado_extraccion,
                nave_id=c.nave_id,
                tarea_apartado_id=de_excel[0].id if de_excel else None,
                tarea_apartado_ids=[ap.id for ap in enlazados],
                apartado_codigo=" · ".join(ap.codigo for ap in enlazados) or None,
                apartado_descripcion=" · ".join(ap.descripcion for ap in enlazados) or None,
                apartados_enlace=[enlace_de(ap) for ap in enlazados],
                apartados_fuera_excel=[
                    ApartadoContratoOut(
                        id=ap.id,
                        codigo=ap.codigo,
                        descripcion=ap.descripcion,
                        importe=ap.importe_presupuestado,
                        linea_pdf_id=texto_linea(ap)[0],
                        linea_pdf_descripcion=texto_linea(ap)[1],
                    )
                    for ap in fuera
                ],
                fichero_origen=c.fichero_origen,
                tiene_fichero=bool(c.ruta_almacen),
                sugerencias=sugerencias,
            )
        )

    documentos = [
        DocumentoProyectoOut(
            id=doc.id,
            fichero_origen=doc.fichero_origen,
            formato=doc.formato,
            tiene_fichero=bool(doc.ruta_almacen),
        )
        for doc in (
            db.query(Presupuesto)
            .filter(Presupuesto.proyecto_id == proyecto_id)
            .order_by(Presupuesto.id)
            .all()
        )
    ]

    return ProyectoDetalleOut(
        id=proyecto.id,
        nombre=proyecto.nombre,
        tipo=proyecto.tipo,
        fecha_inicio=proyecto.fecha_inicio,
        estado=proyecto.estado,
        created_at=proyecto.created_at,
        presupuestado=_presupuestado_raices(db, [proyecto.id]).get(proyecto.id, Decimal("0")),
        facturado=_facturado_confirmado(db, [proyecto.id]).get(proyecto.id, Decimal("0")),
        naves=[NaveResumenOut.model_validate(n) for n in naves],
        apartados=apartados_out,
        contratos=contratos_out,
        documentos=documentos,
        contraste_cliente=contraste_guardado(db, proyecto_id),
        inversion_sujeto_pasivo=bool(proyecto.inversion_sujeto_pasivo),
        tiene_carta_isp=bool(proyecto.ruta_carta_isp),
        fichero_carta_isp=proyecto.fichero_carta_isp,
        mano_obra=mano_obra_svc.bloque(db, proyecto.id),
    )


def borrar_contrato(
    db: Session, proyecto_id: int, contrato_id: int, usuario: Usuario
) -> None:
    """Quita el contrato del proveedor.

    Las facturas se quedan y dejan de apuntar a él. Se borran el fichero,
    los enlaces a apartados y las partidas que nacieron solo de ese contrato.
    Los apartados del presupuesto se quedan. El contratista también.
    """
    contrato = db.get(Contrato, contrato_id)
    if contrato is None or contrato.proyecto_id != proyecto_id:
        raise ValueError(f"Contrato {contrato_id} no encontrado")

    proyecto = db.get(Proyecto, proyecto_id)
    nombre = proyecto.nombre
    referencia = contrato.referencia_presupuesto
    etiqueta = nombre
    if referencia is not None and referencia.strip():
        etiqueta = f"{nombre} · {referencia}"
    registrar(
        db,
        usuario,
        "borrar_contrato",
        tipo_documento="contrato",
        documento_id=contrato_id,
        etiqueta=etiqueta,
    )

    ruta = contrato.ruta_almacen
    propias = _ids_tareas_propias_del_contrato(db, contrato_id)
    db.execute(
        text("UPDATE factura SET contrato_id = NULL WHERE contrato_id = :cid"),
        {"cid": contrato_id},
    )
    if propias:
        _en_ids(
            db,
            "UPDATE contrato SET tarea_apartado_id = NULL WHERE tarea_apartado_id IN :ids",
            propias,
        )
        _en_ids(db, "DELETE FROM contrato_apartado WHERE tarea_id IN :ids", propias)
        _en_ids(
            db,
            "DELETE FROM linea_pdf_cliente_tarea WHERE tarea_id IN :ids",
            propias,
        )
        _en_ids(
            db,
            "UPDATE linea_factura SET tarea_id = NULL WHERE tarea_id IN :ids",
            propias,
        )
        _en_ids(db, "DELETE FROM asignacion WHERE tarea_id IN :ids", propias)
        _en_ids(
            db,
            "UPDATE tarea SET tarea_padre_id = NULL WHERE tarea_padre_id IN :ids",
            propias,
        )
        _en_ids(db, "DELETE FROM tarea WHERE id IN :ids", propias)
    db.execute(
        text("UPDATE tarea SET contrato_id = NULL WHERE contrato_id = :cid"),
        {"cid": contrato_id},
    )
    db.execute(text("DELETE FROM contrato WHERE id = :cid"), {"cid": contrato_id})
    db.commit()
    almacen_svc.borrar_fichero(ruta)


def _ids_tareas_propias_del_contrato(db: Session, contrato_id: int) -> list[int]:
    """Partidas nacidas del contrato, y lo que cuelga de ellas si no es del presupuesto."""
    filas = db.execute(
        text(
            """
            WITH RECURSIVE propias AS (
                SELECT id
                FROM tarea
                WHERE contrato_id = :cid
                  AND presupuesto_id IS NULL
                UNION
                SELECT tarea.id
                FROM tarea
                JOIN propias ON tarea.tarea_padre_id = propias.id
                WHERE tarea.presupuesto_id IS NULL
            )
            SELECT id FROM propias
            """
        ),
        {"cid": contrato_id},
    ).scalars()
    return list(filas)


def _en_ids(db: Session, sql: str, ids: list[int]) -> None:
    db.execute(
        text(sql).bindparams(bindparam("ids", expanding=True)),
        {"ids": ids},
    )


def borrar_proyecto(db: Session, proyecto_id: int, usuario: Usuario) -> None:
    """Elimina la obra y lo que cuelga de ella. El contratista se conserva.

    [VERIFICAR] docs/readme.md no define el borrado de un proyecto.
    """
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")

    nombre = proyecto.nombre
    codigo = proyecto.codigo
    etiqueta = nombre if codigo is None else f"{nombre} · {codigo}"
    registrar(
        db,
        usuario,
        "borrar_proyecto",
        tipo_documento="proyecto",
        documento_id=proyecto_id,
        etiqueta=etiqueta,
    )

    params = {"id": proyecto_id}
    db.execute(
        text(
            """
            UPDATE factura
            SET duplicado_de_id = NULL
            WHERE proyecto_id = :id
               OR duplicado_de_id IN (SELECT id FROM factura WHERE proyecto_id = :id)
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM asignacion
            WHERE factura_id IN (SELECT id FROM factura WHERE proyecto_id = :id)
               OR nave_id IN (SELECT id FROM nave WHERE proyecto_id = :id)
               OR tarea_id IN (
                    SELECT tarea.id FROM tarea
                    JOIN nave ON nave.id = tarea.nave_id
                    WHERE nave.proyecto_id = :id
               )
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM linea_factura
            WHERE factura_id IN (SELECT id FROM factura WHERE proyecto_id = :id)
               OR tarea_id IN (
                    SELECT tarea.id FROM tarea
                    JOIN nave ON nave.id = tarea.nave_id
                    WHERE nave.proyecto_id = :id
               )
            """
        ),
        params,
    )
    db.execute(text("DELETE FROM factura WHERE proyecto_id = :id"), params)
    db.execute(
        text("UPDATE contrato SET tarea_apartado_id = NULL WHERE proyecto_id = :id"),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM contrato_apartado
            WHERE contrato_id IN (SELECT id FROM contrato WHERE proyecto_id = :id)
               OR tarea_id IN (
                    SELECT tarea.id FROM tarea
                    JOIN nave ON nave.id = tarea.nave_id
                    WHERE nave.proyecto_id = :id
               )
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM linea_pdf_cliente_tarea
            WHERE linea_id IN (
                SELECT linea_pdf_cliente.id
                FROM linea_pdf_cliente
                JOIN presupuesto ON presupuesto.id = linea_pdf_cliente.presupuesto_id
                WHERE presupuesto.proyecto_id = :id
            )
            OR tarea_id IN (
                SELECT tarea.id FROM tarea
                JOIN nave ON nave.id = tarea.nave_id
                WHERE nave.proyecto_id = :id
            )
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM linea_pdf_cliente
            WHERE presupuesto_id IN (
                SELECT id FROM presupuesto WHERE proyecto_id = :id
            )
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            UPDATE tarea
            SET tarea_padre_id = NULL, contrato_id = NULL
            WHERE nave_id IN (SELECT id FROM nave WHERE proyecto_id = :id)
            """
        ),
        params,
    )
    db.execute(
        text(
            """
            DELETE FROM tarea
            WHERE nave_id IN (SELECT id FROM nave WHERE proyecto_id = :id)
            """
        ),
        params,
    )
    db.execute(text("DELETE FROM pedido WHERE proyecto_id = :id"), params)
    db.execute(text("DELETE FROM contrato WHERE proyecto_id = :id"), params)
    db.execute(text("DELETE FROM presupuesto WHERE proyecto_id = :id"), params)
    db.execute(text("DELETE FROM nave WHERE proyecto_id = :id"), params)
    mano_obra_svc.borrar_partes_de_la_obra(db, proyecto_id)
    db.delete(proyecto)
    db.commit()
    almacen_svc.borrar_proyecto(proyecto_id)


def asignar_codigo_contrato(
    db: Session,
    proyecto_id: int,
    contrato_id: int,
    codigo: str,
) -> Contrato:
    """Guarda el código que la persona indica cuando el PDF no lo traía."""
    contrato = db.get(Contrato, contrato_id)
    if contrato is None or contrato.proyecto_id != proyecto_id:
        raise ValueError(f"Contrato {contrato_id} no encontrado")
    otro = (
        db.query(Contrato)
        .filter(Contrato.codigo == codigo, Contrato.id != contrato.id)
        .first()
    )
    if otro is not None:
        raise ValueError("Ese código ya está en otro contrato.")
    contrato.codigo = codigo
    if contrato.aviso in {AVISO_SIN_CODIGO, AVISO_VARIOS, AVISO_REPETIDO}:
        contrato.aviso = None
    pendientes = (
        db.query(Factura)
        .filter(
            Factura.proyecto_id == proyecto_id,
            Factura.contratista_id == contrato.contratista_id,
            Factura.codigo_contrato == codigo,
            Factura.contrato_id.is_(None),
        )
        .all()
    )
    for factura in pendientes:
        factura.contrato_id = contrato.id
        factura.aviso_codigo = None
    db.commit()
    db.refresh(contrato)
    return contrato
