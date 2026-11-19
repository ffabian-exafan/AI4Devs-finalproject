"""Ingesta, casado y revisión humana de facturas."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Asignacion,
    Contratista,
    Contrato,
    Factura,
    LineaFactura,
    Proyecto,
    Tarea,
    Usuario,
)
from app.services.codigo_contrato import (
    AVISO_SIN_CODIGO_FACTURA,
    AVISO_VARIOS,
    aviso_otra_obra,
    aviso_sin_contrato,
    codigos_en_texto,
)
from app.services.registro import ZONA, registrar
from app.services.sello_factura import DatosSello, lineas_sello, pdf_con_sello
from app.services.sujeto_pasivo import AVISO_ISP, aviso_de
from app.schemas.factura import (
    ConfirmarFacturaIn,
    ConfirmarFacturaOut,
    ContratoCandidatoFacturaOut,
    EnlazarContratoFacturaIn,
    FacturaImportacionOut,
    FacturaRevisionOut,
    FacturaResumenOut,
    LineaFacturaCreate,
)
from app.services import almacen as almacen_svc
from app.services import ocr

_NIF_RE = re.compile(r"\b(?:[A-Z]\d{7}[A-Z0-9]|\d{8}[A-Z])\b", re.IGNORECASE)
_NUMERO_ETIQUETA_RE = re.compile(
    r"^(?:n[úu]mero(?:\s+de\s+factura)?|factura(?:\s+n[.º°o]*)?)\s*[:#-]\s*(.*)$",
    re.IGNORECASE,
)
_IMPORTE_SUELTO_RE = re.compile(
    r"^[€$]?\s*-?[\d.]+(?:,\d+)?\s*(?:€|eur)?$",
    re.IGNORECASE,
)


def importar_factura(
    db: Session,
    proyecto_id: int,
    contenido: bytes,
    nombre_fichero: str,
) -> FacturaImportacionOut:
    proyecto = db.get(Proyecto, proyecto_id)
    if proyecto is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    rutas = [
        fila.ruta_almacen
        for fila in db.query(Factura).filter(Factura.proyecto_id == proyecto.id).all()
    ]
    almacen_svc.exigir_distinto(contenido, nombre_fichero, rutas)

    texto, es_escaneada = _extraer_texto(contenido, nombre_fichero)
    datos = _parsear_factura(texto)

    contratista = _contratista_por_nif(db, datos["contratista_nif"])
    if contratista is None:
        raise ValueError(
            f"No existe un contratista con NIF {datos['contratista_nif']}"
        )

    codigo, aviso, contrato_por_codigo = _codigo_de_factura(
        db, proyecto_id, contratista.id, texto
    )
    if contrato_por_codigo is not None:
        contrato_sugerido = contrato_por_codigo
    elif codigo is None:
        contratos = _contratos_candidatos(db, proyecto_id, contratista.id)
        contrato_sugerido = contratos[0] if len(contratos) == 1 else None
    else:
        contrato_sugerido = None

    factura = Factura(
        proyecto_id=proyecto_id,
        contratista_id=contratista.id,
        codigo_contrato=codigo,
        aviso_codigo=aviso,
        contrato_id=contrato_sugerido.id if contrato_sugerido else None,
        numero=datos["numero"],
        fecha_emision=datos["fecha_emision"],
        base_imponible=datos["base_imponible"],
        iva=datos["iva"],
        irpf=datos["irpf"],
        retencion_garantia=datos["retencion_garantia"],
        total=datos["total"],
        tipo=datos["tipo"],
        fichero_origen=Path(nombre_fichero).name,
        es_escaneada=es_escaneada,
        estado_revision="pendiente",
    )
    db.add(factura)
    db.flush()
    factura.ruta_almacen = almacen_svc.guardar(
        proyecto_id,
        "factura",
        factura.id,
        nombre_fichero,
        contenido,
    )
    for linea in datos["lineas"]:
        db.add(
            LineaFactura(
                factura_id=factura.id,
                descripcion=linea.descripcion,
                importe=linea.importe,
            )
        )
    db.commit()

    return FacturaImportacionOut(
        factura_id=factura.id,
        contratista_nif=contratista.nif,
        contrato_id=factura.contrato_id,
        codigo_contrato=factura.codigo_contrato,
        aviso_codigo=factura.aviso_codigo,
        estado_revision=factura.estado_revision,
        requiere_revision=True,
    )


def listar_facturas(db: Session, proyecto_id: int) -> list[FacturaResumenOut]:
    if db.get(Proyecto, proyecto_id) is None:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado")
    facturas = (
        db.query(Factura)
        .options(
            joinedload(Factura.contratista),
            joinedload(Factura.proyecto),
            joinedload(Factura.contrato).joinedload(Contrato.contratista),
        )
        .filter(Factura.proyecto_id == proyecto_id)
        .order_by(Factura.id.desc())
        .all()
    )
    _rellenar_contrato_unico(db, facturas)
    return [_a_resumen(f) for f in facturas]


def obtener_factura(db: Session, factura_id: int) -> FacturaRevisionOut:
    factura = (
        db.query(Factura)
        .options(
            joinedload(Factura.contratista),
            joinedload(Factura.proyecto),
            joinedload(Factura.lineas),
            joinedload(Factura.contrato).joinedload(Contrato.contratista),
        )
        .filter(Factura.id == factura_id)
        .first()
    )
    if factura is None:
        raise ValueError(f"Factura {factura_id} no encontrada")
    if factura.proyecto_id is None:
        raise ValueError(f"La factura {factura_id} no tiene proyecto")
    _rellenar_contrato_unico(db, [factura])

    candidatos = _contratos_candidatos(
        db, factura.proyecto_id, factura.contratista_id
    )
    resumen = _a_resumen(factura)
    return FacturaRevisionOut(
        **resumen.model_dump(),
        base_imponible=factura.base_imponible,
        iva=factura.iva,
        irpf=factura.irpf,
        retencion_garantia=factura.retencion_garantia,
        lineas=sorted(factura.lineas, key=lambda linea: linea.id),
        inversion_sujeto_pasivo=bool(
            factura.proyecto and factura.proyecto.inversion_sujeto_pasivo
        ),
        contratos_candidatos=[
            ContratoCandidatoFacturaOut(
                id=contrato.id,
                contratista_nombre=(
                    contrato.contratista.nombre if contrato.contratista else "—"
                ),
                precio_total=contrato.precio_total,
                codigo=contrato.codigo,
            )
            for contrato in candidatos
        ],
    )


def confirmar_factura(
    db: Session,
    factura_id: int,
    payload: ConfirmarFacturaIn,
    usuario: Usuario,
) -> ConfirmarFacturaOut:
    factura = db.get(Factura, factura_id)
    if factura is None:
        raise ValueError(f"Factura {factura_id} no encontrada")
    if factura.proyecto_id is None:
        raise ValueError(f"La factura {factura_id} no tiene proyecto")

    proyecto = db.get(Proyecto, factura.proyecto_id)
    if proyecto is not None and proyecto.inversion_sujeto_pasivo and payload.iva != 0:
        raise ValueError(AVISO_ISP)

    if payload.codigo_contrato:
        contrato = _exigir_contrato_del_codigo(
            db,
            factura.proyecto_id,
            factura.contratista_id,
            payload.codigo_contrato,
        )
        if payload.contrato_id is not None and payload.contrato_id != contrato.id:
            raise ValueError("El contrato no coincide con el código")
        factura.codigo_contrato = payload.codigo_contrato
        factura.aviso_codigo = None
        factura.contrato_id = contrato.id
    elif payload.contrato_id is not None:
        contrato = db.get(Contrato, payload.contrato_id)
        if contrato is None:
            raise ValueError(f"Contrato {payload.contrato_id} no encontrado")
        if contrato.proyecto_id != factura.proyecto_id:
            raise ValueError("El contrato no pertenece al proyecto de la factura")
        if contrato.contratista_id != factura.contratista_id:
            raise ValueError("El contrato no pertenece al contratista de la factura")
        factura.contrato_id = contrato.id

    factura.numero = payload.numero
    factura.fecha_emision = payload.fecha_emision
    factura.base_imponible = payload.base_imponible
    factura.iva = payload.iva
    factura.irpf = payload.irpf
    factura.retencion_garantia = payload.retencion_garantia
    factura.total = payload.total
    factura.tipo = payload.tipo
    factura.referencia_alc = payload.referencia_alc
    if factura.contrato_id is None and not payload.codigo_contrato:
        factura.contrato_id = payload.contrato_id or _contrato_unico_id(
            db, factura.proyecto_id, factura.contratista_id
        )
    factura.estado_revision = "confirmada"

    db.query(LineaFactura).filter(
        LineaFactura.factura_id == factura.id
    ).delete(synchronize_session=False)
    for linea in payload.lineas:
        db.add(
            LineaFactura(
                factura_id=factura.id,
                descripcion=linea.descripcion.strip(),
                importe=linea.importe,
            )
        )
    db.flush()
    proyecto = db.get(Proyecto, factura.proyecto_id)
    ahora = datetime.now(ZONA)
    datos = _datos_sello(db, factura, proyecto, usuario, ahora)
    origen = almacen_svc.abrir_si_existe(factura.ruta_almacen)
    contenido = pdf_con_sello(origen, lineas_sello(datos))
    factura.ruta_sello = almacen_svc.guardar(
        factura.proyecto_id,
        "factura",
        factura.id,
        "sello-confirmacion.pdf",
        contenido,
    )
    factura.confirmada_en = ahora
    factura.confirmada_por = datos.nombre
    registrar(
        db,
        usuario,
        "confirmar_factura",
        tipo_documento="factura",
        documento_id=factura.id,
        etiqueta=f"{payload.numero} · {proyecto.nombre}",
    )
    db.commit()

    return ConfirmarFacturaOut(
        ok=True,
        factura_id=factura.id,
        proyecto_id=factura.proyecto_id,
        contrato_id=factura.contrato_id,
        estado_revision=factura.estado_revision,
        tiene_sello=True,
    )


def _datos_sello(
    db: Session,
    factura: Factura,
    proyecto: Proyecto | None,
    usuario: Usuario,
    ahora: datetime,
) -> DatosSello:
    contrato = db.get(Contrato, factura.contrato_id) if factura.contrato_id else None
    presupuestado = (
        Decimal(contrato.precio_total) if contrato is not None else Decimal("0")
    )
    codigo = factura.codigo_contrato or (contrato.codigo if contrato is not None else None)
    hermanas = _facturas_del_mismo_contrato(db, factura)
    ordinal = 1
    acumulado = Decimal("0")
    for indice, hermana in enumerate(hermanas, start=1):
        acumulado += Decimal(hermana.total)
        if hermana.id == factura.id:
            ordinal = indice
    obra = proyecto.nombre.strip() if proyecto is not None and proyecto.nombre else "—"
    nombre = (usuario.nombre or "").strip() or "—"
    return DatosSello(
        obra=obra,
        codigo=codigo,
        referencia_alc=factura.referencia_alc or "",
        nombre=nombre,
        fecha=ahora.astimezone(ZONA).date(),
        presupuestado=presupuestado,
        ordinal=ordinal,
        importe_factura=Decimal(factura.total),
        pendiente=presupuestado - acumulado,
    )


def _facturas_del_mismo_contrato(db: Session, factura: Factura) -> list[Factura]:
    """Confirmadas del mismo contrato, por fecha de emisión. La actual entra."""
    consulta = db.query(Factura).filter(
        Factura.proyecto_id == factura.proyecto_id,
        Factura.estado_revision == "confirmada",
    )
    if factura.contrato_id is not None:
        consulta = consulta.filter(Factura.contrato_id == factura.contrato_id)
    else:
        consulta = consulta.filter(
            Factura.contrato_id.is_(None),
            Factura.contratista_id == factura.contratista_id,
        )
    filas = consulta.all()
    if all(fila.id != factura.id for fila in filas):
        filas.append(factura)

    def orden(fila: Factura) -> tuple:
        return (fila.fecha_emision is None, fila.fecha_emision or date.min, fila.id)

    filas.sort(key=orden)
    return filas


def enlazar_contrato(
    db: Session,
    factura_id: int,
    payload: EnlazarContratoFacturaIn,
) -> FacturaResumenOut:
    factura = (
        db.query(Factura)
        .options(
            joinedload(Factura.contratista),
            joinedload(Factura.contrato).joinedload(Contrato.contratista),
        )
        .filter(Factura.id == factura_id)
        .first()
    )
    if factura is None:
        raise ValueError(f"Factura {factura_id} no encontrada")
    if factura.proyecto_id is None:
        raise ValueError(f"La factura {factura_id} no tiene proyecto")
    contrato = db.get(Contrato, payload.contrato_id)
    if contrato is None:
        raise ValueError(f"Contrato {payload.contrato_id} no encontrado")
    if contrato.proyecto_id != factura.proyecto_id:
        raise ValueError("El contrato no pertenece al proyecto de la factura")
    if contrato.contratista_id != factura.contratista_id:
        raise ValueError("El contrato no pertenece al contratista de la factura")
    factura.contrato_id = contrato.id
    db.commit()
    db.refresh(factura)
    return _a_resumen(factura)


def borrar_factura(db: Session, factura_id: int, usuario: Usuario) -> None:
    factura = db.get(Factura, factura_id)
    if factura is None:
        raise ValueError(f"Factura {factura_id} no encontrada")
    numero = factura.numero
    proyecto = db.get(Proyecto, factura.proyecto_id)
    registrar(
        db,
        usuario,
        "borrar_factura",
        tipo_documento="factura",
        documento_id=factura.id,
        etiqueta=f"{numero} · {proyecto.nombre}",
    )
    ruta = factura.ruta_almacen
    ruta_sello = factura.ruta_sello
    db.query(Factura).filter(Factura.duplicado_de_id == factura.id).update(
        {Factura.duplicado_de_id: None},
        synchronize_session=False,
    )
    db.query(Asignacion).filter(Asignacion.factura_id == factura.id).delete(
        synchronize_session=False
    )
    db.query(LineaFactura).filter(LineaFactura.factura_id == factura.id).delete(
        synchronize_session=False
    )
    db.delete(factura)
    db.commit()
    almacen_svc.borrar_fichero(ruta)
    if ruta_sello != ruta:
        almacen_svc.borrar_fichero(ruta_sello)


def guardar_codigo_factura(db: Session, factura_id: int, codigo: str) -> Factura:
    """Guarda el código que la persona indica y, si existe, enlaza el contrato."""
    factura = (
        db.query(Factura)
        .options(
            joinedload(Factura.contratista),
            joinedload(Factura.contrato).joinedload(Contrato.contratista),
        )
        .filter(Factura.id == factura_id)
        .first()
    )
    if factura is None:
        raise ValueError(f"Factura {factura_id} no encontrada")
    if factura.proyecto_id is None:
        raise ValueError(f"La factura {factura_id} no tiene proyecto")
    factura.codigo_contrato = codigo
    contrato, aviso = _enlace_por_codigo(
        db, factura.proyecto_id, factura.contratista_id, codigo
    )
    factura.aviso_codigo = aviso
    factura.contrato_id = contrato.id if contrato is not None else None
    db.commit()
    db.refresh(factura)
    return factura


def _codigo_de_factura(
    db: Session,
    proyecto_id: int,
    contratista_id: int,
    texto: str,
) -> tuple[str | None, str | None, Contrato | None]:
    encontrados = codigos_en_texto(texto)
    if len(encontrados) > 1:
        return None, AVISO_VARIOS, None
    if not encontrados:
        return None, AVISO_SIN_CODIGO_FACTURA, None
    codigo = encontrados[0]
    contrato, aviso = _enlace_por_codigo(db, proyecto_id, contratista_id, codigo)
    return codigo, aviso, contrato


def _enlace_por_codigo(
    db: Session,
    proyecto_id: int,
    contratista_id: int,
    codigo: str,
) -> tuple[Contrato | None, str | None]:
    contrato = db.query(Contrato).filter(Contrato.codigo == codigo).one_or_none()
    if contrato is None:
        return None, aviso_sin_contrato(codigo)
    if contrato.proyecto_id != proyecto_id:
        return None, aviso_otra_obra(codigo)
    _dejar_el_proveedor_que_factura(db, contrato, contratista_id)
    return contrato, None


def _dejar_el_proveedor_que_factura(
    db: Session,
    contrato: Contrato,
    contratista_id: int,
) -> None:
    """El que factura es el subcontratista. El PDF del contrato a veces trae antes a quien encarga."""
    if contrato.contratista_id == contratista_id:
        return
    anterior = contrato.contratista_id
    contrato.contratista_id = contratista_id
    db.query(Tarea).filter(
        Tarea.contrato_id == contrato.id,
        Tarea.contratista_id == anterior,
    ).update({Tarea.contratista_id: contratista_id}, synchronize_session=False)


def _exigir_contrato_del_codigo(
    db: Session,
    proyecto_id: int,
    contratista_id: int,
    codigo: str,
) -> Contrato:
    contrato, aviso = _enlace_por_codigo(db, proyecto_id, contratista_id, codigo)
    if contrato is None:
        raise ValueError(aviso or aviso_sin_contrato(codigo))
    return contrato


def _contratos_candidatos(
    db: Session,
    proyecto_id: int,
    contratista_id: int,
) -> list[Contrato]:
    return (
        db.query(Contrato)
        .options(joinedload(Contrato.contratista))
        .filter(
            Contrato.proyecto_id == proyecto_id,
            Contrato.contratista_id == contratista_id,
        )
        .order_by(Contrato.id.desc())
        .all()
    )


def _contrato_unico_id(
    db: Session,
    proyecto_id: int,
    contratista_id: int,
) -> int | None:
    candidatos = _contratos_candidatos(db, proyecto_id, contratista_id)
    if len(candidatos) == 1:
        return candidatos[0].id
    return None


def _rellenar_contrato_unico(db: Session, facturas: list[Factura]) -> None:
    """Si el proveedor solo tiene un contrato en la obra, la factura se le enlaza."""
    cambio = False
    for factura in facturas:
        if factura.contrato_id is not None or factura.proyecto_id is None:
            continue
        if factura.codigo_contrato:
            contrato, aviso = _enlace_por_codigo(
                db,
                factura.proyecto_id,
                factura.contratista_id,
                factura.codigo_contrato,
            )
            if contrato is None:
                continue
            factura.contrato_id = contrato.id
            factura.aviso_codigo = aviso
            cambio = True
            continue
        contrato_id = _contrato_unico_id(db, factura.proyecto_id, factura.contratista_id)
        if contrato_id is None:
            continue
        factura.contrato_id = contrato_id
        cambio = True
    if cambio:
        db.commit()


def _etiqueta_contrato(factura: Factura) -> str | None:
    if factura.contrato_id is None:
        return None
    contrato = factura.contrato
    if contrato is not None and contrato.contratista and contrato.contratista.nombre:
        return contrato.contratista.nombre
    return f"Contrato #{factura.contrato_id}"


def _a_resumen(factura: Factura) -> FacturaResumenOut:
    marcada = bool(factura.proyecto and factura.proyecto.inversion_sujeto_pasivo)
    return FacturaResumenOut(
        id=factura.id,
        proyecto_id=factura.proyecto_id,
        numero=factura.numero,
        fecha_emision=factura.fecha_emision,
        contratista_nombre=(
            factura.contratista.nombre if factura.contratista else "—"
        ),
        contratista_nif=factura.contratista.nif if factura.contratista else "—",
        contrato_id=factura.contrato_id,
        codigo_contrato=factura.codigo_contrato,
        aviso_codigo=factura.aviso_codigo,
        contrato_etiqueta=_etiqueta_contrato(factura),
        total=factura.total,
        tipo=factura.tipo,
        es_escaneada=factura.es_escaneada,
        estado_revision=factura.estado_revision,
        tiene_fichero=bool(factura.ruta_almacen),
        fichero_origen=factura.fichero_origen,
        aviso_isp=aviso_de(marcada, factura.iva),
        referencia_alc=factura.referencia_alc,
        tiene_sello=bool(factura.ruta_sello),
    )


def _extraer_texto(contenido: bytes, nombre_fichero: str) -> tuple[str, bool]:
    extension = Path(nombre_fichero).suffix.lower()
    if extension in {".md", ".txt"}:
        try:
            return contenido.decode("utf-8"), False
        except UnicodeDecodeError as exc:
            raise ValueError("La factura de texto no está codificada en UTF-8") from exc

    if ocr.es_extension_imagen(nombre_fichero):
        return ocr.ocr_imagen(contenido).texto, True

    if extension == ".pdf":
        try:
            documento = pymupdf.open(stream=contenido, filetype="pdf")
            try:
                texto = "\n".join(pagina.get_text() for pagina in documento)
            finally:
                documento.close()
        except Exception as exc:
            raise ValueError("No se pudo leer el PDF de la factura") from exc
        if ocr.pdf_parece_escaneado(texto):
            return ocr.ocr_paginas_pdf(contenido).texto, True
        return texto, False

    raise ValueError("Formato no admitido. Usa PDF, JPG, PNG, TIFF, WEBP o MD")


def _parsear_factura(texto: str) -> dict:
    nif_match = _NIF_RE.search(texto.upper())
    if nif_match is None:
        raise ValueError("No se ha detectado el NIF del contratista")

    numero = _numero_factura(texto)
    if not numero:
        raise ValueError("No se ha detectado el número de factura")

    fecha_texto = _campo_texto(texto, ("fecha de emisión", "fecha emision", "fecha"))
    fecha_emision = _parsear_fecha(fecha_texto) if fecha_texto else None
    base = _campo_importe(texto, ("base imponible",))
    total = _campo_importe(texto, ("total factura", "total"))
    if base is None:
        raise ValueError("No se ha detectado la base imponible")
    if total is None:
        raise ValueError("No se ha detectado el total de la factura")

    tipo = (_campo_texto(texto, ("tipo",)) or "ordinaria").lower()
    if tipo not in {"ordinaria", "anticipo", "certificacion"}:
        tipo = "ordinaria"

    return {
        "contratista_nif": nif_match.group(0).upper(),
        "numero": numero,
        "fecha_emision": fecha_emision,
        "base_imponible": base,
        "iva": _campo_importe(texto, ("iva",)) or Decimal("0"),
        "irpf": _campo_importe(texto, ("irpf",)) or Decimal("0"),
        "retencion_garantia": (
            _campo_importe(texto, ("retención de garantía", "retencion de garantia"))
            or Decimal("0")
        ),
        "total": total,
        "tipo": tipo,
        "lineas": _parsear_lineas(texto),
    }


def _nif_clave(nif: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", nif.upper())


def _contratista_por_nif(db: Session, nif: str) -> Contratista | None:
    clave = _nif_clave(nif)
    if not clave:
        return None
    for contratista in db.query(Contratista).all():
        if _nif_clave(contratista.nif) == clave:
            return contratista
    return None


def _numero_factura(texto: str) -> str | None:
    lineas = [linea.strip() for linea in texto.splitlines()]
    for indice, limpia in enumerate(lineas):
        if not limpia:
            continue
        match = _NUMERO_ETIQUETA_RE.match(limpia)
        if not match:
            continue
        valor = match.group(1).strip()
        if valor:
            return valor
        for siguiente in lineas[indice + 1 :]:
            if not siguiente:
                continue
            if (
                ":" in siguiente
                or not re.search(r"\d", siguiente)
                or len(siguiente) > 100
            ):
                return None
            return siguiente
        return None
    return None


def _campo_texto(texto: str, etiquetas: tuple[str, ...]) -> str | None:
    for linea in texto.splitlines():
        limpia = linea.strip()
        for etiqueta in etiquetas:
            match = re.match(
                rf"^{re.escape(etiqueta)}\s*(?:n[.º°o]\s*)?[:#-]\s*(.+)$",
                limpia,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).strip()
    return None


def _campo_importe(texto: str, etiquetas: tuple[str, ...]) -> Decimal | None:
    lineas = texto.splitlines()
    for indice, linea in enumerate(lineas):
        limpia = linea.strip()
        if not limpia:
            continue
        for etiqueta in etiquetas:
            match = re.match(
                rf"^{re.escape(etiqueta)}(?:\s+\d+(?:[.,]\d+)?\s*%)?\s*[:#-]\s*(.*)$",
                limpia,
                flags=re.IGNORECASE,
            )
            if match and match.group(1).strip():
                return _parsear_decimal(match.group(1))
            if match or re.match(
                rf"^{re.escape(etiqueta)}\b", limpia, flags=re.IGNORECASE
            ):
                siguiente = _importe_en_linea_siguiente(lineas, indice + 1)
                if siguiente is not None:
                    return siguiente
    return None


def _importe_en_linea_siguiente(lineas: list[str], inicio: int) -> Decimal | None:
    for linea in lineas[inicio:]:
        limpia = linea.strip()
        if not limpia:
            continue
        if _IMPORTE_SUELTO_RE.match(limpia):
            return _parsear_decimal(limpia)
        return None
    return None


def _parsear_decimal(valor: str) -> Decimal:
    limpio = re.sub(r"[^\d,.\-]", "", valor)
    if not limpio:
        raise ValueError(f"Importe no válido: {valor}")
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif limpio.count(".") > 1:
        partes = limpio.split(".")
        limpio = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return Decimal(limpio).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Importe no válido: {valor}") from exc


def _parsear_fecha(valor: str) -> date:
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(valor.strip(), formato).date()
        except ValueError:
            continue
    raise ValueError(f"Fecha de emisión no válida: {valor}")


def _parsear_lineas(texto: str) -> list[LineaFacturaCreate]:
    resultado: list[LineaFacturaCreate] = []
    en_lineas = False
    for linea in texto.splitlines():
        limpia = linea.strip()
        if limpia.lower() in {"líneas", "lineas", "detalle"}:
            en_lineas = True
            continue
        if not en_lineas or "|" not in limpia:
            continue
        descripcion, importe = limpia.rsplit("|", 1)
        if descripcion.strip():
            resultado.append(
                LineaFacturaCreate(
                    descripcion=descripcion.strip(),
                    importe=_parsear_decimal(importe),
                )
            )
    return resultado
