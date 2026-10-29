# Proposición: que el PDF llegue con texto, no como foto

Para dirección. El detalle de tarifas y de llamadas está en `docs/eficiencia_coste_analisis_ia.md`.

Proponemos que el cauce normal de un presupuesto, un contrato y una factura sea el PDF generado por el programa que lo escribe, con el texto seleccionable. La foto y el escaneo se aceptan, y pasan a ser la excepción.

Un PDF puede llamarse `.pdf` y ser solo una foto metida en un fichero. Ese no vale. Vale el que, al abrirlo, deja seleccionar una cifra con el ratón. Comprobarlo lleva diez segundos y no hace falta ningún técnico.

## Qué se pide, y a quién

**Presupuesto.** Lo genera EXAFAN, desde su plantilla. Se exporta el PDF y se sube ese fichero. No se imprime para escanearlo, ni se fotografía el papel. Quien lo prepara es quien puede cumplir esto desde el primer día: no depende de un tercero.

**Contrato.** El cuerpo (precios, partidas, NIF, plazos) sale del editor en PDF con texto. La firma puede ir en digital sobre ese mismo PDF. Si hay que firmar en papel, se escanea solo la hoja de firmas y el resto se deja en el PDF original. Escanear el contrato entero vuelve a convertir las partidas en imagen.

**Factura.** La manda el contratista, desde su programa de facturación. Se le pide el PDF que ese programa exporta, el mismo que ya archiva, no una foto del papel ni un escaneo de la copia impresa. En el acuse o en la condición de facturación cabe una frase: «Enviar la factura en PDF con texto seleccionable, no fotografía ni escaneo.» Quien solo tenga papel puede seguir mandando el escaneo: el sistema lo lee, más despacio y con revisión obligatoria.

## Qué no se pide

- No se prohíbe el bolígrafo. Si alguien corrige una cifra a mano sobre el presupuesto, lo sube igual y lo dice. Esa página sí tiene que verla el modelo: el texto del PDF no contiene el tachón.
- No se rechaza un escaneo el día que no haya otro fichero. Cortar la entrada pararía la obra por un ahorro de céntimos por documento. El escaneo entra, se marca y se revisa, como ahora.
- No se pide a los contratistas un formato nuevo ni un portal. Se pide el PDF que su programa ya sabe generar.

## Cómo se leería a partir de ahí

1. Si el PDF trae texto, se lee en el servidor. Coste de API de esa lectura: cero.
2. Si no trae texto, OCR. Más barato que el modelo de lenguaje, y suficiente para una factura o un impreso claro.
3. La API de visión solo si el OCR no saca un texto usable, o si hay una corrección a mano.

En la factura, con el paso 1 no hay más llamadas. En presupuesto y contrato, el modelo barato sigue rellenando los campos a partir de ese texto: no ve la página. El modelo que ve la página queda para el fallo del OCR y para el manuscrito.

## Qué se gana si se acepta

En la factura, el 100 % del coste de API de ese documento. Con la tarifa pública de octubre de 2026, la nativa son 0 USD y la escaneada unos 0,02 USD por página, con una espera por hoja.

En presupuesto y contrato, leer la página con el modelo caro sale unas seis veces más que rellenar los campos sobre el texto. Un documento de 10 páginas pasaría de unos 0,40 USD a unos 0,06 USD, y uno de 30 páginas de unos 1,20 USD a unos 0,18 USD. Ese ahorro llega cuando el texto nativo deje de enviarse al modelo que ve la página. Pedir el PDF nativo sin ese cambio mejora la calidad de la lectura y no baja todavía esa partida. Las cifras son orden de magnitud, no la factura del contrato.

El efecto que ve quien revisa: menos lecturas rotas, menos reenvíos del mismo papel y, en el presupuesto, la revisión obligatoria solo cuando hay tachón, falta un importe o las sumas no cuadran. El escaneo entra siempre en esa cola.

## Decisión

Aprobar el PDF con texto seleccionable como cauce normal en presupuesto, contrato y factura, sin cerrar la puerta al escaneo.
