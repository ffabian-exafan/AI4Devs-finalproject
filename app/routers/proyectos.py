"""Endpoints de proyectos (ingesta de presupuesto y contrato)."""

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import usuario_actual
from app.models import Contrato, Factura, Pedido, Presupuesto, Usuario
from app.schemas.casado import (
    ApartadoEnlazadoOut,
    DesenlazarApartadoOut,
    EnlazarApartadoIn,
    EnlazarApartadoOut,
)
from app.schemas.contrato import CodigoContratoIn, CodigoContratoOut, ImportarContratoOut
from app.schemas.control_economico import ControlEconomicoOut
from app.schemas.pedido import ImportarPedidosOut
from app.schemas.presupuesto import (
    ContrastarClienteOut,
    ImporteClienteIn,
    LineaPdfManualIn,
    ImporteClienteOut,
    ImportarExcelOut,
    ImportarPresupuestoOut,
    ImportesClienteIn,
    ImportesClienteOut,
    SoloGestionOut,
)
from app.schemas.proyecto import ProyectoDetalleOut, ProyectoRead
from app.schemas.tarea import LineaPresupuestoIn, LineaPresupuestoOut
from app.services import almacen as almacen_svc
from app.services import casado as casado_svc
from app.services import economico as economico_svc
from app.services import ingesta as ingesta_svc
from app.services import linea_pdf_manual as linea_pdf_manual_svc
from app.services import lineas as lineas_svc
from app.services import pedidos as pedidos_svc
from app.services import presupuesto_excel as presupuesto_excel_svc
from app.services import proyectos as proyectos_svc
from app.services import solo_gestion as solo_gestion_svc
from app.services import sujeto_pasivo as sujeto_pasivo_svc

router = APIRouter(tags=["proyectos"])


def _ver_pagina(valor: str | None) -> bool:
    return (valor or "").strip().lower() in {"1", "true", "on", "si", "sí", "yes"}


@router.get("/proyectos", response_model=list[ProyectoRead])
def listar_proyectos(db: Session = Depends(get_db)) -> list[ProyectoRead]:
    return proyectos_svc.listar_proyectos(db)


@router.delete("/proyectos/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> None:
    try:
        proyectos_svc.borrar_proyecto(db, proyecto_id, actual)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/{proyecto_id}/lineas",
    response_model=LineaPresupuestoOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_linea(
    proyecto_id: int,
    payload: LineaPresupuestoIn,
    db: Session = Depends(get_db),
) -> LineaPresupuestoOut:
    try:
        return lineas_svc.crear_linea(db, proyecto_id, payload)
    except lineas_svc.LineaNoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.patch(
    "/proyectos/{proyecto_id}/lineas/{tarea_id}",
    response_model=LineaPresupuestoOut,
)
def editar_linea(
    proyecto_id: int,
    tarea_id: int,
    payload: LineaPresupuestoIn,
    db: Session = Depends(get_db),
) -> LineaPresupuestoOut:
    try:
        return lineas_svc.editar_linea(db, proyecto_id, tarea_id, payload)
    except lineas_svc.LineaNoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.delete(
    "/proyectos/{proyecto_id}/lineas/{tarea_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def borrar_linea(
    proyecto_id: int,
    tarea_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> None:
    try:
        lineas_svc.borrar_linea(db, proyecto_id, tarea_id, actual)
    except lineas_svc.LineaNoEncontrada as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except lineas_svc.LineaEnlazada as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/proyectos/{proyecto_id}", response_model=ProyectoDetalleOut)
def obtener_proyecto(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> ProyectoDetalleOut:
    try:
        return proyectos_svc.obtener_proyecto(db, proyecto_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/importar-presupuesto",
    response_model=ImportarPresupuestoOut,
    status_code=status.HTTP_201_CREATED,
)
async def importar_presupuesto(
    fichero: UploadFile = File(...),
    ver_pagina: str = Form(""),
    db: Session = Depends(get_db),
) -> ImportarPresupuestoOut:
    if not fichero.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el nombre del fichero",
        )

    contenido = await fichero.read()
    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío",
        )

    try:
        return ingesta_svc.importar_presupuesto(
            db,
            contenido,
            fichero.filename,
            forzar_vision=_ver_pagina(ver_pagina),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/importar-presupuestos-excel",
    response_model=ImportarExcelOut,
    status_code=status.HTTP_201_CREATED,
)
async def importar_presupuestos_excel(
    nombre: str = Form(...),
    ficheros: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> ImportarExcelOut:
    pares = await _leer_excels(ficheros)
    try:
        return presupuesto_excel_svc.importar_presupuestos_excel(db, nombre, pares)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/{proyecto_id}/presupuestos-excel",
    response_model=ImportarExcelOut,
    status_code=status.HTTP_201_CREATED,
)
async def anadir_presupuesto_excel(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportarExcelOut:
    pares = await _leer_excels([fichero])
    try:
        nombre_f, contenido = pares[0]
        return presupuesto_excel_svc.anadir_presupuesto_excel(
            db, proyecto_id, nombre_f, contenido
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.post(
    "/proyectos/importar-pedidos",
    response_model=ImportarPedidosOut,
    status_code=status.HTTP_201_CREATED,
)
async def importar_pedidos(
    nombre: str = Form(...),
    ficheros: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> ImportarPedidosOut:
    pares = await _leer_excels(ficheros)
    try:
        return pedidos_svc.importar_pedidos(db, nombre, pares)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/{proyecto_id}/pedidos",
    response_model=ImportarPedidosOut,
    status_code=status.HTTP_201_CREATED,
)
async def anadir_pedido(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportarPedidosOut:
    pares = await _leer_excels([fichero])
    try:
        nombre_f, contenido = pares[0]
        return pedidos_svc.anadir_pedido(db, proyecto_id, nombre_f, contenido)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.get("/proyectos/{proyecto_id}/pedidos/{pedido_id}/fichero")
def descargar_pedido(
    proyecto_id: int,
    pedido_id: int,
    ver: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Pedido, pedido_id)
    if doc is None or doc.proyecto_id != proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado",
        )
    return _responder_fichero(doc.ruta_almacen, doc.fichero_origen, ver=ver)


@router.post(
    "/proyectos/{proyecto_id}/contrastar-presupuesto-cliente",
    response_model=ContrastarClienteOut,
    status_code=status.HTTP_201_CREATED,
)
async def contrastar_presupuesto_cliente(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    ver_pagina: str = Form(""),
    db: Session = Depends(get_db),
) -> ContrastarClienteOut:
    if not fichero.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el nombre del fichero",
        )
    contenido = await fichero.read()
    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío",
        )
    try:
        return presupuesto_excel_svc.contrastar_presupuesto_cliente(
            db,
            proyecto_id,
            contenido,
            fichero.filename,
            forzar_vision=_ver_pagina(ver_pagina),
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.get(
    "/proyectos/{proyecto_id}/contraste-cliente",
    response_model=ContrastarClienteOut,
)
def leer_contraste_cliente(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> ContrastarClienteOut:
    try:
        return presupuesto_excel_svc.obtener_contraste_cliente(db, proyecto_id)
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower() or "no tiene" in detail.lower() or "no está" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.post(
    "/proyectos/{proyecto_id}/apartados/{tarea_id}/importe-cliente",
    response_model=ImporteClienteOut,
)
def confirmar_importe_cliente(
    proyecto_id: int,
    tarea_id: int,
    body: ImporteClienteIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ImporteClienteOut:
    try:
        return presupuesto_excel_svc.confirmar_importe_cliente(
            db, proyecto_id, tarea_id, body.importe, actual
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.post(
    "/proyectos/{proyecto_id}/importe-cliente",
    response_model=ImportesClienteOut,
)
def confirmar_importes_cliente(
    proyecto_id: int,
    body: ImportesClienteIn,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ImportesClienteOut:
    try:
        return presupuesto_excel_svc.confirmar_importes_cliente(
            db, proyecto_id, body.tarea_ids, body.importe, body.linea_id, usuario=actual
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


def _error_linea_pdf(exc: ValueError) -> HTTPException:
    detail = str(exc)
    bajo = detail.lower()
    codigo = (
        status.HTTP_404_NOT_FOUND
        if "no encontrado" in bajo or "no encontrada" in bajo or "no tiene" in bajo
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(status_code=codigo, detail=detail)


@router.post(
    "/proyectos/{proyecto_id}/lineas-pdf",
    response_model=ContrastarClienteOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_linea_pdf_manual(
    proyecto_id: int,
    body: LineaPdfManualIn,
    db: Session = Depends(get_db),
) -> ContrastarClienteOut:
    try:
        return linea_pdf_manual_svc.crear(
            db, proyecto_id, body.codigo, body.descripcion, body.importe
        )
    except ValueError as exc:
        raise _error_linea_pdf(exc) from exc


@router.patch(
    "/proyectos/{proyecto_id}/lineas-pdf/{linea_id}",
    response_model=ContrastarClienteOut,
)
def editar_linea_pdf_manual(
    proyecto_id: int,
    linea_id: int,
    body: LineaPdfManualIn,
    db: Session = Depends(get_db),
) -> ContrastarClienteOut:
    try:
        return linea_pdf_manual_svc.editar(
            db, proyecto_id, linea_id, body.codigo, body.descripcion, body.importe
        )
    except ValueError as exc:
        raise _error_linea_pdf(exc) from exc


@router.delete(
    "/proyectos/{proyecto_id}/lineas-pdf/{linea_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def borrar_linea_pdf_manual(
    proyecto_id: int,
    linea_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        linea_pdf_manual_svc.borrar(db, proyecto_id, linea_id)
    except ValueError as exc:
        raise _error_linea_pdf(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _error_valor(exc: ValueError) -> HTTPException:
    detail = str(exc)
    bajo = detail.lower()
    codigo = (
        status.HTTP_404_NOT_FOUND
        if "no encontrado" in bajo or "no encontrada" in bajo
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return HTTPException(status_code=codigo, detail=detail)


@router.post(
    "/proyectos/{proyecto_id}/lineas-pdf/{linea_id}/solo-gestion",
    response_model=SoloGestionOut,
    status_code=status.HTTP_201_CREATED,
)
def marcar_solo_gestion(
    proyecto_id: int,
    linea_id: int,
    db: Session = Depends(get_db),
) -> SoloGestionOut:
    try:
        return solo_gestion_svc.marcar(db, proyecto_id, linea_id)
    except ValueError as exc:
        raise _error_valor(exc) from exc


@router.delete(
    "/proyectos/{proyecto_id}/lineas-pdf/{linea_id}/solo-gestion",
    status_code=status.HTTP_204_NO_CONTENT,
)
def desmarcar_solo_gestion(
    proyecto_id: int,
    linea_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        solo_gestion_svc.desmarcar(db, proyecto_id, linea_id)
    except ValueError as exc:
        raise _error_valor(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/proyectos/{proyecto_id}/apartados/{tarea_id}/confirmar-gestion",
    response_model=SoloGestionOut,
)
def confirmar_solo_gestion(
    proyecto_id: int,
    tarea_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> SoloGestionOut:
    try:
        return solo_gestion_svc.confirmar(db, proyecto_id, tarea_id, actual)
    except ValueError as exc:
        raise _error_valor(exc) from exc


@router.delete(
    "/proyectos/{proyecto_id}/contratos/{contrato_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def borrar_contrato(
    proyecto_id: int,
    contrato_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> Response:
    try:
        proyectos_svc.borrar_contrato(db, proyecto_id, contrato_id, actual)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/proyectos/{proyecto_id}/contratos/{contrato_id}/desenlazar-apartado",
    response_model=DesenlazarApartadoOut,
)
def desenlazar_apartado(
    proyecto_id: int,
    contrato_id: int,
    db: Session = Depends(get_db),
) -> DesenlazarApartadoOut:
    try:
        return solo_gestion_svc.desenlazar(db, proyecto_id, contrato_id)
    except ValueError as exc:
        raise _error_valor(exc) from exc


async def _leer_excels(ficheros: list[UploadFile]) -> list[tuple[str, bytes]]:
    if not ficheros:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el fichero",
        )
    pares: list[tuple[str, bytes]] = []
    for fichero in ficheros:
        if not fichero.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Falta el nombre del fichero",
            )
        contenido = await fichero.read()
        if not contenido:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El fichero está vacío",
            )
        pares.append((fichero.filename, contenido))
    return pares


@router.post(
    "/proyectos/{proyecto_id}/importar-contrato",
    response_model=ImportarContratoOut,
    status_code=status.HTTP_201_CREATED,
)
async def importar_contrato(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    nave_id: int | None = Form(default=None),
    ver_pagina: str = Form(""),
    db: Session = Depends(get_db),
) -> ImportarContratoOut:
    if not fichero.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Falta el nombre del fichero",
        )

    contenido = await fichero.read()
    if not contenido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fichero está vacío",
        )

    try:
        return ingesta_svc.importar_contrato(
            db,
            proyecto_id,
            contenido,
            fichero.filename,
            nave_id=nave_id,
            forzar_vision=_ver_pagina(ver_pagina),
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.post(
    "/proyectos/{proyecto_id}/contratos/{contrato_id}/codigo",
    response_model=CodigoContratoOut,
)
def guardar_codigo_contrato(
    proyecto_id: int,
    contrato_id: int,
    body: CodigoContratoIn,
    db: Session = Depends(get_db),
) -> CodigoContratoOut:
    try:
        contrato = proyectos_svc.asignar_codigo_contrato(
            db, proyecto_id, contrato_id, body.codigo
        )
    except ValueError as exc:
        raise _error_valor(exc) from exc
    return CodigoContratoOut(contrato_id=contrato.id, codigo=contrato.codigo or body.codigo)


@router.post(
    "/proyectos/{proyecto_id}/contratos/{contrato_id}/enlazar-apartado",
    response_model=EnlazarApartadoOut,
)
def enlazar_apartado(
    proyecto_id: int,
    contrato_id: int,
    body: EnlazarApartadoIn,
    db: Session = Depends(get_db),
) -> EnlazarApartadoOut:
    try:
        contrato, apartados = casado_svc.enlazar_contrato_apartado(
            db,
            proyecto_id,
            contrato_id,
            body.tarea_apartado_ids,
            explicaciones={item.tarea_id: item.explicacion for item in body.explicaciones},
            apartados_nuevos=[
                (item.linea_id, item.nombre, item.importe, item.explicacion)
                for item in body.apartados_nuevos
            ],
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower() or "no encontrada" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc

    primero = apartados[0]
    return EnlazarApartadoOut(
        contrato_id=contrato.id,
        tarea_apartado_id=primero.id,
        codigo_apartado=primero.codigo,
        descripcion_apartado=primero.descripcion,
        apartados=[
            ApartadoEnlazadoOut(
                tarea_apartado_id=ap.id,
                codigo_apartado=ap.codigo,
                descripcion_apartado=ap.descripcion,
            )
            for ap in apartados
        ],
    )


@router.get(
    "/proyectos/{proyecto_id}/control-economico",
    response_model=ControlEconomicoOut,
)
def control_economico(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> ControlEconomicoOut:
    try:
        return economico_svc.control_economico(db, proyecto_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/proyectos/{proyecto_id}/inversion-sujeto-pasivo",
    response_model=ProyectoDetalleOut,
)
async def marcar_inversion_sujeto_pasivo(
    proyecto_id: int,
    fichero: UploadFile = File(...),
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> ProyectoDetalleOut:
    contenido = await fichero.read()
    try:
        return sujeto_pasivo_svc.marcar(
            db,
            proyecto_id,
            actual,
            fichero.filename or "",
            contenido,
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


@router.delete(
    "/proyectos/{proyecto_id}/inversion-sujeto-pasivo",
    status_code=status.HTTP_204_NO_CONTENT,
)
def quitar_inversion_sujeto_pasivo(
    proyecto_id: int,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(usuario_actual),
) -> Response:
    try:
        sujeto_pasivo_svc.quitar(db, proyecto_id, actual)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/proyectos/{proyecto_id}/carta-isp")
def descargar_carta_isp(
    proyecto_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        ruta, nombre = sujeto_pasivo_svc.carta(db, proyecto_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return _responder_fichero(ruta, nombre)


@router.get("/proyectos/{proyecto_id}/presupuestos/{presupuesto_id}/fichero")
def descargar_presupuesto(
    proyecto_id: int,
    presupuesto_id: int,
    ver: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Presupuesto, presupuesto_id)
    if doc is None or doc.proyecto_id != proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado",
        )
    return _responder_fichero(doc.ruta_almacen, doc.fichero_origen, ver=ver)


@router.get("/proyectos/{proyecto_id}/contratos/{contrato_id}/fichero")
def descargar_contrato(
    proyecto_id: int,
    contrato_id: int,
    ver: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Contrato, contrato_id)
    if doc is None or doc.proyecto_id != proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado",
        )
    return _responder_fichero(doc.ruta_almacen, doc.fichero_origen, ver=ver)


@router.get("/proyectos/{proyecto_id}/facturas/{factura_id}/fichero")
def descargar_factura(
    proyecto_id: int,
    factura_id: int,
    ver: bool = False,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Factura, factura_id)
    if doc is None or doc.proyecto_id != proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada",
        )
    return _responder_fichero(doc.ruta_almacen, doc.fichero_origen, ver=ver)


def _responder_fichero(
    ruta_almacen: str | None,
    nombre: str,
    *,
    ver: bool = False,
    ausente: str = "El fichero no está guardado",
) -> FileResponse:
    ruta = almacen_svc.abrir_si_existe(ruta_almacen)
    if ruta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ausente,
        )
    nombre_final = nombre or ruta.name
    en_linea = ver and Path(nombre_final).suffix.lower() == ".pdf"
    return FileResponse(
        path=ruta,
        filename=nombre_final,
        media_type="application/pdf" if en_linea else "application/octet-stream",
        content_disposition_type="inline" if en_linea else "attachment",
    )
