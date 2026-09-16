# Stack tecnológico — Gestor de presupuestos y facturas de obra

Núcleo relacional (PostgreSQL) con capa vectorial, backend en Python por el peso de PDF/OCR/IA y front ligero en HTML + Alpine.js.

*Versión 2 — 6 de septiembre de 2026. Sin cambios de arquitectura; se ajustan los apartados de modelo de datos y de revisión humana con los hallazgos de un presupuesto y un contrato reales anonimizados.*

---

## 1. Decisión en una línea

- **Front:** HTML + Alpine.js + Chart.js. Ligero, sin build.
- **Back:** Python con FastAPI.
- **BDD:** PostgreSQL + `pgvector` + `pg_trgm`.
- **IA/OCR:** lectura de PDF, OCR de escaneados, extracción con LLM y embeddings para el casado.

Una sola base de datos hace todo (relacional + vectorial). No montamos base vectorial dedicada.

## 2. Por qué este stack

- **El back pide Python.** Todo el trabajo duro está ahí: leer PDF nativos, OCR de escaneados, extracción estructurada con LLM y embeddings. El ecosistema Python es mucho más maduro que Node en esto.
- **Los datos son relacionales de verdad.** Proyecto → naves → partidas (con jerarquía apartado/subapartado/partida) → contratos → facturas → importes → estados exige integridad referencial y sumas que cuadren. Eso es SQL, no un almacén de documentos.
- **La jerarquía de partidas no obliga a cambiar de modelo.** Un presupuesto que cierra por apartado y un contrato que baja a partida con precio unitario son el mismo tipo de fila con distinto nivel de detalle: se resuelve con una tabla auto-referenciada (`tarea_padre_id`), no con un motor de documentos.
- **Lo vectorial es un medio, no el fin.** Resuelve el casado factura-partida (concepto de la factura ↔ descripción de la partida). No necesita infraestructura aparte: cabe en Postgres.
- **El front debe ser ligero.** Alpine da la reactividad que necesita la pantalla de revisión sin bundler ni proyecto separado; se sirve desde el propio FastAPI.

## 3. Componentes

### Front
- **HTML + Alpine.js:** reactividad con atributos en el propio HTML. Cero build, un `<script>` desde CDN.
- **Chart.js:** gráficos de desvío presupuesto vs. contratado vs. gasto real.
- **Tabulator** (opcional): tablas editables si la revisión crece en complejidad — especialmente útil para revisar jerarquías apartado → partida con varios niveles.
- Se sirve desde FastAPI: un solo proyecto, sin front aparte.

### Back
- **FastAPI (Python):** API tipada con Pydantic, que además valida los datos extraídos casi gratis.
- Librerías de documento: **PyMuPDF** o **pdfplumber** para PDF nativos.

### Base de datos
- **PostgreSQL:** modelo relacional (proyectos, naves, partidas jerárquicas, contratos, facturas, casado, estados).
- **`pgvector`:** embeddings para el casado semántico, en la misma base.
- **`pg_trgm`:** match difuso por texto (trigramas), suficiente para el MVP.

### IA / OCR
- **Presupuestos:** pueden ser PDF nativo, **PDF escaneado o imagen** (JPG/PNG/TIFF). El nativo se lee con PyMuPDF/pdfplumber; el escaneado/imagen pasa por **OCR**. Baja fiabilidad → `es_escaneado = true` y revisión humana obligatoria.
- **OCR sin instalar nada en el SO (camino por defecto):** API cloud (`OCR_API_*`) o visión del LLM (`LLM_API_*` + `LLM_VISION_MODEL`). Solo pip (`pillow`, `pymupdf`). Requiere autorización de Seguridad y [NO-ENTRENAR].
- PDF nativos: lectura fiable **en el texto impreso**. Pueden llevar anotaciones manuscritas que prevalecen sobre el valor impreso. Tampoco se guardan sin revisión humana.
- PDF/imagen escaneados (presupuestos y facturas): OCR cloud/visión; Tesseract local es **opcional**, no requisito.
- Extracción estructurada de apartados/partidas: **LLM vía API**, con un prompt que debe distinguir explícitamente entre valor impreso y valor manuscrito cuando ambos aparecen, y marcar el caso para revisión obligatoria.
- Casado: **embeddings** para proponer candidatos + reglas duras (proveedor/NIF, fechas, importe) para rankear.

## 4. Alternativas de stack

- **Opción A (recomendada) — Python full.** Front HTML+Alpine, back FastAPI, Postgres+pgvector. Un solo lenguaje donde importa; Postgres hace de todo. Es la del MVP.
- **Opción B — Todo TypeScript.** Next.js/NestJS + Postgres+pgvector. Un único lenguaje, equipo más pequeño. Punto débil: las librerías JS de OCR/PDF son más flojas, justo donde más nos la jugamos.
- **Opción C — Híbrido.** Orquestación en TS + microservicio de IA en FastAPI aislado. Escala mejor, pero añade infraestructura. Solo con volumen alto o si la parte de IA va a crecer mucho.

## 5. El sistema vectorial, matizado

- Brilla en el casado factura-partida: embedding del concepto de la factura → partidas más parecidas por similitud → rankeo con reglas de negocio. Vectores para el "se parece", reglas para el "cuadra".
- **No** base vectorial dedicada (Pinecone, Qdrant, Weaviate): un proyecto tiene decenas de partidas, no millones. `pgvector` sobra.
- En el MVP puede bastar `pg_trgm` + reglas. Lo vectorial es la mejora natural cuando el match por texto se quede corto, no el punto de partida obligatorio.
- **Plan:** arrancar con Postgres + reglas + `pg_trgm`; tener `pgvector` listo para activar la capa semántica en la fase de facturas. Misma base de datos.

## 6. Orden de trabajo

1. Ingesta de presupuestos (PDF nativo **o escaneado/imagen** → OCR si hace falta → naves y partidas jerárquicas). Validar antes de seguir.
2. Modelo de datos y control económico (presupuesto vs. contratado vs. gasto real).
3. Ingesta de contratos de subcontrata (cuando aporten desglose más fino que el presupuesto).
4. Ingesta de facturas + OCR + pantalla de revisión humana.
5. Casado factura-partida (reglas → `pg_trgm` → `pgvector`).

## 7. Privacidad y datos [SENSIBLE]

- Los presupuestos, contratos y facturas llevan NIF, nombres, direcciones e importes pactados. Mandar eso a OCR/LLM en la nube es sacar datos personales y financieros a terceros.
- Validar con **ai.seguridad@exafan.com** y asegurar por contrato que el proveedor **no entrena con esos datos** [NO-ENTRENAR].
- Si Seguridad no lo autoriza: OCR/LLM self-hosted en nuestra infra (contenedor), no Tesseract en cada PC de desarrollo. Menos calidad o más mantenimiento, pero los datos no salen.
- La pantalla de revisión humana no es opcional: aplica a presupuestos escaneados, facturas escaneadas, y también a presupuestos/contratos nativos con anotaciones manuscritas.
- La validación del front (no guardar hasta verificar) es comodidad, no seguridad. Repetirla siempre en el back.
- No subir documentos reales sin anonimizar. Datos dudosos → [VERIFICAR].
- Ya existen dos fixtures anonimizadas para diseño y test: `presupuesto_nave_destete_anonimizado.md` y `contrato_subcontrata_electricidad_anonimizado.md`.

---

*Documento de trabajo interno. Pendiente de cerrar: si el cierre por apartado es el patrón general de los presupuestos, si el desglose por Sala del contrato sobrevive a la factura real, origen de las facturas (Drive vs SharePoint) y existencia de ERP previo. [VERIFICAR]*
