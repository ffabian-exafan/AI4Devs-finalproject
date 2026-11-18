# Inversión del sujeto pasivo en la obra

Fecha: 18 de noviembre de 2026.

Una persona adjunta la carta del promotor y marca la obra. A partir de ahí, el contrato con el cliente y el precio de cada subcontrata se leen como base, sin sumar el 21 %. Toda factura de esa obra tiene que confirmarse con IVA a cero. Si el IVA no es cero, sigue pendiente.

La carta no se lee con OCR ni con el modelo. No se copian al repositorio su texto, nombres, NIF ni importes.

## Decisiones cerradas

- La marca vive en el proyecto. No se copia a cada contrato y no hay excepciones por tipo de factura.
- La activa una persona, subiendo un PDF. La extracción del contrato no la infiere.
- `importe_contrato_cliente` y `precio_total` no cambian de cifra. La pantalla añade «sin IVA».
- El control económico sigue comparando el precio del contrato con `factura.total`. No se recalcula ni se suma el IVA autorrepercutido.
- IRPF y retención no cambian.
- No se emiten facturas al promotor. La ficha solo deja constancia de que la facturación al promotor es sin IVA.
- Al borrar la obra se borra la carpeta de uploads, carta incluida.

## Datos

Migración Alembic `0016_inversion_sujeto_pasivo`, revisa `0015_registro_accion`.

En `proyecto`:

- `inversion_sujeto_pasivo`: booleano, no nulo, por defecto `false`.
- `ruta_carta_isp`: texto, nulo. Ruta relativa bajo uploads.
- `fichero_carta_isp`: texto, nulo. Nombre original del PDF.

Las obras ya creadas quedan en false y sin carta.

El almacén acepta el tipo `carta_isp`. El fichero queda en `{proyecto_id}/carta_isp/{proyecto_id}_{nombre}`.

El registro de acciones suma `marcar_isp` («Marcó la inversión del sujeto pasivo») y `quitar_isp` («Quitó la inversión del sujeto pasivo»). Hay que ampliar el check `registro_accion_codigo`, el catálogo `ACCIONES`, las etiquetas del servicio y la lista de `registro.js`. Las dos acciones usan `tipo_documento = "proyecto"`, `documento_id` el id de la obra y `etiqueta` el nombre del proyecto.

## API

Hace falta sesión, igual que el resto de cambios de la obra.

`POST /proyectos/{proyecto_id}/inversion-sujeto-pasivo`

Cuerpo `multipart` con el campo `fichero`. Solo PDF: el nombre acaba en `.pdf` y el contenido empieza por `%PDF`. El fichero vacío no vale.

Guarda el PDF, pone `inversion_sujeto_pasivo` en true y, si ya había carta, sustituye el fichero. Las facturas de esa obra con `estado_revision = "confirmada"` e `iva` distinto de cero pasan a `pendiente`. El resto de campos de la factura no se toca. Las que ya estaban pendientes siguen pendientes. Las de IVA cero siguen confirmadas.

Respuesta 200 con `ProyectoDetalleOut`.

`DELETE /proyectos/{proyecto_id}/inversion-sujeto-pasivo`

Pone la marca en false, borra el fichero y limpia ruta y nombre. No cambia el estado de las facturas y no reconfirma ninguna.

Respuesta 204. Si la obra existe y no estaba marcada, también 204.

`GET /proyectos/{proyecto_id}/carta-isp`

Devuelve el PDF. Sin carta, 404.

`ProyectoDetalleOut` añade:

- `inversion_sujeto_pasivo`: bool
- `tiene_carta_isp`: bool
- `fichero_carta_isp`: string o null

La ruta interna no sale en el JSON.

`FacturaResumenOut` y, por herencia, `FacturaRevisionOut` añaden `aviso_isp`. Es null, o el texto «La obra está en inversión del sujeto pasivo. El IVA tiene que ser 0.» cuando la obra está marcada y el IVA de esa factura no es cero. Se calcula al listar y al abrir; no se guarda en la factura.

`FacturaRevisionOut` añade también `inversion_sujeto_pasivo` de la obra, para que el formulario lo sepa aunque el IVA ya sea cero.

`ControlEconomicoOut` añade `inversion_sujeto_pasivo`. Las cifras de desvío no cambian.

## Confirmar una factura

`POST /facturas/{id}/confirmar` sigue validando el cuerpo con Pydantic. La regla de ISP depende de la obra, así que se aplica en el servicio, antes de escribir.

Si la obra está marcada y `iva` no es cero (tampoco si es negativo), no se guarda nada y la factura se queda como estaba. Respuesta 422 con el mismo texto que `aviso_isp`. Cero y `0.00` sí confirman.

Si la obra no está marcada, el IVA se guarda como hasta ahora.

## Errores

| Caso | Respuesta |
|---|---|
| Obra inexistente | 404 |
| Carta que no existe, al descargarla | 404 |
| Fichero vacío, que no es PDF, o sin fichero | 422 |
| Confirmar factura con IVA distinto de cero en obra marcada | 422, sin guardar |

## Pantalla

En la ficha de la obra (`index.html`, cabecera que pinta `obras.js`), con la obra abierta:

- Sin marca: botón «Marcar inversión del sujeto pasivo» y un selector de PDF.
- Con marca: el texto «Facturación al promotor: sin IVA», el enlace «Ver carta», «Sustituir carta» y «Quitar la marca». Quitar pide confirmación.

En el resumen de contraste, el título «Contrato cliente» lleva «sin IVA» si la obra está marcada. En la lista de contratos, el precio lleva el mismo texto. Los importes no se recalculan.

En la bandeja de facturas de la ficha, si `aviso_isp` viene informado, se muestra junto a la factura y no se ofrece la acción de confirmar. El IVA se corrige en `facturas.html`. Si la petición de confirmar llegara igual, el backend responde 422 y no guarda.

En `facturas.html`, con la obra marcada, el campo IVA muestra el aviso. Si el IVA escrito no es cero, el formulario no se envía. Si aun así llega, el backend responde 422.

En el control (`index.html` y `control.html`), con la marca activa, una línea dice «Importes sin IVA». Las tablas no cambian.

`proyecto.html` muestra la misma marca en el resumen y «sin IVA» junto al precio de cada contrato. No es la ficha principal, y no puede quedar desfasada.

## Fuera de alcance

- No se emite ni se registra la factura de Exafan al promotor.
- No se lee la carta para rellenar campos.
- No se altera el precio extraído del contrato ni del presupuesto.
- No se cambia la fórmula de contratado contra facturado.
- No se marca una obra sin PDF.
- La carta real no se usa como fixture.

## Documentación

Al implementarlo se actualizan el modelo de `PROYECTO` y la API en `docs/readme.md`: las dos columnas, los tres endpoints y la regla de que una factura con IVA no se confirma si la obra está marcada.

## Pruebas

Datos ficticios. El PDF de prueba es un fichero mínimo que empieza por `%PDF`. Sin nombres, NIF ni importes reales.

- Marcar una obra guarda la carta, deja `inversion_sujeto_pasivo` en true y escribe `marcar_isp`.
- Un fichero vacío o que no es PDF responde 422 y no activa la marca.
- Sustituir la carta mantiene la marca y deja un solo fichero.
- Una factura confirmada con IVA distinto de cero pasa a pendiente al marcar. Una con IVA cero sigue confirmada.
- Confirmar con IVA cero en obra marcada responde 200. Con IVA distinto de cero responde 422 y no cambia la factura.
- En una obra sin marca, confirmar con IVA distinto de cero sigue igual que ahora.
- Quitar la marca borra el fichero, deja el indicador en false, escribe `quitar_isp` y no toca las facturas.
- Descargar la carta sin fichero responde 404.
- El listado de facturas trae `aviso_isp` solo en las de IVA distinto de cero de una obra marcada.
- El control devuelve el indicador y las mismas cifras que antes.
