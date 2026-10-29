# Coste y eficiencia del análisis con IA

Nota para dirección. Describe cómo lee hoy el gestor un presupuesto, un contrato o una factura, dónde se va el tiempo y el dinero, y qué se puede cambiar sin debilitar la revisión humana.

Las cifras de más abajo son un orden de magnitud con la tarifa pública de Claude a octubre de 2026, en dólares. No son la factura del contrato: el sistema no guarda el consumo de cada llamada, y la tarifa aplicada la confirma Seguridad.

## Qué paga el sistema, en una frase

El modelo caro se usa para **ver la página**. El modelo barato se usa para **rellenar los campos**. Lo que ya es texto seleccionable no debería pagar el primero.

La revisión humana no se toca. Un presupuesto, un contrato o una factura leídos por OCR o por un modelo siguen en pendiente de revisión hasta que una persona los confirma. Una anotación manuscrita sobre un valor impreso sigue marcándose y no la resuelve el sistema solo.

Enviar estos documentos a un proveedor externo sigue exigiendo la autorización de Seguridad y la cláusula de que el proveedor no entrena con ellos.

## Cómo se lee cada documento hoy

Con la clave de Claude activa, presupuesto y contrato hacen **dos llamadas** por fichero.

| Documento | Qué ocurre | Modelo | Cuándo se paga |
| --- | --- | --- | --- |
| Presupuesto PDF | El PDF entero se envía al modelo para pasarlo a markdown. Luego ese texto se convierte en naves y apartados. | Sonnet para ver el PDF. Haiku para el JSON. | Siempre, también si el PDF ya tiene texto seleccionable. |
| Contrato PDF | Igual: primero markdown, después árbol de partidas y sugerencia de apartado. | Sonnet y luego Haiku. | Siempre, con el mismo criterio. |
| Factura PDF con texto | Se lee en local y se reconocen NIF, número, base y total con reglas. | Ninguno. | No hay llamada. |
| Factura escaneada, foto o PDF sin texto | Cada página se convierte en imagen (200 ppp) y se transcribe. | El de visión. Con Claude, cae en Sonnet. Si hay API de OCR dedicada, esa va antes. | Una llamada por página. |
| PDF de más de 80 páginas | Se parte en tramos y cada tramo es una llamada de transcripción. | Sonnet, una vez por tramo. | El coste crece con las páginas. |
| Casado contrato–apartado | Comparación de texto (palabras y raíces del oficio). | Ninguno. | La columna de embeddings existe y no se calcula. |

Lo que ya está bien y conviene no deshacer:

- Sonnet solo mira el documento. Haiku, más barato, hace la extracción. No se paga dos veces el modelo caro por el mismo PDF.
- En Sonnet 5 el «pensamiento» del modelo va apagado. Ese razonamiento interno consume el tope de salida y no aporta en una transcripción.
- La factura con texto no pasa por ningún modelo.
- Si la respuesta JSON llega cortada, el sistema intenta cerrarla. No relanza solo la llamada.

## Cuánto se gana si el PDF llega nativo

Un PDF nativo es el que lleva el texto dentro (se puede seleccionar). Una foto o un escaneo es una imagen: el modelo tiene que ver la página para leerla. La tarifa pública de los dos modelos que usa el gestor, por millón de fichas (tokens):

| Modelo | Para qué | Entrada | Salida |
| --- | --- | --- | --- |
| Claude Sonnet 5 | Ver el PDF o la foto | 2 USD | 10 USD |
| Claude Haiku 4.5 | Rellenar los campos | 1 USD | 5 USD |

Fuente: tarifa lista de Anthropic, lista de precios del 7 de octubre de 2026. Sin descuento de lote ni de caché. La salida se paga cinco veces más que la entrada.

### Factura: el ahorro ya está en el código

Una factura en PDF nativo se lee en el servidor y no llama al modelo. Cuesta 0 USD de API.

La misma factura en foto o en PDF escaneado hace una llamada a Sonnet por página. El programa rasteriza cada hoja a 200 ppp. Sonnet 5 cuenta la imagen por recuadros de 28×28 píxeles y la recorta a un tope de unas 4.800 fichas visuales por página. Solo esa imagen son unos 0,01 USD de entrada. La transcripción de la página, en salida, suma otro céntimo si el texto ocupa del orden de 500 a 1.500 fichas.

| Factura | Llamadas | Coste de API, orden de magnitud |
| --- | --- | --- |
| PDF nativo, las páginas que sea | Ninguna | 0 USD |
| Foto o escaneo, 1 página | 1 a Sonnet | unos 0,02 USD |
| Foto o escaneo, 5 páginas | 5 a Sonnet, una detrás de otra | unos 0,10 USD |

Se gana el 100 % del coste de API de esa factura, y la espera: el nativo no espera al modelo; el escaneo espera una llamada por página, cada una con un tope de 3 minutos. La revisión humana sigue en los dos casos: toda factura entra pendiente de confirmar.

### Presupuesto y contrato: hoy el formato no cambia la factura

Con la clave de Claude activa, un PDF de presupuesto o de contrato se envía entero a Sonnet tanto si tiene texto como si es un escaneo. Anthropic, al recibir el PDF, vuelve a convertir cada página en imagen y le suma el texto. El nativo y el escaneado pagan la misma lectura visual.

La foto suelta (JPG, PNG, TIFF) es el caso más lento: una llamada de visión por imagen, no un solo envío del documento.

El ahorro del PDF nativo en presupuesto y contrato aparece cuando el texto local deje de pasar por Sonnet y vaya directo a Haiku. Hasta ese cambio, pedir el PDF nativo mejora la lectura (menos errores de OCR) y no baja esta partida de la factura.

### Presupuesto y contrato: lo que se ganaría con ese cambio

Cuentas de una página, para poder multiplicar. No es un documento real medido; es la tarifa aplicada a cómo está hecho el código.

Escaneado o foto, como ahora:

- Sonnet ve la página: unas 4.800 fichas de imagen, más unas 2.000 de texto si la hoja va densa. Entrada ≈ 0,014 USD.
- Sonnet devuelve la transcripción. Si ocupa unas 2.000 fichas, la salida ≈ 0,020 USD. Es la partida mayor, porque la salida de Sonnet va a 10 USD el millón.
- Haiku rellena los campos sobre ese texto: entrada y salida juntas, ≈ 0,006 USD.

Total de una página leída como imagen: unos 0,04 USD.

La misma página en PDF nativo, leyendo el texto en local y llamando solo a Haiku: unos 0,006 USD. No hay imagen y no hay transcripción de Sonnet.

| Documento de ejemplo | Como foto o escaneo | PDF nativo, sin pasar por Sonnet | Se deja de pagar |
| --- | --- | --- | --- |
| 10 páginas | unos 0,40 USD | unos 0,06 USD | unos 0,34 USD, en torno al 85 % |
| 30 páginas | unos 1,20 USD | unos 0,18 USD | unos 1,00 USD, la misma proporción |

Esas 4.800 fichas son las de una foto o de una factura rasterizada por nosotros a 200 ppp. Un presupuesto o un contrato que ya llega en PDF, aunque sea escaneado, no se parte en una llamada por hoja: se manda el fichero entero y es Anthropic quien convierte cada página en imagen. El importe por página queda en el mismo orden. Lo que cambia es la espera: una llamada para todo el PDF, frente a una llamada por cada foto.

En un presupuesto o contrato de pocas decenas de páginas, la diferencia es de céntimos a cerca de un dólar por documento. El ahorro mensual es esa cifra por el número de documentos. Ese número no está en el proyecto. [VERIFICAR] con el volumen real de obras.

Lo que la oficina nota antes que la factura de la API:

- Desaparece la llamada larga. Hoy la transcripción espera a Sonnet, con un tope de 3 minutos por tramo de 80 páginas, y solo después llama a Haiku. El nativo se queda en una llamada, la corta.
- Un presupuesto escaneado entra siempre en revisión. Uno nativo, solo si hay tachón, si falta un importe o si las sumas no cuadran.
- Un contrato entra siempre en revisión, sea nativo o escaneado. Ahí el formato no acorta la cola; acorta la llamada.
- Si alguien reenvía el mismo escaneo porque la lectura salió mal, se vuelve a pagar la página. Con texto seleccionable ese reintento es mucho menos frecuente.

Un PDF nativo con un importe escrito a mano encima no entra en esta cuenta. El texto del fichero no ve el bolígrafo, y esa página sigue teniendo que verla el modelo, o se pierde la corrección. El ahorro de esta sección es el de los PDF generados en digital, sin pasar por la fotocopiadora.

## Dónde se va el dinero y el tiempo

**1. Se vuelve a leer un PDF que ya se puede leer en local.**  
Antes de llamar a Sonnet, el sistema ya extrae el texto con PyMuPDF (y, si hace falta, con pdfplumber). Ese texto solo sirve para decidir si el PDF parece escaneado. Después se envía el PDF entero igual. En un PDF de plantilla, con texto seleccionable, la llamada cara es redundante.

**2. El mismo fichero se paga dos veces.**  
La transcripción (Sonnet) produce un markdown casi tan largo como el documento. La extracción (Haiku) se lo vuelve a leer entero para devolver JSON. La segunda llamada es la barata y hace falta. La primera es la cara, y solo hace falta cuando el texto local no basta.

**3. Un tachón a mano no sale en el texto local.**  
Por eso no se puede apagar Sonnet en todos los PDF nativos. El texto extraído del PDF no ve una corrección escrita encima de una cifra. Si se prescinde de la visión, esa corrección se pierde y la regla de negocio (el manuscrito prevalece, y obliga a revisión) deja de cumplirse. El ahorro está en reservar la visión para ese caso, no en quitarla.

**4. El escaneado y la foto se pagan por página, con el modelo grande.**  
Una factura de 8 páginas son 8 llamadas de visión. El presupuesto y el contrato en PDF, con Claude, van mejor: un solo envío del documento por cada 80 páginas, no una llamada por hoja. Las imágenes y las facturas escaneadas no usan ese atajo.

**5. El contrato pide un techo de salida muy alto.**  
La extracción del contrato admite hasta 64.000 tokens de respuesta. La del presupuesto usa el tope por defecto, 16.000. La salida es la parte cara de la tarifa. Un árbol de partidas largo se acerca a ese techo; un contrato corto no necesita tenerlo reservado.

**6. Si el administrativo vuelve a subir el mismo PDF, se paga otra vez.**  
No hay memoria del fichero. Un fallo, un reintento o una segunda subida del mismo presupuesto repite Sonnet y Haiku desde cero.

**7. No hay contador.**  
La respuesta del proveedor trae el consumo (entrada, salida, modelo). No se guarda. Sin eso, dirección no puede ver el coste por obra, por tipo de documento ni por reintento.

**8. La espera es la de la llamada, en el acto.**  
Cada subida espera al modelo (tope de 3 minutos por llamada). Un presupuesto largo, partido en tramos, se lee en serie. El administrativo no puede seguir con otra cosa mientras tanto.

## Qué cambiar, por este orden

El orden es el del ahorro esperado frente al riesgo. Las cuatro primeras no cambian lo que ve la persona que revisa: cambia cuántas veces y con qué modelo se lee el documento.

### 1. Medir antes de prometer un ahorro

Guardar, por cada documento y sin datos personales: tipo (presupuesto, contrato, factura), si era escaneado, modelo, tokens de entrada, tokens de salida, duración y si la llamada se repitió.

Con eso, en un piloto corto, se ve el coste real por documento y qué medida merece la pena. Hasta entonces el ahorro se cuenta en «llamadas que dejamos de hacer», no en euros.

### 2. No mandar a Sonnet el PDF que ya tiene texto

Si el PDF trae texto útil, ese texto va directo a Haiku. Sonnet queda para el PDF sin texto, la foto y el caso en el que haya que ver la página.

La excepción es el manuscrito. Hay que acordar con quien revisa los presupuestos con qué frecuencia aparecen tachones en PDF que por lo demás son digitales. Tres opciones, de más segura a más barata:

- Mantener Sonnet en todo PDF hasta tener esa respuesta. No ahorra en presupuestos nativos.
- Texto local + Haiku por defecto, y un botón «este documento tiene correcciones a mano» que lanza la visión solo entonces. Ahorra en el caso general y no se salta la regla: quien sube el papel sabe si hay bolígrafo.
- Una pasada barata de detección (modelo pequeño, o solo las páginas donde suela cerrarse el precio) y Sonnet únicamente si esa pasada marca algo. Hay que probarlo con documentos reales anonimizados antes de fiarse. [VERIFICAR] con el equipo que marca los presupuestos.

### 3. No repetir la lectura cara

Guardar el markdown de la transcripción asociado a la huella del fichero. Si Haiku falla o el administrativo corrige y pide releer los campos, se repite solo la llamada barata. Sonnet no vuelve a ver el mismo PDF.

### 4. Bajar el modelo de los escaneados

La visión de una factura o de una foto no tiene por qué ser Sonnet. Orden que ya contempla el código, y que conviene usar de verdad:

1. API de OCR dedicada, si Seguridad la autoriza. Suele costar por página, no a precio de modelo de lenguaje.
2. Si no hay OCR dedicado, el modelo de visión pequeño (Haiku), no el de transcripción.
3. Sonnet solo cuando el OCR barato devuelve texto insuficiente y una persona pide releer la página.

Misma regla de revisión: escaneado implica `es_escaneado` y confirmación humana.

### 5. Recortar lo que entra y lo que sale en el contrato

A Haiku le hace falta la cabecera (contratista, NIF, objeto, precio, fechas, facturación) y las tablas de partidas. Las condiciones generales largas no cambian el árbol y sí alargan la entrada. El PDF original sigue disponible en la pantalla de revisión.

El tope de 64.000 tokens de salida se puede ajustar al tamaño del documento (páginas o filas de la tabla), no dejarlo fijo en el máximo.

### 6. Separar lo urgente de lo que puede esperar

La subida de un presupuesto, con alguien delante de la pantalla, sigue en el acto: es la que nota la espera.

Una carpeta de facturas escaneadas puede procesarse en lote, fuera de hora, si el proveedor tiene tarifa de lote. Eso no sirve para la pantalla de revisión del momento. [VERIFICAR] si la tarifa contratada incluye lote y con qué plazo de entrega.

### 7. Dejar los embeddings para cuando el texto no baste

El casado de un contrato con el apartado del presupuesto se hace hoy por palabras, sin modelo. La columna de embeddings en la línea de factura está prevista y no se rellena.

No activarla «por si acaso». Si más adelante las sugerencias fallan en oficios que no comparten vocabulario, un embedding barato, calculado una vez por línea y guardado, basta. No hace falta un modelo de lenguaje en cada consulta.

## Qué no hacer

- Quitar la revisión humana para ir más rápido. El fallo del OCR o de una cifra manuscrita cuesta más que la llamada.
- Pasar las facturas con texto por el modelo. Ya se leen sin coste de API.
- Mandar documentos a un proveedor nuevo, o activar caché y lote en la cuenta actual, sin el visto bueno de Seguridad y sin la cláusula de no entrenar.
- Tomar la tabla de más arriba como el ahorro del mes. Es el coste de API por documento con la tarifa pública. Faltan el volumen de obras y la tarifa del contrato.

## Qué se le pide a dirección

1. Autorizar el piloto de medición: registrar consumo durante unas semanas, con documentos anonimizados o con la cuenta ya autorizada, y traer el coste por tipo de documento.
2. Confirmar, con quien revisa las obras, si los tachones a mano son la excepción o la norma en los PDF digitales. De eso depende la opción del punto 2.
3. Confirmar con Seguridad si se puede usar una API de OCR dedicada y, en la cuenta actual, la tarifa de lote.
4. Aprobar la proposición de `docs/proposicion_pdf_nativo.md`: PDF con texto seleccionable como cauce normal en presupuesto, contrato y factura, sin cerrar la puerta al escaneo.

Con el punto 2 en la opción del botón de manuscrito, y con el punto 3 (no repetir Sonnet), el presupuesto digital típico pasa de dos modelos a uno, el barato, y un reintento deja de pagar la lectura del PDF. El escaneado sigue pagando visión, pero con el modelo u OCR del punto 4, no con Sonnet por cada página.
