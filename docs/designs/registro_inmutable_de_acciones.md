# Registro inmutable de acciones

*   **Author:** ffabian-exafan
*   **Status:** Draft
*   **Date:** 2026-11-17

--------------------------------------------------------------------------------

## Overview

Dirección tiene que poder decir, meses después, qué persona confirmó un cambio de obra y quién entró bien en la aplicación. Hoy el estado de revisión y el sufijo de versión del presupuesto describen el documento, no a la persona ni el momento.

Este diseño guarda una fila por cada gesto de persona que la aplicación ya tiene, y una consulta que solo abren dirección y un rol nuevo, `superadministrador`. La fila conserva el nombre de ese día y una etiqueta del documento, y se puede leer aunque el documento se haya borrado. No guarda el importe de antes ni el de después. Dentro de la aplicación nadie puede cambiar la fila. Quien administra la base de datos sí puede.

## The Problem

Cuando un importe de obra no cuadra, dirección no tiene forma de saber qué persona confirmó el presupuesto, la factura, el importe de cliente o el apartado de solo gestión, ni quién borró el proyecto, el contrato, la factura o una línea. El inicio de sesión correcto tampoco queda anotado. El estado `pendiente` / `revisada` / `confirmada` dice en qué punto está el documento. No dice quién lo dejó ahí.

Las confirmaciones de obra no reciben hoy al usuario de la sesión. Una fila escrita sin ese usuario quedaría vacía o se podría atribuir a cualquiera. El nombre de la persona se puede cambiar y no es único, y la factura o el proyecto se pueden borrar. Si la fila depende del nombre vivo o del documento vivo, meses después no se lee.

La consulta no puede estar abierta a jefe de obra ni a administración. El rol nuevo entra en este mismo trabajo, pero no convierte al superadministrador en un atajo sobre el resto de pantallas: esas pantallas siguen como están.

## Goals

*   Por cada gesto ya existente —confirmar revisión, confirmar factura, confirmar importe de cliente, confirmar solo gestión, borrar proyecto, contrato, factura o línea, e inicio de sesión correcto— queda una fila con la persona, la acción, el documento y el momento.
*   La fila muestra el nombre tal como era ese día, aunque luego cambie o la persona cause baja.
*   La fila se lee igual si la factura o el proyecto ya no existen.
*   Una confirmación que toca muchas tareas deja una sola fila, no una por tarea.
*   Si la fila no se puede guardar, el gesto tampoco queda guardado.
*   Dirección y `superadministrador` consultan la lista. Jefe de obra y administración no.
*   Nadie, desde la aplicación, modifica ni borra una fila.

## Non-Goals

*   Anotar intentos de inicio de sesión fallidos.
*   Anotar la ingesta, la extracción o el prorrateo antes de que una persona confirme.
*   Guardar el importe anterior o el nuevo.
*   Escribir una fila por cada tarea hija del mismo gesto.
*   Cerrar las lecturas de la API de obra.
*   Construir la pantalla que cambia el estado de obra o el avance físico. Esas acciones se reservan y no se escriben hasta que esa pantalla exista.
*   Definir la matriz de permisos de jefe de obra, administración y dirección.
*   Borrar filas por antigüedad.
*   Sustituir el histórico de versiones del presupuesto (el sufijo de versión del documento).

## Open Questions

*   **Quién asigna `superadministrador`**: los documentos vigentes no lo dicen. Supuesto de trabajo: quien ya puede editar usuarios. [VERIFICAR]

## Critical User Journeys (CUJs)

### CUJ 1: Dirección busca quién confirmó una factura que ya no está

*   **Given**: Una persona de administración confirmó una factura. Después alguien borró esa factura. Han pasado meses y el nombre de quien confirmó ha cambiado.
*   **When**: Dirección abre la consulta y filtra por esa factura.
*   **Then**: Ve una fila con el nombre de aquel día, la acción de confirmar y una etiqueta que sigue identificando la factura. No ve importes. No puede editar ni borrar la fila.

### CUJ 2: Un inicio de sesión correcto queda anotado, un fallo no

*   **Given**: Una persona entra con la clave correcta. Otra intenta entrar y falla.
*   **When**: Dirección abre la consulta.
*   **Then**: Hay una fila del acceso correcto, separada de los cambios de obra. No hay fila del intento fallido.

### CUJ 3: Jefe de obra no abre la consulta

*   **Given**: Hay sesión de jefe de obra.
*   **When**: Abre la dirección de la consulta.
*   **Then**: No ve la lista. Ve que la pantalla es para dirección y el superadministrador.

### CUJ 4: Confirmar un presupuesto no llena la lista de tareas

*   **Given**: Un presupuesto en revisión tiene muchas tareas.
*   **When**: Una persona pulsa confirmar revisión.
*   **Then**: Queda una fila por ese gesto, con la etiqueta del documento confirmado. No queda una fila por cada tarea. Lo que el sistema escribió antes de esa confirmación no genera fila propia.

## Technical Plan (Architecture)

Una sola tabla, `registro_accion`, sin clave ajena. Un solo escritor, `registrar`, al que llaman los servicios de los gestos ya cerrados, en la misma transacción y antes de su `commit`. Si el insert falla, el gesto no se guarda. No hay un gancho del ORM sobre el resto de modelos: la ingesta, la extracción y el prorrateo no pasan por `registrar`.

La fila guarda `usuario_id` como entero suelto, `nombre_en_el_momento` copiado de `usuario.nombre`, un código de acción cerrado, y, salvo en el inicio de sesión, el tipo de documento, su id y una etiqueta. El momento es un `timestamptz` tomado en la base. La consulta calcula el día y la hora en `Europe/Madrid`. El brief pedía la zona de cada obra; el autor eligió `Europe/Madrid` para todas las filas porque el proyecto no guarda una zona. Si una obra se consultara desde otra zona, el día alrededor de medianoche no coincidiría con el de esa zona.

La aplicación entra en PostgreSQL como superusuario del contenedor. La migración `0015`, encadenada a `0014_linea_pdf_manual`, crea la tabla y un disparador `BEFORE UPDATE OR DELETE` que rechaza las dos operaciones. Quitar permisos no basta. Quien conecte como dueño de la base puede desactivar el disparador. El `downgrade` de esa migración tira la tabla: es el único vaciado, y no hay purga en la aplicación.

```text
gesto (confirmar o borrar)          POST /auth/login correcto
        |                                      |
        v                                      v
  lee la etiqueta del documento          no hay documento
        |                                      |
        +-----> registrar() en la misma sesión <----+
                          |
                          v
                   registro_accion
                          |
              commit del gesto, o fallo y nada queda
                          |
                          v
              GET /registro  (dirección | superadministrador)
                          |
                          v
                   registro.html
```

Códigos de acción y etiqueta, copiada antes de borrar:

| Código | Gesto que ya existe | Etiqueta |
| --- | --- | --- |
| `confirmar_revision` | `POST /revisiones/confirmar` | Nombre del proyecto y si el documento es presupuesto o contrato |
| `confirmar_factura` | `POST /facturas/{id}/confirmar` | Número de factura y nombre del proyecto |
| `confirmar_importe_cliente` | `POST /proyectos/{id}/apartados/{tarea_id}/importe-cliente` | Código y descripción de la tarea, y nombre del proyecto |
| `confirmar_importes_cliente` | `POST /proyectos/{id}/importe-cliente` | Una fila por el gesto, con el nombre del proyecto. No una fila por tarea |
| `confirmar_solo_gestion` | `POST /proyectos/{id}/apartados/{tarea_id}/confirmar-gestion` | Código y descripción del apartado, y nombre del proyecto |
| `borrar_proyecto` | `DELETE /proyectos/{id}` | Nombre y código del proyecto |
| `borrar_contrato` | `DELETE /proyectos/{id}/contratos/{contrato_id}` | Nombre del proyecto y, si existe, `referencia_presupuesto`. El contrato no tiene número propio |
| `borrar_factura` | `DELETE /facturas/{id}` | Número de factura y nombre del proyecto |
| `borrar_linea` | `DELETE /proyectos/{id}/lineas/{tarea_id}` | Código y descripción de la tarea, y nombre del proyecto |
| `inicio_sesion` | `POST /auth/login` cuando la clave es válida | Sin tipo ni id de documento |

La etiqueta no copia NIF ni el nombre del contratista. Se corta a 255 caracteres. `borrar_contrato` usa el nombre del proyecto porque no hay otra referencia estable.

El router de cada gesto de esa tabla pasa a depender de `usuario_actual` y entrega el usuario al servicio. El servicio llama a `registrar` y luego hace el `commit` que ya tiene. El resto de rutas de obra, incluidas las de lectura, no cambian. Siguen sin fila, entre otras: importar presupuesto o factura, editar una línea, enlazar un contrato, borrar una línea de PDF manual, marcar o desmarcar solo gestión. Un cambio hecho por esas rutas no aparecerá en la consulta.

En el login correcto el orden es: comprobar la clave, insertar la fila, hacer `commit` y solo entonces escribir la cookie. Si el insert falla, no hay cookie. El login fallido no inserta nada. El logout no inserta nada.

`GET /registro` exige sesión y rol `direccion` o `superadministrador`. Si no, responde 403 con el texto «La consulta es para dirección y el superadministrador.» Devuelve una página de 50 filas como máximo, de la más reciente a la más antigua, filtrable por persona, código de acción, tipo de documento y día en `Europe/Madrid`. Cada ítem trae el nombre de aquel día, la etiqueta en español del código y la etiqueta del documento. No trae importes. No hay `PATCH` ni `DELETE`.

`superadministrador` se añade a `ROLES` en `app/schemas/usuario.py` y al formulario de `usuarios.html`. Cabe en `usuario.rol`, que ya es un `varchar(50)`. Quien hoy puede hacer `PATCH /usuarios/{id}` puede asignarlo. No se añade otra comprobación. Las demás rutas no miran el rol. La semilla sigue siendo dirección.

La entrada de la consulta se añade al menú de `index.html` y de `usuarios.html`, que son las pantallas con el enlace de Usuarios. Se muestra tras leer `GET /auth/yo`, solo para esos dos roles. Las páginas sueltas (`proyecto.html`, `presupuesto.html`, `contrato.html`, `revision.html`, `facturas.html`, `control.html`) no ganan ese enlace. Quien abra `registro.html` sin el rol ve la frase del 403, no la lista.

## Alternatives Considered

Cada alternativa sale de `concepts_brief.md`. No se atribuye un rechazo a un mantenedor externo.

### Alternative A: Registrar cada clic, cada consulta y cada acceso fallido

*   **Pros**: La consulta respondería también a «quién miró el control» y a «quién intentó entrar».
*   **Cons**: Mezcla la navegación con los cambios de obra. El acceso fallido no tiene una persona confirmada. El volumen no responde a la pregunta que dirección hace.
*   **Reason for Rejection**: Rejected by author: solo entran los gestos de obra ya existentes y el inicio de sesión correcto.

### Alternative B: Guardar el importe anterior y el nuevo

*   **Pros**: Una fila explicaría un descuadre, no solo quién confirmó el documento.
*   **Cons**: Cada fila conservaría cifras de obra para siempre, en la misma copia de seguridad que el registro.
*   **Reason for Rejection**: Rejected by author: bastan la persona, la acción, el documento y el momento.

### Alternative C: Anotar la ingesta, la extracción y el prorrateo antes de la confirmación

*   **Pros**: Se vería qué escribió el sistema cuando todavía no hay una persona.
*   **Cons**: Esas escrituras no tienen un usuario de sesión. Un gancho sobre cada `commit` las mezclaría con los gestos de persona y podría tumbar la carga si el insert falla.
*   **Reason for Rejection**: Rejected by author: solo se anota lo que una persona confirma.

### Alternative D: Borrar la fila cuando se borra la factura o el proyecto

*   **Pros**: La tabla no conserva etiquetas de documentos que ya no existen.
*   **Cons**: El borrado es justo el gesto que meses después hay que poder leer. Una clave ajena con `ON DELETE CASCADE` se lleva la fila. Una clave obligatoria impide borrados que la aplicación ya hace.
*   **Reason for Rejection**: Rejected by author: la fila permanece, con la etiqueta copiada ese día.

### Alternative E: Mostrar el nombre vivo de la persona

*   **Pros**: La consulta usa el nombre que dirección ve hoy en Usuarios.
*   **Cons**: `usuario.nombre` se edita, no es único, y la persona se puede dar de baja. Las filas antiguas cambiarían o dejarían de resolverse.
*   **Reason for Rejection**: Rejected by author: se muestra el nombre de ese día.

### Alternative F: Permitir corregir la fila

*   **Pros**: Un registro mal atribuido se podría arreglar desde la pantalla.
*   **Cons**: Si dirección o el superadministrador pueden editarla, deja de servir para decir quién hizo el gesto.
*   **Reason for Rejection**: Rejected by author: la fila no se modifica desde la aplicación.

### Alternative G: Dejar los usuarios para un trabajo posterior

*   **Pros**: El registro se podría escribir sin tocar el rol ni la sesión.
*   **Cons**: Sin el usuario de la sesión la fila no tiene persona. El rol nuevo y la consulta son parte de la misma pregunta.
*   **Reason for Rejection**: Rejected by author: la fila nombra a quien ha iniciado sesión, y este trabajo incluye el rol nuevo y la consulta.

### Alternative H: Clave ajena al documento o al usuario vivos

*   **Pros**: La consulta podría abrir el documento y seguir el nombre actual con un join.
*   **Cons**: El borrado del documento o la baja del usuario rompen el registro o dejan de funcionar.
*   **Reason for Rejection**: Rejected by author: se copia la identidad ese día y no hay clave ajena.

### Alternative I: Una fila por cada tarea tocada

*   **Pros**: Se vería qué partida entró en una confirmación de presupuesto o de factura.
*   **Cons**: Un solo gesto escribe decenas de filas. La consulta cuenta la jerarquía, no las acciones de la persona.
*   **Reason for Rejection**: Rejected by author: una fila por gesto.

### Alternative J: Purga por plazo en este trabajo

*   **Pros**: Los nombres no se quedan sin límite en la misma base.
*   **Cons**: Borrar por antigüedad rompe la regla de que la fila no se modifica. El plazo no está decidido.
*   **Reason for Rejection**: Rejected by author: las filas se conservan sin plazo y sin purga.

### Alternative K: Construir ahora la pantalla de estado y avance

*   **Pros**: El catálogo podría anotar `estado` y `avance_fisico_pct` desde este trabajo.
*   **Cons**: Esas columnas solo se inicializan al crear la tarea. No hay un gesto de persona que registrar, y la pantalla no está definida.
*   **Reason for Rejection**: Rejected by author: se reservan y no se escriben hasta que esa pantalla exista.

### Alternative L: Superadministrador como atajo del resto de comprobaciones

*   **Pros**: Un solo `if` daría a ese rol todas las rutas, presentes y futuras.
*   **Cons**: Los tres roles actuales no tienen matriz. El atajo se olvidaría la excepción del registro en el primer cambio genérico, y cerraría pantallas que hoy usa cualquier sesión.
*   **Reason for Rejection**: Rejected by author: la única comprobación nueva es la consulta. El rol no abre permisos nuevos en las demás pantallas.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security & Privacy**: `GET /registro` solo responde a `direccion` y `superadministrador`. Los gestos de la lista exigen sesión. La etiqueta no copia NIF ni nombre de contratista. Nadie en la aplicación puede hacer `UPDATE` ni `DELETE`; el disparador los rechaza. Quien administra la base sí puede.
*   **Performance & Latency**: La consulta devuelve como máximo 50 filas, con índice por instante. Este trabajo no llama al modelo de lenguaje. Las filas se quedan sin plazo en la misma base.
*   **Rollout & Rollback**: Primero el código que escribe, después `alembic upgrade head`. Para volver atrás, primero el código que deja de escribir y después el `downgrade`, que tira la tabla y las filas. No hay purga en la aplicación.

### Additional Resources

*   `concepts_brief.md`
*   `docs/readme.md`
*   `docs/contexto_proyecto_obra.md`

### Future Improvements

*   **Zona por obra**: hoy el día se muestra en `Europe/Madrid` porque el proyecto no guarda zona. Hace falta una zona en la obra para que el día sea el de esa obra.
*   **Estado y avance**: reservados. Se escriben cuando exista la pantalla que los cambia.
*   **Quién asigna el rol**: sigue en [VERIFICAR]. Hoy lo asigna quien ya edita usuarios.
*   **Gestos sin fila**: importar, editar una línea, enlazar un contrato y borrar una línea de PDF manual no entran en este corte.

## Detailed Implementation Plan

Un gesto que responde 404 o 422 no escribe fila. La fila se inserta solo en el camino que ya hace `db.commit()`, y en la misma sesión, antes de ese `commit`. Si `registrar` lanza, no se llega al `commit` y el gesto no queda. `registrar` no hace `commit`.

### Target Files to Create/Modify

#### 1. `migrations/versions/0015_registro_accion.py` (Create)

*   **Type / Scope**: Migración Alembic.
*   **Proposed Changes**: `revision = "0015_registro_accion"`, `down_revision = "0014_linea_pdf_manual"`. Crea `registro_accion` con `id` entero clave primaria, `ocurrido_en` `timestamptz` no nulo con `now()` de la base, `usuario_id` entero no nulo sin clave ajena, `nombre_en_el_momento` `varchar(255)` no nulo, `accion` `varchar(40)` no nulo, `tipo_documento` `varchar(32)` nulo, `documento_id` entero nulo, `etiqueta` `varchar(255)` nulo. Un `CHECK` limita `accion` a los diez códigos del plan técnico. Otro `CHECK` exige que `inicio_sesion` lleve tipo, id y etiqueta nulos, y que el resto lleve los tres rellenos. Índices en `ocurrido_en`, `usuario_id`, `accion` y `(tipo_documento, documento_id)`. Crea la función `registro_accion_rechazar_cambio` y el disparador `registro_accion_bloquear` `BEFORE UPDATE OR DELETE FOR EACH ROW` que lanza `La fila del registro no se puede modificar`. El `downgrade` quita el disparador, la función y la tabla.

#### 2. `app/models/registro_accion.py` (Create)

*   **Type / Scope**: Modelo SQLAlchemy.
*   **Proposed Changes**: Clase `RegistroAccion` mapeada a esa tabla, sin `relationship` hacia `Usuario`, `Proyecto`, `Factura`, `Contrato` ni `Tarea`.

#### 3. `app/models/__init__.py` (Modify)

*   **Type / Scope**: Export del paquete de modelos.
*   **Proposed Changes**: Importa y exporta `RegistroAccion` para que Alembic y el resto de la app lo vean igual que el resto de entidades.

#### 4. `app/services/registro.py` (Create)

*   **Type / Scope**: Único escritor y catálogo de acciones.
*   **Proposed Changes**: Un diccionario cerrado, en este orden, de código a etiqueta en español: `confirmar_revision` «Confirmó la revisión», `confirmar_factura` «Confirmó la factura», `confirmar_importe_cliente` «Confirmó el importe de cliente», `confirmar_importes_cliente` «Confirmó los importes de cliente», `confirmar_solo_gestion` «Confirmó el apartado de solo gestión», `borrar_proyecto` «Borró el proyecto», `borrar_contrato` «Borró el contrato», `borrar_factura` «Borró la factura», `borrar_linea` «Borró la línea», `inicio_sesion` «Entró». `registrar(db, usuario, accion, tipo_documento=None, documento_id=None, etiqueta=None)` copia `usuario.id` y `usuario.nombre` en el momento, recorta la etiqueta a 255 caracteres, rechaza un código desconocido o una combinación que viole el `CHECK`, y hace `db.add` sin `commit`. `consultar(db, page, usuario_id, accion, tipo_documento, dia)` filtra, ordena por `ocurrido_en` descendente y devuelve la página de 50. El día se interpreta como el intervalo de esa fecha en `Europe/Madrid`.

#### 5. `app/schemas/registro.py` (Create)

*   **Type / Scope**: Esquemas Pydantic de la consulta.
*   **Proposed Changes**: `RegistroItem` con `id`, `ocurrido_en`, `dia_hora` (texto ya calculado en `Europe/Madrid`, formato `DD/MM/YYYY HH:MM`), `nombre`, `accion`, `accion_etiqueta`, `tipo_documento`, `documento_id`, `etiqueta`. `RegistroPagina` con `page`, `page_size` fijo en 50, `total` e `items`. La validación de query (`page >= 1`, `accion` y `tipo_documento` vacíos o pertenecientes al catálogo) vive aquí, no solo en el router.

#### 6. `app/routers/registro.py` (Create)

*   **Type / Scope**: API de solo lectura.
*   **Proposed Changes**: `GET /registro`. Depende de `usuario_actual`. Si `actual.rol` no es `direccion` ni `superadministrador`, 403 con el detalle `La consulta es para dirección y el superadministrador.` No hay `POST`, `PATCH` ni `DELETE`. Una página vacía es 200 con `items` vacío. Una página más allá del final también es 200, no 404.

#### 7. `app/main.py` (Modify)

*   **Type / Scope**: Arranque.
*   **Proposed Changes**: Incluye el router de registro junto al resto, antes del montaje de estáticos. No cambia el middleware que deja la API de obra abierta.

#### 8. `app/schemas/usuario.py` (Modify)

*   **Type / Scope**: Contrato del rol.
*   **Proposed Changes**: Añade `superadministrador` a `ROLES`. El mensaje de rol desconocido nombra también ese valor. `UsuarioRead` sigue sin revalidar el rol, así que `GET /auth/yo` puede devolverlo.

#### 9. `app/routers/auth.py` (Modify)

*   **Type / Scope**: Inicio de sesión.
*   **Proposed Changes**: Si `autenticar` devuelve `None`, la respuesta sigue siendo 401 y no se llama a `registrar`. Si la clave es válida, llama a `registrar` con `inicio_sesion`, hace `db.commit()` y solo entonces escribe `request.session["usuario_id"]`. Si el insert o el `commit` fallan, la cookie no se escribe.

#### 10. `app/routers/revisiones.py` (Modify)

*   **Type / Scope**: Gesto de confirmar revisión.
*   **Proposed Changes**: `POST /revisiones/confirmar` depende de `usuario_actual` y pasa ese usuario a `confirmar_revision`. El resto de rutas del router no cambia.

#### 11. `app/services/revision.py` (Modify)

*   **Type / Scope**: Servicio de revisión.
*   **Proposed Changes**: `confirmar_revision(db, payload, usuario)` llama a `registrar` justo antes del `db.commit()` que ya existe, con `accion="confirmar_revision"`, `tipo_documento=payload.tipo`, `documento_id=payload.documento_id` y etiqueta `"{proyecto.nombre} · presupuesto"` o `"{proyecto.nombre} · contrato"`. Una sola llamada aunque `payload.tareas` tenga muchas filas. Si el documento o el proyecto no existen, se lanza antes y no hay fila.

#### 12. `app/routers/facturas.py` (Modify)

*   **Type / Scope**: Confirmar y borrar factura.
*   **Proposed Changes**: `POST /facturas/{factura_id}/confirmar` y `DELETE /facturas/{factura_id}` dependen de `usuario_actual` y pasan el usuario al servicio. Importar, leer y enlazar contrato no lo hacen.

#### 13. `app/services/facturas.py` (Modify)

*   **Type / Scope**: Servicio de facturas.
*   **Proposed Changes**: `confirmar_factura` recibe `usuario` y, antes de su `commit`, registra `confirmar_factura` con tipo `factura`, el id de la factura y etiqueta `"{payload.numero} · {proyecto.nombre}"`. `borrar_factura` lee número y nombre del proyecto antes del `DELETE`, registra `borrar_factura` con esa etiqueta y después borra, en la misma sesión, antes del `commit`.

#### 14. `app/routers/proyectos.py` (Modify)

*   **Type / Scope**: Gestos de proyecto, contrato, línea e importes.
*   **Proposed Changes**: Dependen de `usuario_actual` y pasan el usuario solo estas funciones: `borrar_proyecto`, `borrar_linea`, `confirmar_importe_cliente`, `confirmar_importes_cliente`, `confirmar_solo_gestion`, `borrar_contrato`. El resto del archivo, incluidos importar, editar líneas, líneas PDF y enlazar apartados, no exige sesión y no registra.

#### 15. `app/services/proyectos.py` (Modify)

*   **Type / Scope**: Borrado de proyecto y de contrato.
*   **Proposed Changes**: `borrar_proyecto(db, proyecto_id, usuario)` copia nombre y código antes de borrar y registra `borrar_proyecto` con etiqueta `"{nombre} · {codigo}"` (sin el código si es nulo) antes del `commit`. `borrar_contrato(db, proyecto_id, contrato_id, usuario)` copia el nombre del proyecto y `referencia_presupuesto` si existe, registra `borrar_contrato` y después ejecuta el borrado que ya tiene.

#### 16. `app/services/lineas.py` (Modify)

*   **Type / Scope**: Borrado de línea de presupuesto.
*   **Proposed Changes**: `borrar_linea(db, proyecto_id, tarea_id, usuario)` copia código, descripción y nombre del proyecto antes de borrar, registra `borrar_linea` con tipo `tarea` y luego sigue con el borrado actual. `crear_linea` y la edición no reciben usuario ni registran.

#### 17. `app/services/presupuesto_excel.py` (Modify)

*   **Type / Scope**: Importe de cliente.
*   **Proposed Changes**: `confirmar_importe_cliente` recibe `usuario` y registra una fila `confirmar_importe_cliente` de tipo `tarea`, con etiqueta de código, descripción y nombre del proyecto, antes de su `commit`. `confirmar_importes_cliente` registra una sola fila `confirmar_importes_cliente` de tipo `proyecto`, con el nombre del proyecto, aunque `tarea_ids` tenga varias. El resto de commits de este archivo no llaman a `registrar`.

#### 18. `app/services/solo_gestion.py` (Modify)

*   **Type / Scope**: Confirmación de solo gestión.
*   **Proposed Changes**: `confirmar` recibe `usuario` y registra `confirmar_solo_gestion` de tipo `tarea` antes de su `commit`. `marcar` y `desmarcar` no registran.

#### 19. `app/static/registro.html` (Create)

*   **Type / Scope**: Pantalla de consulta.
*   **Proposed Changes**: Misma cáscara que `usuarios.html` (menú, `exafan.css`, Alpine, `sesion.js`). No tiene botones de editar ni de borrar. Pide `GET /registro` de una página en página. Filtros: persona (id de usuario), acción, tipo de documento y día. Si no hay filas, el texto es «No hay filas.» Si la API responde 403, muestra ese detalle y no la tabla. El enlace de menú a esta pantalla usa la misma condición que en `index.html`.

#### 20. `app/static/js/registro.js` (Create)

*   **Type / Scope**: Estado Alpine de la consulta.
*   **Proposed Changes**: Parte de `sesionLateral()`. Carga la página 1 al abrir. Cambiar un filtro vuelve a la página 1. No envía cuerpos de escritura. No formatea la hora en el navegador: muestra `dia_hora` tal como llega.

#### 21. `app/static/index.html` (Modify)

*   **Type / Scope**: Menú de obras.
*   **Proposed Changes**: Junto al enlace de Usuarios, un enlace a `/registro.html` con etiqueta «Registro», visible solo si `yo.rol` es `direccion` o `superadministrador`. `gestionObras` ya extiende `sesionLateral`, que rellena `yo`.

#### 22. `app/static/usuarios.html` (Modify)

*   **Type / Scope**: Formulario de rol y menú.
*   **Proposed Changes**: Añade `<option value="superadministrador">Superadministrador</option>` al select de rol, al mismo nivel que los tres actuales. Añade el enlace «Registro» con la misma condición de rol.

#### 23. `app/static/js/usuarios.js` (Modify)

*   **Type / Scope**: Etiquetas de rol.
*   **Proposed Changes**: Añade `superadministrador: "Superadministrador"` al mapa `roles`. Sin eso, la tabla mostraría el código crudo.

#### 24. `docs/readme.md` (Modify)

*   **Type / Scope**: Modelo y API vigentes.
*   **Proposed Changes**: Añade la entidad `REGISTRO_ACCION` con las columnas de esta sección, el cuarto rol y `GET /registro`. No reescribe la matriz de permisos de los otros tres roles: sigue sin estar definida.

#### 25. `tests/sesion.py` (Create)

*   **Type / Scope**: Ayuda de tests, sin fixture automático.
*   **Proposed Changes**: `entrar(client, db, rol="direccion")` crea un usuario ficticio (`nombre` y correo evidentes de prueba, nunca datos reales), hace `POST /auth/login` y devuelve el usuario. No se registra como fixture de `conftest` para no abrir sesión en los tests que no la piden.

#### 26. `tests/test_registro.py` (Create)

*   **Type / Scope**: Pruebas del registro.
*   **Proposed Changes**: Cubre: el login correcto escribe una fila y el fallido no; el logout no escribe; cambiar `usuario.nombre` no cambia la fila ya guardada; confirmar una revisión con varias tareas escribe una fila; confirmar y luego borrar una factura deja la fila con el número copiado; `GET /registro` con dirección o superadministrador devuelve 200 y con jefe de obra o administración devuelve 403; sin sesión, `POST /revisiones/confirmar` devuelve 401 y el documento no cambia; un `UPDATE` SQL directo sobre `registro_accion` falla con el mensaje del disparador; importar un presupuesto no escribe fila.

#### 27. Tests que ya llaman a un gesto protegido (Modify)

*   **Type / Scope**: Pruebas existentes. Hay que entrar antes de la llamada, también si el `delete` solo limpia, porque sin sesión responderá 401 y no borrará.
*   **Proposed Changes**:
    *   `tests/test_revision.py`: antes de `POST /revisiones/confirmar`.
    *   `tests/test_facturas.py`: antes de `POST /facturas/{id}/confirmar` y de `DELETE /facturas/{id}`.
    *   `tests/test_presupuesto_excel.py`: antes de los `POST` a `importe-cliente`.
    *   `tests/test_linea_pdf_manual.py`: antes de los `POST` a `/importe-cliente`. Los `DELETE` de `lineas-pdf` siguen sin sesión.
    *   `tests/test_solo_gestion.py`: antes de los `POST` a `confirmar-gestion`. Marcar y desmarcar siguen sin sesión.
    *   `tests/test_listar_proyectos.py`: antes de `DELETE /proyectos/{id}`.
    *   `tests/test_lineas_presupuesto.py`: antes de `DELETE` de línea y de proyecto.
    *   `tests/test_borrar_contrato.py`: antes de `DELETE` de contrato.
    *   `tests/test_usuarios.py`: el login correcto comprueba que existe una fila `inicio_sesion`; el login fallido comprueba que no existe.

### Verification Plan

*   **Compilation/Build**: `alembic upgrade head` sobre la base de desarrollo. No hay build de front.
*   **Unit Tests**: `pytest tests/test_registro.py` y los nueve archivos de tests modificados.
*   **Static Analysis & Linting**: el linter que ya use el repo sobre los Python tocados.
*   **Test Coverage Requirement**: cada código de acción tiene al menos una prueba que ve la fila. No se fija un porcentaje nuevo.
*   **E2E/Integration**: abrir `registro.html` con dirección y ver una página; abrirla con jefe de obra y ver la frase del 403; confirmar que no hay control para editar ni borrar una fila.

--------------------------------------------------------------------------------

*Drafted with EGM*
