"""Genera los PDF ficticios del vídeo. Cifras de ejemplo, sin datos reales."""

from pathlib import Path

import pymupdf

SALIDA = Path(__file__).resolve().parent
FUENTES = Path(r"C:\Windows\Fonts")

CSS = """
@font-face { font-family: demo; src: url(arial.ttf); }
@font-face { font-family: demob; src: url(arialbd.ttf); }
body { font-family: demo; font-size: 10.5pt; color: #1c1c1c; }
h1 { font-family: demob; font-size: 16pt; color: #6e2094; margin: 0 0 4pt 0; }
h2 { font-family: demob; font-size: 12pt; color: #6e2094; margin: 14pt 0 6pt 0; }
p { margin: 0 0 6pt 0; }
.marca { font-family: demob; font-size: 11pt; color: #6e2094; }
.aviso { background: #fff6e8; padding: 6pt 8pt; }
table { width: 100%; border-collapse: collapse; margin-top: 4pt; }
th { font-family: demob; text-align: left; background: #f3e8f8; padding: 4pt 6pt; }
td { padding: 4pt 6pt; border-bottom: 0.4pt solid #ddd; vertical-align: top; }
.num { text-align: right; font-family: demob; }
.pie { font-size: 9pt; color: #555; }
.fijo { white-space: nowrap; }
"""


def _pdf(nombre: str, html: str) -> Path:
    destino = SALIDA / nombre
    mediabox = pymupdf.paper_rect("a4")
    donde = mediabox + (40, 36, -40, -40)
    story = pymupdf.Story(html, user_css=CSS, archive=pymupdf.Archive(str(FUENTES)))
    writer = pymupdf.DocumentWriter(str(destino))
    mas = 1
    while mas:
        device = writer.begin_page(mediabox)
        mas, _ = story.place(donde)
        story.draw(device)
        writer.end_page()
    writer.close()
    return destino


def presupuesto() -> Path:
    html = """
    <p class="marca">EXAFAN, S.A.U. — documento de demostración</p>
    <h1>Presupuesto de obra llave en mano</h1>
    <p>Presupuesto nº <span class="fijo">PRES-DEMO-2026-014</span>. Versión 1. Zaragoza, 15 de febrero de 2026.</p>
    <p><b>Proyecto:</b> Nave de cebo de demostración, 1.200 plazas.</p>
    <p><b>Tipo de proyecto:</b> llave en mano.</p>
    <p><b>Cliente:</b> Granja Demostración Norte, S.L. (nombre ficticio).</p>
    <p><b>Ubicación:</b> Calle Ejemplo 12, Villaficticia (Zaragoza).</p>
    <p><b>Nave N1:</b> una nave de cebo de 80 m x 14 m, interior en tres zonas de cebo.</p>
    <h2>Apartados. El precio cierra en el apartado, sin precio unitario</h2>
    <table>
      <tr><th>Código</th><th>Capítulo</th><th>Descripción</th><th>Importe EUR</th></tr>
      <tr><td>1.1</td><td>Materiales</td><td>Cubierta a dos aguas de panel sándwich. Color impreso: Gris, tachado. Corrección manuscrita sobre ese valor: Verde.</td><td class="num">86000.00</td></tr>
      <tr><td>1.2</td><td>Materiales</td><td>Aislamiento de cubierta y cerramiento con panel de poliuretano de 40 mm.</td><td class="num">42000.00</td></tr>
      <tr><td>2.1</td><td>Equipamiento</td><td>Alimentación: 4 silos, circuito de cadena y tolvas de cebo.</td><td class="num">120000.00</td></tr>
      <tr><td>2.2</td><td>Equipamiento</td><td>Suelos de slat de polipropileno sobre fosas.</td><td class="num">54000.00</td></tr>
      <tr><td>2.3</td><td>Equipamiento</td><td>Ventilación: ventanas de entrada, chimeneas y reguladores.</td><td class="num">68000.00</td></tr>
      <tr><td>3.1</td><td>Obra e instalaciones</td><td>Estructura metálica de pórticos de acero.</td><td class="num">95000.00</td></tr>
      <tr><td>3.2</td><td>Obra e instalaciones</td><td>Instalación eléctrica de nave, cuadros y alumbrado.</td><td class="num">48000.00</td></tr>
      <tr><td>3.3</td><td>Obra e instalaciones</td><td>Fontanería y bebederos de cazoleta.</td><td class="num">31000.00</td></tr>
    </table>
    <h2>Cierre. Los descuentos no son apartados</h2>
    <p>Suma de apartados 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2 y 3.3: 544000.00 EUR.</p>
    <p>Descuento comercial impreso: 14000.00 EUR. No es un apartado.</p>
    <p><b>Precio total final impreso: 530000.00 EUR.</b></p>
    <p class="aviso">Anotación manuscrita: sobre el total impreso hay un descuento adicional escrito a mano de 10000.00 EUR. Precio total final manuscrito: 520000.00 EUR. Esta corrección obliga a revisión humana.</p>
    <p class="pie">Importes inventados para una demostración. No corresponden a ninguna obra ni a ningún cliente real.</p>
    """
    return _pdf("presupuesto_nave_cebo_demostracion.pdf", html)


def contrato() -> Path:
    html = """
    <p class="marca">EXAFAN, S.A.U. — documento de demostración</p>
    <h1>Contrato de ejecución de instalación eléctrica</h1>
    <p>En Villaficticia (Zaragoza), a 12 de marzo de 2026.</p>
    <p><b>Contratista:</b> EXAFAN, S.A.U., Polígono Industrial Río Gállego, calle D, nº 10, San Mateo de Gállego (Zaragoza).</p>
    <p><b>Empresa instaladora:</b> Instalaciones Demo Volt, S.L. Domicilio: Calle Ficticia 4, Villaficticia. CIF: B00000077. Tipo: externo.</p>
    <p>La persona que firma por la empresa instaladora es Representante Demo, mayor de edad. Nombre ficticio.</p>
    <p><b>Objeto:</b> montaje eléctrico de la nave de cebo de Granja Demostración Norte, S.L., sita en Calle Ejemplo 12, Villaficticia (Zaragoza), según el presupuesto <span class="fijo">PRES-DEMO-2026-014</span>.</p>
    <p><b>Referencia de presupuesto:</b> <span class="fijo">PRES-DEMO-2026-014</span>.</p>
    <p><b>Apartado de presupuesto al que corresponde este contrato:</b> 3.2 Instalación eléctrica.</p>
    <p><b>Precio total cerrado:</b> 61500.00 EUR.</p>
    <p><b>Fecha de firma:</b> <span class="fijo">2026-03-12</span>.</p>
    <p><b>Plazo de ejecución:</b> <span class="fijo">2026-06-30</span>.</p>
    <p><b>Condiciones de facturación:</b> la empresa instaladora entrega la factura dentro de los cinco primeros días del mes. Las facturas, salvo la de liquidación, son pagos a cuenta. EXAFAN paga tras la conformidad de la factura.</p>
    <h2>Desglose de partidas con precio unitario</h2>
    <table>
      <tr><th>Código</th><th>Nivel</th><th>Descripción</th><th>Ud</th><th>Cantidad</th><th>Precio unitario EUR</th><th>Importe EUR</th></tr>
      <tr><td>1</td><td>apartado</td><td>Cuadro general y protecciones</td><td>ud</td><td>1</td><td class="num">8500.00</td><td class="num">8500.00</td></tr>
      <tr><td>2</td><td>apartado</td><td>Derivaciones desde el cuadro general hasta las zonas</td><td>ml</td><td>400</td><td class="num">12.50</td><td class="num">5000.00</td></tr>
      <tr><td>3</td><td>apartado</td><td>Zona de cebo 1</td><td></td><td></td><td></td><td class="num">10500.00</td></tr>
      <tr><td>3.1</td><td>partida</td><td>Subcuadro de zona, montado y conexionado</td><td>ud</td><td>1</td><td class="num">4200.00</td><td class="num">4200.00</td></tr>
      <tr><td>3.2</td><td>partida</td><td>Canalización bajo tubo</td><td>ml</td><td>180</td><td class="num">15.00</td><td class="num">2700.00</td></tr>
      <tr><td>3.3</td><td>partida</td><td>Cableado de fuerza y señal</td><td>ml</td><td>600</td><td class="num">6.00</td><td class="num">3600.00</td></tr>
      <tr><td>4</td><td>apartado</td><td>Zona de cebo 2. Mismas partidas y precios que la zona 1</td><td></td><td></td><td></td><td class="num">10500.00</td></tr>
      <tr><td>4.1</td><td>partida</td><td>Subcuadro de zona, montado y conexionado</td><td>ud</td><td>1</td><td class="num">4200.00</td><td class="num">4200.00</td></tr>
      <tr><td>4.2</td><td>partida</td><td>Canalización bajo tubo</td><td>ml</td><td>180</td><td class="num">15.00</td><td class="num">2700.00</td></tr>
      <tr><td>4.3</td><td>partida</td><td>Cableado de fuerza y señal</td><td>ml</td><td>600</td><td class="num">6.00</td><td class="num">3600.00</td></tr>
      <tr><td>5</td><td>apartado</td><td>Zona de cebo 3. Mismas partidas y precios que la zona 1</td><td></td><td></td><td></td><td class="num">10500.00</td></tr>
      <tr><td>5.1</td><td>partida</td><td>Subcuadro de zona, montado y conexionado</td><td>ud</td><td>1</td><td class="num">4200.00</td><td class="num">4200.00</td></tr>
      <tr><td>5.2</td><td>partida</td><td>Canalización bajo tubo</td><td>ml</td><td>180</td><td class="num">15.00</td><td class="num">2700.00</td></tr>
      <tr><td>5.3</td><td>partida</td><td>Cableado de fuerza y señal</td><td>ml</td><td>600</td><td class="num">6.00</td><td class="num">3600.00</td></tr>
      <tr><td>6</td><td>apartado</td><td>Luminarias LED estancas</td><td>ud</td><td>80</td><td class="num">95.00</td><td class="num">7600.00</td></tr>
      <tr><td>7</td><td>apartado</td><td>Toma de tierra de la nave</td><td>pa</td><td>1</td><td class="num">3400.00</td><td class="num">3400.00</td></tr>
      <tr><td>8</td><td>apartado</td><td>Conexionado de ventilación y alimentación</td><td>pa</td><td>1</td><td class="num">5500.00</td><td class="num">5500.00</td></tr>
    </table>
    <p><b>Suma del desglose y precio total del contrato: 61500.00 EUR.</b></p>
    <p class="pie">El apartado 3.2 del presupuesto vale 48000.00 EUR. Este contrato cierra en 61500.00 EUR: es el desvío que debe verse al enlazarlos. Importes y empresa inventados.</p>
    """
    return _pdf("contrato_electricidad_demostracion.pdf", html)


if __name__ == "__main__":
    print(presupuesto())
    print(contrato())
