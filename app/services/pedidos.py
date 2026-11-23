"""Alta de una obra desde pedidos de compra de serie 1."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Contrato, Nave, Pedido, Presupuesto, Proyecto, Tarea, Usuario
from app.schemas.pedido import ImportarPedidosOut, LineaPedidoOut, NavePedidoOut
from app.services import almacen as almacen_svc
from app.services.pedido_compra import LecturaPedido, leer_pedido
from app.services.registro import registrar

_AVISO_SIN_LINEAS = "El pedido no trae líneas de montaje ni de instalación"


def importar_pedidos(
    db: Session,
    nombre: str,
    ficheros: list[tuple[str, bytes]],
) -> ImportarPedidosOut:
    """Crea la obra. Cada PDF que cuadra es una nave."""
    nombre_obra = (nombre or "").strip()
    if not nombre_obra:
        raise ValueError("Falta el nombre de la obra")
    if not ficheros:
        raise ValueError("Falta el fichero")
    preparados = _preparar_lote(db, ficheros)
    almacen_svc.exigir_lote_distinto(ficheros)

    proyecto = Proyecto(
        nombre=nombre_obra[:255],
        tipo="llave_en_mano",
        estado="pendiente_revision",
        fase="Pedido",
    )
    db.add(proyecto)
    db.flush()
    naves = [
        _guardar(db, proyecto, nombre_f, contenido, lectura)
        for nombre_f, contenido, lectura in preparados
    ]
    db.commit()
    return ImportarPedidosOut(proyecto_id=proyecto.id, naves=naves)


def anadir_pedido(
    db: Session,
    proyecto_id: int,
    nombre_fichero: str,
    contenido: bytes,
) -> ImportarPedidosOut:
    """Añade otro pedido a una obra que no nació del Excel."""
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    excel = (
        db.query(Presupuesto)
        .filter(
            Presupuesto.proyecto_id == proyecto.id,
            Presupuesto.formato == "excel_expertis",
        )
        .first()
    )
    if excel is not None:
        raise ValueError("Esta obra nace del Excel")
    preparados = _preparar_lote(db, [(nombre_fichero, contenido)])
    rutas = [
        fila.ruta_almacen
        for fila in db.query(Pedido).filter(Pedido.proyecto_id == proyecto.id).all()
    ]
    almacen_svc.exigir_distinto(contenido, nombre_fichero, rutas)
    nombre_f, contenido, lectura = preparados[0]
    nave = _guardar(db, proyecto, nombre_f, contenido, lectura)
    proyecto.estado = "pendiente_revision"
    db.commit()
    return ImportarPedidosOut(proyecto_id=proyecto.id, naves=[nave])


def _preparar_lote(
    db: Session,
    ficheros: list[tuple[str, bytes]],
) -> list[tuple[str, bytes, LecturaPedido]]:
    preparados: list[tuple[str, bytes, LecturaPedido]] = []
    numeros: list[str] = []
    for nombre_f, contenido in ficheros:
        lectura = leer_pedido(contenido)
        if not lectura.cuadra or lectura.numero is None:
            raise ValueError(lectura.aviso or "El pedido no trae la plantilla de Exafan")
        if lectura.numero in numeros:
            raise ValueError(f"El pedido {lectura.numero} ya está en una obra")
        existente = db.query(Pedido).filter(Pedido.numero == lectura.numero).first()
        if existente is not None:
            raise ValueError(f"El pedido {lectura.numero} ya está en una obra")
        numeros.append(lectura.numero)
        preparados.append((nombre_f, contenido, lectura))
    return preparados


def _guardar(
    db: Session,
    proyecto: Proyecto,
    nombre_fichero: str,
    contenido: bytes,
    lectura: LecturaPedido,
) -> NavePedidoOut:
    nave = Nave(
        proyecto_id=proyecto.id,
        codigo=lectura.numero or "",
        descripcion=(lectura.rotulo or lectura.numero or "")[:255],
        importe_presupuestado=sum((linea.importe for linea in lectura.lineas), Decimal("0")),
    )
    db.add(nave)
    db.flush()
    pedido = Pedido(
        proyecto_id=proyecto.id,
        nave_id=nave.id,
        numero=lectura.numero or "",
        rotulo=lectura.rotulo,
        fichero_origen=nombre_fichero[:512],
        estado_revision="pendiente",
        aviso=None if lectura.lineas else _AVISO_SIN_LINEAS,
    )
    db.add(pedido)
    db.flush()
    pedido.ruta_almacen = almacen_svc.guardar(
        proyecto.id,
        "pedido",
        pedido.id,
        nombre_fichero,
        contenido,
    )
    lineas: list[LineaPedidoOut] = []
    for linea in lectura.lineas:
        tarea = Tarea(
            nave_id=nave.id,
            pedido_id=pedido.id,
            presupuesto_id=None,
            contrato_id=None,
            codigo=linea.codigo[:50],
            nivel="apartado",
            descripcion=linea.descripcion,
            cantidad=linea.cantidad,
            precio_unitario=linea.precio_unitario,
            descuento_pct=linea.descuento_pct,
            importe_presupuestado=linea.importe,
            es_montaje=True,
            solo_gestion=False,
            tiene_anotacion_manual=False,
            estado_revision="pendiente",
            estado="no_iniciada",
            avance_fisico_pct=Decimal("0"),
        )
        db.add(tarea)
        db.flush()
        lineas.append(
            LineaPedidoOut(
                tarea_id=tarea.id,
                codigo=tarea.codigo,
                descripcion=tarea.descripcion,
                importe=tarea.importe_presupuestado,
                estado_revision=tarea.estado_revision,
            )
        )
    return NavePedidoOut(
        pedido_id=pedido.id,
        nave_id=nave.id,
        numero=pedido.numero,
        rotulo=pedido.rotulo,
        aviso=pedido.aviso,
        estado_revision=pedido.estado_revision,
        lineas=lineas,
    )


def confirmar_pedido(db: Session, proyecto_id: int, pedido_id: int, usuario: Usuario) -> Pedido:
    """Pasa el pedido y sus líneas a confirmada. La obra sigue si queda algo pendiente."""
    pedido = db.get(Pedido, pedido_id)
    if pedido is None or pedido.proyecto_id != proyecto_id:
        raise ValueError(f"Pedido {pedido_id} no encontrado")
    pedido.estado_revision = "confirmada"
    for tarea in db.query(Tarea).filter(Tarea.pedido_id == pedido.id).all():
        tarea.estado_revision = "confirmada"
    db.flush()
    pendientes = (
        db.query(Pedido)
        .filter(Pedido.proyecto_id == proyecto_id, Pedido.estado_revision == "pendiente")
        .count()
    )
    otros_presupuestos = (
        db.query(Presupuesto)
        .filter(
            Presupuesto.proyecto_id == proyecto_id,
            Presupuesto.estado_extraccion == "pendiente_revision",
        )
        .count()
    )
    otros_contratos = (
        db.query(Contrato)
        .filter(
            Contrato.proyecto_id == proyecto_id,
            Contrato.estado_extraccion == "pendiente_revision",
        )
        .count()
    )
    proyecto = db.get(Proyecto, proyecto_id)
    if (
        proyecto is not None
        and pendientes == 0
        and otros_presupuestos == 0
        and otros_contratos == 0
    ):
        proyecto.estado = "en_curso"
    registrar(db, usuario, "confirmar_pedido", "pedido", pedido.id, pedido.numero)
    db.commit()
    db.refresh(pedido)
    return pedido
