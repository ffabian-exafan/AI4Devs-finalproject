"""Lectura determinista de un presupuesto Excel de plantilla Expertis.

No usa OCR ni LLM: la rejilla es fija (Cant., Cod., Descripción, Ref., Euros, Dto., TOTAL).
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import load_workbook
from pydantic import BaseModel, Field

from app.schemas.tipos import Money

_HOJAS_IGNORADAS = {"traduce", "data"}
_HOJAS_GENERICAS = {"presupuesto", "hoja 1", "hoja1", "sheet", "sheet1", "sheet 1"}
_ETIQUETAS = {
    "cliente",
    "nombre",
    "direccion",
    "ciudad",
    "telefono",
    "observaciones",
    "referencia",
    "presupuesto",
    "elaboracion",
    "fecha",
    "contacto",
    "e-mail",
    "email",
    "pais",
    "fax",
    "cp",
    "tel",
    "validez",
    "cotizacion",
}
_TOLERANCIA = Decimal("0.02")
_RE_TOTAL = re.compile(r"^total\b", re.IGNORECASE)
_RE_TOTAL_GENERAL = re.compile(r"^total\s+general\b", re.IGNORECASE)


class AvisoCuadre(BaseModel):
    bloque: str
    suma_lineas: Money
    total_documento: Money


class NodoExcel(BaseModel):
    codigo: str
    nivel: str
    descripcion: str
    cantidad: Money | None = None
    precio_unitario: Money | None = None
    descuento_pct: Money | None = None
    referencia: str | None = None
    referencia_alt: str | None = None
    importe: Money = Decimal("0")
    es_montaje: bool = False
    # Apartado o bloque del que se sacó la línea al agruparla en Montaje.
    capitulo: str | None = None
    hijos: list[NodoExcel] = Field(default_factory=list)


class ExcelLeido(BaseModel):
    """Árbol de un fichero, validado antes de persistir."""

    nombre_apartado: str
    nodos: list[NodoExcel] = Field(default_factory=list)
    importe: Money = Decimal("0")
    partidas: int = 0
    lineas_montaje: int = 0
    sumas_cuadran: bool = True
    avisos: list[AvisoCuadre] = Field(default_factory=list)


def leer_excel_expertis(contenido: bytes) -> ExcelLeido:
    """Lee el primer libro con la cabecera Expertis y devuelve el árbol."""
    if not contenido:
        raise ValueError("El fichero está vacío")
    try:
        formulas = load_workbook(BytesIO(contenido), data_only=False, read_only=True)
        valores = load_workbook(BytesIO(contenido), data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError("No se ha podido abrir el Excel") from exc

    try:
        candidatos: list[tuple[int, str, list, list]] = []
        for nombre in formulas.sheetnames:
            if _normalizar(nombre) in _HOJAS_IGNORADAS:
                continue
            if nombre not in valores.sheetnames:
                continue
            filas_f, negritas, cursivas = _filas(formulas[nombre])
            filas_v = list(valores[nombre].iter_rows(values_only=True))
            cabecera = _buscar_cabecera(filas_f)
            if cabecera is None:
                continue
            candidatos.append((len(filas_f), nombre, filas_f, filas_v, negritas, cursivas))
        if not candidatos:
            raise ValueError(
                "El Excel no tiene la cabecera de presupuesto Expertis "
                "(Cant., Cod., Descripción, Euros, TOTAL)"
            )
        candidatos.sort(key=lambda item: item[0], reverse=True)
        _, nombre, filas_f, filas_v, negritas, cursivas = candidatos[0]
        return _leer_hoja(nombre, filas_f, filas_v, negritas, cursivas)
    finally:
        formulas.close()
        valores.close()


def _leer_hoja(
    nombre_hoja: str,
    filas_f: list,
    filas_v: list,
    negritas: list[list[bool]],
    cursivas: list[list[bool]],
) -> ExcelLeido:
    cabecera = _buscar_cabecera(filas_f)
    if cabecera is None:
        raise ValueError(
            "El Excel no tiene la cabecera de presupuesto Expertis "
            "(Cant., Cod., Descripción, Euros, TOTAL)"
        )
    fila_cab, cols = cabecera
    nombre = _nombre_apartado(nombre_hoja, filas_f, fila_cab, cols)

    nodos: list[NodoExcel] = []
    actual: NodoExcel | None = None
    padre_codigo: NodoExcel | None = None
    n_bloque = 0
    suma_bloque = Decimal("0")
    suma_documento = Decimal("0")
    avisos: list[AvisoCuadre] = []
    partidas = 0
    montaje = 0

    for indice in range(fila_cab + 1, max(len(filas_f), len(filas_v))):
        celdas_f = list(filas_f[indice]) if indice < len(filas_f) else []
        celdas_v = list(filas_v[indice]) if indice < len(filas_v) else []
        textos = [
            _texto(_valor(celdas_f, celdas_v, col))
            for col in range(max(len(celdas_f), len(celdas_v)))
        ]
        if any("detalles de pago" in _normalizar(t) for t in textos if t):
            break

        descripcion = _texto(_valor(celdas_f, celdas_v, cols["descripcion"]))
        if not descripcion and not _texto(_valor(celdas_f, celdas_v, cols["cod"])):
            continue

        if _RE_TOTAL.match(_normalizar(descripcion).replace("  ", " ")):
            total = _numero(_valor(celdas_f, celdas_v, cols["total"]))
            if _RE_TOTAL_GENERAL.match(descripcion.strip()):
                suma = suma_documento
            else:
                suma = suma_bloque
                suma_bloque = Decimal("0")
            if total is not None and abs(suma - total) > _TOLERANCIA:
                avisos.append(
                    AvisoCuadre(
                        bloque=descripcion.strip(),
                        suma_lineas=_dinero(suma),
                        total_documento=_dinero(total),
                    )
                )
            continue

        codigo = _texto(_valor(celdas_f, celdas_v, cols["cod"]))[:50]
        # Cant. es el número de unidades. Solo entra como partida si es mayor que 0.
        # Negrita y sin precio: subapartado (08 ALIMENTACION).
        # Cursiva y sin precio: bloque dentro de ese subapartado.
        cantidad = _numero(_valor(celdas_f, celdas_v, cols["cant"]))
        precio = _numero(_valor(celdas_f, celdas_v, cols["euros"]))
        columnas = (cols.get("descripcion"), cols.get("cod"))
        if cantidad is None or cantidad <= 0:
            if precio is None and (codigo or descripcion):
                if _fila_marca(negritas, indice, *columnas):
                    if codigo:
                        padre_codigo = NodoExcel(
                            codigo=codigo,
                            nivel="subapartado",
                            descripcion=descripcion or codigo,
                            importe=Decimal("0"),
                        )
                        nodos.append(padre_codigo)
                        actual = padre_codigo
                    else:
                        actual = _anidar_titulo(nodos, padre_codigo, descripcion)
                        n_bloque += 1
                        actual.codigo = f"b{n_bloque}"
                elif _fila_marca(cursivas, indice, *columnas) and descripcion:
                    actual = _anidar_titulo(nodos, padre_codigo, descripcion)
                    n_bloque += 1
                    actual.codigo = f"b{n_bloque}"
            continue

        dto = _numero(_valor(celdas_f, celdas_v, cols["dto"])) if "dto" in cols else None
        cacheado = _numero(_valor(celdas_f, celdas_v, cols["total"]))
        importe = _importe_linea(cantidad, precio, dto, cacheado)
        if importe is None:
            importe = Decimal("0")
            avisos.append(
                AvisoCuadre(
                    bloque=descripcion[:80],
                    suma_lineas=Decimal("0"),
                    total_documento=Decimal("0"),
                )
            )
        ref1 = _texto(_valor(celdas_f, celdas_v, cols["ref1"])) if "ref1" in cols else ""
        ref2 = _texto(_valor(celdas_f, celdas_v, cols["ref2"])) if "ref2" in cols else ""
        partida = NodoExcel(
            codigo=codigo or "s/c",
            nivel="partida",
            descripcion=descripcion or codigo or "s/c",
            cantidad=cantidad,
            precio_unitario=precio,
            descuento_pct=dto,
            referencia=ref1 or None,
            referencia_alt=ref2 or None,
            importe=_dinero(importe),
            es_montaje=_es_montaje(descripcion),
        )
        if actual is None:
            nodos.append(partida)
        else:
            actual.hijos.append(partida)
        partidas += 1
        if partida.es_montaje:
            montaje += 1
        suma_bloque += partida.importe
        suma_documento += partida.importe

    nodos = _colocar_montajes(nodos, nombre)
    importe = _dinero(_cerrar_importes(nodos))
    return ExcelLeido(
        nombre_apartado=nombre,
        nodos=nodos,
        importe=importe,
        partidas=partidas,
        lineas_montaje=montaje,
        sumas_cuadran=not avisos,
        avisos=avisos,
    )


def _anidar_titulo(
    nodos: list[NodoExcel],
    padre: NodoExcel | None,
    descripcion: str,
) -> NodoExcel:
    titulo = NodoExcel(
        codigo="b0",
        nivel="subapartado",
        descripcion=descripcion,
        importe=Decimal("0"),
    )
    if padre is None:
        nodos.append(titulo)
    else:
        padre.hijos.append(titulo)
    return titulo


def _filas(hoja) -> tuple[list, list[list[bool]], list[list[bool]]]:
    filas: list = []
    negritas: list[list[bool]] = []
    cursivas: list[list[bool]] = []
    for row in hoja.iter_rows():
        filas.append([celda.value for celda in row])
        negritas.append([_tiene_estilo(celda, "bold") for celda in row])
        cursivas.append([_tiene_estilo(celda, "italic") for celda in row])
    return filas, negritas, cursivas


def _tiene_estilo(celda, atributo: str) -> bool:
    fuente = getattr(celda, "font", None)
    if fuente is not None and getattr(fuente, atributo, None):
        return True
    valor = getattr(celda, "value", None)
    if isinstance(valor, str) or valor is None:
        return False
    if getattr(valor, "__iter__", None) is None:
        return False
    for trozo in valor:
        fuente_trozo = getattr(trozo, "font", None)
        if fuente_trozo is not None and getattr(fuente_trozo, atributo, None):
            return True
    return False


def _fila_marca(marcas: list[list[bool]], indice: int, *columnas: int | None) -> bool:
    if indice >= len(marcas):
        return False
    fila = marcas[indice]
    return any(col is not None and col < len(fila) and fila[col] for col in columnas)


def _buscar_cabecera(filas: list) -> tuple[int, dict[str, int]] | None:
    for indice, fila in enumerate(filas[:80]):
        roles: dict[str, int] = {}
        for col, valor in enumerate(list(fila)):
            rol = _rol_cabecera(_texto(valor))
            if rol and rol not in roles:
                roles[rol] = col
        if {"cant", "cod", "descripcion", "euros", "total"} <= set(roles):
            return indice, roles
    return None


def _rol_cabecera(texto: str) -> str | None:
    n = _normalizar(texto)
    if not n:
        return None
    if n.startswith("cant"):
        return "cant"
    if n.startswith("cod"):
        return "cod"
    if n.startswith("descrip"):
        return "descripcion"
    if n.startswith("ref") and "1" in n and "2" not in n:
        return "ref1"
    if n.startswith("ref") and "2" in n:
        return "ref2"
    if n.startswith("euro"):
        return "euros"
    if n.startswith("dto"):
        return "dto"
    if n == "total" or n.startswith("total"):
        return "total"
    return None


def _nombre_apartado(hoja: str, filas: list, fila_cab: int, cols: dict[str, int]) -> str:
    col_desc = cols.get("descripcion", 3)
    vistos: list[str] = []
    for fila in filas[:fila_cab]:
        celdas = list(fila)
        for valor in celdas:
            texto = _texto(valor)
            if _es_titulo_sistema(texto):
                vistos.append(texto)
    if vistos:
        return vistos[-1][:255]
    for fila in filas[fila_cab + 1 :]:
        celdas = list(fila)
        if col_desc >= len(celdas):
            continue
        texto = _texto(celdas[col_desc])
        if _RE_TOTAL_GENERAL.match(texto.strip()):
            continue
        if _RE_TOTAL.match(texto.strip()):
            resto = _RE_TOTAL.sub("", texto).strip(" :.-")
            if resto:
                return resto[:255]
    hoja_norm = _normalizar(hoja)
    if hoja_norm and hoja_norm not in _HOJAS_GENERICAS:
        return hoja.strip()[:255]
    return "Apartado"


def _es_titulo_sistema(texto: str) -> bool:
    limpio = texto.strip()
    if len(limpio) < 8:
        return False
    n = _normalizar(limpio).rstrip(":")
    if not n or n in _ETIQUETAS or any(n.startswith(et + " ") or n.startswith(et + ":") for et in _ETIQUETAS):
        return False
    if "@" in limpio or "http" in n:
        return False
    letras = sum(1 for c in n if c.isalpha())
    return letras >= 6


def _colocar_montajes(nodos: list[NodoExcel], nombre: str) -> list[NodoExcel]:
    """Deja el montaje dentro del subapartado al que pertenece.

    Si en este nivel las líneas cubren varios subapartados, forman un único
    bloque «Montaje general». Si son de uno solo, el bloque se llama
    «Montaje» más el nombre de ese subapartado.
    """
    etiqueta = (nombre or "").strip()[:255]
    material: list[NodoExcel] = []
    sueltos: list[NodoExcel] = []
    for nodo in nodos:
        if nodo.nivel == "partida":
            if nodo.es_montaje:
                if not nodo.capitulo:
                    nodo.capitulo = etiqueta or None
                sueltos.append(nodo)
            else:
                material.append(nodo)
            continue
        titulo = (nodo.descripcion or "").strip() or etiqueta
        nodo.hijos = _colocar_montajes(nodo.hijos, titulo)
        if nodo.hijos:
            material.append(nodo)
    if not sueltos:
        return material
    return _colgar_montaje(sueltos, material, etiqueta)


def _colgar_montaje(
    lineas: list[NodoExcel],
    hermanos: list[NodoExcel],
    nombre: str,
) -> list[NodoExcel]:
    subapartados = [nodo for nodo in hermanos if nodo.nivel == "subapartado"]
    if len(subapartados) > 1:
        return [_bloque_montaje(lineas, "Montaje general"), *hermanos]
    if len(subapartados) == 1:
        destino = subapartados[0]
        for linea in lineas:
            linea.capitulo = _etiqueta_bloque(destino)
        bloque = _bloque_montaje(lineas, _titulo_montaje(destino.descripcion))
        destino.hijos = [bloque, *destino.hijos]
        return hermanos
    return [_bloque_montaje(lineas, _titulo_montaje(nombre)), *hermanos]


def _bloque_montaje(lineas: list[NodoExcel], titulo: str) -> NodoExcel:
    return NodoExcel(
        codigo="0",
        nivel="subapartado",
        descripcion=titulo,
        importe=_dinero(sum((linea.importe for linea in lineas), Decimal("0"))),
        hijos=lineas,
    )


def _titulo_montaje(nombre: str) -> str:
    """«Montaje Cikkis», o «Montaje general» si el bloque no tiene nombre propio."""
    limpio = (nombre or "").strip()
    normal = _normalizar(limpio)
    if not normal or normal in {"montaje", "montaje general"}:
        return "Montaje general"
    if normal.startswith("montaje "):
        resto = limpio.split(None, 1)[1].strip()
        return _titulo_montaje(resto)
    return f"Montaje {limpio}"[:255]


def lineas_y_productos_montaje(
    nodos: list[NodoExcel],
) -> tuple[list[NodoExcel], list[NodoExcel]]:
    """Líneas de montaje que no están dentro de un producto, y los productos.

    En ventilación el montaje va junto al final, en un bloque GENERAL. En otros
    Excel va dentro del producto. Solo las del cajón general salen para relacionarlas.
    """
    lineas: list[NodoExcel] = []
    productos: list[NodoExcel] = []

    def visitar(lista: list[NodoExcel], pila: list[NodoExcel]) -> None:
        for nodo in lista:
            if (
                nodo.nivel == "subapartado"
                and not _es_nombre_montaje(nodo.descripcion)
                and not _es_cajon_general(nodo.descripcion)
            ):
                productos.append(nodo)
            if (
                nodo.nivel == "partida"
                and nodo.es_montaje
                and any(_es_cajon_general(padre.descripcion) for padre in pila)
            ):
                lineas.append(nodo)
            visitar(nodo.hijos, [*pila, nodo])

    visitar(nodos, [])
    return lineas, productos


def asignar_montaje_por_nombre(lineas: list[str], productos: list[str]) -> list[int | None]:
    """Si no hay LLM: el producto cuyo nombre aparece en la línea. Si hay empate, ninguno."""
    normas = [_normalizar(nombre) for nombre in productos]
    salida: list[int | None] = []
    for linea in lineas:
        texto = _normalizar(linea)
        if texto.startswith("montaje "):
            texto = texto[len("montaje ") :]
        candidatos = [i for i, nombre in enumerate(normas) if nombre and nombre in texto]
        if not candidatos:
            salida.append(None)
            continue
        mejor = max(candidatos, key=lambda i: len(normas[i]))
        empatados = [i for i in candidatos if len(normas[i]) == len(normas[mejor])]
        salida.append(mejor if len(empatados) == 1 else None)
    return salida


def aplicar_relacion_montaje(nodos: list[NodoExcel], asignaciones: list[int | None]) -> Decimal:
    """Mueve las líneas del cajón general al producto indicado, o a «Montaje general»."""
    lineas, productos = lineas_y_productos_montaje(nodos)
    if len(asignaciones) != len(lineas):
        raise ValueError("La relación de montaje no cubre las líneas")
    if not lineas:
        return _cerrar_importes(nodos)
    grupos: dict[int | None, list[NodoExcel]] = {}
    for linea, destino in zip(lineas, asignaciones, strict=True):
        if not isinstance(destino, int) or isinstance(destino, bool) or not 0 <= destino < len(productos):
            grupos.setdefault(None, []).append(linea)
        else:
            grupos.setdefault(destino, []).append(linea)
    quitar = {id(linea) for linea in lineas}
    nodos[:] = _filtrar_nodos(nodos, quitar)
    nodos[:] = _podar_vacios(nodos, {id(producto) for producto in productos})
    for indice, grupo in grupos.items():
        if indice is None:
            continue
        destino = productos[indice]
        titulo = _titulo_montaje(destino.descripcion)
        for linea in grupo:
            linea.capitulo = (destino.descripcion or "").strip()[:255] or None
        bloque = _bloque_por_titulo(destino.hijos, titulo)
        if bloque is None:
            destino.hijos = [_bloque_montaje(grupo, titulo), *destino.hijos]
        else:
            bloque.hijos.extend(grupo)
    generales = grupos.get(None) or []
    if generales:
        for linea in generales:
            if _es_cajon_general(linea.capitulo or ""):
                linea.capitulo = None
        nodos.append(_bloque_montaje(generales, "Montaje general"))
    return _cerrar_importes(nodos)


def _es_nombre_montaje(nombre: str) -> bool:
    normal = _normalizar(nombre)
    return normal == "montaje" or normal.startswith("montaje ")


def _es_cajon_general(nombre: str) -> bool:
    return _normalizar(nombre) in {"general", "montaje general"}


def _filtrar_nodos(nodos: list[NodoExcel], quitar: set[int]) -> list[NodoExcel]:
    vivos: list[NodoExcel] = []
    for nodo in nodos:
        if id(nodo) in quitar:
            continue
        if nodo.hijos:
            nodo.hijos = _filtrar_nodos(nodo.hijos, quitar)
        vivos.append(nodo)
    return vivos


def _podar_vacios(nodos: list[NodoExcel], conservar: set[int]) -> list[NodoExcel]:
    vivos: list[NodoExcel] = []
    for nodo in nodos:
        if nodo.nivel == "subapartado":
            nodo.hijos = _podar_vacios(nodo.hijos, conservar)
            if not nodo.hijos and id(nodo) not in conservar:
                continue
        vivos.append(nodo)
    return vivos


def _bloque_por_titulo(nodos: list[NodoExcel], titulo: str) -> NodoExcel | None:
    buscado = _normalizar(titulo)
    for nodo in nodos:
        if nodo.nivel == "subapartado" and _normalizar(nodo.descripcion) == buscado:
            return nodo
    return None


def _etiqueta_bloque(nodo: NodoExcel) -> str:
    """Nombre del bloque del que sale una línea de montaje."""
    codigo = (nodo.codigo or "").strip()
    nombre = (nodo.descripcion or "").strip()
    if codigo and codigo != "0" and not re.fullmatch(r"b\d+", codigo):
        texto = f"{codigo} {nombre}".strip()
    else:
        texto = nombre or codigo
    return texto[:255]


def _cerrar_importes(nodos: list[NodoExcel]) -> Decimal:
    total = Decimal("0")
    for nodo in nodos:
        if nodo.nivel == "subapartado":
            nodo.importe = _dinero(_cerrar_importes(nodo.hijos))
        total += nodo.importe
    return total


def _es_montaje(descripcion: str) -> bool:
    """La subcontrata factura la línea que empieza por MONTAJE.

    ELEMENTOS DE MONTAJE es material de su bloque: no entra en la partida Montaje.
    """
    n = _normalizar(descripcion)
    if n.startswith("elementos de montaje"):
        return False
    return n.startswith("montaje")


def _importe_linea(
    cantidad: Decimal | None,
    precio: Decimal | None,
    dto: Decimal | None,
    cacheado: Decimal | None,
) -> Decimal | None:
    if cacheado is not None:
        return cacheado
    if cantidad is None or precio is None:
        return None
    factor = Decimal("1") - (dto or Decimal("0")) / Decimal("100")
    return cantidad * precio * factor


def _valor(formulas: list, valores: list, col: int):
    """Prefiere el valor cacheado; si no hay, la celda de la fórmula."""
    if col < len(valores) and valores[col] is not None:
        return valores[col]
    if col < len(formulas):
        return formulas[col]
    return None


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor == int(valor):
        return str(int(valor))
    if isinstance(valor, str) and valor.startswith("="):
        return ""
    return str(valor).replace("\n", " ").strip()


def _numero(valor) -> Decimal | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, str):
        limpio = valor.strip()
        if not limpio or limpio.startswith("="):
            return None
        limpio = limpio.replace(" ", "")
        if limpio.count(",") == 1 and limpio.count(".") >= 1:
            limpio = limpio.replace(".", "").replace(",", ".")
        elif limpio.count(",") == 1:
            limpio = limpio.replace(",", ".")
        try:
            return Decimal(limpio)
        except InvalidOperation:
            return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        return None


def _dinero(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"))


def _normalizar(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto.lower())
    sin = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin).strip()
