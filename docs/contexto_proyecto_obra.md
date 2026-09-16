# Contexto del proyecto — Gestor de presupuestos y facturas de obra

Documento base del proyecto. Reúne qué construimos, qué está decidido, qué falta por cerrar y cómo trabajar. Es la referencia común para todas las conversaciones del proyecto.

*Versión 2 — actualizada el 6 de septiembre de 2026 con los hallazgos de un presupuesto y un contrato reales (anonimizados). Fuente: conversación de proyecto "Pendientes por definir" y los documentos `presupuesto_nave_destete_anonimizado.md` / `contrato_subcontrata_electricidad_anonimizado.md`.*

---

## 1. Objetivo

Desarrollar una aplicación para el seguimiento de proyectos de explotaciones ganaderas (obra llave en mano y reformas). El sistema debe:

- Leer presupuestos (PDF nativo, PDF escaneado o imagen) y extraer su desglose económico (por apartado/sistema constructivo y, cuando exista, por partida con precio unitario).
- Leer también los contratos de ejecución firmados con subcontratistas, que a veces bajan a más detalle que el presupuesto al cliente.
- Generar un proyecto en la aplicación con su lista de naves y partidas.
- Leer las facturas asociadas y relacionarlas con su contratista (y, cuando se pueda, con su contrato o partida).
- Ofrecer seguimiento del estado de cada partida y comparar gasto real con presupuestado y con contratado.

## 2. Flujo previsto

Detalle de pantallas y API: `docs/flujo_ui_proyecto.md` (acordado 15 sept. 2026).

1. El usuario sube un presupuesto (PDF nativo, PDF escaneado o imagen).
2. El sistema lo lee (texto directo u OCR si es escaneado) y detecta naves y partidas, respetando el nivel de desglose real (apartado o, si lo hay, partida con precio unitario).
3. Se crea el proyecto; la pantalla del proyecto muestra la **lista de apartados**.
4. Dentro del proyecto se suben los contratos de subcontrata; el sistema **sugiere** qué contrato va con cada apartado y una persona confirma el enlace (`CONTRATO.tarea_apartado_id`). El contrato puede aportar desglose más fino (por sala, con precio unitario) sin mezclar árboles.
5. Los usuarios suben facturas, o el sistema las lee de una carpeta compartida (por definir).
6. El sistema casa cada factura con su contratista (por NIF) y, cuando el desglose lo permite, con su contrato o partida.
7. Se actualiza el estado de las partidas y el control económico: presupuestado vs. contratado vs. facturado.

## 3. Contexto técnico cerrado

- **Formatos de entrada (presupuestos):** no solo PDF nativo. **Muchos presupuestos llegan escaneados** (imagen JPG/PNG/TIFF, o PDF solo imagen sin texto seleccionable). También hay PDF nativos de plantilla EXAFAN y fixtures `.md` en pruebas. La ingesta debe aceptar ambos y pasar los escaneados por **OCR**.
- **PDF nativo** (cuando lo es): lectura fiable en el texto impreso. Puede llevar correcciones **manuscritas** sobre el valor impreso; el manuscrito prevalece. Revisión humana también aquí.
- **Escaneado / imagen:** OCR vía API cloud o visión LLM (**sin instalar Tesseract en el SO**) → baja fiabilidad → `es_escaneado = true` y revisión humana **obligatoria** sin excepción.
- Las facturas vienen de terceros y pueden ser nativas o escaneadas: mismo patrón OCR + revisión.
- Contratos: hoy modelados como PDF; **[VERIFICAR]** si también llegan escaneados o en imagen.
- Sí hay revisiones de presupuesto: el número de presupuesto lleva sufijo de versión (ej. "V2"). Hay que modelar el histórico.

## 4. Decisiones cerradas por el ejemplo real (6 sept. 2026)

- **Granularidad del presupuesto al cliente:** no cierra por partida con precio unitario — cierra por **apartado o sistema constructivo** (cubierta, alimentación, suelos, corrales, ventilación, obra civil, estructura, instalaciones...), cada uno con un único importe. El detalle de unidades y cantidades aparece en el texto descriptivo, pero no siempre enlazado a un precio unitario visible. **[VERIFICAR si es el patrón general o un caso particular de este presupuesto.]**
- **Multiplicidad de entidades facturadoras:** un mismo proyecto reparte el gasto entre partidas que monta y factura EXAFAN directamente y partidas que factura cada proveedor externo (obra civil, estructura, fontanería, electricidad...), cada bloque con su propio total y sus propias condiciones de pago. No hay "un contratista", hay varios por proyecto.
- **Nuevo tipo de documento: CONTRATO.** El contrato de ejecución con un subcontratista (precio cerrado, plazo, condiciones de medición y facturación) es un documento distinto del presupuesto y de la factura, y el modelo de datos anterior no lo contemplaba.
- **El contrato sí puede bajar a partida con precio unitario** (en el ejemplo, desglosado por Sala 1/2/3), justo el nivel de detalle que el presupuesto al cliente no da. Queda abierto si ese desglose sobrevive hasta la factura real del subcontratista — no tenemos ninguna factura de ejemplo todavía. **[VERIFICAR]**
- **Caso real de desvío presupuesto-vs-contratado:** el importe de electricidad presupuestado al cliente y el importe realmente contratado con el subcontratista eléctrico no coinciden. Es el primer caso de prueba real para el control económico.

## 5. Decisiones abiertas

- ¿Todos los presupuestos a cliente cierran por apartado, o algunos bajan a partida con precio unitario? Depende de más ejemplos.
- ¿El desglose por Sala del contrato de subcontrata se mantiene también en la factura mensual real, o se agrega en un único importe?
- ~~¿Conviene enlazar `CONTRATO` con `PRESUPUESTO` de forma estructurada?~~ **Parcialmente cerrado (15 sept. 2026):** el enlace operativo es contrato ↔ **apartado** (`tarea_apartado_id`), no obligatorio al `PRESUPUESTO.id`. `referencia_presupuesto` sigue siendo texto libre al nº de presupuesto.
- Origen de las facturas: Drive u OneDrive/SharePoint.
- Existencia de un ERP o programa de contabilidad previo (Sage, A3, Holded...).
- Definición del estado de tarea/partida y quién lo marca.
- Alcance: MVP por fases frente a sistema completo.
- Validación de Dirección sobre el reparto estimado a nave/tarea cuando el contratista no desglosa (ver `desglose_factura_direccion.docx`) — sigue pendiente y es independiente de lo anterior.

## 6. Cómo trabajar en el proyecto

- Actúa como analista técnico y de producto: propón, cuestiona supuestos y señala riesgos antes de dar soluciones.
- Empieza siempre por la ingesta de presupuestos; deja el casado de facturas para una fase posterior.
- Distingue el seguimiento económico del avance físico de la obra: no son lo mismo. Una tarea puede estar pagada al 100% y sin terminar, o al revés.
- Propón pantallas de revisión humana donde el OCR (o una anotación manuscrita) pueda fallar — también en presupuestos, no solo en facturas.
- Tono interno: español coloquial de tú, frases breves y voz activa.

## 7. Privacidad y datos [SENSIBLE]

- Las facturas y contratos contienen datos personales y financieros (NIF, nombres, cuentas, importes pactados).
- No subir documentos reales sin anonimizar.
- Validar cualquier prueba con datos sensibles con ai.seguridad@exafan.com.
- Marca los datos dudosos con [VERIFICAR] y el material sensible con [SENSIBLE].
- Ya existen dos documentos de referencia anonimizados en el proyecto: `presupuesto_nave_destete_anonimizado.md` y `contrato_subcontrata_electricidad_anonimizado.md`. Úsalos como fixtures de diseño y de test; los originales firmados no se suben ni se comparten.

## 8. Pendiente de recibir

- ~~Un presupuesto de ejemplo (anonimizado)~~ — **recibido y anonimizado el 6 de septiembre de 2026**, junto con un contrato de subcontrata.
- Un ejemplo real de **factura** de subcontratista (aún no lo tenemos) — hace falta para confirmar si el desglose por Sala sobrevive a la factura o se agrega.
- Un segundo presupuesto de un tipo de obra distinto, para confirmar si el cierre por apartado es el patrón general.
- El listado de preguntas abiertas está en el documento de trabajo del proyecto (`preguntas_proyecto_obra.md`).
