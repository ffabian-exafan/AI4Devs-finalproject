> Prompts principales empleados y refinados durante el ciclo de vida del proyecto. Se han reconstruido en formato reutilizable a partir del trabajo realizado. Cada prompt define rol, contexto, restricciones, entregable y criterios de aceptación.

## Índice

1. [Descripción general del producto](#1-descripción-general-del-producto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Especificación de la API](#4-especificación-de-la-api)
5. [Historias de usuario](#5-historias-de-usuario)
6. [Tickets de trabajo](#6-tickets-de-trabajo)
7. [Pull requests](#7-pull-requests)

---

## 1. Descripción general del producto

**Prompt 1 — Descubrimiento inicial del producto**

```text
Actúa como analista de producto y arquitecto de software especializado en automatización documental para construcción.

Contexto:
Mi empresa ejecuta proyectos de explotaciones ganaderas, tanto obras llave en mano como reformas. Cada obra parte de un presupuesto que describe los trabajos, responsables e importes. El sistema debe leer ese documento, crear un proyecto con sus naves y tareas y, posteriormente, recibir facturas para relacionarlas con el proyecto y controlar el gasto real frente al previsto. El origen futuro de las facturas podría ser una carga manual o una carpeta compartida de Drive o Microsoft, pero todavía no está decidido.

Tarea:
1. Reformula el problema y el valor aportado para jefe de obra, administración y dirección.
2. Separa requisitos funcionales, no funcionales, riesgos y decisiones pendientes.
3. Identifica supuestos que no debamos dar por ciertos.
4. Propón un flujo de usuario inicial, priorizando primero la ingesta de presupuestos.
5. Plantea preguntas concretas para cerrar el alcance del MVP.

Restricciones:
- No inventes campos ni reglas de negocio.
- Distingue seguimiento económico de avance físico.
- Marca como [VERIFICAR] cualquier decisión que necesite ejemplos documentales o validación de negocio.
- Considera que los documentos contienen información personal y financiera sensible.

Entrega:
Un análisis estructurado, en español, que pueda convertirse después en documentación de producto, arquitectura e historias de usuario.
```

**Prompt 2 — Refinamiento con presupuesto y contrato anonimizados**

```text
Actúa como analista funcional senior de software de gestión de obras.

Contexto:
Ya disponemos de un presupuesto y un contrato de subcontrata anonimizados. El presupuesto al cliente cierra principalmente por apartados o sistemas constructivos y no siempre aporta unidad, cantidad o precio unitario. El contrato es un documento diferente y puede contener un desglose más fino, por salas y partidas. En un mismo proyecto participan varios contratistas. Presupuesto, contrato y factura representan, respectivamente, lo ofertado, lo contratado y lo facturado.

Tarea:
- Revisa la definición del producto con estos hallazgos.
- Describe el flujo presupuesto → proyecto → contratos → facturas → control económico.
- Explica cómo respetar el nivel de detalle real de cada documento sin inventar datos.
- Identifica qué decisiones iniciales cambian y qué preguntas siguen abiertas.
- Define los conceptos que deben aparecer en la descripción general: apartados, tareas jerárquicas, contratos, revisión humana, estimaciones y avance físico.

Reglas:
- No mezcles el árbol del presupuesto con el árbol de detalle del contrato.
- El enlace contrato ↔ apartado es una sugerencia hasta que una persona lo confirma.
- Todo dato extraído mediante OCR o LLM permanece pendiente de revisión humana.
- Una anotación manuscrita sobre un valor impreso debe marcarse explícitamente y forzar revisión.
- Usa únicamente documentación y fixtures anonimizadas.

Entrega:
Una descripción actualizada del objetivo, funcionalidades, usuarios, alcance y decisiones abiertas del producto.
```

**Prompt 3 — Diseño del flujo completo de la aplicación**

```text
Actúa como product designer y analista técnico. Diseña el flujo funcional de una aplicación interna de control de obras.

Flujo acordado:
1. Se sube un presupuesto con todos sus apartados.
2. La extracción crea el proyecto y su lista de apartados.
3. Dentro del proyecto se suben contratos de los contratistas.
4. El sistema sugiere qué contrato corresponde a cada apartado y una persona confirma el enlace.
5. Se incorporan facturas y se relacionan con contratista, contrato y, cuando sea posible, tarea.
6. Dirección consulta presupuestado vs. contratado vs. facturado.

Necesito:
- Un recorrido por pantallas y acciones del usuario.
- Estados vacíos, carga, error, extracción pendiente y confirmación.
- Responsabilidad de cada rol: jefe de obra, administración y dirección.
- Separación visual entre datos medidos y repartos estimados.
- Separación entre avance físico y control económico.
- Puntos exactos en los que la revisión humana es obligatoria.

No diseñes funcionalidades que la documentación no defina. Señala como [VERIFICAR] el origen automático de facturas, los estados definitivos y las reglas de alertas.

Devuelve el flujo en pasos y un diagrama Mermaid.
```

---

## 2. Arquitectura del Sistema

### **2.1. Diagrama de arquitectura**

**Prompt 1 — Selección y justificación de arquitectura**

```text
Actúa como arquitecto de software senior. Propón la arquitectura de un MVP que ingiere presupuestos, contratos y facturas, aplica lectura de PDF/OCR/LLM, requiere revisión humana y ofrece control económico.

Stack fijado:
- Backend: Python + FastAPI + Pydantic.
- Persistencia: PostgreSQL + SQLAlchemy + Alembic.
- Búsqueda: pg_trgm y pgvector en la misma base de datos.
- Frontend: HTML + Alpine.js + Chart.js servido por FastAPI, sin build.
- PDF nativo: PyMuPDF o pdfplumber.
- OCR de escaneados: API cloud o visión LLM, sin exigir Tesseract en el sistema operativo.

Compara brevemente monolito modular, solución TypeScript y arquitectura con microservicio de IA. Selecciona una para el MVP y justifica beneficios, sacrificios y criterios para evolucionarla.

Entrega:
- Diagrama Mermaid con navegador, API, servicios de ingesta, OCR, extracción, revisión, casado, control económico y PostgreSQL.
- Explicación del patrón arquitectónico.
- Flujo de datos principal y límites de confianza.

No propongas una base vectorial externa: el volumen por proyecto es reducido y pgvector debe permanecer en PostgreSQL.
```

**Prompt 2 — Actualización del diagrama por OCR y revisión**

```text
Actúa como arquitecto responsable de actualizar un diseño existente.

Modifica el diagrama de arquitectura para reflejar correctamente que:
- La entrada admite PDF nativo, PDF escaneado e imágenes JPG, PNG o TIFF.
- Primero se intenta extraer texto nativo y, si no existe, se usa OCR cloud o visión LLM.
- No hay dependencia obligatoria de Tesseract instalado en cada equipo.
- El resultado del OCR/LLM no se persiste como confirmado: pasa por validación Pydantic y revisión humana.
- Si se detecta una anotación manuscrita, debe conservarse el valor impreso, el valor interpretado y la marca de revisión.
- El casado usa reglas duras, después pg_trgm y finalmente pgvector.

Devuelve el diagrama Mermaid revisado y una explicación breve de cada transición. No ocultes los puntos de fallo ni presentes la IA como determinista.
```

### **2.2. Descripción de componentes principales**

**Prompt 1 — Catálogo técnico de componentes**

```text
Actúa como arquitecto de soluciones. Describe los componentes principales del gestor de obra y la responsabilidad exacta de cada uno.

Incluye:
- Front HTML + Alpine.js y gráficos Chart.js.
- FastAPI, routers y validación Pydantic.
- SQLAlchemy, Alembic y PostgreSQL.
- Lectura de PDF nativo.
- OCR para escaneados e imágenes.
- Extracción estructurada con LLM.
- Revisión humana.
- Casado por NIF, reglas, pg_trgm y pgvector.
- Servicio de control económico.

Para cada componente indica: responsabilidad, entradas, salidas, dependencia tecnológica, errores esperables y frontera con otros componentes.

Restricciones:
- La validación de frontend no sustituye la validación backend.
- Presupuesto, contrato y factura son documentos distintos.
- Los repartos sin desglose son estimaciones.
- El avance físico no se deriva de pagos o facturas.

Entrega una descripción apta para la sección de arquitectura de un README técnico.
```

**Prompt 2 — Componentes de ingesta documental**

```text
Actúa como ingeniero de IA aplicada a documentos y define el subsistema de ingesta.

Diseña una tubería con estas fases:
1. Validación de tipo y tamaño del fichero.
2. Extracción de texto en PDF nativo.
3. Detección de documento escaneado.
4. OCR cloud o visión LLM cuando proceda.
5. Extracción a un esquema estructurado.
6. Validación Pydantic y comprobaciones de sumas.
7. Persistencia en estado pendiente.
8. Revisión y confirmación humana.

Explica cómo registrar `es_escaneado`, `tiene_anotacion_manual`, confianza y procedencia del dato. Incluye estrategia de errores y reintentos sin inventar valores faltantes.

Privacidad:
No se enviará documentación real a terceros sin autorización de Seguridad y garantía [NO-ENTRENAR]. Si no existe autorización, deja indicada la alternativa self-hosted.
```

### **2.3. Descripción de alto nivel del proyecto y estructura de ficheros**

**Prompt 1 — Creación del esqueleto**

```text
Actúa como desarrollador backend senior en Python. Crea el esqueleto del proyecto según la arquitectura acordada.

Necesito:
- `app/main.py`, `app/config.py` y `app/db.py`.
- Carpetas `app/models/`, `app/schemas/`, `app/routers/` y `app/services/`.
- `app/static/` servido por FastAPI desde la raíz.
- Configuración por entorno para `DATABASE_URL` y credenciales opcionales de OCR/LLM.
- `requirements.txt` con FastAPI, Uvicorn, SQLAlchemy, Alembic, PostgreSQL, Pydantic, pydantic-settings, PyMuPDF y pdfplumber.
- `.env.example` sin secretos.
- `GET /health` que devuelva `{"status": "ok"}`.

No implementes aún la lógica de presupuestos, contratos o facturas. Mantén una separación routers → services → models y usa nombres y comentarios en español.

Verifica que la aplicación arranca y que `/health` responde correctamente.
```

**Prompt 2 — Evolución de estructura para UI completa**

```text
Actúa como desarrollador full-stack responsable de un monolito FastAPI sin build de frontend.

Sobre la estructura existente, organiza una UI para todas las fases disponibles:
- Inicio con listado de proyectos y pendientes.
- Subida de presupuesto.
- Subida de contrato dentro de un proyecto.
- Revisión humana.
- Control económico.
- Facturas como placeholder si el backend aún no existe.

Usa `app/static/*.html`, `app/static/js/*.js` y un CSS compartido. Añade solo los endpoints de consulta imprescindibles para navegar, como listado y detalle de proyectos con sus naves.

Requisitos:
- Navegación común.
- Helpers HTTP reutilizables.
- Mensajes de carga, éxito y error.
- Tras importar, dirigir a revisión sin declarar el documento confirmado.
- HTML + Alpine.js + Chart.js, sin bundler.
- Mantener validación Pydantic en backend.

Entrega los cambios y pruebas de los endpoints nuevos.
```

### **2.4. Infraestructura y despliegue**

**Prompt 1 — Diseño de infraestructura local y productiva**

```text
Actúa como ingeniero DevOps. Diseña la infraestructura mínima para desplegar el gestor de obra.

Componentes:
- Contenedor FastAPI que sirve API y frontend.
- PostgreSQL 16 con extensiones pgvector y pg_trgm.
- Reverse proxy con HTTPS.
- Proveedor OCR/LLM cloud solo si está autorizado.
- Alternativa de OCR/modelo self-hosted en contenedor.

Describe:
- Diagrama Mermaid de despliegue.
- Variables de entorno y gestión de secretos.
- Migraciones Alembic.
- Health checks.
- Persistencia de PostgreSQL.
- Flujo de build y despliegue.
- Diferencias entre desarrollo local y producción.

No incluyas credenciales, datos personales ni documentos reales. Evita introducir servicios adicionales que no sean necesarios para el MVP.
```

**Prompt 2 — Arranque verificable del entorno local**

```text
Actúa como ingeniero de plataforma y deja el entorno local operativo.

Pasos:
1. Comprueba si Docker Desktop y el contenedor PostgreSQL están disponibles.
2. Arranca PostgreSQL en el puerto configurado, sin mostrar secretos.
3. Comprueba la disponibilidad con `pg_isready`.
4. Habilita `vector` y `pg_trgm`.
5. Ejecuta `alembic upgrade head`.
6. Arranca FastAPI con Uvicorn.
7. Verifica `/health`, la conexión a base de datos y las páginas estáticas.

Si una dependencia no está disponible, informa del bloqueo con evidencia. No sustituyas PostgreSQL por SQLite porque el proyecto depende de pgvector y pg_trgm.

Entrega un resumen de servicios, puertos y verificaciones realizadas.
```

### **2.5. Seguridad**

**Prompt 1 — Análisis de riesgos y controles**

```text
Actúa como especialista en seguridad y privacidad para aplicaciones empresariales que procesan documentación financiera.

Analiza el gestor de presupuestos, contratos y facturas. Los documentos pueden contener NIF, nombres, direcciones, cuentas e importes pactados.

Genera un modelo de amenazas práctico y controles para:
- Subida y almacenamiento de ficheros.
- OCR/LLM de terceros.
- Inyección de prompt desde documentos.
- Validación de tipos, tamaños y contenido.
- Autenticación y autorización por rol.
- Gestión de secretos.
- Cifrado en tránsito y reposo.
- Trazabilidad de correcciones y confirmaciones.
- Prevención de exposición en logs, fixtures y repositorio.

Reglas obligatorias:
- No enviar documentos reales a cloud sin autorización de Seguridad y cláusula [NO-ENTRENAR].
- Usar únicamente fixtures anonimizadas.
- Revalidar en backend con Pydantic.
- Mantener toda extracción automática pendiente de revisión humana hasta confirmación.

Prioriza los riesgos por impacto y probabilidad e indica qué controles pertenecen al MVP.
```

**Prompt 2 — Revisión de seguridad de la ingesta**

```text
Actúa como revisor de seguridad de código. Audita el flujo de importación de presupuesto, contrato y factura.

Comprueba:
- Lista permitida de formatos.
- Límites de tamaño y protección frente a archivos maliciosos.
- Nombres de fichero no confiables.
- Manejo de excepciones sin filtrar secretos.
- Validación Pydantic independiente del frontend.
- Separación entre estado pendiente y confirmado.
- Rechazo de relaciones con proyectos o contratos ajenos.
- Ausencia de datos sensibles en código, pruebas, migraciones y logs.
- Protección ante contenido documental que intente dar instrucciones al LLM.

Devuelve hallazgos clasificados por severidad, evidencia por fichero y correcciones concretas. No modifiques reglas de negocio sin indicarlo como [VERIFICAR].
```

### **2.6. Tests**

**Prompt 1 — Estrategia de pruebas**

```text
Actúa como QA engineer y diseña la estrategia de pruebas del gestor de obra.

Incluye pruebas unitarias, integración y smoke para:
- Extracción de presupuesto por apartados.
- Detección de anotaciones manuscritas.
- Extracción de contrato con árbol más detallado.
- Jerarquía `tarea_padre_id`.
- Validación Pydantic.
- Estados pendiente y confirmado.
- Listado y detalle de proyectos.
- Sugerencia y confirmación contrato ↔ apartado.
- Ingesta y revisión de facturas.
- Control presupuestado vs. contratado vs. facturado.
- Repartos estimados que conservan el total.

Usa solo fixtures anonimizadas o datos claramente ficticios. No acoples las pruebas a un proveedor real de OCR/LLM: usa dobles o respuestas deterministas.

Entrega matriz de pruebas, casos límite y criterios de aceptación.
```

**Prompt 2 — Implementación y ejecución de pruebas**

```text
Actúa como desarrollador encargado de calidad. Implementa pruebas con pytest para los endpoints y servicios existentes.

Requisitos:
- Aislar llamadas de OCR/LLM.
- Probar respuestas exitosas y errores 404/422.
- Verificar que un documento pendiente no entra en el control económico.
- Verificar que una anotación manual impide confirmar mientras no se revise.
- Verificar sumas con `Decimal`, sin comparaciones imprecisas de float.
- Comprobar integridad de árboles de tareas y relaciones de contrato.
- Probar las consultas de resumen por proyecto, apartado, contratista y contrato.

Ejecuta primero pruebas focalizadas y después la suite completa. Si se bloquea por PostgreSQL, diagnostica la conexión y arranca la dependencia antes de concluir. Informa de pruebas pasadas, fallidas y no ejecutadas sin ocultar resultados.
```

---

## 3. Modelo de Datos

**Prompt 1 — Diseño del modelo relacional**

```text
Actúa como arquitecto de datos. Diseña un modelo PostgreSQL normalizado para proyectos de obra con estas entidades: USUARIO, PROYECTO, PRESUPUESTO, NAVE, CONTRATISTA, CONTRATO, TAREA, FACTURA, LINEA_FACTURA y ASIGNACION.

Decisiones no negociables:
- TAREA es jerárquica mediante `tarea_padre_id` nullable: apartado → subapartado → partida.
- `unidad`, `cantidad` y `precio_unitario` son nullable.
- TAREA tiene `presupuesto_id` y `contrato_id`, ambos nullable, para registrar el documento de origen.
- CONTRATO es independiente de PRESUPUESTO y FACTURA.
- CONTRATO puede enlazar con un apartado mediante `tarea_apartado_id`, confirmado por una persona.
- FACTURA puede enlazar con CONTRATO.
- LINEA_FACTURA contiene embedding pgvector.
- ASIGNACION registra método, confianza y si el reparto es estimado.
- El avance físico no se calcula a partir del gasto.

Entrega:
- ERD completo en Mermaid con PK, FK y cardinalidades.
- Tipos, nulabilidad, restricciones e índices.
- Reglas de integridad y procedencia de datos.
- Decisiones abiertas marcadas [VERIFICAR].
```

**Prompt 2 — Implementación SQLAlchemy y Alembic**

```text
Actúa como desarrollador de persistencia con SQLAlchemy 2 y Alembic.

Implementa en `app/models/` el modelo definido en la documentación y crea una migración inicial.

Debes:
- Mantener nombres de entidad y campo de la documentación.
- Configurar relaciones bidireccionales sin ambigüedad.
- Implementar la autorreferencia de TAREA.
- Usar `Numeric`/`Decimal` para importes y porcentajes.
- Incorporar Vector para `LINEA_FACTURA.embedding`.
- Crear índices por proyecto, NIF, contrato y `tarea_padre_id`.
- Habilitar pgvector y pg_trgm de forma idempotente.
- No añadir datos reales a semillas ni migraciones.

Verificación:
- `alembic upgrade head` desde una base vacía.
- Inspección de tablas, claves y extensiones.
- Pruebas básicas de integridad referencial y jerarquía.
```

**Prompt 3 — Schemas Pydantic y validación**

```text
Actúa como desarrollador FastAPI experto en Pydantic. Genera schemas para todos los modelos SQLAlchemy.

Para cada entidad, separa cuando proceda:
- Create/Input para entrada.
- Read/Out para salida.
- Schemas específicos de importación, revisión y control económico.

Reglas:
- Usa `from_attributes`.
- Valida forma, tipos, enumeraciones y rangos.
- No traslades a los schemas cálculos de negocio o comprobaciones agregadas de sumas; eso corresponde a services.
- Repite en backend todas las restricciones relevantes aunque el frontend ya valide.
- Impide confirmar extracciones con anotaciones manuales sin revisar.
- Respeta campos nullable y no inventes valores por defecto que cambien el significado del documento.

Añade pruebas de payloads válidos e inválidos y documenta los errores esperados.
```

---

## 4. Especificación de la API

**Prompt 1 — Contrato OpenAPI inicial**

```text
Actúa como diseñador de APIs REST con FastAPI. Define la especificación OpenAPI de los endpoints principales del gestor:
- Importar presupuesto y crear proyecto.
- Importar contrato dentro de un proyecto.
- Sugerir y confirmar el enlace contrato ↔ apartado.
- Importar, listar, revisar y confirmar factura.
- Obtener control económico.

Para cada endpoint incluye método, ruta, parámetros, multipart o JSON, códigos de estado y schemas de respuesta.

Reglas:
- Toda importación devuelve estado pendiente y `requiere_revision`.
- Una factura pendiente no modifica el control económico.
- El enlace contrato ↔ apartado no se confirma automáticamente.
- Los errores de validación deben ser explícitos.
- No incluyas datos sensibles reales en ejemplos.

Devuelve YAML OpenAPI y un ejemplo ficticio de respuesta para el control económico.
```

**Prompt 2 — Implementación de ingesta de presupuesto y contrato**

```text
Actúa como desarrollador backend senior. Implementa:
- `POST /proyectos/importar-presupuesto`.
- `POST /proyectos/{id}/importar-contrato`.
- Endpoint de confirmación contrato ↔ apartado.

Presupuesto:
- Acepta PDF nativo, escaneado, imagen y fixture markdown anonimizada.
- Extrae naves y apartados sin inventar unidad, cantidad ni precio unitario.
- Detecta anotaciones manuales y obliga a revisión.

Contrato:
- Extrae contratista, precio total, plazo y condiciones.
- Conserva su propio árbol de subapartados y partidas.
- Sugiere apartados candidatos del presupuesto con confianza y motivo.
- Persiste `tarea_apartado_id` solo después de confirmación humana.

Usa Pydantic, transacciones y errores HTTP coherentes. Añade pruebas de integración con fixtures anonimizadas.
```

**Prompt 3 — API de proyectos, facturas y seguimiento**

```text
Actúa como desarrollador full-stack orientado a API. Amplía el backend para soportar la pantalla principal y el seguimiento económico.

Necesito:
- `GET /proyectos` con resumen de cada proyecto.
- `GET /proyectos/{id}` con sus naves.
- `GET /proyectos/{id}/apartados` con tareas raíz del presupuesto, contrato asociado y métricas.
- `POST /facturas`, listado, detalle y confirmación.
- `GET /proyectos/{id}/control-economico`.

Reglas de cálculo:
- Presupuestado procede del apartado del presupuesto.
- Contratado procede solo de contratos confirmados enlazados al apartado.
- Facturado procede solo de facturas confirmadas.
- Una factura solo puede sugerir contratos del mismo proyecto y contratista.
- Lo no desglosado se marca `es_estimacion = true`.
- No deduzcas avance físico a partir de importes.

Entrega implementación, schemas, consultas eficientes y pruebas de autorización relacional y agregados.
```

---

## 5. Historias de Usuario

**Prompt 1 — Historias principales**

```text
Actúa como Product Owner. Redacta las historias de usuario principales para un gestor de obra usado por jefe de obra, administración y dirección.

Incluye al menos:
1. Ingesta y revisión de presupuesto.
2. Ingesta de contrato y confirmación de su apartado.
3. Ingesta y revisión de factura.
4. Consulta del control económico.

Formato:
Como [rol], quiero [capacidad], para [valor].

Para cada historia añade criterios de aceptación verificables en Given/When/Then o lista inequívoca. Incluye estados de error, revisión humana, anotaciones manuscritas, datos estimados y separación entre gasto y avance físico.

No conviertas decisiones abiertas en requisitos. Márcalas como [VERIFICAR].
```

**Prompt 2 — Refinamiento de la pantalla principal**

```text
Actúa como Product Owner y UX analyst. Refina una historia para esta necesidad:

“Quiero una pantalla principal con todos los proyectos. Al entrar en uno, quiero ver sus apartados, saber si cada apartado tiene contrato asociado y seguir el importe contratado frente a las facturas que van entrando.”

Define:
- Roles y objetivo.
- Información mínima de la tarjeta de proyecto.
- Contenido de la vista de detalle.
- Estados “sin contrato”, “contrato pendiente de confirmar”, “con contrato” y “con facturas”.
- Métricas por apartado y reglas de procedencia.
- Navegación a carga de contrato, factura y revisión.
- Criterios de aceptación y casos vacíos.

No presentes importes pendientes como confirmados ni datos estimados como medidos.
```

---

## 6. Tickets de Trabajo

**Prompt 1 — Descomposición técnica por capas**

```text
Actúa como tech lead. Convierte la documentación del gestor de obra en tickets pequeños y ejecutables.

Crea tickets para:
- Backend de ingesta de presupuesto.
- Backend de ingesta de contrato y sugerencia de apartado.
- Frontend de revisión humana.
- Base de datos y control económico.
- Ingesta y seguimiento de facturas.
- Pantalla principal de proyectos y detalle por apartados.

Cada ticket debe incluir:
- Objetivo y contexto.
- Alcance y fuera de alcance.
- Archivos o capas afectadas.
- Tareas técnicas.
- Dependencias.
- Criterios de aceptación verificables.
- Pruebas.
- Definición de hecho.
- Riesgos de privacidad y datos.

Respeta la numeración y los nombres de entidad de la documentación. Prioriza primero presupuesto, después modelo/control, contratos y finalmente facturas.
```

**Prompt 2 — Plan de implementación de UI por fases**

```text
Actúa como líder full-stack. Prepara un plan implementable para una UI HTML + Alpine.js + Chart.js, servida por FastAPI y sin build.

Alcance:
- Hub con proyectos y documentos pendientes.
- Formulario de presupuesto.
- Revisión humana.
- Formulario de contrato con proyecto y nave opcional.
- Control económico con tablas y gráficos.
- Facturas como placeholder si su API todavía no está lista.

Identifica qué endpoints faltan para que la navegación funcione. Divide el trabajo en tareas ordenadas, indicando ficheros, dependencias y verificación.

Criterios:
- Navegación común.
- Diseño adaptable.
- Errores de API visibles.
- Ninguna importación se muestra como confirmada antes de revisión.
- Datos estimados identificados visualmente.
- Tests para endpoints nuevos y smoke de páginas estáticas.
```

**Prompt 3 — Ejecución autónoma de un ticket**

```text
Actúa como agente de desarrollo responsable de completar el ticket adjunto de principio a fin.

Antes de editar:
1. Lee la documentación de contexto, stack, modelo, API y ticket.
2. Inspecciona implementación y pruebas existentes.
3. Identifica cualquier contradicción con el modelo de negocio.

Durante la implementación:
- Mantén el stack fijado.
- Usa TAREA jerárquica con `tarea_padre_id`.
- Valida entrada con Pydantic.
- Usa datos anonimizados o ficticios.
- Mantén OCR/LLM pendiente de revisión humana.
- Marca las anotaciones manuales y obliga a confirmarlas.
- No realices refactorizaciones ajenas al ticket.

Al finalizar:
- Ejecuta pruebas focalizadas y suite relevante.
- Revisa lint y migraciones si aplican.
- Resume ficheros modificados, comportamiento, pruebas y cualquier [VERIFICAR].
No te detengas mientras quede una acción segura y necesaria para cumplir la definición de hecho.
```

---

## 7. Pull Requests

**Prompt 1 — Preparación y revisión de PR**

```text
Actúa como revisor senior antes de abrir una Pull Request.

Revisa los cambios de la rama frente a main y comprueba:
- Alcance coherente y sin cambios accidentales.
- Modelo TAREA jerárquico correcto.
- Presupuesto, contrato y factura separados.
- Validación Pydantic en backend.
- Estados pendiente/confirmado correctos.
- Ausencia de secretos y datos sensibles.
- Migraciones reversibles y consistentes.
- Pruebas relevantes ejecutadas.
- Documentación actualizada.

Entrega:
- Título de PR en español.
- Resumen funcional.
- Cambios técnicos.
- Pasos de prueba.
- Riesgos y decisiones [VERIFICAR].
- Checklist de revisión.

No afirmes que una prueba pasó si no se ejecutó correctamente.
```

**Prompt 2 — División del trabajo en PRs revisables**

```text
Actúa como tech lead y divide el trabajo del gestor de obra en Pull Requests pequeñas, ordenadas y revisables.

Propuesta de bloques:
1. Esqueleto, configuración y health check.
2. Modelo SQLAlchemy, Alembic y schemas.
3. Ingesta de presupuesto y revisión humana.
4. Ingesta de contratos y enlace con apartados.
5. UI de proyectos y flujo por fases.
6. Facturas y control económico.

Para cada PR define objetivo, dependencias, cambios incluidos, fuera de alcance, pruebas y estrategia de migración. Evita mezclar cambios de infraestructura, modelo y UI si pueden revisarse por separado.
```

**Prompt 3 — Integración y publicación de la entrega**

```text
Actúa como responsable de integración Git.

Objetivo:
Integrar el proyecto local con la rama `main` del repositorio de entrega y publicar el resultado en una rama de feature, sin modificar directamente `main`.

Procedimiento:
1. Inspecciona estado, remotos, ramas y posibles cambios locales.
2. Protege secretos y entornos locales mediante `.gitignore`.
3. Obtén `origin/main`.
4. Crea la rama de entrega desde main e integra el proyecto conservando el historial cuando sea posible.
5. Resuelve conflictos sin descartar trabajo local.
6. Ejecuta pruebas relevantes con PostgreSQL disponible.
7. Crea un commit en español y publica la rama.
8. Verifica árbol limpio y upstream.

Entrega:
Enlace a la rama y a la creación de la PR, hash del commit y resultado real de las pruebas. No uses operaciones destructivas ni fuerces la actualización de main.
```

---



