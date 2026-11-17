"""Arranque FastAPI: sirve el front estático y monta routers."""

from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from app.config import get_settings
from app.routers import auth, facturas, health, proyectos, registro, revisiones, usuarios, vista

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Cuadra",
    version="0.2.0",
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(proyectos.router)
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
