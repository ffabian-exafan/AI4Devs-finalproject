"""Endpoints de proyectos (ingesta de presupuesto y contrato)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Contrato, Factura, Presupuesto
from app.schemas.casado import EnlazarApartadoIn, EnlazarApartadoOut
from app.schemas.contrato import ImportarContratoOut
from app.schemas.control_economico import ControlEconomicoOut
from app.schemas.presupuesto import (
    ContrastarClienteOut,
    ImporteClienteIn,
    ImporteClienteOut,
    ImportarExcelOut,
    ImportarPresupuestoOut,
    ImportesClienteIn,
    ImportesClienteOut,
)
from app.schemas.proyecto import ProyectoDetalleOut, ProyectoRead
from app.schemas.tarea import LineaPresupuestoIn, LineaPresupuestoOut
from app.services import almacen as almacen_svc
from app.services import casado as casado_svc
from app.services import economico as economico_svc
from app.services import ingesta as ingesta_svc
from app.services import lineas as lineas_svc
from app.services import presupuesto_excel as presupuesto_excel_svc
from app.services import proyectos as proyectos_svc

router = APIRouter(tags=["proyectos"])


@router.get("/proyectos", response_model=list[ProyectoRead])
def listar_proyectos(db: Session = Depends(get_db)) -> list[ProyectoRead]:
    return proyectos_svc.listar_proyectos(db)


@router.delete("/proyectos/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_proyecto(proyecto_id: int, db: Session = Depends(get_db)) -> None:
    try:
        proyectos_svc.borrar_proyecto(db, proyecto_id)
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
) -> None:
    try:
        lineas_svc.borrar_linea(db, proyecto_id, tarea_id)
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
        return ingesta_svc.importar_presupuesto(db, contenido, fichero.filename)
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
    "/proyectos/{proyecto_id}/contrastar-presupuesto-cliente",
    response_model=ContrastarClienteOut,
    status_code=status.HTTP_201_CREATED,
)
async def contrastar_presupuesto_cliente(
    proyecto_id: int,
    fichero: UploadFile = File(...),
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
            db, proyecto_id, contenido, fichero.filename
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
) -> ImporteClienteOut:
    try:
        return presupuesto_excel_svc.confirmar_importe_cliente(
            db, proyecto_id, tarea_id, body.importe
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
) -> ImportesClienteOut:
    try:
        return presupuesto_excel_svc.confirmar_importes_cliente(
            db, proyecto_id, body.tarea_ids, body.importe, body.linea_id
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc


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
        contrato, apartado = casado_svc.enlazar_contrato_apartado(
            db,
            proyecto_id,
            contrato_id,
            body.tarea_apartado_id,
        )
    except ValueError as exc:
        detail = str(exc)
        codigo = (
            status.HTTP_404_NOT_FOUND
            if "no encontrado" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=codigo, detail=detail) from exc

    return EnlazarApartadoOut(
        contrato_id=contrato.id,
        tarea_apartado_id=apartado.id,
        codigo_apartado=apartado.codigo,
        descripcion_apartado=apartado.descripcion,
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


@router.get("/proyectos/{proyecto_id}/presupuestos/{presupuesto_id}/fichero")
def descargar_presupuesto(
    proyecto_id: int,
    presupuesto_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Presupuesto, presupuesto_id)
    if doc is None or doc.proyecto_id != proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado",
        )
    return _responder_fichero(doc.ruta_almacen, doc.fichero_origen)


@router.get("/proyectos/{proyecto_id}/contratos/{contrato_id}/fichero")
def descargar_contrato(
    proyecto_id: int,
    contrato_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Contrato, contrato_id)
    if doc is None or doc.proyecto_id != proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contrato no encontrado",
        )
    return _responder_fichero(doc.ruta_almacen, doc.fichero_origen)


@router.get("/proyectos/{proyecto_id}/facturas/{factura_id}/fichero")
def descargar_factura(
    proyecto_id: int,
    factura_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    doc = db.get(Factura, factura_id)
    if doc is None or doc.proyecto_id != proyecto_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factura no encontrada",
        )
    return _responder_fichero(doc.ruta_almacen, doc.fichero_origen)


def _responder_fichero(ruta_almacen: str | None, nombre: str) -> FileResponse:
    ruta = almacen_svc.abrir_si_existe(ruta_almacen)
    if ruta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El fichero no está guardado",
        )
    return FileResponse(
        path=ruta,
        filename=nombre or ruta.name,
        media_type="application/octet-stream",
    )
