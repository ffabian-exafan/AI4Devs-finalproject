# Flujo de UI — Proyecto, apartados y contratos

Documento de producto acordado (15 septiembre 2026). Describe cómo se usa la aplicación en el día a día. Complementa `contexto_proyecto_obra.md` y la sección 1.3 de `readme.md`.

---

## Idea en una frase

Los **presupuestos Excel** de Expertis crean el **proyecto** y su desglose (material y montaje). El **PDF firmado con el cliente** se sube después y solo contrasta importes por apartado: no trae el montaje. Dentro del proyecto se suben los **contratos** de subcontrata y el sistema **sugiere** qué contrato va con cada apartado; la cifra de comparación es la suma de las líneas de montaje.

---

## Flujo paso a paso

### 1. Subir los presupuestos Excel

1. El jefe de obra da nombre a la obra y sube uno o varios Excel `.xlsx` / `.xlsm` de plantilla Expertis. Cada fichero es un apartado. El título del apartado es el nombre del archivo, sin la extensión.
2. La lectura de la rejilla es determinista, sin OCR. Solo entra como partida la fila cuya `Cant.` es mayor que 0. El precio no decide si la línea entra. En pantalla `Ud` muestra esa `Cant.` y `Descuento` muestra `Dto. %`. Una subsección es la fila en negrita y sin precio (por ejemplo `08` / `ALIMENTACION`). Dentro, una fila en cursiva y sin precio abre otro bloque (por ejemplo el título en cursiva bajo ese código). Una fila con precio no abre bloque, aunque no traiga `Cant.`. No se guarda si no agrupa ninguna partida y no sale como línea. De cada partida se guardan `cantidad`, `precio_unitario`, `descuento_pct` y las referencias. `es_montaje = true` si la descripción empieza por `MONTAJE` o por `COLOCACIÓN`. Si la línea ya está dentro de su subapartado, el bloque se llama «Montaje» más ese nombre (por ejemplo «Montaje Cikkis»). Después de leer el árbol se busca si ese subapartado tiene montaje en otra parte del Excel y se le asocia cuando su nombre aparece en la línea o en el bloque de origen. Lo que no casa por nombre y sigue en GENERAL lo propone el LLM: al modelo solo se le mandan los nombres, sin importes. Lo que no es de un solo subapartado queda en «Montaje general». Sigue pendiente de revisión. Una línea `ELEMENTOS DE MONTAJE` se queda en el bloque en cursiva donde aparece y no entra en esa partida. En alimentación ese bloque es el último, Exafeed.
3. Eso **crea el proyecto**, con una sola nave. [VERIFICAR] si un Excel llega a partir varias naves; los ejemplos no lo hacen en columnas.
4. El documento queda en `pendiente_revision`. Si un `total` del Excel no cuadra con la suma de sus líneas, la revisión queda forzada y se muestra el aviso.
5. El Excel se guarda en disco (`uploads/{proyecto}/presupuesto/...`) y en la base queda `ruta_almacen`. Se puede descargar desde la obra. Si se borra la obra, se borra también su carpeta en `uploads/`.
6. Se puede añadir otro Excel a la misma obra más tarde. Si el fichero es el mismo que ya está guardado, no se vuelve a subir, aunque cambie el nombre.

### 2. Contrastar el contrato con el cliente

1. Se sube el PDF (o imagen) firmado con el cliente. No crea partidas ni otro proyecto. El fichero se guarda igual que el Excel. Si es el mismo que ya está guardado, no se vuelve a leer.
2. El modelo propone un primer cruce y marca los bloques. No escribe el importe: una persona confirma o cambia la marca. El montaje de un subapartado no se marca aparte: su importe va sumado en ese subapartado. Las dietas y desplazamientos que no están dentro de un subapartado se reparten entre ellos según su importe y entran en su montaje. «Montaje general» queda solo para lo que no es de uno ni son dietas. La diferencia de cada línea es el Excel menos el PDF. Si el Excel es mayor, sale en positivo y en rojo; si el PDF es mayor, en negativo y en verde. Debajo de los descuentos del cierre hay un resumen por apartado del PDF: el Excel es la suma de los bloques marcados en esa línea (la misma cifra del pie) y la diferencia es ese Excel menos el PDF. Un bloque de Excel que ninguna línea tiene marcado sale en su fila, sin PDF. Lo que aún no tiene bloque sale aparte y entra en el total del PDF, salvo que se desmarque esa fila. Ese total resta los descuentos del cierre.
3. Una persona confirma y se guarda `importe_contrato_cliente` en el apartado. Las líneas del PDF quedan guardadas: al volver a abrir la obra no hay que subir el fichero otra vez.
4. Si la lectura no ha sacado un importe, en la cabecera de «Importes del PDF» se añade a mano con código, descripción e importe. Esa línea se contrasta igual que las leídas. Solo ella se puede editar o borrar. Al cambiar el PDF, las líneas leídas se sustituyen y las añadidas a mano se conservan al final.
5. Si una línea de importe es trabajo que Exafan gestiona y no suministra, se marca «Solo gestión». Eso crea un apartado (`solo_gestion`) con el importe de la línea, sin Excel y sin montaje. La línea deja de contar como PDF sin bloque y no se contrasta con un bloque de Excel. Si el importe es manuscrito, el apartado queda pendiente y no admite contrato hasta confirmarlo. Luego los contratos se enlazan a ese apartado; si hay varios, se suman contra el importe de la línea. `POST .../contratos/{id}/desenlazar-apartado` quita el enlace. `DELETE .../contratos/{id}` quita el contrato: las facturas se quedan sin él, y se borran su fichero, sus enlaces y las partidas que nacieron solo de ese contrato. Con un contrato enlazado no se puede desmarcar.

### 3. Pantalla del proyecto = lista de apartados

Tras la creación (y tras confirmar la revisión del presupuesto), la vista principal del proyecto muestra:

- Cabecera: nombre, estado, naves.
- **Lista de apartados** del presupuesto: código, descripción, importe presupuestado, estado de revisión, y si ya hay un contrato enlazado.
- Acciones: subir contrato, ir a revisión, control económico.

Los apartados son filas `TAREA` con `nivel = "apartado"` y `presupuesto_id` relleno. La jerarquía más fina (subapartado / partida) cuelga con `tarea_padre_id` cuando un contrato o el propio presupuesto la aportan.

### 4. Subir contratos dentro del proyecto

1. Desde la pantalla del proyecto se sube el contrato firmado con un subcontratista. El PDF (o imagen) se guarda en `uploads/{proyecto}/contrato/...`.
2. El sistema extrae contratista, precio total, plazo y, si existe, el desglose fino (p. ej. por salas).
3. Ese desglose se guarda como árbol propio de `TAREA` con `contrato_id` (no mezcla ni sustituye los apartados del presupuesto).
4. El contrato también queda pendiente de revisión humana hasta confirmar.

### 5. Sugerencia automática contrato ↔ apartado

Tras importar un contrato (o al abrir el proyecto):

1. El sistema propone qué **apartado de presupuesto** encaja con ese contrato (texto del objeto/descripciones del contrato vs. código y descripción del apartado; en MVP reglas + similitud de texto; `pg_trgm` / embeddings cuando haga falta).
2. La propuesta es una **sugerencia**: no se enlaza sola.
3. La persona confirma uno o varios apartados: un contrato puede cubrir varios.
4. Al confirmar se guarda el conjunto en `contrato_apartado` (y `CONTRATO.tarea_apartado_id` queda con el primero del Excel, si hay alguno). La cifra con la que se compara el contrato es la suma de las partidas `es_montaje` de esos apartados, no el total de cada apartado (ese total incluye material). [VERIFICAR] el reparto del precio entre apartados: se prorratea por esa base. [VERIFICAR] si un contrato puede cubrir solo una parte de las líneas de un apartado; de momento cada apartado entra entero.
5. Si el PDF del cliente tiene un apartado que no sale en el Excel, el contrato del proveedor se relaciona con esa línea: se anotan a mano un nombre, un importe y una explicación. Ese importe entra en la base del contrato y esa parte del precio no se carga como descuadre del apartado de Excel.

Reglas:

- Un contrato sin confirmar no cuenta como enlace medido en control económico por apartado.
- Un mismo contrato puede enlazar varios apartados. En el control, su precio se reparte entre ellos según la base de cada uno (montaje, o el importe del PDF si es solo gestión). [VERIFICAR]
- Varios contratos pueden apuntar a apartados distintos. En un apartado de solo gestión pueden colgar varios a la vez: lo contratado es la suma de sus precios y se compara con el importe de la línea del PDF. En un apartado del Excel la comparación sigue siendo la suma de montaje.
- El desglose del contrato (hijas con precio unitario) no se asume igual al del presupuesto: se muestra aparte hasta confirmar el enlace al apartado padre.

### 6. Facturas y seguimiento

1. Administración sube una factura desde la pantalla de facturas del proyecto. El fichero se guarda en `uploads/{proyecto}/factura/...` y se puede descargar.
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
| Subir presupuestos Excel | Arranca el flujo; crea la obra y el desglose, montaje incluido |
| Contrato cliente | Contrasta importes del PDF firmado; no crea partidas |
| Revisión humana | Confirma presupuesto/contrato antes de darlos por válidos |
| **Proyecto** (lista de apartados) | Vista central: apartados + subir/enlazar contratos |
| Subir contrato | También accesible desde el proyecto (atajo legacy) |
| Facturas | Carga, revisión humana y confirmación del contrato asociado |
| Control económico | Desvíos cuando ya hay enlaces y facturas |

---

## API asociada (resumen)

- `POST /proyectos/importar-presupuestos-excel` → crea la obra desde uno o varios Excel (pendiente revisión).
- `POST /proyectos/{id}/presupuestos-excel` → añade otro Excel a la obra.
- `POST /proyectos/{id}/contrastar-presupuesto-cliente` → sugiere el contraste de importes del PDF y guarda las líneas. No crea partidas.
- `GET /proyectos/{id}/contraste-cliente` → devuelve esas líneas. Si el PDF ya estaba guardado y aún no había líneas, las lee del fichero. Si aún no hay relación, el modelo marca una propuesta; no queda confirmada.
- `POST /proyectos/{id}/lineas-pdf` → añade un importe que la lectura no trajo. `PATCH` y `DELETE` en `/proyectos/{id}/lineas-pdf/{linea_id}` editan o borran solo esa línea manual.
- `POST /proyectos/{id}/apartados/{tarea_id}/importe-cliente` → confirma el importe del cliente en el apartado. Un importe puede repartirse entre varios subapartados, pero no entre un bloque y lo que cuelga de él: el importe del bloque ya los incluye.
- `POST /proyectos/{id}/lineas-pdf/{linea_id}/solo-gestion` → crea el apartado de solo gestión. `DELETE` en la misma ruta lo desmarca si no hay contrato enlazado.
- `POST /proyectos/{id}/apartados/{tarea_id}/confirmar-gestion` → confirma el importe manuscrito de ese apartado.
- `POST /proyectos/{id}/contratos/{contrato_id}/desenlazar-apartado` → quita todos los apartados del contrato.
- `DELETE /proyectos/{id}/contratos/{contrato_id}` → quita el contrato. Las facturas se quedan y dejan de apuntar a él.
- `POST /proyectos/importar-presupuesto` → sigue creando una obra desde PDF (obras ya existentes y pruebas). La UI de alta ya no lo usa.
- `GET /proyectos/{id}` → detalle con naves, **apartados** y **contratos** (con sugerencia si aún no hay enlace).
- `POST /proyectos/{id}/importar-contrato` → crea contrato + árbol propio; responde con sugerencias de apartado.
- `POST /proyectos/{id}/contratos/{contrato_id}/enlazar-apartado` → confirma (o corrige) uno o varios apartados; valida en backend con Pydantic. El body lleva `tarea_apartado_ids` (o `tarea_apartado_id` si es uno solo).
- `POST /facturas` → extrae una factura y la deja pendiente de revisión.
- `GET /facturas?proyecto_id={id}` y `GET /facturas/{id}` → listado y revisión.
- `POST /facturas/{id}/confirmar` → valida y confirma los datos y el contrato.
- `GET /proyectos/{id}/presupuestos/{presupuesto_id}/fichero` (y análogos de contrato y factura) → descarga el documento guardado.

---

## Qué no hace este flujo

- No inventa partidas con precio unitario si el documento solo cierra por apartado. El Excel sí guarda precio unitario cuando la rejilla lo trae.
- El PDF firmado con el cliente no crea partidas ni sustituye el árbol del Excel.
- No mezcla el árbol del contrato bajo el apartado del presupuesto al importar: el enlace es a nivel contrato ↔ apartado, no un `tarea_padre_id` cruzado.
- No da por guardado un documento OCR/LLM sin revisión humana.
- No incluye facturas pendientes en los importes facturados.
