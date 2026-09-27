"""Desviación por partida: precio y medición, sin sumar duplicados sin resolver.

Fórmula (handoff):
    (precio_facturado − precio_presupuesto) × cantidad_facturada
    + max(0, cantidad_acumulada − medición_presupuesto) × precio_presupuesto

Si una partida llega en varias facturas con precios distintos, el primer término
se suma línea a línea y el exceso de medición se aplica una sola vez sobre el
acumulado. Un duplicado (mismo proveedor, número e importe) no entra en el
acumulado hasta que alguien lo marca como «No es duplicado».
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

CENTIMO = Decimal("0.01")
UMBRAL = Decimal("0.50")


def desviacion_partida(
    precio_presupuesto: Decimal,
    precio_facturado: Decimal,
    cantidad_facturada: Decimal,
    cantidad_acumulada: Decimal,
    medicion_presupuesto: Decimal,
) -> Decimal:
    """Desviación de una partida con un solo precio facturado."""
    exceso = cantidad_acumulada - medicion_presupuesto
    if exceso < 0:
        exceso = Decimal(0)
    bruto = (precio_facturado - precio_presupuesto) * cantidad_facturada + exceso * precio_presupuesto
    return bruto.quantize(CENTIMO, rounding=ROUND_HALF_UP)


def _dinero(valor: Decimal) -> Decimal:
    return valor.quantize(CENTIMO, rounding=ROUND_HALF_UP)


@dataclass
class PartidaBase:
    codigo: str
    descripcion: str
    unidad: str
    medicion: Decimal
    precio: Decimal
    marca_duda: str | None = None


@dataclass
class ApartadoBase:
    codigo: str
    nombre: str
    partidas: list[PartidaBase]


@dataclass
class LineaEntrada:
    codigo_partida: str
    cantidad: Decimal
    precio: Decimal


@dataclass
class FacturaEntrada:
    id: str
    numero: str
    proveedor: str
    fecha: str
    fecha_orden: str
    apartado_idx: int
    lineas: list[LineaEntrada]


@dataclass
class ContratoEntrada:
    id: int
    gremio: str
    archivo: str
    importe: Decimal
    apartado_idx: int
    confianza: int
    motivo: str
    aviso: str | None
    asociado: bool


@dataclass
class PartidaResultado:
    codigo: str
    descripcion: str
    unidad: str
    medicion: Decimal
    precio: Decimal
    marca_duda: str | None
    importe_presupuesto: Decimal
    cantidad_facturada: Decimal
    importe_facturado: Decimal
    delta_precio: Decimal
    exceso_medicion: Decimal
    desviacion: Decimal


@dataclass
class ApartadoResultado:
    codigo: str
    nombre: str
    presupuestado: Decimal
    contratado: Decimal
    facturado: Decimal
    desviacion: Decimal
    partidas: list[PartidaResultado]


@dataclass
class LineaResultado:
    codigo: str
    descripcion: str
    unidad: str
    cantidad: Decimal
    precio: Decimal
    medicion_presupuesto: Decimal
    precio_presupuesto: Decimal
    cantidad_acumulada: Decimal
    importe: Decimal
    nota_precio: Decimal | None
    nota_medicion: Decimal | None


@dataclass
class FacturaResultado:
    id: str
    numero: str
    proveedor: str
    fecha: str
    apartado_idx: int
    apartado: str
    importe: Decimal
    desviacion: Decimal
    kind: str
    es_duplicado: bool
    original_numero: str | None
    original_fecha: str | None
    lineas: list[LineaResultado] = field(default_factory=list)


@dataclass
class CalculoObra:
    apartados: list[ApartadoResultado]
    facturas: list[FacturaResultado]
    total_presupuestado: Decimal
    total_contratado: Decimal
    total_facturado: Decimal
    total_desviacion: Decimal
    partidas_con_desvio: int
    apartados_con_contrato: int


def _importe_linea(cantidad: Decimal, precio: Decimal) -> Decimal:
    return _dinero(cantidad * precio)


def _clave_duplicado(factura: FacturaEntrada) -> tuple[str, str, Decimal]:
    importe = sum((_importe_linea(ln.cantidad, ln.precio) for ln in factura.lineas), Decimal(0))
    return (factura.proveedor, factura.numero, _dinero(importe))


def calcular_obra(
    apartados: list[ApartadoBase],
    facturas: list[FacturaEntrada],
    contratos: list[ContratoEntrada],
    duplicados_que_cuentan: set[str] | None = None,
) -> CalculoObra:
    """Acumula facturas en orden de fecha. `duplicados_que_cuentan` son ids validados."""
    if duplicados_que_cuentan is None:
        duplicados_que_cuentan = set()

    partidas: dict[str, PartidaBase] = {}
    for apartado in apartados:
        for partida in apartado.partidas:
            partidas[partida.codigo] = partida

    ordenadas = sorted(facturas, key=lambda f: (f.fecha_orden, f.id))
    vistos: dict[tuple[str, str, Decimal], FacturaEntrada] = {}
    es_duplicado: dict[str, FacturaEntrada | None] = {}
    for factura in ordenadas:
        clave = _clave_duplicado(factura)
        previa = vistos.get(clave)
        if previa is None:
            vistos[clave] = factura
            es_duplicado[factura.id] = None
        else:
            es_duplicado[factura.id] = previa

    def cuenta(factura: FacturaEntrada) -> bool:
        original = es_duplicado[factura.id]
        if original is None:
            return True
        return factura.id in duplicados_que_cuentan

    cantidad_acum: dict[str, Decimal] = {c: Decimal(0) for c in partidas}
    importe_acum: dict[str, Decimal] = {c: Decimal(0) for c in partidas}
    delta_precio: dict[str, Decimal] = {c: Decimal(0) for c in partidas}
    diff_factura: dict[str, Decimal] = {}

    for factura in ordenadas:
        if not cuenta(factura):
            diff_factura[factura.id] = Decimal(0)
            continue
        diff = Decimal(0)
        for linea in factura.lineas:
            base = partidas[linea.codigo_partida]
            delta = (linea.precio - base.precio) * linea.cantidad
            antes = cantidad_acum[linea.codigo_partida]
            despues = antes + linea.cantidad
            exceso_antes = max(Decimal(0), antes - base.medicion) * base.precio
            exceso_despues = max(Decimal(0), despues - base.medicion) * base.precio
            delta_med = exceso_despues - exceso_antes
            cantidad_acum[linea.codigo_partida] = despues
            importe_acum[linea.codigo_partida] += _importe_linea(linea.cantidad, linea.precio)
            delta_precio[linea.codigo_partida] += delta
            diff += delta + delta_med
        diff_factura[factura.id] = _dinero(diff)

    apartados_out: list[ApartadoResultado] = []
    contratado_por_idx = [Decimal(0) for _ in apartados]
    for contrato in contratos:
        contratado_por_idx[contrato.apartado_idx] += contrato.importe

    con_contrato = sum(1 for importe in contratado_por_idx if importe > 0)

    for idx, apartado in enumerate(apartados):
        partidas_out: list[PartidaResultado] = []
        presupuestado = Decimal(0)
        facturado = Decimal(0)
        desviacion = Decimal(0)
        for partida in apartado.partidas:
            importe_pres = _importe_linea(partida.medicion, partida.precio)
            acum = cantidad_acum[partida.codigo]
            exceso_qty = max(Decimal(0), acum - partida.medicion)
            exceso = _dinero(exceso_qty * partida.precio)
            delta = _dinero(delta_precio[partida.codigo])
            desv = _dinero(delta + exceso)
            partidas_out.append(
                PartidaResultado(
                    codigo=partida.codigo,
                    descripcion=partida.descripcion,
                    unidad=partida.unidad,
                    medicion=partida.medicion,
                    precio=partida.precio,
                    marca_duda=partida.marca_duda,
                    importe_presupuesto=importe_pres,
                    cantidad_facturada=acum,
                    importe_facturado=_dinero(importe_acum[partida.codigo]),
                    delta_precio=delta,
                    exceso_medicion=exceso,
                    desviacion=desv,
                )
            )
            presupuestado += importe_pres
            facturado += _dinero(importe_acum[partida.codigo])
            desviacion += desv
        apartados_out.append(
            ApartadoResultado(
                codigo=apartado.codigo,
                nombre=apartado.nombre,
                presupuestado=_dinero(presupuestado),
                contratado=_dinero(contratado_por_idx[idx]),
                facturado=_dinero(facturado),
                desviacion=_dinero(desviacion),
                partidas=partidas_out,
            )
        )

    por_codigo = {p.codigo: p for ap in apartados_out for p in ap.partidas}
    facturas_out: list[FacturaResultado] = []
    for factura in facturas:
        original = es_duplicado[factura.id]
        importe = _dinero(sum((_importe_linea(ln.cantidad, ln.precio) for ln in factura.lineas), Decimal(0)))
        desv = diff_factura[factura.id]
        if original is not None and factura.id not in duplicados_que_cuentan:
            kind = "dup"
        elif desv > UMBRAL:
            kind = "bad"
        else:
            kind = "ok"
        lineas_out: list[LineaResultado] = []
        for linea in factura.lineas:
            base = partidas[linea.codigo_partida]
            res = por_codigo[linea.codigo_partida]
            nota_precio = None
            nota_medicion = None
            if kind != "dup" and linea.precio > base.precio + Decimal("0.001"):
                extra = _dinero((linea.precio - base.precio) * linea.cantidad)
                nota_precio = extra
            if kind != "dup" and res.exceso_medicion > UMBRAL:
                nota_medicion = res.exceso_medicion
            lineas_out.append(
                LineaResultado(
                    codigo=linea.codigo_partida,
                    descripcion=base.descripcion,
                    unidad=base.unidad,
                    cantidad=linea.cantidad,
                    precio=linea.precio,
                    medicion_presupuesto=base.medicion,
                    precio_presupuesto=base.precio,
                    cantidad_acumulada=res.cantidad_facturada,
                    importe=_importe_linea(linea.cantidad, linea.precio),
                    nota_precio=nota_precio,
                    nota_medicion=nota_medicion,
                )
            )
        etiqueta = f"{apartados[factura.apartado_idx].codigo} · {apartados[factura.apartado_idx].nombre}"
        facturas_out.append(
            FacturaResultado(
                id=factura.id,
                numero=factura.numero,
                proveedor=factura.proveedor,
                fecha=factura.fecha,
                apartado_idx=factura.apartado_idx,
                apartado=etiqueta,
                importe=importe,
                desviacion=desv,
                kind=kind,
                es_duplicado=original is not None,
                original_numero=original.numero if original else None,
                original_fecha=original.fecha if original else None,
                lineas=lineas_out,
            )
        )

    total_pres = _dinero(sum((a.presupuestado for a in apartados_out), Decimal(0)))
    total_contr = _dinero(sum((c.importe for c in contratos), Decimal(0)))
    total_fac = _dinero(sum((a.facturado for a in apartados_out), Decimal(0)))
    total_desv = _dinero(sum((a.desviacion for a in apartados_out), Decimal(0)))
    n_desvio = sum(1 for ap in apartados_out for p in ap.partidas if p.desviacion > UMBRAL)

    return CalculoObra(
        apartados=apartados_out,
        facturas=facturas_out,
        total_presupuestado=total_pres,
        total_contratado=total_contr,
        total_facturado=total_fac,
        total_desviacion=total_desv,
        partidas_con_desvio=n_desvio,
        apartados_con_contrato=con_contrato,
    )
