Diseña la interfaz de una aplicación web interna de escritorio, en español, para Exafan. Se llama «Gestor de presupuestos y facturas de obra». Sirve para seguir el gasto de obras en explotaciones ganaderas (naves de destete, llave en mano y reformas).

No es una app de consumidor ni un panel de marketing. La usan tres personas en oficina, con ratón y pantalla de portátil o sobremesa (~1280 px):

- Jefe de obra: sube el presupuesto, crea el proyecto, sube contratos y confirma a qué apartado pertenece cada uno. Marca el avance físico de la obra.
- Administración: sube facturas, corrige lo que el sistema ha leído y confirma contratista y contrato antes de que cuenten en los totales.
- Dirección: consulta el control económico y las alertas de desvío. No captura documentos.

El problema que resuelve: el presupuesto al cliente va en PDF, cada subcontrata tiene su contrato y las facturas llegan sueltas. Cruzarlo a mano es lento. La app lee esos documentos, pide confirmación humana y compara tres cifras distintas: lo presupuestado al cliente, lo contratado con el subcontratista y lo facturado.

Reglas que la interfaz no puede romper:

- Ningún presupuesto, contrato o factura leído por OCR o por un modelo se da por guardado hasta que una persona lo confirma. El botón de cierre dice «Pasar a revisión» o «Confirmar», nunca «Guardado».
- Si el documento es un escaneo, una foto o un PDF sin texto, la revisión es obligatoria.
- Si hay una anotación manuscrita encima de un valor impreso, el manuscrito prevalece. Muestra el impreso tachado y el manuscrito al lado, en naranja, y no dejes confirmar hasta revisarlo.
- Una factura pendiente de revisión no entra en los totales.
- Si el sistema reparte un importe porque la factura no desglosa, etiquétalo siempre como «estimación», nunca como dato medido.
- El avance físico (no iniciada / en curso / finalizada, más un porcentaje) es independiente del dinero. Una partida puede estar pagada al 100 % y sin terminar. No mezcles esas dos lecturas.
- El presupuesto al cliente cierra por apartado: un importe por sistema constructivo, casi nunca con precio unitario. No inventes precios unitarios en esos apartados.
- El contrato de subcontrata puede traer un árbol más fino (por sala, con unidad, cantidad y precio unitario). Ese árbol es otro documento: no lo metas dentro de la tabla del presupuesto. El enlace es uno solo —este contrato corresponde a este apartado— y hasta que una persona lo confirma es solo una sugerencia. Un contrato sin confirmar no pinta el cruce presupuestado/contratado como dato cerrado.
- Un proyecto tiene varios contratistas. Parte lo factura Exafan y parte cada proveedor (obra civil, estructura, fontanería, electricidad). No diseñes la obra como si tuviera un único contratista.

Objetos que aparecen en pantalla:

- Proyecto: nombre, tipo (llave en mano o reforma), estado, naves.
- Presupuesto: versión (el número lleva sufijo, por ejemplo V2), origen (PDF nativo, PDF escaneado o imagen), estado de revisión.
- Apartado: código, descripción, importe presupuestado, estado de revisión, contrato enlazado o «sin contrato».
- Contrato: contratista, NIF, precio cerrado, plazo, condiciones de facturación, apartado sugerido o confirmado, y su desglose propio si existe.
- Factura: número, fecha, contratista, base, IVA, IRPF, retención de garantía, total, tipo (ordinaria, anticipo o certificación), contrato asociado, estado de revisión (pendiente o confirmada).
- Nave: unidad de la obra. En el ejemplo, una nave de destete y un almacén.

Diseña estas siete pantallas, en este orden, como un flujo continuo:

1. Inicio. Barra superior con el nombre de la app y el rol de quien ha entrado. Dos bloques: lista de proyectos (nombre, tipo, estado, accesos a facturas y a control) y cola de revisión pendiente (documento, tipo, motivo: escaneado o anotación manuscrita). Estado vacío: ningún proyecto y un único botón, «Subir el primer presupuesto».

2. Subir presupuesto. Zona de arrastre para PDF, JPG, PNG o TIFF. Tras procesar, un resumen antes de la revisión: naves detectadas, apartados detectados, si la suma cuadra con el total, avisos de escaneo y de anotaciones manuscritas. Cierre: «Pasar a revisión».

3. Revisión humana. Una sola pantalla con tres modos (presupuesto, contrato, factura). Dos columnas: a la izquierda el documento o un extracto legible; a la derecha los campos editables. Ámbar para baja confianza, naranja para manuscrito. Aviso visible si las sumas no cuadran. En factura, el enlace propuesto al contratista (por NIF) y al contrato se puede corregir. Solo se proponen contratos ya confirmados, del mismo proyecto y del mismo contratista. No se puede confirmar mientras quede un manuscrito sin revisar.

4. Proyecto, vista principal. Cabecera: nombre de la obra, tipo, estado, naves, versión del presupuesto. Tabla de apartados con código, descripción, importe presupuestado, estado de revisión y contrato enlazado. Fila expandible si el apartado tiene hijos. Acción principal: «Subir contrato». Acciones secundarias: revisión, facturas, control. Bloque aparte, no mezclado en la tabla: contratos del proyecto, cada uno con la sugerencia («este contrato parece corresponder a Electricidad») y dos acciones, «Confirmar» y «Elegir otro apartado».

5. Detalle de contrato. Cabecera con contratista, NIF, precio total, plazo y condiciones de facturación. Debajo, el desglose propio (salas y precios unitarios) con un aspecto visual distinto al del presupuesto. Debajo, el apartado de presupuesto sugerido, pendiente de confirmar.

6. Facturas del proyecto. Listado con estado pendiente o confirmada. Las pendientes se distinguen y no suman. Alta por arrastre. Al abrir una factura, el mismo patrón de revisión de la pantalla 3.

7. Control económico, para dirección. Arriba, tres cifras del proyecto: presupuestado, contratado, facturado, y el desvío. Gráfico de barras agrupadas por contratista con esas tres series. Tabla por apartado con las tres cifras, el desvío y una marca si el enlace de contrato no está confirmado. Tabla por nave con el gasto marcado como estimación cuando no hay medición real. Leyenda fija: medido frente a estimación. Bloque separado de avance físico (estado y porcentaje), para que no se lea como dinero. Alertas discretas: desvío sobre presupuesto, desvío sobre contratado, partida sin facturas. Filtro por proyecto y por nave.

Incluye también estos estados, no solo el camino feliz: lista vacía, documento pendiente de revisión, documento confirmado, sumas que no cuadran, y sugerencia de apartado aún sin confirmar.

Usa estos datos ficticios, solo para las maquetas. No son cifras reales.

Obra: «Nave de destete — Granja Norte». Tipo: llave en mano. Naves: nave de destete y almacén. Presupuesto versión V2.

| Apartado | Presupuestado | Contratado | Facturado |
|---|---:|---:|---:|
| Cubierta | 80.000 € | — | — |
| Alimentación | 120.000 € | — | — |
| Obra civil | 90.000 € | 90.000 € | 40.000 € |
| Electricidad | 50.000 € | 62.000 € | 20.000 € |

Electricidad es el caso que tiene que verse de un golpe: presupuestado 50.000 €, contratado 62.000 €. El desvío aparece en la fila del proyecto y otra vez en el control, sin abrir un detalle.

Contrato de ejemplo: «Instalaciones Eléctricas Norte, S.L.», NIF B00000000, precio 62.000 €, plazo 8 semanas, desglose propio en Sala 1, Sala 2 y Sala 3 con precio unitario. Sugerencia: apartado Electricidad. Estado: pendiente de confirmar.

Facturas de ejemplo: una ordinaria de ese contratista, escaneada y pendiente de revisión, que no suma; otra de obra civil ya confirmada, que sí suma.

En el presupuesto, un descuento final con el importe impreso tachado y un importe manuscrito al lado. Ese campo bloquea la confirmación hasta que alguien lo acepte.

Tono visual: herramienta interna de oficina, sobria, densa en tablas, tipografía clara. El color solo marca estado: pendiente, confirmado, alerta, manuscrito, estimación. Verde oscuro como acento, sin ilustraciones ni fotos de granja. Textos cortos, en español. Iconos solo cuando sustituyen una etiqueta.

No diseñes alta de usuarios, contabilidad ni un chat. No juntes el árbol del contrato dentro de la tabla del presupuesto. No sumes facturas pendientes. No des por cerrada una sugerencia de enlace.

Entrega el flujo de las siete pantallas en escritorio, con los estados pedidos y con el desvío de electricidad visible en el proyecto y en el control.
