# Arranque del gestor de obra

Guía para dejar el proyecto en marcha en Windows, macOS o Linux. El front no se compila: FastAPI sirve el HTML desde `app/static/`.

Lo único que cambia entre máquinas es cómo activas el entorno de Python y cómo levantas PostgreSQL. El resto de comandos es el mismo.

## 1. Qué hace falta

- **Python 3.11 o superior.** Comprueba con `python --version` o `python3 --version`. En Windows, si `python` no existe, usa el lanzador `py -3.11`.
- **PostgreSQL 16 con las extensiones `pgvector` y `pg_trgm`.** La imagen oficial de Postgres no trae `pgvector`. El camino que vale en cualquier sistema es el contenedor `pgvector/pgvector:pg16` (sección 3).
- **Git** y, para la base, **Docker** (Docker Desktop en Windows y macOS, Docker Engine en Linux).
- **Claves de LLM u OCR:** opcionales. Sin ellas arranca la aplicación y se pueden leer PDF con texto. Los escaneados e imágenes piden `OCR_API_*` o `LLM_API_*`, y eso solo si Seguridad lo autoriza (sección 8).

No hace falta Node, ni un bundler, ni Tesseract en el sistema.

## 2. Código y dependencias

Desde la raíz del repositorio.

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si `py` no está, sustituye `py -3.11` por `python`. No hace falta activar el entorno: llama siempre a `.\.venv\Scripts\python.exe`. Si prefieres activarlo:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea el script, en esa misma ventana:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**macOS y Linux:**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Para activar el entorno en la sesión actual: `source .venv/bin/activate`. A partir de ahí, `python` y `pip` son los del `.venv`.

## 3. Base de datos

La aplicación habla con Postgres por `DATABASE_URL`. El ejemplo del repo usa el puerto **5433** en el host para no chocar con un Postgres que ya escuche en el 5432.

### 3.1. Contenedor (recomendado, mismo comando en todos los sistemas)

Con Docker en marcha:

```bash
docker run -d --name gestor-obra-db \
  -e POSTGRES_USER=usuario \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=gestor_obra \
  -p 5433:5432 \
  pgvector/pgvector:pg16
```

En PowerShell el salto de línea es el acento grave (`` ` ``), no la barra invertida. También puedes pegarlo en una sola línea.

Ese usuario es superusuario del contenedor y puede crear las extensiones. Alembic las crea al migrar; no hace falta un `CREATE EXTENSION` a mano.

Comprueba que el contenedor está arriba: `docker ps`. Para pararlo: `docker stop gestor-obra-db`. Para volver a usarlo: `docker start gestor-obra-db`.

### 3.2. Postgres ya instalado en la máquina

Solo si el servidor tiene el paquete de `pgvector` (en Debian/Ubuntu, `postgresql-16-pgvector`; en macOS, `brew install pgvector`). En Windows nativo es más frágil: usa el contenedor.

1. Crea la base `gestor_obra`.
2. El usuario de `DATABASE_URL` tiene que poder ejecutar `CREATE EXTENSION`.
3. Si el servidor escucha en el 5432, apunta la URL a ese puerto.

`pg_trgm` viene con `postgresql-contrib`. `vector` no: sin el paquete, `alembic upgrade head` falla al crear la extensión.

## 4. Variables de entorno

Copia la plantilla y no subas el resultado: `.env` está en `.gitignore`.

**Windows (PowerShell):** `Copy-Item .env.example .env`

**macOS y Linux:** `cp .env.example .env`

Con el contenedor de la sección 3.1, deja esta línea:

```text
DATABASE_URL=postgresql+psycopg://usuario:password@localhost:5433/gestor_obra
```

El driver es `postgresql+psycopg` (no `postgresql://` a secas). Si la contraseña lleva `@`, `:`, `/` o `#`, codifícala en la URL (`@` → `%40`).

Si no existe `.env`, la app usa el valor por defecto de `app/config.py`: mismo usuario y base, pero puerto **5432**. El ejemplo del repo y ese defecto no coinciden a propósito: el 5433 es el del contenedor.

Las claves `LLM_*` y `OCR_*` pueden quedarse vacías para arrancar.

## 5. Migraciones

Desde la raíz, con el `.env` ya creado y Postgres aceptando conexiones:

**Windows:**

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

**macOS y Linux** (con el entorno activado, o con `.venv/bin/python`):

```bash
python -m alembic upgrade head
```

Alembic lee `DATABASE_URL` desde `app.config` (ignora la URL de ejemplo de `alembic.ini`) y, antes de las tablas, ejecuta `CREATE EXTENSION` de `vector` y `pg_trgm`.

`python -m app.seed` hoy lanza `NotImplementedError`. Las semillas no forman parte del arranque.

## 6. Arrancar la aplicación

**Windows:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**macOS y Linux:**

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Interfaz: http://127.0.0.1:8000/
- Salud del proceso: http://127.0.0.1:8000/health → `{"status":"ok"}`
- OpenAPI: http://127.0.0.1:8000/docs

`/health` solo dice que el proceso responde. No abre la base. La primera pantalla que lista proyectos sí la usa: si Postgres está parado, esa llamada falla aunque `/health` siga en ok.

Para cortar el servidor: Ctrl+C.

## 7. Tests

`pytest` usa la misma `DATABASE_URL` y **escribe filas de verdad** en esa base. Apúntala a `gestor_obra` local (o a otra base de pruebas), nunca a datos de obra.

```bash
python -m pytest
```

En Windows, el intérprete es `.\.venv\Scripts\python.exe -m pytest`.

## 8. OCR y LLM (opcional)

Los PDF con texto seleccionable se leen en local (PyMuPDF / pdfplumber). No hace falta clave.

Escaneados e imágenes (JPG, PNG, TIFF, PDF sin texto) siguen este orden:

1. OCR cloud, si hay `OCR_API_KEY` y `OCR_API_BASE`.
2. Visión del LLM, si hay `LLM_API_KEY`.
3. Tesseract, solo si ya está instalado. No es requisito y `pytesseract` no está en `requirements.txt`.

Presupuestos, contratos y facturas llevan datos personales y financieros. Mandarlos a un proveedor cloud exige autorización de ai.seguridad@exafan.com y cláusula de no entrenamiento. Sin esa autorización, deja las claves vacías.

Para extracción de presupuesto con LLM, en `.env`:

- Claude: `LLM_API_KEY` rellena y `LLM_API_BASE` vacía.
- Otro proveedor compatible: `LLM_PROVEEDOR=openai` y `LLM_API_BASE` con la URL que termine en `/v1`.

Tras cambiar `.env` hay que reiniciar Uvicorn. La configuración se cachea al arrancar.

## 9. Si algo no arranca

| Síntoma | Qué revisar |
| --- | --- |
| `python` no se reconoce en Windows | Usa `py -3.11`, o la ruta `.\.venv\Scripts\python.exe`. |
| PowerShell no deja activar el venv | Activa solo para ese proceso (sección 2) o no actives y llama al `python.exe` del `.venv`. |
| `connection refused` en el puerto 5433 | El contenedor no está en marcha (`docker start gestor-obra-db`) o `DATABASE_URL` apunta a otro puerto. |
| Falla `CREATE EXTENSION vector` | El servidor no es una imagen/paquete con `pgvector`. Cambia al contenedor de la sección 3.1. |
| `alembic` no ve la base nueva | El comando se lanzó fuera de la raíz, o `.env` no está ahí. `get_settings` lee `.env` del directorio de trabajo. |
| La UI carga y las listas fallan | `/health` no prueba Postgres. Revisa que el contenedor sigue arriba y que la URL coincide. |
| Escaneado sin texto | Faltan claves autorizadas. Con PDF nativo no deberían hacer falta. |
| Puerto 8000 ocupado | Añade `--port 8001` (u otro libre) al comando de Uvicorn. |
