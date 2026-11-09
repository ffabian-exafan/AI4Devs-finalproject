# Apartado de solo gestión

Fecha: 9 de noviembre de 2026.

Una línea de precio del PDF firmado con el cliente puede ser trabajo que Exafan gestiona y no suministra. Al marcarla, nace un apartado de la obra, sin Excel y sin montaje. El contratista entra después, al enlazar su contrato. Si hay varios contratos sobre esa línea, se suman y la suma se compara con el importe de la línea.

## Decisiones cerradas

- Cada línea de importe del PDF es un apartado. No se agrupan líneas.
- Marcar no elige contratista. El contrato se sube y se enlaza como hasta ahora.
- Un contrato cuelga de un solo apartado. Varios contratos pueden colgar del mismo apartado de solo gestión.
- La cifra de comparación es el importe de esa línea. No hay montaje.
- La línea «Gestión EXAFAN» no se marca sola. Sigue siendo el recargo.
- Los apartados que vienen del Excel no cambian: su comparación sigue siendo la suma de montaje.

## Marca

En el contraste del contrato cliente, cada línea de tipo importe que no está confirmada contra un bloque de Excel muestra el botón «Solo gestión».

Al pulsarlo:

- Se crea una `TAREA` de nivel `apartado` en la nave de la obra. Si hay más de una nave, se usa la de menor id.
- `presupuesto_id` es el del PDF de esa línea.
- Código y descripción salen de la línea. Si el código está vacío o ya existe en la nave, el código es `pdf.{id de la línea}`.
- `importe_presupuestado` e `importe_contrato_cliente` son el importe de la línea, también si es cero.
- Sin padre, sin hijos, `es_montaje = false`, `estado = no_iniciada`, `avance_fisico_pct = 0`.
- `solo_gestion = true`.
- La línea guarda `apartado_gestion_id` hacia ese apartado.
- Se borran las sugerencias de bloque de Excel de esa línea (`es_sugerencia = true`).
- La línea deja de contar en «PDF sin bloque». En el contraste, `confirmada` sigue queriendo decir «bloque de Excel confirmado»: en una línea de solo gestión se queda en false. La pantalla mira `solo_gestion`.

Si la línea es manuscrita, el apartado nace con `tiene_anotacion_manual = true` y `estado_revision = pendiente`. El botón no da por bueno el número escrito a mano. Hasta que una persona lo confirme, el apartado se ve en la lista y en el contraste, con el aviso, y no entra en el desplegable de contratos, ni en las sugerencias, ni en el desvío.

Si la línea no es manuscrita, `estado_revision = confirmada`. Vale también cuando el PDF es un escaneo: la persona ha aceptado esa línea al marcarla. El presupuesto sigue con `es_escaneado` como hasta ahora.

Desmarcar suelta primero `apartado_gestion_id` y después borra el apartado. La línea vuelve a «PDF sin bloque». Si algún contrato apunta a ese apartado, no se puede desmarcar: antes hay que quitar el enlace.

Una línea confirmada contra Excel no se puede marcar. Una línea no puede estar a la vez contrastada con Excel y ser solo gestión.

## Datos

Migración Alembic:

- `tarea.solo_gestion`: booleano, no nulo, por defecto `false`.
- `linea_pdf_cliente.apartado_gestion_id`: entero nulo, clave ajena a `tarea.id`, único.

`ApartadoResumenOut` y `DesvioApartadoOut` incluyen `solo_gestion` (por defecto `false`). `SugerenciaContrasteOut` incluye `solo_gestion` y `apartado_gestion_id` (nulo si no está marcada).

## API

`POST /proyectos/{proyecto_id}/lineas-pdf/{linea_id}/solo-gestion`

Crea el apartado. Respuesta 201:

```json
{
  "tarea_id": 1,
  "linea_id": 2,
  "codigo": "5",
  "descripcion": "Obra civil",
  "importe": 1000.0,
  "estado_revision": "confirmada",
  "tiene_anotacion_manual": false,
  "solo_gestion": true
}
```

`POST /proyectos/{proyecto_id}/apartados/{tarea_id}/confirmar-gestion`

Sin cuerpo. Pasa a `confirmada` un apartado de solo gestión. Si ya estaba confirmado, responde 200 con el mismo estado. No cambia el importe.

`DELETE /proyectos/{proyecto_id}/lineas-pdf/{linea_id}/solo-gestion`

Borra el apartado y suelta la línea. Respuesta 204.

`POST /proyectos/{proyecto_id}/contratos/{contrato_id}/desenlazar-apartado`

Sin cuerpo. Pone `tarea_apartado_id` a nulo. Hace falta porque, una vez asociado, la pantalla no deja cambiar el apartado, y sin quitar el enlace no se puede desmarcar. Respuesta 200 con `contrato_id` y `tarea_apartado_id: null`.

El enlace que ya existe (`POST .../enlazar-apartado`) acepta un apartado de solo gestión confirmado. El desplegable y las sugerencias de contrato incluyen ese apartado confirmado, también si su descripción lleva la palabra «gestión». Uno pendiente no entra en ninguno de los dos. Las filas que no son solo gestión y cuya descripción lleva «gestión» siguen fuera de la lista que se manda al leer un contrato y fuera del desplegable: son el recargo, no un apartado de contratista. Un apartado de Excel pendiente se sigue pudiendo sugerir, como ahora.

Pydantic valida cada cuerpo. Confirmar gestión y desenlazar no llevan cuerpo.

## Errores

| Caso | Respuesta |
|---|---|
| Proyecto, línea, apartado o contrato que no es de esta obra | 404 |
| Línea de tipo descuento | 422 |
| Línea ya marcada | 422 |
| Línea con un bloque de Excel ya confirmado (`es_sugerencia = false`) | 422 |
| Desmarcar una línea que no está marcada | 422 |
| Desmarcar con un contrato enlazado | 422 |
| Enlazar un contrato a un apartado de solo gestión pendiente | 422 |
| Confirmar gestión de un apartado que no es solo gestión | 422 |
| Desenlazar un contrato que no tiene apartado | 200, sigue sin apartado |

## Pantalla

En el contraste, el botón «Solo gestión» está en el pie de la línea, junto a «Confirmar importe», y solo si la línea no está confirmada contra Excel.

Cuando la línea ya es solo gestión, no se muestran los bloques de Excel. Se ve el apartado, su importe y «Desmarcar». Si está pendiente por manuscrito, se ve el aviso y el botón «Confirmar importe», que llama a confirmar gestión.

En el resumen del contraste, cada línea marcada es una fila: Excel «—», PDF el importe, diferencia «—». No suma en «PDF sin bloque».

En la lista de apartados de la obra sale con la insignia «Solo gestión», no en la tarjeta del recargo «Gestión». En contratos, la base se etiqueta «Importe del PDF». En el control, lo contratado y lo facturado de esos contratos se suman y se comparan con el importe de la línea. Uno pendiente se ve en la lista y no se suma en el control.

## Control económico

`_por_apartado` incluye el apartado de solo gestión confirmado. `presupuestado` y `contrato_cliente` son el importe de la línea. `montaje` es 0. `contratado` es la suma de `precio_total` de los contratos enlazados. `facturado` sigue siendo la suma de facturas confirmadas de esos contratos. Un apartado pendiente no entra en `por_apartado` ni en la suma de la pantalla de control.

## Fuera de alcance

- No se elige el contratista al marcar.
- No se reparte el importe de la línea entre contratistas.
- No se juntan varias líneas en un apartado.
- No se marca sola la línea «Gestión EXAFAN».
- No cambia la comparación por montaje de los apartados del Excel.

## Documentación

Al implementarlo se actualizan el modelo y la API en `docs/readme.md` y el flujo en `docs/flujo_ui_proyecto.md`: la marca, `solo_gestion`, varios contratos sobre un apartado de solo gestión y `desenlazar-apartado`.

## Pruebas

- Marcar una línea de importe crea el apartado con ese importe, `solo_gestion`, el enlace a la línea, y la línea deja de contar como PDF sin bloque.
- Un código vacío o repetido en la nave se guarda como `pdf.{id de la línea}`.
- Un descuento, una línea ya confirmada contra Excel o una segunda marca fallan con 422.
- Desmarcar sin contrato borra el apartado. Con contrato enlazado, 422.
- Desenlazar deja `tarea_apartado_id` a nulo y después sí se puede desmarcar.
- Dos contratos sobre la misma línea: lo contratado es la suma y el montaje es 0.
- Una línea manuscrita queda pendiente, el enlace del contrato responde 422 y, tras confirmar gestión, el enlace ya vale.
- Confirmar gestión de un apartado que no es solo gestión responde 422.
- Un cuerpo mal formado lo rechaza Pydantic.
