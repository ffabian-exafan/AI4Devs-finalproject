# Preguntas y puntos a cerrar — Gestor de presupuestos y facturas de obra

Documento de trabajo para cerrar decisiones antes de diseñar el sistema.

*Versión 2 — 6 de septiembre de 2026. Se marcan con ✅ los puntos que un presupuesto y un contrato reales (anonimizados) ya han resuelto o matizado.*

---

## 1. Presupuestos (entrada del sistema)

- ✅ **Formato (actualizado 15 sept. 2026):** **no solo PDF nativo.** Muchos presupuestos llegan **escaneados** (imagen o PDF sin texto). También hay PDF nativos de plantilla EXAFAN. Escaneado → OCR + `es_escaneado` + revisión humana obligatoria. **[VERIFICAR]** el mix real de extensiones en producción (JPG/PNG/TIFF/PDF).
- ¿Se generan con algún programa de presupuestos de construcción (Presto, Arquímedes, TCQ...) para exportar en BC3/FIEBDC? El ejemplo visto no parece venir de ahí — es una plantilla propia. **[VERIFICAR si es así en general.]**
- ✅ **Estructura:** no es constante "por tarea" — cierra por apartado/sistema constructivo (importe único por apartado). **[VERIFICAR si esto es general o particular de este presupuesto.]**
- ✅ **Campos por apartado:** código de apartado, descripción técnica extensa, importe. No siempre hay cantidad ni precio unitario visibles a ese nivel.
- ✅ **Versiones:** sí existen, con sufijo en el número de presupuesto (ej. "V2"). Hay que gestionar histórico.
- **Nueva pregunta:** ¿el reparto EXAFAN-directo / proveedor-externo es siempre a nivel de apartado completo, o puede mezclarse dentro de un mismo apartado?

## 2. Contratos de ejecución con subcontratistas (documento nuevo, no contemplado antes)

- ✅ Existen como documento aparte del presupuesto y de la factura: fijan precio cerrado, plazo y condiciones de facturación/medición con un subcontratista concreto.
- ✅ Sí pueden bajar a partida con precio unitario (visto: desglose por Sala).
- ¿Todos los subcontratistas firman este tipo de contrato, o solo algunos gremios (ej. electricidad)?
- ¿Hay un contrato por nave, por proyecto completo, o puede cubrir varias naves?
- ¿Cómo se referencia el presupuesto de origen dentro del contrato? Hoy solo hay un número de presupuesto en texto libre — ¿conviene enlazarlo de forma estructurada?

## 3. Responsable de la obra

- ¿El responsable de cada partida es equipo interno o subcontrata externa?
- ✅ Confirmado que ambos casos conviven en el mismo proyecto, con condiciones de pago distintas por bloque.
- ¿Existe un listado maestro de contratistas o hay que darlos de alta sobre la marcha?

## 4. Facturas (la parte más delicada)

- ¿Cómo llegan? PDF nativo, PDF escaneado o imagen.
- **Punto crítico:** las facturas casi nunca citan el código de apartado/partida del presupuesto. ¿Con qué criterio se relaciona una factura con su partida? El enlace fiable que sí tenemos es factura ↔ contratista por NIF.
- **Nueva pregunta, abierta por el contrato de ejemplo:** el contrato exige al subcontratista identificar en la factura mensual las unidades ejecutadas de forma verificable. ¿Se cumple esto en la práctica? Si sí, el desglose por Sala podría sobrevivir hasta la factura real. **No tenemos ninguna factura de ejemplo para confirmarlo — sigue siendo el bloqueante principal de este bloque.**
- ¿Una factura corresponde siempre a una sola partida, o puede cubrir varias, varios proyectos o una partida parcialmente?
- ¿Hay que contemplar anticipos, certificaciones parciales, retenciones de garantía, IVA e IRPF? El contrato de ejemplo confirma que las facturas mensuales (salvo la de liquidación) son pagos a cuenta sobre medición a origen — encaja con el modelo ya previsto.
- Cuando el OCR falle o dude, ¿asumimos una pantalla de revisión donde una persona confirma o corrige antes de guardar? Sí, y ahora aplica también a presupuestos y contratos por el caso de anotaciones manuscritas.

## 5. Origen de los datos

- Drive vs OneDrive/SharePoint: cambia autenticación, permisos y sincronización. Conviene decidirlo pronto.
- ¿Ya tenéis un ERP o programa de contabilidad donde entran las facturas (Sage, A3, Holded...)? Quizá el sistema deba leer de ahí en lugar de duplicar el flujo.

## 6. Tracking y estado

- ¿Qué define el estado de una partida? (no iniciada / en curso / finalizada).
- ¿El estado lo marca una persona o se infiere de las facturas?
- Ojo: el gasto ejecutado no equivale al avance físico de la obra. Conviene separar seguimiento económico de seguimiento de ejecución.
- ¿Qué alertas quieres? (desvío sobre presupuesto, desvío sobre lo contratado, partida sin facturas, sobrecoste...). El caso real de electricidad (presupuestado ≠ contratado) es un buen ejemplo de alerta a incluir.

## 7. Uso y alcance

- ¿Quién usa la app y con qué permisos? (jefe de obra, administración, dirección).
- ¿Cuántos proyectos, naves, partidas, contratos y facturas manejáis al año? El volumen condiciona la arquitectura.
- ¿MVP por fases o sistema completo de golpe? Recomendación: empezar por la ingesta de presupuestos (ya con el modelo de apartado/partida corregido) y validarla antes de atacar contratos y facturas.

---

## Privacidad y datos [SENSIBLE]

- Los presupuestos, contratos y facturas contienen datos personales y financieros (NIF, nombres, cuentas, importes pactados).
- No subir documentos reales sin anonimizar.
- Validar cualquier prueba con datos sensibles con ai.seguridad@exafan.com.
- Ya hay dos ejemplos anonimizados disponibles como fixtures de referencia: `presupuesto_nave_destete_anonimizado.md` y `contrato_subcontrata_electricidad_anonimizado.md`.
