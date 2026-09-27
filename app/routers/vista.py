"""Vista de obras: el cálculo vive en el servidor, la pantalla solo lo muestra."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.vista_obra import EstadoObraIn, VistaObraOut
from app.services import vista_obra as vista_svc

router = APIRouter(tags=["vista"])


@router.get("/vista/obra", response_model=VistaObraOut)
def obtener_vista() -> VistaObraOut:
    return vista_svc.construir_vista(vista_svc.estado_inicial())


@router.post("/vista/obra", response_model=VistaObraOut)
def aplicar_estado(body: EstadoObraIn) -> VistaObraOut:
    try:
        return vista_svc.construir_vista(body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
