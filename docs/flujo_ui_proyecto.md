# Flujo de UI — Proyecto, apartados y contratos

Documento de producto acordado (15 septiembre 2026). Describe cómo se usa la aplicación en el día a día. Complementa `contexto_proyecto_obra.md` y la sección 1.3 de `readme.md`.

---

## Idea en una frase

El **presupuesto** crea el **proyecto** y su lista de **apartados**. Dentro del proyecto se suben los **contratos** de subcontrata y el sistema **sugiere** qué contrato va con cada apartado; una persona confirma el enlace.

---

## Flujo paso a paso

### 1. Subir el presupuesto

1. El jefe de obra sube el presupuesto (PDF nativo, PDF escaneado o imagen; fixtures `.md` en pruebas).
2. Si es escaneado/imagen, pasa por OCR y se marca `es_escaneado`. El sistema extrae naves y apartados (y partidas solo si el documento las trae).
3. Eso **crea el proyecto**. El documento queda en `pendiente_revision`: no se da por “guardado” hasta la revisión humana.
4. Si hay anotación manuscrita (`tiene_anotacion_manual = true`) o el origen es escaneado, la revisión es obligatoria antes de confirmar.

### 2. Pantalla del proyecto = lista de apartados

Tras la creación (y tras confirmar la revisión del presupuesto), la vista principal del proyecto muestra:

- Cabecera: nombre, estado, naves.
- **Lista de apartados** del presupuesto: código, descripción, importe presupuestado, estado de revisión, y si ya hay un contrato enlazado.
- Acciones: subir contrato, ir a revisión, control económico.

Los apartados son filas `TAREA` con `nivel = "apartado"` y `presupuesto_id` relleno. La jerarquía más fina (subapartado / partida) cuelga con `tarea_padre_id` cuando un contrato o el propio presupuesto la aportan.

### 3. Subir contratos dentro del proyecto

1. Desde la pantalla del proyecto se sube el contrato firmado con un subcontratista.
2. El sistema extrae contratista, precio total, plazo y, si existe, el desglose fino (p. ej. por salas).
3. Ese desglose se guarda como árbol propio de `TAREA` con `contrato_id` (no mezcla ni sustituye los apartados del presupuesto).
4. El contrato también queda pendiente de revisión humana hasta confirmar.

### 4. Sugerencia automática contrato ↔ apartado

Tras importar un contrato (o al abrir el proyecto):

1. El sistema propone qué **apartado de presupuesto** encaja con ese contrato (texto del objeto/descripciones del contrato vs. código y descripción del apartado; en MVP reglas + similitud de texto; `pg_trgm` / embeddings cuando haga falta).
2. La propuesta es una **sugerencia**: no se enlaza sola.
3. La persona confirma o elige otro apartado.
4. Al confirmar se guarda `CONTRATO.tarea_apartado_id` → FK al apartado de presupuesto. Queda trazable el cruce presupuestado vs. contratado (caso real: electricidad).

Reglas:

- Un contrato sin confirmar no cuenta como enlace medido en control económico por apartado.
- Varios contratos pueden apuntar a apartados distintos; un apartado puede acabar con cero o un contrato (MVP: un enlace principal por contrato). **[VERIFICAR]** si un apartado puede tener varios contratos a la vez.
- El desglose del contrato (hijas con precio unitario) no se asume igual al del presupuesto: se muestra aparte hasta confirmar el enlace al apartado padre.

### 5. Facturas y seguimiento

1. Administración sube una factura desde la pantalla de facturas del proyecto.
2. El sistema lee el texto nativo o aplica OCR y casa el NIF con `CONTRATISTA`.
3. Solo propone contratos confirmados del mismo proyecto y contratista.
4. La factura se registra como `pendiente`; una persona revisa importes, tipo,
   líneas y contrato antes de confirmarla.
5. Solo las facturas con `estado_revision = "confirmada"` cuentan en el control
   económico y en el seguimiento contratado vs. facturado de cada apartado.

---

## Pantallas

| Pantalla | Rol en este flujo |
|---|---|
| Subir presupuesto | Arranca el flujo; crea proyecto |
| Revisión humana | Confirma presupuesto/contrato antes de darlos por válidos |
| **Proyecto** (lista de apartados) | Vista central: apartados + subir/enlazar contratos |
| Subir contrato | También accesible desde el proyecto (atajo legacy) |
| Facturas | Carga, revisión humana y confirmación del contrato asociado |
| Control económico | Desvíos cuando ya hay enlaces y facturas |

---

## API asociada (resumen)

- `POST /proyectos/importar-presupuesto` → crea proyecto + apartados (pendiente revisión).
- `GET /proyectos/{id}` → detalle con naves, **apartados** y **contratos** (con sugerencia si aún no hay enlace).
- `POST /proyectos/{id}/importar-contrato` → crea contrato + árbol propio; responde con sugerencias de apartado.
- `POST /proyectos/{id}/contratos/{contrato_id}/enlazar-apartado` → confirma (o corrige) el enlace; valida en backend con Pydantic.
- `POST /facturas` → extrae una factura y la deja pendiente de revisión.
- `GET /facturas?proyecto_id={id}` y `GET /facturas/{id}` → listado y revisión.
- `POST /facturas/{id}/confirmar` → valida y confirma los datos y el contrato.

---

## Qué no hace este flujo

- No inventa partidas con precio unitario si el presupuesto solo cierra por apartado.
- No mezcla el árbol del contrato bajo el apartado del presupuesto al importar: el enlace es a nivel contrato ↔ apartado, no un `tarea_padre_id` cruzado.
- No da por guardado un documento OCR/LLM sin revisión humana.
- No incluye facturas pendientes en los importes facturados.
