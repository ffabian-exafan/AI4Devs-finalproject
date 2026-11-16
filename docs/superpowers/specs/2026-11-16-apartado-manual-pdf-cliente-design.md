# Apartado manual en los importes del PDF del cliente

Fecha: 16 de noviembre de 2026.

En Contrato cliente, la lectura del PDF a veces no saca un importe. Una persona puede añadir esa línea a mano (código, descripción e importe). Entra en la misma lista y se contrasta igual que las leídas. Solo las líneas añadidas a mano se editan o se borran.

## Decisiones cerradas

- La línea manual es una fila de `linea_pdf_cliente` con `tipo = "importe"` y `es_manual = true`. No es una `TAREA` ni un descuento.
- Código, descripción e importe son obligatorios. El importe puede ser cero. No puede ser negativo.
- `es_manuscrito` queda en false. Añadir, editar o borrar no deja el presupuesto pendiente de revisión: la cifra la ha escrito una persona.
- El contraste no cambia de reglas. La línea se asigna a bloques del Excel o se marca como solo gestión, y entra en el resumen y en el total del PDF.
- Las líneas leídas del PDF (`es_manual = false`) no se editan ni se borran por estos endpoints.
- Hace falta un PDF del cliente ya guardado. Sin él no se puede añadir la línea.
- Al subir otro PDF se crea un presupuesto nuevo. Las líneas manuales del PDF anterior se copian al final, con el contraste que ya tenían.

## Datos

Migración Alembic `0014_linea_pdf_manual`, revisa `0013_presupuesto_ver_pagina`.

- `linea_pdf_cliente.es_manual`: booleano, no nulo, por defecto `false`.

Las filas ya guardadas quedan en false.

`SugerenciaContrasteOut` incluye `es_manual` (por defecto `false`).

## API

Pydantic valida el cuerpo. Código de 1 a 128 caracteres, descripción de 2 a 512, importe `>= 0`. Se recortan los espacios de código y descripción.

`POST /proyectos/{proyecto_id}/lineas-pdf`

```json
{ "codigo": "12", "descripcion": "Fontanería", "importe": 1500.0 }
```

Crea la línea en el último presupuesto `pdf_cliente` de la obra. `orden` es el máximo más uno, así queda la última de los importes. `es_manual = true`, `es_manuscrito = false`, `relacion_intentada = false`. Después se pide la propuesta de bloques, igual que al abrir el contraste: si hay un bloque libre que encaja por nombre, queda como sugerencia y sin confirmar. Respuesta 201 con `ContrastarClienteOut`.

`PATCH /proyectos/{proyecto_id}/lineas-pdf/{linea_id}`

Mismo cuerpo que el alta. Solo si `es_manual` es true. Actualiza código, descripción e importe de la línea.

- Si está confirmada contra bloques de Excel, se reparte el importe nuevo con la misma regla que confirmar el contraste. No se sueltan los bloques.
- Si es solo gestión, el apartado actualiza descripción, `importe_presupuestado` e `importe_contrato_cliente`. El código del apartado no cambia: puede ser `pdf.{id}` y lo usan los contratos.

Respuesta 200 con `ContrastarClienteOut`.

`DELETE /proyectos/{proyecto_id}/lineas-pdf/{linea_id}`

Solo si `es_manual` es true.

- Si está confirmada contra Excel, se borran los enlaces de esa línea y `importe_contrato_cliente` de esos bloques pasa a nulo. Un bloque solo puede estar confirmado en una línea, así que no se pisa el importe de otra.
- Si es solo gestión y algún contrato la enlaza, no se borra.
- Si es solo gestión y no hay contrato, se desmarca (se borra el apartado) y después se borra la línea.
- Si solo tenía una sugerencia, se borra la sugerencia y la línea.

Respuesta 204.

## Cambio de PDF

`POST .../contrastar-presupuesto-cliente` sigue creando un presupuesto nuevo y guardando ahí las líneas leídas. Después copia las líneas `es_manual` del PDF de cliente anterior:

- Código, descripción, importe y `es_manual = true`. `es_manuscrito` sigue en false.
- Si la línea vieja estaba confirmada contra Excel, la copia recrea esos enlaces con `es_sugerencia = false`. No vuelve a escribir `importe_contrato_cliente`: ya está en los bloques.
- Si era solo gestión, `apartado_gestion_id` pasa a la línea nueva y se quita de la vieja. El apartado no se duplica.
- Si no estaba contrastada, la copia nace sin enlaces y puede recibir propuesta.
- El orden de las copias es el que tenían, detrás de las líneas leídas del fichero nuevo.

Volver a leer un presupuesto que ya tiene líneas de importe no las regenera. Una línea manual cuenta como línea de importe, así que no dispara esa relectura.

## Errores

| Caso | Respuesta |
|---|---|
| Obra inexistente o sin PDF del cliente | 404 |
| Línea inexistente o de otra obra | 404 |
| Cuerpo mal formado, código vacío, descripción de menos de 2 caracteres o importe negativo | 422 |
| Editar o borrar una línea que no es manual, o una línea de descuento | 422 |
| Borrar una línea de solo gestión con contrato enlazado | 422 |

## Pantalla

En Contrato cliente, el botón «Añadir apartado» está en la cabecera de «Importes del PDF». También se ve cuando el PDF no ha traído importes.

El formulario pide código, descripción e importe. Al guardar, la fila entra en la lista con el texto «Añadido a mano».

En esa fila, y solo si `es_manual` es true, hay «Editar» y «Borrar». Editar reabre el mismo formulario con los tres campos. Borrar pide confirmación. Las filas leídas del PDF no muestran esas acciones.

El resto del contraste no cambia: bloques del Excel, «Solo gestión», descuentos y resumen.

## Fuera de alcance

- No se editan ni se borran las líneas leídas del PDF ni los descuentos.
- No se añade una línea si la obra aún no tiene PDF del cliente.
- No se crea un apartado de Excel ni una partida.
- No se marca la línea como anotación manuscrita.

## Documentación

Al implementarlo se actualizan la API en `docs/readme.md` y el paso «Contrastar el contrato con el cliente» en `docs/flujo_ui_proyecto.md`: alta, edición y borrado de la línea manual, y que al cambiar el PDF esas líneas se conservan.

## Pruebas

- Alta con código, descripción e importe crea una línea `es_manual` al final de los importes y la devuelve en el contraste.
- Un importe cero se guarda. Un importe negativo, un código vacío o una descripción de un carácter responden 422.
- Sin PDF del cliente, el alta responde 404.
- Editar una línea manual confirmada contra dos bloques reparte el importe nuevo y mantiene los enlaces.
- Editar una línea de solo gestión actualiza descripción e importes del apartado y no cambia su código.
- Editar o borrar una línea leída del PDF responde 422.
- Borrar una línea manual confirmada contra Excel deja los enlaces vacíos y `importe_contrato_cliente` a nulo en esos bloques.
- Borrar una línea de solo gestión sin contrato borra el apartado y la línea. Con contrato enlazado, 422.
- Al contrastar un PDF nuevo, las líneas leídas son las del fichero y las manuales del PDF anterior siguen al final, con su contraste.
