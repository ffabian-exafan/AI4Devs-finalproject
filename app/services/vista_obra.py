"""Arma la vista de las cinco pantallas a partir del cálculo de desviaciones."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.schemas.vista_obra import (
    AccionFacturaOut,
    AlertaOut,
    ApartadoPresupuestoOut,
    ContratoEstadoIn,
    ContratoFilaOut,
    ContratosVistaOut,
    ControlVistaOut,
    EstadoObraIn,
    FacturaFilaOut,
    FilaControlOut,
    KpiOut,
    LineaFacturaOut,
    ObraFilaOut,
    OpcionApartadoOut,
    PartidaControlOut,
    PartidaPresupuestoOut,
    PasoOut,
    PresupuestoVistaOut,
    ProyectoVistaOut,
    VistaObraOut,
)
from app.services.desviaciones import (
    CalculoObra,
    ContratoEntrada,
    FacturaResultado,
    PartidaResultado,
    calcular_obra,
)
from app.services.obra_referencia import (
    APARTADOS,
    FACTURAS,
    IMPORTE_CONTRATO,
    OTRAS_OBRAS,
    PROYECTO,
    contratos_iniciales,
    ficha_contrato,
)

UMBRAL = Decimal("0.50")
MORADO = "#6e2094"
TINTA = "#444242"
ROJO = "#a52a17"


def eur(valor: Decimal, decimales: int = 0) -> str:
    cuantos = Decimal("1") if decimales == 0 else Decimal("0.01")
    redondo = valor.quantize(cuantos, rounding=ROUND_HALF_UP)
    negativo = redondo < 0
    texto = _miles(abs(redondo), decimales)
    signo = "−" if negativo else ""
    return f"{signo}{texto} €"


def num(valor: Decimal, decimales: int = 0) -> str:
    cuantos = Decimal("1") if decimales == 0 else Decimal("0.01")
    redondo = abs(valor).quantize(cuantos, rounding=ROUND_HALF_UP)
    return _miles(redondo, decimales)


def precio(valor: Decimal) -> str:
    return num(valor, 2) + " €"


def _miles(valor: Decimal, decimales: int) -> str:
    bruto = f"{valor:.{decimales}f}"
    entero, _, fraccion = bruto.partition(".")
    grupos = f"{int(entero):,}".replace(",", ".")
    if decimales:
        return f"{grupos},{fraccion}"
    return grupos


def _pct(parte: Decimal, total: Decimal) -> str:
    if total == 0:
        return "0%"
    valor = (parte / total * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{int(valor)}%"


def _ancho(parte: Decimal, escala: Decimal) -> str:
    if escala <= 0:
        return "0%"
    return _pct(parte, escala)


def estado_inicial() -> EstadoObraIn:
    return EstadoObraIn(
        revisados=[True] * len(APARTADOS),
        contratos=[
            ContratoEstadoIn(id=c.id, apartado_idx=c.apartado_idx, asociado=c.asociado)
            for c in contratos_iniciales()
        ],
    )


def construir_vista(estado: EstadoObraIn) -> VistaObraOut:
    contratos = _contratos_desde_estado(estado)
    cuentan = {
        factura_id
        for factura_id, resolucion in estado.resueltas.items()
        if resolucion == "Validada"
    }
    calculo = calcular_obra(APARTADOS, FACTURAS, contratos, cuentan)
    return _presentar(estado, contratos, calculo)


def _contratos_desde_estado(estado: EstadoObraIn) -> list[ContratoEntrada]:
    ids = [c.id for c in estado.contratos]
    if len(ids) != len(set(ids)):
        raise ValueError("Hay contratos repetidos")
    esperados = {c.id for c in contratos_iniciales()}
    if set(ids) != esperados:
        raise ValueError("El estado no trae los contratos de la obra")
    for factura_id in estado.resueltas:
        if factura_id not in {f.id for f in FACTURAS}:
            raise ValueError(f"Factura {factura_id} no existe en la obra")

    salida: list[ContratoEntrada] = []
    for fila in estado.contratos:
        ficha = ficha_contrato(fila.id)
        salida.append(
            ContratoEntrada(
                id=fila.id,
                gremio=ficha["gremio"],
                archivo=ficha["archivo"],
                importe=IMPORTE_CONTRATO[fila.id],
                apartado_idx=fila.apartado_idx,
                confianza=ficha["confianza"],
                motivo=ficha["motivo"],
                aviso=ficha["aviso"],
                asociado=fila.asociado,
            )
        )
    return salida


def _duda(marca: str | None) -> str | None:
    if marca == "Unidad":
        return "Unidad ambigua"
    if marca == "Medición":
        return "Medición dudosa"
    return None


def _diferencia(importe: Decimal, presupuestado: Decimal) -> tuple[str, bool]:
    gap = importe - presupuestado
    if abs(gap) < UMBRAL:
        return "coincide", False
    if gap > 0:
        return "+" + eur(gap) + " sobre presupuesto", True
    return eur(gap) + " bajo presupuesto", False


def _nota_linea(linea) -> str | None:
    trozos: list[str] = []
    if linea.nota_precio is not None:
        extra = Decimal(linea.nota_precio)
        trozos.append(
            f"Precio unitario {precio(linea.precio)} frente a {precio(linea.precio_presupuesto)} "
            f"presupuestado (+{eur(extra, 2)})"
        )
    if linea.nota_medicion is not None:
        extra = Decimal(linea.nota_medicion)
        trozos.append(
            f"Medición acumulada {num(linea.cantidad_acumulada)} {linea.unidad} de "
            f"{num(linea.medicion_presupuesto)} presupuestados (+{eur(extra, 2)})"
        )
    if not trozos:
        return None
    return ". ".join(trozos)


def _acciones(kind: str) -> list[AccionFacturaOut]:
    if kind == "dup":
        return [
            AccionFacturaOut(etiqueta="Descartar duplicado", variante="primary", resolucion="Descartada"),
            AccionFacturaOut(etiqueta="No es duplicado", variante="secondary", resolucion="Validada"),
        ]
    if kind == "bad":
        return [
            AccionFacturaOut(etiqueta="Reclamar al gremio", variante="primary", resolucion="Reclamada"),
            AccionFacturaOut(
                etiqueta="Aprobar desviación",
                variante="secondary",
                resolucion="Desviación aprobada",
            ),
        ]
    return [AccionFacturaOut(etiqueta="Validar factura", variante="primary", resolucion="Validada")]


def _factura_fila(factura: FacturaResultado, resueltas: dict[str, str]) -> FacturaFilaOut:
    resolucion = resueltas.get(factura.id)
    if resolucion:
        estado, tono, diferencia = resolucion, "neutral", ""
    elif factura.kind == "dup":
        estado, tono, diferencia = "Posible duplicado", "warning", ""
    elif factura.kind == "bad":
        estado, tono, diferencia = "Descuadre", "error", "+" + eur(factura.desviacion, 2)
    else:
        estado, tono, diferencia = "Cuadra", "success", ""

    aviso = None
    if factura.kind == "dup" and factura.original_numero:
        aviso = (
            f"Mismo proveedor, número e importe que la factura {factura.original_numero} "
            f"recibida el {factura.original_fecha}. No se ha sumado al acumulado."
        )
    lineas = []
    for linea in factura.lineas:
        nota = _nota_linea(linea)
        lineas.append(
            LineaFacturaOut(
                codigo=linea.codigo,
                descripcion=linea.descripcion,
                importe=eur(linea.importe, 2),
                facturado=f"{num(linea.cantidad)} {linea.unidad} × {precio(linea.precio)}",
                presupuesto=(
                    f"{num(linea.medicion_presupuesto)} {linea.unidad} × {precio(linea.precio_presupuesto)}"
                ),
                acumulado=(
                    f"{num(linea.cantidad_acumulada)} / {num(linea.medicion_presupuesto)} {linea.unidad}"
                ),
                mala=nota is not None,
                nota=nota,
            )
        )
    if factura.kind == "bad":
        desviacion = "+" + eur(factura.desviacion, 2)
        negativa = True
    else:
        desviacion = "0,00 €"
        negativa = False
    return FacturaFilaOut(
        id=factura.id,
        proveedor=factura.proveedor,
        numero=factura.numero,
        fecha=factura.fecha,
        apartado=factura.apartado,
        importe=eur(factura.importe, 2),
        kind=factura.kind,
        estado=estado,
        tono=tono,
        diferencia=diferencia,
        es_duplicado=factura.kind == "dup",
        aviso_duplicado=aviso,
        desviacion=desviacion,
        desviacion_negativa=negativa,
        acciones=_acciones(factura.kind),
        lineas=lineas,
    )


def _alertas(calculo: CalculoObra, contratos: list[ContratoEntrada], resueltas: dict[str, str]) -> list[AlertaOut]:
    por_codigo = {p.codigo: p for ap in calculo.apartados for p in ap.partidas}
    alertas: list[AlertaOut] = []
    for factura in calculo.facturas:
        if factura.id in resueltas:
            continue
        if factura.kind == "dup":
            fechas = " y ".join(
                f.replace("/2026", "") for f in (factura.original_fecha or "", factura.fecha) if f
            )
            alertas.append(
                AlertaOut(
                    id=factura.id,
                    tipo="Posible duplicado",
                    tono="warning",
                    importe=eur(factura.importe),
                    titulo=f"{factura.numero} recibida dos veces",
                    texto=f"{factura.proveedor} · {fechas}. No sumada al acumulado.",
                    destino="facturas",
                    factura_id=factura.id,
                )
            )
            continue
        if factura.kind != "bad":
            continue
        vistos: set[str] = set()
        for linea in factura.lineas:
            if linea.codigo in vistos:
                continue
            partida = por_codigo[linea.codigo]
            if linea.nota_medicion is not None:
                vistos.add(linea.codigo)
                alertas.append(_alerta_medicion(factura, partida))
            elif linea.nota_precio is not None:
                vistos.add(linea.codigo)
                alertas.append(_alerta_precio(factura, partida, linea.precio, linea.unidad))
    for contrato in contratos:
        clave = f"contrato-{contrato.id}"
        if clave in resueltas:
            continue
        apartado = calculo.apartados[contrato.apartado_idx]
        if contrato.importe <= apartado.presupuestado + UMBRAL:
            continue
        gap = contrato.importe - apartado.presupuestado
        alertas.append(
            AlertaOut(
                id=clave,
                tipo="Importe superior",
                tono="warning",
                importe="+" + eur(gap),
                titulo=f"Contrato de {apartado.codigo} · {apartado.nombre}",
                texto=f"{contrato.gremio} contrata por encima de lo presupuestado en el apartado.",
                destino="contratos",
            )
        )
    return alertas


def _alerta_medicion(factura: FacturaResultado, partida: PartidaResultado) -> AlertaOut:
    return AlertaOut(
        id=factura.id,
        tipo="Medición excedida",
        tono="error",
        importe="+" + eur(partida.desviacion),
        titulo=f"{partida.codigo} {partida.descripcion}",
        texto=(
            f"Facturados {num(partida.cantidad_facturada)} {partida.unidad} de "
            f"{num(partida.medicion)} presupuestados. Factura {factura.numero}."
        ),
        destino="facturas",
        factura_id=factura.id,
    )


def _alerta_precio(
    factura: FacturaResultado,
    partida: PartidaResultado,
    precio_facturado: Decimal,
    unidad: str,
) -> AlertaOut:
    return AlertaOut(
        id=factura.id,
        tipo="Importe superior",
        tono="error",
        importe="+" + eur(partida.desviacion),
        titulo=f"{partida.codigo} {partida.descripcion}",
        texto=(
            f"Precio facturado {precio(precio_facturado)}/{unidad} frente a "
            f"{precio(partida.precio)} presupuestado. Factura {factura.numero}."
        ),
        destino="facturas",
        factura_id=factura.id,
    )


def _control(calculo: CalculoObra, contratos: list[ContratoEntrada], resueltas: dict[str, str]) -> ControlVistaOut:
    n_partidas = sum(len(a.partidas) for a in calculo.apartados)
    desvio_txt = eur(calculo.total_desviacion)
    if calculo.total_desviacion > UMBRAL:
        desvio_txt = "+" + desvio_txt
    kpis = [
        KpiOut(
            etiqueta="Presupuestado",
            valor=eur(calculo.total_presupuestado),
            detalle=f"{len(calculo.apartados)} apartados · {n_partidas} partidas",
            color=MORADO,
        ),
        KpiOut(
            etiqueta="Contratado",
            valor=eur(calculo.total_contratado),
            detalle=f"{calculo.apartados_con_contrato} de {len(calculo.apartados)} apartados con contrato",
            color=TINTA,
        ),
        KpiOut(
            etiqueta="Facturado",
            valor=eur(calculo.total_facturado),
            detalle=f"{_pct(calculo.total_facturado, calculo.total_presupuestado)} del presupuesto",
            color=TINTA,
        ),
        KpiOut(
            etiqueta="Desviación detectada",
            valor=desvio_txt,
            detalle=f"En {calculo.partidas_con_desvio} partidas",
            color=ROJO,
        ),
    ]
    filas: list[FilaControlOut] = []
    for apartado in calculo.apartados:
        escala = max(apartado.presupuestado, apartado.contratado, apartado.facturado) * Decimal("1.08")
        if apartado.desviacion > UMBRAL:
            desvio, alerta = "+" + eur(apartado.desviacion), True
        elif apartado.contratado == 0:
            desvio, alerta = "Sin contrato", True
        else:
            desvio, alerta = "—", False
        partidas = []
        for partida in apartado.partidas:
            if partida.desviacion > UMBRAL:
                pdesvio, palerta = "+" + eur(partida.desviacion), True
            else:
                pdesvio, palerta = "—", False
            partidas.append(
                PartidaControlOut(
                    codigo=partida.codigo,
                    descripcion=partida.descripcion,
                    presupuesto=eur(partida.importe_presupuesto),
                    medicion=f"{num(partida.medicion)} {partida.unidad}",
                    facturado=eur(partida.importe_facturado),
                    medicion_facturada=f"{num(partida.cantidad_facturada)} {partida.unidad}",
                    desviacion=pdesvio,
                    alerta=palerta,
                )
            )
        filas.append(
            FilaControlOut(
                codigo=apartado.codigo,
                nombre=apartado.nombre,
                facturado=eur(apartado.facturado),
                presupuestado=eur(apartado.presupuestado),
                ancho_presupuesto=_ancho(apartado.presupuestado, escala),
                ancho_contratado=_ancho(apartado.contratado, escala),
                ancho_facturado=_ancho(apartado.facturado, escala),
                desviacion=desvio,
                alerta=alerta,
                partidas=partidas,
            )
        )
    return ControlVistaOut(kpis=kpis, filas=filas, alertas=_alertas(calculo, contratos, resueltas))


def _presentar(
    estado: EstadoObraIn,
    contratos: list[ContratoEntrada],
    calculo: CalculoObra,
) -> VistaObraOut:
    n = len(calculo.apartados)
    n_rev = sum(1 for marca in estado.revisados if marca)
    n_pend = sum(1 for c in contratos if not c.asociado)
    n_asoc = len(contratos) - n_pend
    incidencias = sum(
        1 for f in calculo.facturas if f.kind != "ok" and f.id not in estado.resueltas
    )
    facturas = [_factura_fila(f, estado.resueltas) for f in calculo.facturas]

    obras = [_obra_principal(calculo, incidencias)]
    descuadres = 1 if incidencias else 0
    for otra in OTRAS_OBRAS:
        if otra["tono"] in {"error", "warning"}:
            descuadres += 1
        pres = Decimal(otra["presupuestado"])
        fac = Decimal(otra["facturado"])
        obras.append(
            ObraFilaOut(
                especie=otra["especie"],
                nombre=otra["nombre"],
                meta=otra["meta"],
                presupuestado=eur(pres) if pres else "Pendiente",
                facturado=eur(fac),
                porcentaje=_pct(fac, pres) if pres else "0%",
                fase=otra["fase"],
                estado=otra["estado"],
                tono=otra["tono"],
                destino=otra["destino"],
            )
        )

    if descuadres == 1:
        cola = "1 con descuadres abiertos"
    else:
        cola = f"{descuadres} con descuadres abiertos"

    opciones = [
        OpcionApartadoOut(valor=str(i), etiqueta=f"{ap.codigo} · {ap.nombre}")
        for i, ap in enumerate(calculo.apartados)
    ]
    cubiertos = {c.apartado_idx for c in contratos if c.asociado}
    descubiertos = [op.etiqueta for i, op in enumerate(opciones) if i not in cubiertos]
    filas_contrato = []
    for contrato in contratos:
        apartado = calculo.apartados[contrato.apartado_idx]
        diferencia, supera = _diferencia(contrato.importe, apartado.presupuestado)
        filas_contrato.append(
            ContratoFilaOut(
                id=contrato.id,
                gremio=contrato.gremio,
                archivo=contrato.archivo,
                importe=eur(contrato.importe),
                apartado_idx=contrato.apartado_idx,
                confianza=contrato.confianza,
                motivo=contrato.motivo,
                aviso=contrato.aviso,
                hay_aviso=bool(contrato.aviso) and not contrato.asociado,
                presupuestado=eur(apartado.presupuestado),
                diferencia=diferencia,
                supera=supera,
                asociado=contrato.asociado,
            )
        )

    apartados_ui = []
    n_dudas = 0
    n_partidas = 0
    for idx, apartado in enumerate(calculo.apartados):
        dudas = 0
        partidas_ui = []
        for partida in apartado.partidas:
            n_partidas += 1
            duda = _duda(partida.marca_duda)
            if duda:
                dudas += 1
                n_dudas += 1
            partidas_ui.append(
                PartidaPresupuestoOut(
                    codigo=partida.codigo,
                    descripcion=partida.descripcion,
                    unidad=partida.unidad,
                    medicion=num(partida.medicion),
                    precio=precio(partida.precio),
                    importe=eur(partida.importe_presupuesto),
                    duda=duda,
                )
            )
        resumen = f"{len(partidas_ui)} partidas"
        if dudas:
            resumen += f" · {dudas} a revisar"
        apartados_ui.append(
            ApartadoPresupuestoOut(
                codigo=apartado.codigo,
                nombre=apartado.nombre,
                importe=eur(apartado.presupuestado),
                resumen=resumen,
                hay_dudas=dudas > 0,
                revisado=estado.revisados[idx],
                partidas=partidas_ui,
            )
        )

    detalle_rev = f"{n_rev} apartados revisados" if n_rev == n else f"{n_rev}/{n} revisados"
    return VistaObraOut(
        estado=estado,
        nav_incidencias=incidencias,
        resumen_obras=f"{len(obras)} obras en curso · {cola}",
        obras=obras,
        proyecto=ProyectoVistaOut(
            codigo=PROYECTO["codigo"],
            nombre=PROYECTO["nombre"],
            subtitulo=(
                f"{PROYECTO['cliente']} · {PROYECTO['ubicacion']} · "
                f"Presupuesto firmado {eur(calculo.total_presupuestado)}"
            ),
        ),
        pasos=[
            PasoOut(id="presupuesto", etiqueta="Presupuesto", detalle=detalle_rev, completo=n_rev == n),
            PasoOut(
                id="contratos",
                etiqueta="Contratos",
                detalle=f"{n_asoc}/{len(contratos)} asociados",
                completo=n_pend == 0,
            ),
            PasoOut(
                id="facturas",
                etiqueta="Facturas",
                detalle=f"{len(facturas)} leídas · {incidencias} incidencias",
                completo=False,
            ),
            PasoOut(
                id="control",
                etiqueta="Control de desviaciones",
                detalle="Por apartado y partida",
                completo=False,
            ),
        ],
        presupuesto=PresupuestoVistaOut(
            revisados=f"{n_rev}/{n}",
            revisados_pct=_pct(Decimal(n_rev), Decimal(n)),
            n_partidas=n_partidas,
            n_dudas=n_dudas,
            total=eur(calculo.total_presupuestado),
            falta_revisar=n_rev < n,
            apartados=apartados_ui,
        ),
        contratos=ContratosVistaOut(
            pendientes=n_pend,
            sin_contrato=", ".join(descubiertos),
            hay_sin_contrato=bool(descubiertos),
            opciones=opciones,
            filas=filas_contrato,
        ),
        facturas=facturas,
        control=_control(calculo, contratos, estado.resueltas),
    )


def _obra_principal(calculo: CalculoObra, incidencias: int) -> ObraFilaOut:
    if incidencias == 1:
        estado, tono = "1 descuadre", "error"
    elif incidencias > 1:
        estado, tono = f"{incidencias} descuadres", "error"
    else:
        estado, tono = "Cuadra", "success"
    return ObraFilaOut(
        especie=PROYECTO["especie"],
        nombre=PROYECTO["nombre"],
        meta="OB-2026-014 · Hnos. Lacasa · Ejea de los Caballeros",
        presupuestado=eur(calculo.total_presupuestado),
        facturado=eur(calculo.total_facturado),
        porcentaje=_pct(calculo.total_facturado, calculo.total_presupuestado),
        fase=PROYECTO["fase"],
        estado=estado,
        tono=tono,
        destino="control",
    )
