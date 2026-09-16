"""Arranque FastAPI: sirve el front estático y monta routers."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import facturas, health, proyectos, revisiones

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Gestor de presupuestos y facturas de obra",
    version="0.2.0",
)

app.include_router(health.router)
app.include_router(proyectos.router)
app.include_router(revisiones.router)
app.include_router(facturas.router)

# El front se sirve en "/". Los routers de API deben registrarse antes del mount.
app.mount(
    "/",
    StaticFiles(directory=STATIC_DIR, html=True),
    name="static",
)
