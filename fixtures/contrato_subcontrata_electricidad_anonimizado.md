# Contrato de ejecución de obra o instalación por subcontratista — Ejemplo anonimizado

Resumen: contrato de montaje eléctrico entre EXAFAN S.A.U. y una subcontrata eléctrica para una nave de destete, con desglose de partidas por sala; nombres, CIF y todos los importes anonimizados.

**Anonimización aplicada:**
- Personas físicas → `REPRESENTANTE_EXAFAN_1`, `REPRESENTANTE_SUBCONTRATISTA_1`
- Empresa subcontratista → `SUBCONTRATISTA_1`
- Cliente final de la obra → `CLIENTE_1`
- CIF/NIF de ambas empresas → `[CIF_EXAFAN]`, `[CIF_SUBCONTRATISTA_1]`
- Dirección de la subcontrata → `[DIRECCION_SUBCONTRATISTA_1]`
- Ubicación de la explotación del cliente → `[UBICACION_EXPLOTACION_1]`
- Nº de presupuesto de referencia → `[REF_PRESUPUESTO_1]`
- Todos los precios e importes → `[IMPORTE_X]`

EXAFAN S.A.U. se mantiene sin anonimizar por ser la propia empresa (convención del proyecto), igual que su dirección y contacto públicos de sede. Descripciones técnicas, unidades y cantidades se mantienen tal cual figuran en el original firmado: no son datos identificativos.

Este documento es una reconstrucción de referencia para el diseño del extractor de contratos/presupuestos. El original firmado real no debe subirse ni compartirse sin pasar antes por ai.seguridad@exafan.com.

---

## Cabecera

En SAN MATEO DE GALLEGO (ZARAGOZA) a 01 de junio de 2026.

**Reunidos:**

D. REPRESENTANTE_EXAFAN_1, mayor de edad, perteneciente a la empresa EXAFAN S.A.U., ubicada en Polígono Industrial Río Gállego, calle D, nº 10, 50840 San Mateo de Gállego (Zaragoza). CIF: [CIF_EXAFAN].

D. REPRESENTANTE_SUBCONTRATISTA_1, mayor de edad, en nombre y representación de la sociedad SUBCONTRATISTA_1, con domicilio a estos efectos en [DIRECCION_SUBCONTRATISTA_1]. CIF: [CIF_SUBCONTRATISTA_1].

El primero actúa como **Contratista** (en representación de EXAFAN S.A.U.); el segundo, como **Subcontratista**.

**Manifiestan:** que al Contratista se le ha adjudicado el montaje eléctrico de la obra de CLIENTE_1, sita en el término municipal de [UBICACION_EXPLOTACION_1]. Objeto del contrato: ejecución del montaje eléctrico según presupuesto [REF_PRESUPUESTO_1].

## Desglose de partidas (Anexo 1 — presupuesto de electricidad)

> Estructura de cada partida: Unidad, Descripción, Cantidad (parcial), Precio unitario, Importe. Precio e Importe anonimizados; descripciones y cantidades tal cual el original.

| Nº | Descripción | Cantidad | Precio | Importe |
|---|---|---|---|---|
| 1 | Modificación de cuadro eléctrico: modificación cuadro general existente (3 interruptores magnetotérmico 4x40A, 1 interruptor magnetotérmico 4x25A, 4 interruptores diferencial 4x40A/300mA) | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 2 | Derivaciones subcuadros: ML cable unipolar de cobre 1x6mm² 750V, colocado bajo tubo | 250 | [IMPORTE_X] | [IMPORTE_X] |

*Notas del original: se considera acometida a cada subcuadro de sala de 10 m (si es mayor, se factura la distancia real); pendiente de valorar la canalización entre caseta de manejo y ubicación de armarios de cada sala.*

**3. Circuitos sistema Exofeed (silos)**

| Subapartado | Descripción | Cantidad | Precio | Importe |
|---|---|---|---|---|
| 3.1 Fuerza | ML cable unipolar cobre 1x1,5mm² | 280 | [IMPORTE_X] | [IMPORTE_X] |
| 3.1 Fuerza | ML tubo abocardado Tuperplas gris D=20, colocado grapeado | 70 | [IMPORTE_X] | [IMPORTE_X] |
| 3.2 Maniobra | ML cable unipolar cobre 1x1,5mm² | 180 | [IMPORTE_X] | [IMPORTE_X] |
| 3.2 Maniobra | ML tubo abocardado D=20, grapeado | 60 | [IMPORTE_X] | [IMPORTE_X] |
| 3.3 Conexionado | UD colocación y conexionado cuadro control Exafeed | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 3.3 Conexionado | UD colocación y conexionado Exafeed central | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 3.3 Conexionado | UD conexionado motor silo | 6 | [IMPORTE_X] | [IMPORTE_X] |
| 3.3 Conexionado | UD conexionado capacitivo silo | 6 | [IMPORTE_X] | [IMPORTE_X] |
| 3.3 Conexionado | UD conexionado máquina arrastre reparto | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 3.4 Toma de tierra | ML cable desnudo 1x35mm² colocado en zanja | 15 | [IMPORTE_X] | [IMPORTE_X] |
| 3.4 Toma de tierra | UD pica de acero cobreada 2m, clavada verticalmente en zanja red de tierra | 3 | [IMPORTE_X] | [IMPORTE_X] |
| 3.4 Toma de tierra | UD caja de tierras Quintela PCT-C, colocada | 1 | [IMPORTE_X] | [IMPORTE_X] |

**4. Sala 1** *(Sala 2 y Sala 3 repiten exactamente esta misma estructura y descripciones — no se duplican aquí; solo cambia el importe total anonimizado de cada sala)*

| Subapartado | Descripción | Cantidad | Precio | Importe |
|---|---|---|---|---|
| 4.1 Subcuadro sala | UD subcuadro sala ABB (1 interruptor general automático 4x40A, 2 diferenciales 4x40A/300mA, 1 magnetotérmico 4x32A cuadro fuerza, 1 magnetotérmico 4x16A cuadro Exafeed sala, 3 diferenciales 2x40A/30mA, 8 magnetotérmicos 2x10A), totalmente montado y conexionado | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.2 Canalizaciones | ML tubo abocardado D=25, colocado grapeado | 60 | [IMPORTE_X] | [IMPORTE_X] |
| 4.2 Canalizaciones | ML tubo abocardado D=25, colocado embridado a la sirga del sistema de alimentación | 177 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.1 Máquinas arrastre — Fuerza | ML cable 1x1,5mm² bajo tubo | 72 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.1 Máquinas arrastre — Señal | ML cable 1x1,5mm² bajo tubo | 144 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.2 Balaitus (ventanas) — Fuerza | ML cable 1x1,5mm² bajo tubo | 390 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.2 Balaitus (ventanas) — Señal | ML cable 1x1,5mm² bajo tubo | 260 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.3 Balaitus (chimenea) — Fuerza | ML cable 1x1,5mm² bajo tubo | 195 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.3 Balaitus (chimenea) — Señal | ML cable 1x1,5mm² bajo tubo | 130 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.4 Ventiladores EC-63 — Fuerza | ML cable 1x1,5mm² bajo tubo | 540 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.4 Ventiladores EC-63 — Señal | ML cable 1x2,5mm² bajo tubo | 360 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.4 Ventiladores EC-63 — Señal | ML cable 1x1,5mm² bajo tubo | 720 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.5 Iluminación interior | ML cable 1x1,5mm² bajo tubo | 420 | [IMPORTE_X] | [IMPORTE_X] |
| 4.3.6 Sondas | ML cable 1x1,5mm² bajo tubo | 360 | [IMPORTE_X] | [IMPORTE_X] |
| 4.4 Receptores | UD pantalla LED estanca 1200mm Atmoss 16W, lámpara incluida, colocada | 19 | [IMPORTE_X] | [IMPORTE_X] |
| 4.4 Receptores | UD cuadro de fuerza trifásico (1 toma corriente trifásica 3P+T 32A, 1 toma corriente monofásico 16A), montado y conexionado | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.4 Receptores | UD proyector LED estanco 50W Atmoss, colocado | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.4 Receptores | Tasa RAEE | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.5 Mecanismos | UD punto de luz conmutador Bticino Luna blanco alpino, colocado | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado máquina arrastre sala | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado cuadro Exafeed sala | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado Exafeed sala | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado paleta control sala cargada | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado capacitivo control entrada pienso sala | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionada capacitiva control central sala | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado ventilador EC-63 con válvula de regulación de caudal | 3 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado motor Balaitus ventanas | 2 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado motor Balaitus chimenea | 1 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado sonda temperatura | 2 | [IMPORTE_X] | [IMPORTE_X] |
| 4.6 Conexiones | UD conexionado sonda DOL 139 humedad-CO2 | 1 | [IMPORTE_X] | [IMPORTE_X] |

**5. Sala 2** — mismo desglose que Sala 1 (subcuadro, canalizaciones, máquinas arrastre, Balaitus ventanas/chimenea, ventiladores EC-63, iluminación, sondas, receptores, mecanismos, conexiones); mismas cantidades; importe anonimizado.

**6. Sala 3** — idéntico desglose de nuevo; mismas cantidades; importe anonimizado.

**Partida adicional (última fila de la tabla):** sobrecosto para poder realizar la instalación eléctrica por el exterior de la nave | 1 | [IMPORTE_X] | [IMPORTE_X]

**Total montaje de electricidad: [IMPORTE_TOTAL_CONTRATO]**

**Plazo de ejecución:** hasta el 15 de julio de 2026 (salvo fuerza mayor).

## Pactos (cláusulas contractuales — texto general, sin datos identificativos)

1. **Objeto:** ejecución de los trabajos según presupuesto anexo firmado por las partes.
2. **Precio:** fijo, sin modificación por fluctuación de precios o salarios; incluye materiales, maquinaria, mano de obra, proyectos, permisos y visados.
3. **Subcontratación:** el Subcontratista no puede subcontratar sin autorización escrita previa del Contratista; responde solidariamente si lo hace.
4. **Plazo de ejecución:** incumplimiento grave permite al Contratista resolver y contratar a un tercero con cargo al Subcontratista.
5. **Penalizaciones:** 1% del importe fijado por día natural de retraso, deducido de la primera factura posterior.
6. **Precios de obra no contratada:** no se admiten trabajos por administración.
7. **Mediciones de obra:** medición a origen mensual (primeros 5 días de cada mes y al final), sin acopios, sometida a aprobación del Jefe de Obra.
8. **Facturación:** el Subcontratista entrega factura original y copia dentro de los primeros 5 días del mes, con datos que permitan verificar la obra realizada sin desplazarse — identificación y localización de las unidades ejecutadas. Las facturas (salvo la de liquidación) son pagos a cuenta.
9. **Pagos:** el Contratista paga tras conformidad total de la factura.
10. **Garantías:** el Subcontratista garantiza la perfecta ejecución y cumplimiento de plazos.
11. **Perjuicios a terceros:** a cargo del Subcontratista por mala ejecución o materiales de inferior calidad.
12–13. **Trabajos mal ejecutados / garantías de materiales:** corrección a cargo del Subcontratista; debe aportar certificados de garantía de materiales y fabricantes.
14. **Recepción provisional/definitiva:** acta conjunta a los 3 días de finalización comunicada; subsanación de deficiencias en máximo 3 días.
15. **Plazo de garantía:** 7 días desde recepción provisional hasta la definitiva.
16. **Mediciones de las obras:** el Contratista puede comprobar calidad y funcionamiento; coste de comprobación a cargo del Subcontratista si hay irregularidades.
17. **Recepción definitiva:** firman Contratista, Subcontratista y Director de Obra.
18. **Obligaciones laborales:** cumplimiento de legislación laboral; el Subcontratista debe acreditar estar al corriente de pago de seguros sociales.
19. **Seguridad y salud:** cumplimiento del Plan de Seguridad y Salud de la obra; designación de recursos preventivos.
21. **Personal incompetente:** el Contratista puede exigir retirar personal que comprometa seguridad, calidad o ritmo de obra.
22. **Resolución del contrato:** causas tasadas (quiebra, embargo, disolución, incumplimiento de plazos, deficiencias graves, impago de certificación, suspensión administrativa, etc.).
23. **Responsabilidad futura:** el Subcontratista queda relevado tras recepción de conformidad, salvo responsabilidad del art. 1591 CC y la LOE.
24. **Paralización de las obras:** el contrato queda en suspenso; si excede 3 meses, se liquida.
25. **Pago saldo definitivo:** el Subcontratista firma finiquito acreditando ausencia de deudas de materiales, mano de obra, impuestos y seguros.
26. **Certificado de estar al corriente de obligaciones tributarias:** exigido al Subcontratista (art. 43.1.f Ley General Tributaria); renovación cada 12 meses.
27. **Libro de subcontratación:** el Subcontratista debe comunicar los datos necesarios.
28. **Régimen jurídico:** legislación española y de la UE; sumisión a los Juzgados y Tribunales de Zaragoza, con cláusula de arbitraje previo.

---

*Documento de trabajo interno — reconstrucción anonimizada de un contrato real firmado, con fines de referencia para el diseño del extractor de presupuestos/contratos.*
