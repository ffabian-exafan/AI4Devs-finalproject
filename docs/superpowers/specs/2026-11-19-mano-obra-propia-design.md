# Mano de obra propia

Fecha: 19 de noviembre de 2026.

En Contratos hay trabajo que ejecuta la propia empresa. Ese trabajo no tiene contrato de proveedor ni factura. Una persona añade a mano una línea con nombre y sube partes de trabajo (PDF o imagen). El sistema lee las horas. El parte queda pendiente hasta que alguien confirma. Al confirmar se copia el precio por hora de la obra y el importe es horas × ese precio. El acumulado de la línea es la suma de los partes confirmados. No se compara con presupuesto, contrato ni montaje.

## Decisiones cerradas

- La línea no es una `TAREA`. `TAREA` exige nave e importe presupuestado, y el control económico suma esas filas.
- No se crea `CONTRATO` ni `FACTURA`.
- El precio por hora vive en la obra. Cada obra tiene el suyo.
- Al confirmar un parte se copian en él el precio y el importe. Un cambio posterior del precio de la obra no los toca.
- Un parte pendiente no entra en el acumulado.
- El acumulado no entra en presupuestado, contratado ni facturado, ni en el control de desviaciones.
- La fecha del parte se guarda si el documento la trae. No hace falta para confirmar.
- El nombre de la línea no tiene que ser único.
- Hace falta sesión, la misma que para cambiar la obra.

## Datos

Migración Alembic `0020_mano_obra_propia`, revisa `0019_bandeja_factura`.

En `proyecto`:

- `precio_hora`: `Numeric(14, 4)`, nulo. Euros por hora. Las obras ya creadas quedan en nulo.

Tabla `linea_mano_obra`:

- `id`
- `proyecto_id`, FK a `proyecto`, índice, al borrar la obra se borra la línea
- `nombre`, texto, no nulo, hasta 255
- `created_at`, con zona horaria, no nulo

Tabla `parte_trabajo`:

- `id`
- `linea_mano_obra_id`, FK a `linea_mano_obra`, índice, `ON DELETE RESTRICT`
- `fichero_origen`, texto, no nulo
- `ruta_almacen`, texto, no nulo. Ruta relativa bajo uploads
- `es_escaneado`, booleano, no nulo
- `horas`, `Numeric(10, 2)`, nulo hasta que haya una cifra
- `fecha`, fecha, nulo
- `tiene_anotacion_manual`, booleano, no nulo, por defecto false
- `aviso`, texto, nulo
- `estado_revision`, `pendiente` o `confirmada`
- `precio_hora_aplicado`, `Numeric(14, 4)`, nulo hasta confirmar
- `importe`, `Numeric(14, 2)`, nulo hasta confirmar
- `confirmada_por`, texto, nulo
- `confirmada_en`, con zona horaria, nulo

Si `estado_revision` es `confirmada`, `horas`, `precio_hora_aplicado`, `importe` y `confirmada_en` no son nulos. El check se llama `parte_trabajo_confirmado`.

El almacén acepta el tipo `parte`. El fichero queda en `{proyecto_id}/parte/{parte_id}_{nombre}`.

Al borrar la obra, el servicio borra primero los partes y sus ficheros, y después la obra. La línea cae en cascada con la obra. La FK del parte no hace cascada, así que el orden es ese. La carpeta de uploads de la obra se borra con ella, partes incluidos.

El registro suma cuatro acciones. Hay que ampliar el check `registro_accion_codigo`, el catálogo `ACCIONES`, las etiquetas del servicio y la lista de `registro.js`, igual que en `0016_inversion_sujeto_pasivo`.

| Acción | Etiqueta | Documento | `etiqueta` de la fila |
|---|---|---|---|
| `guardar_precio_hora` | Guardó el precio por hora | `proyecto` | nombre de la obra |
| `borrar_linea_mano_obra` | Borró la línea de mano de obra | `linea_mano_obra` | nombre de la línea |
| `confirmar_parte` | Confirmó el parte | `parte_trabajo` | nombre del fichero |
| `borrar_parte` | Borró el parte | `parte_trabajo` | nombre del fichero |

El registro no guarda horas ni importes. Si la fila no se puede escribir, el gesto tampoco se guarda. Confirmar un parte que ya está confirmado no escribe otra fila.

## Cifras

- `precio_hora` es mayor que cero y tiene como mucho cuatro decimales.
- `horas` es mayor que cero y tiene como mucho dos decimales.
- `importe` = `horas × precio_hora_aplicado`, redondeo half-up a dos decimales. Se calcula una vez, al confirmar, y se guarda.
- El acumulado en euros de una línea es la suma de `importe` de sus partes confirmados. No es «horas totales × precio de hoy», porque cada parte puede llevar un precio distinto.
- El acumulado en horas es la suma de `horas` de esos mismos partes.
- El acumulado de la obra es la suma de sus líneas.
- Un parte pendiente, o con horas vacías, suma cero.

## Lectura del parte

Se lee como una factura: texto del PDF, u OCR si es imagen o PDF sin texto. La extracción solo devuelve `horas`, `fecha` y `tiene_anotacion_manual`. No crea contrato, partida ni proveedor.

- PDF o imagen vacíos se rechazan y no se crea el parte.
- Extensiones admitidas: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`. Un PDF tiene que empezar por `%PDF`.
- Imagen, o PDF sin texto, dejan `es_escaneado = true`.
- Si la extracción no devuelve horas, o falla, `horas` queda nulo y `aviso` es «No se han leído las horas. Escríbelas.» El parte se guarda pendiente.
- Anotación manuscrita: `tiene_anotacion_manual = true` y el parte sigue pendiente. Confirmar es la revisión humana.
- El mismo contenido ya guardado como parte de esa obra se rechaza con `exigir_distinto`.
- Las pruebas no llaman al modelo. Sustituyen la extracción.

## API

Todas las rutas exigen `usuario_actual`. Un id que no es de esa obra responde 404 con «No está en esta obra». El cuerpo se valida con Pydantic. Un 422 no escribe nada.

`PATCH /proyectos/{proyecto_id}/precio-hora`

Cuerpo: `{ "precio_hora": "18.50" }`. Sustituye el precio. No se puede dejar vacío ni en cero. No modifica partes ya confirmados. Registra `guardar_precio_hora`. Respuesta 200, `ManoObraOut`.

`POST /proyectos/{proyecto_id}/lineas-mano-obra`

Cuerpo: `{ "nombre": "Montaje de comederos" }`. El nombre se recorta. Vacío, 422. Respuesta 201, `ManoObraOut`.

`PATCH /proyectos/{proyecto_id}/lineas-mano-obra/{linea_id}`

Cuerpo: `{ "nombre": "..." }`. Misma regla de nombre. No se registra. Respuesta 200, `ManoObraOut`.

`DELETE /proyectos/{proyecto_id}/lineas-mano-obra/{linea_id}`

Si queda algún parte confirmado, 409 con «Quita antes los partes confirmados.» y no se borra nada. Si solo hay pendientes, se borran sus ficheros y sus filas, luego la línea. Se registra una sola fila, `borrar_linea_mano_obra`. No se registra `borrar_parte` por cada pendiente. Respuesta 204.

`POST /proyectos/{proyecto_id}/lineas-mano-obra/{linea_id}/partes`

`multipart`, campo `fichero`. Crea el parte en `pendiente`. No confirma y no suma. Respuesta 201, `ManoObraOut`.

`GET /proyectos/{proyecto_id}/partes/{parte_id}/fichero`

Devuelve el fichero. Sin fichero, 404.

`PATCH /proyectos/{proyecto_id}/partes/{parte_id}`

Cuerpo: `horas` y `fecha`, los dos opcionales. Solo en `pendiente`. Si está confirmado, 409 con «El parte ya está confirmado.» `horas` nulo vuelve a dejarlas vacías. Respuesta 200, `ManoObraOut`.

`POST /proyectos/{proyecto_id}/partes/{parte_id}/confirmar`

Si ya está confirmado, 200 con los mismos datos y sin otro registro. Si la obra no tiene `precio_hora`, 422 con «Falta el precio por hora de la obra.» Si `horas` es nulo o no es mayor que cero, 422 con «Las horas tienen que ser mayores que cero.» Si pasa, copia `precio_hora` de la obra a `precio_hora_aplicado`, calcula `importe`, pasa a `confirmada`, rellena `confirmada_por` y `confirmada_en`, y registra `confirmar_parte`. Respuesta 200, `ManoObraOut`.

`DELETE /proyectos/{proyecto_id}/partes/{parte_id}`

Borra la fila y el fichero. Si estaba confirmado, deja de contar en el acumulado. El resto de partes conserva su precio. Registra `borrar_parte`. Respuesta 204.

`ManoObraOut`:

- `precio_hora`: string o null. Cuatro decimales si hay cifra.
- `acumulado_horas`: string, dos decimales
- `acumulado`: string en euros, el mismo formato que el resto de la vista
- `lineas`: `id`, `nombre`, `horas`, `acumulado`, `partes`
- Cada parte: `id`, `archivo`, `tiene_fichero`, `url_fichero`, `horas` (string o null), `fecha` (ISO o null), `estado_revision`, `es_escaneado`, `tiene_anotacion_manual`, `aviso`, `precio_hora_aplicado` (string o null), `importe` (string en euros o null). `url_fichero` es la ruta GET del fichero. La ruta de disco no sale en el JSON.

`VistaObraOut` añade `mano_obra: ManoObraOut`. Las líneas van por `created_at` e `id`. Los partes de cada línea van por `fecha` (los nulos al final) e `id`.

## Pantalla

En Contratos, debajo del bloque de los gremios, un bloque «Mano de obra propia». Subir un contrato no cambia.

- Arriba del bloque se ven el acumulado de la obra y el campo de precio por hora, con un botón para guardarlo. Si el precio está vacío, se puede subir un parte y el botón de confirmar se ve deshabilitado, con el texto «Falta el precio por hora de la obra.»
- «Añadir línea» pide el nombre.
- Cada línea muestra el nombre editable, las horas confirmadas y el acumulado en euros.
- En la línea se arrastra el parte. Mientras se lee, el mismo estado de espera que un contrato.
- El parte pendiente enseña el fichero (ver si es PDF, descargar), las horas editables y la fecha si existe. Escaneo y anotación manuscrita se marcan y siguen pendientes.
- Confirmar deja las horas y la fecha quietas y muestra el precio copiado y el importe.
- Quitar un parte, pendiente o confirmado, lo borra. Al recargar la vista el acumulado ya no lo incluye.
- Borrar la línea solo se ofrece si no tiene partes confirmados.

Tras cada gesto con éxito la pantalla vuelve a cargar la vista de la obra. Un 422 o un 409 se enseña junto al bloque, sin dar el parte por confirmado.

## Qué no entra

- Importe previsto, nave o enlace a un apartado del Excel.
- Varios precios por categoría.
- Editar horas o precio de un parte confirmado.
- Meter el acumulado en los KPI o en las filas del control de desviaciones.
- Sello ALC, código de contrato o NIF.

## Documentación

Al implementarlo se actualizan el modelo y la API en `docs/readme.md` y el flujo en `docs/flujo_ui_proyecto.md`: la línea añadida a mano, el parte pendiente hasta confirmar, el precio copiado y el acumulado fuera del desvío.

## Pruebas

Horas y precios ficticios. Sin NIF, nombres reales ni importes de obra.

- Nombre vacío, 422. Nombre con espacios se guarda recortado.
- Subir un parte lo deja `pendiente`. El acumulado de la línea sigue en cero.
- Sin `precio_hora`, confirmar responde 422 y el parte sigue pendiente.
- Horas nulas o cero, confirmar responde 422.
- Al confirmar se copian el precio y el importe half-up, y el acumulado suma solo ese parte.
- Cambiar el precio de la obra no modifica `precio_hora_aplicado` ni `importe` del parte confirmado. Un parte todavía pendiente, al confirmarse después, usa el precio nuevo.
- Confirmar dos veces no cambia cifras ni escribe otra fila de registro.
- Quitar un parte confirmado lo saca del acumulado. Otro parte confirmado de la misma línea conserva su precio.
- Borrar una línea con un parte confirmado responde 409 y no borra nada.
- Borrar una línea que solo tiene pendientes borra ficheros y filas.
- El control de desviaciones de esa obra devuelve las mismas cifras con y sin la línea y sus partes.
- PDF que no empieza por `%PDF`, extensión no admitida y fichero vacío responden error y no crean parte.
- Extracción sin horas: parte pendiente, `aviso` con el texto fijo, acumulado en cero.
- `tiene_anotacion_manual` deja el parte pendiente hasta el `POST` de confirmar.
- Parte de otra obra: 404 en confirmar, editar, descargar y borrar.
