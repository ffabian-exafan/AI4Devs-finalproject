# Registro inmutable de acciones

* **Author:** ffabian-exafan
* **Date:** 2026-11-17

## Overview

Dirección y un superadministrador nuevo tienen que poder ver, meses después, quién confirmó un cambio de datos de obra y quién entró bien en la aplicación. Cada hecho queda en una fila que nadie puede modificar desde la aplicación. La fila copia el nombre de la persona tal como era ese día, la acción y una etiqueta del documento. No guarda el importe anterior ni el nuevo. Sigue existiendo aunque luego se borre la factura o el proyecto.

Los siete revisores terminaron. El catalizador inventivo no encontró un compromiso falso. Los otros seis señalaron tres roturas. El autor aceptó el cierre de abajo el 2026-11-17. Esa aceptación no ha vuelto a pasar por los revisores.

## Analysis

La fila no apunta con clave ajena a la factura, el proyecto, el contrato, la tarea ni el usuario. Esos borrados ya existen: una clave que se lleva la fila borra el registro, y una clave que impide el borrado rompe borrados que la aplicación ya hace. La fila guarda el nombre de ese día, el id de usuario como número suelto, el tipo de documento, su id y una etiqueta legible. El día y la hora son un solo instante; el día visible se calcula en la zona de la obra. La aplicación entra en PostgreSQL como superusuario del contenedor, así que quitar permisos no basta: un disparador rechaza `UPDATE` y `DELETE`. Quien tenga acceso de dueño a la base sigue pudiendo tocar la tabla. Dentro de la aplicación, nadie puede.

La fila nace en la misma transacción que el cambio. Si no se inserta, el cambio no se guarda. La escriben el inicio de sesión correcto y los gestos que ya existen: confirmar revisión, confirmar factura, confirmar importe de cliente, confirmar solo gestión, y borrar proyecto, contrato, factura o línea. Esas rutas exigen el usuario de la sesión. Un gancho sobre cada escritura metería la ingesta, la extracción y el prorrateo, y eso queda fuera. Hay una fila por gesto, no por cada tarea hija. Sin importes, la fila no explica un descuadre: dice quién hizo el gesto y sobre qué documento.

El rol `superadministrador` entra en la lista de roles. La única comprobación nueva es la consulta, paginada, en el servidor, solo para dirección y ese rol. Las rutas que hoy usa cualquier sesión no se estrechan. Mientras no exista una matriz de permisos, el rol no concede poderes nuevos: ve el registro y usa las pantallas que ya existen. Quién puede asignarlo no está en los documentos; de momento lo asigna quien ya puede editar usuarios. [VERIFICAR] El estado de obra y el avance físico quedan en el catálogo y no se escriben hasta que exista la pantalla que los cambia. Esa pantalla no se construye aquí. Las filas se conservan sin plazo y sin purga. Un plazo posterior sería otra decisión, porque obligaría a borrar. Este trabajo no llama al modelo de lenguaje.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Una fila inmutable por gesto ya existente: confirmar revisión, confirmar factura, confirmar importe de cliente, confirmar solo gestión, borrar proyecto, contrato, factura o línea, e inicio de sesión correcto.
  * La fila copia el nombre de ese día, el id de usuario sin clave ajena, la acción, el tipo de documento, su id y una etiqueta legible. Un solo instante con zona horaria.
  * La fila permanece si se borra el documento. Un disparador impide modificarla o borrarla desde la aplicación.
  * Esas rutas exigen el usuario de la sesión. Si la fila no se inserta, el cambio no se guarda.
  * Rol `superadministrador` y consulta paginada solo para dirección y ese rol. El rol no abre permisos nuevos en el resto de pantallas.
* **Out-of-Scope Non-Goals:**
  * Intentos de inicio de sesión fallidos.
  * Ingesta, extracción, prorrateo y cualquier escritura que el sistema haga sin un gesto de persona.
  * El importe anterior y el importe nuevo.
  * Una fila por cada tarea hija de un mismo gesto.
  * Cerrar las lecturas de la API de obra.
  * Construir la pantalla que cambia el estado de obra o el avance físico.
  * Una matriz de permisos para jefe de obra, administración y dirección.
  * Una purga por plazo.
  * El histórico de versiones del presupuesto (el sufijo de versión del documento).

## Alternatives Weighed

* Registrar cada clic, cada consulta y cada intento de acceso fallido. Rechazado por el autor: solo los gestos de obra ya existentes y el inicio de sesión correcto.
* Guardar el valor anterior y el nuevo. Rechazado por el autor.
* Anotar lo que calcula el sistema antes de que alguien confirme. Rechazado por el autor.
* Borrar la fila cuando se borra la factura o el proyecto. Rechazado por el autor: la fila permanece.
* Mostrar el nombre actual de la persona. Rechazado por el autor: se muestra el nombre de ese día.
* Permitir corregir la fila. Rechazado por el autor.
* Dejar los usuarios para un trabajo posterior. Rechazado por el autor: la fila nombra a quien ha iniciado sesión, y este trabajo incluye el rol nuevo y la consulta.
* Clave ajena al documento o al usuario vivos. Rechazado por el autor al aceptar el cierre: se copia la identidad ese día.
* Una fila por cada tarea tocada. Rechazado por el autor al aceptar el cierre: una fila por gesto.
* Purga en este trabajo. Rechazado por el autor al aceptar el cierre: se conservan sin plazo.
* Construir ahora la pantalla de estado y avance. Rechazado por el autor al aceptar el cierre: se reservan y no se escriben.
* Tratar al superadministrador como un atajo que salta el resto de comprobaciones. Rechazado por el autor al aceptar el cierre: la única comprobación nueva es la consulta.

## Key Decisions & Staging for Next Steps

Queda decidido y pasa al diseño formal:

* La fila es inmutable dentro de la aplicación. Un disparador de PostgreSQL rechaza `UPDATE` y `DELETE`. El dueño de la base sigue pudiendo tocar la tabla.
* La fila copia el nombre de ese día y un id de usuario sin clave ajena, más el tipo, el id y la etiqueta del documento. Un solo instante con zona horaria.
* No se guardan importes. No se registran acciones de sistema ni accesos fallidos.
* Una fila por gesto, escrita en la misma transacción. Si falla, el cambio no se guarda. Los borrados de proyecto, contrato, factura y línea entran.
* Esas rutas exigen el usuario de la sesión. Las lecturas no se cierran aquí.
* El rol `superadministrador` y la consulta paginada entran en este trabajo. La consulta es solo para dirección y ese rol. El rol no concede poderes nuevos en las demás pantallas.
* Quien ya edita usuarios puede asignar el rol nuevo. [VERIFICAR]
* El estado de obra y el avance físico no se registran hasta que exista quien los cambie.
* Las filas se conservan sin plazo y sin purga.
