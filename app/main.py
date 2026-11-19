"""Arranque FastAPI: sirve el front estático y monta routers."""

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from app.config import get_settings
from app.routers import auth, facturas, health, mano_obra, proyectos, registro, revisiones, usuarios, vista
from app.services.barrido_facturas import bucle_barrido_diario, programar_barrido

STATIC_DIR = Path(__file__).resolve().parent / "static"

@asynccontextmanager
async def _vida(_app: FastAPI):
    tarea = asyncio.create_task(bucle_barrido_diario()) if programar_barrido() else None
    try:
        yield
    finally:
        if tarea is not None:
            tarea.cancel()
            with suppress(asyncio.CancelledError):
                await tarea


app = FastAPI(
    title="Cuadra",
    version="0.2.0",
    lifespan=_vida,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(proyectos.router)
app.include_router(mano_obra.router)
app.include_router(revisiones.router)
app.include_router(facturas.router)
app.include_router(vista.router)
app.include_router(registro.router)


@app.middleware("http")
async def exige_login_en_paginas(request: Request, call_next):
    """Las pantallas piden sesión. La API de obra sigue abierta. [VERIFICAR]"""
    path = request.url.path
    es_pagina = request.method == "GET" and (path == "/" or path.endswith(".html"))
    if es_pagina and path != "/login.html" and not request.session.get("usuario_id"):
        return RedirectResponse(f"/login.html?next={quote(path)}", status_code=303)
    return await call_next(request)


# La sesión tiene que envolver al middleware de las páginas para que request.session exista.
app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().session_secret,
    same_site="lax",
    https_only=False,
    max_age=60 * 60 * 12,
)

# El front se sirve en "/". Los routers de API deben registrarse antes del mount.
app.mount(
    "/",
    StaticFiles(directory=STATIC_DIR, html=True),
    name="static",
)
