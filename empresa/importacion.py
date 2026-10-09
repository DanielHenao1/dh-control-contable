"""Lectura genérica de exportes Excel/CSV con perfiles de mapeo de columnas configurables.

No se conocen los formatos reales de World Office ni de la DIAN, así que nada está atado a
nombres de columna fijos: el perfil dice qué columna del archivo alimenta cada campo interno.
"""
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd


@dataclass
class Campo:
    nombre: str
    etiqueta: str
    tipo: str = "texto"  # texto | numero | fecha
    requerido: bool = False


CAMPOS_POR_TIPO = {
    "balance": [
        Campo("cuenta", "Código de cuenta", "texto", True),
        Campo("nombre", "Nombre de la cuenta"),
        Campo("saldo_inicial", "Saldo inicial", "numero"),
        Campo("debito", "Débitos", "numero", True),
        Campo("credito", "Créditos", "numero", True),
        Campo("saldo_final", "Saldo final", "numero", True),
    ],
    "auxiliar": [
        Campo("fecha", "Fecha", "fecha", True),
        Campo("comprobante", "Comprobante"),
        Campo("documento", "Documento / factura"),
        Campo("cuenta", "Código de cuenta", "texto", True),
        Campo("nit", "NIT del tercero"),
        Campo("tercero_nombre", "Nombre del tercero"),
        Campo("descripcion", "Descripción"),
        Campo("debito", "Débito", "numero", True),
        Campo("credito", "Crédito", "numero", True),
    ],
    "facturas_dian": [
        Campo("tipo_documento", "Tipo de documento"),
        Campo("prefijo", "Prefijo"),
        Campo("numero", "Número", "texto", True),
        Campo("cufe", "CUFE / CUDE"),
        Campo("fecha", "Fecha de emisión", "fecha", True),
        Campo("nit_emisor", "NIT emisor", "texto", True),
        Campo("nombre_emisor", "Nombre emisor"),
        Campo("nit_receptor", "NIT receptor", "texto", True),
        Campo("nombre_receptor", "Nombre receptor"),
        Campo("subtotal", "Base / subtotal", "numero"),
        Campo("iva", "IVA", "numero"),
        Campo("retenciones", "Retenciones", "numero"),
        Campo("total", "Total", "numero", True),
        Campo("estado_dian", "Estado DIAN"),
        Campo("sentido", "Emitido o recibido (columna Grupo)"),
    ],
    "retenciones": [
        Campo("fecha", "Fecha del pago", "fecha", True),
        Campo("documento", "Documento"),
        Campo("nit", "NIT del tercero", "texto", True),
        Campo("concepto", "Concepto de retención", "texto", True),
        Campo("base", "Base", "numero", True),
        Campo("tarifa_aplicada", "Tarifa aplicada (%)", "numero"),
        Campo("retenido", "Valor retenido", "numero", True),
    ],
    "extracto_banco": [
        Campo("fecha", "Fecha", "fecha", True),
        Campo("descripcion", "Descripción"),
        Campo("referencia", "Referencia"),
        Campo("valor", "Valor (+ ingreso / - egreso)", "numero", True),
    ],
}


def normalizar(texto):
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


class ErrorImportacion(Exception):
    pass


@dataclass
class Lectura:
    columnas: list
    filas: list  # list[dict campo_interno -> valor tipado]
    errores: list = field(default_factory=list)
    total_filas: int = 0
    faltantes: list = field(default_factory=list)
    bloqueos: list = field(default_factory=list)  # errores que impiden importar, aunque se omitan filas
    avisos: list = field(default_factory=list)
    info: dict = field(default_factory=dict)  # qué se importó y qué se ignoró (va al resumen de la carga)


def _es_encabezado(fila, siguiente):
    """Una fila es encabezado si todas sus celdas son texto y la siguiente trae algún número."""
    celdas = [c for c in fila if not (c is None or (isinstance(c, float) and pd.isna(c)))]
    if len(celdas) < 3 or not all(isinstance(c, str) for c in celdas):
        return False
    return siguiente is None or any(isinstance(c, (int, float, Decimal)) and not pd.isna(c) for c in siguiente)


def leer_todas_las_hojas(contenido: bytes) -> pd.DataFrame:
    """Libro con una hoja por mes (el exporte de la DIAN): junta todas las hojas en una tabla.

    Una hoja sin encabezado (por ejemplo, borrado a mano) reutiliza el de la hoja anterior si trae las mismas columnas.
    """
    libro = pd.ExcelFile(io.BytesIO(contenido))
    columnas, partes = None, []
    for hoja in libro.sheet_names:
        crudo = libro.parse(hoja, header=None, dtype=object).dropna(how="all")
        if crudo.empty:
            continue
        filas = crudo.values.tolist()
        if _es_encabezado(filas[0], filas[1] if len(filas) > 1 else None):
            columnas = [str(c).strip() for c in filas[0]]
            crudo = crudo.iloc[1:]
        elif columnas is None or len(columnas) != crudo.shape[1]:
            raise ErrorImportacion(f"La hoja «{hoja.strip()}» no tiene encabezado y no hay uno anterior que se pueda reutilizar.")
        crudo = crudo.copy()
        crudo.columns = columnas
        partes.append(crudo)
    if not partes:
        raise ErrorImportacion("El libro no tiene hojas con datos.")
    return pd.concat(partes, ignore_index=True)


def leer_dataframe(contenido: bytes, nombre: str, perfil) -> pd.DataFrame:
    header = max((perfil.fila_encabezado if perfil else 1) - 1, 0)
    ext = nombre.lower().rsplit(".", 1)[-1]
    if ext in ("xlsx", "xlsm", "xls") and perfil and perfil.hoja.strip() == "*":
        return leer_todas_las_hojas(contenido)
    if ext in ("xlsx", "xlsm", "xls"):
        hoja = (perfil.hoja if perfil and perfil.hoja else 0)
        return pd.read_excel(io.BytesIO(contenido), sheet_name=hoja, header=header, dtype=object)
    if ext in ("csv", "txt"):
        sep = perfil.separador_csv if perfil else ","
        for enc in ("utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(contenido), sep=sep, header=header, dtype=object, encoding=enc)
            except UnicodeDecodeError:
                continue
    raise ErrorImportacion("Formato no soportado: use Excel (.xlsx) o CSV.")


def parse_numero(valor, decimal_coma=False):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return Decimal("0")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if s in ("", "-"):
        return Decimal("0")
    negativo = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if s.endswith("-"):  # formato contable 100-
        negativo, s = True, s[:-1]
    if decimal_coma:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"número inválido: {valor!r}") from exc
    return -d if negativo else d


def parse_fecha(valor, formato=""):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, pd.Timestamp):
        return valor.date()
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "nat"):
        raise ValueError("fecha vacía")
    formatos = [formato] if formato else ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%y"]
    for f in formatos:
        try:
            return datetime.strptime(s[:19] if "%H" in f else s[:10] if len(s) >= 10 else s, f).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception as exc:
        raise ValueError(f"fecha inválida: {valor!r}") from exc


def parse_texto(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    s = str(valor).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def sugerir_mapeo(tipo, columnas):
    """Sugiere un mapeo por parecido de nombres; el usuario lo ajusta en pantalla."""
    sugerido = {}
    normas = {normalizar(c): c for c in columnas}
    for campo in CAMPOS_POR_TIPO.get(tipo, []):
        for clave in (normalizar(campo.nombre), normalizar(campo.etiqueta)):
            if clave in normas:
                sugerido[campo.nombre] = normas[clave]
                break
    return sugerido


def leer(contenido: bytes, nombre: str, tipo: str, perfil, max_filas=None) -> Lectura:
    if tipo == "balance" and not (perfil and perfil.mapeo) and nombre.lower().endswith((".xlsx", ".xlsm")):
        jerarquico = leer_balance_world_office(contenido, max_filas)
        if jerarquico is not None:
            return jerarquico
    campos = CAMPOS_POR_TIPO[tipo]
    df = leer_dataframe(contenido, nombre, perfil)
    df.columns = [str(c).strip() for c in df.columns]
    columnas = list(df.columns)
    mapeo = (perfil.mapeo if perfil else {}) or sugerir_mapeo(tipo, columnas)
    faltantes = [
        c.etiqueta for c in campos if c.requerido and (c.nombre not in mapeo or mapeo[c.nombre] not in columnas)
    ]
    lectura = Lectura(columnas=columnas, filas=[], total_filas=len(df), faltantes=faltantes)
    if faltantes:
        return lectura
    dec = bool(perfil and perfil.decimal_coma)
    fmt = perfil.formato_fecha if perfil else ""
    for i, (_, fila) in enumerate(df.iterrows()):
        if max_filas is not None and i >= max_filas:
            break
        if fila.isna().all():
            continue
        registro, problemas = {}, []
        for c in campos:
            col = mapeo.get(c.nombre)
            bruto = fila[col] if col in columnas else None
            try:
                if c.tipo == "numero":
                    registro[c.nombre] = parse_numero(bruto, dec)
                elif c.tipo == "fecha":
                    registro[c.nombre] = parse_fecha(bruto, fmt) if (c.requerido or not _vacio(bruto)) else None
                else:
                    registro[c.nombre] = parse_texto(bruto)
                    if c.requerido and not registro[c.nombre]:
                        raise ValueError("valor requerido vacío")
            except ValueError as exc:
                problemas.append(f"{c.etiqueta}: {exc}")
        if problemas:
            lectura.errores.append({"fila": i + 1 + (perfil.fila_encabezado if perfil else 1), "problemas": problemas})
        else:
            lectura.filas.append(registro)
    return lectura


def _vacio(v):
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


# ---------- Balance de prueba de World Office (formato jerárquico, con terceros) ----------
def parse_numero_colombiano(valor):
    """Cifras del exporte: 1.454.134,91, (51.999,00) para negativos y «-» para cero. Celda vacía = None."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if s == "":
        return None
    if s in ("-", "–", "—"):
        return Decimal("0")
    negativo = (s.startswith("(") and s.endswith(")")) or s.startswith("-") or s.endswith("-")
    s = s.strip("()").strip("-")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        d = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"número inválido: {valor!r}") from exc
    return -d if negativo else d


ETIQUETAS_BALANCE = {"saldo inicial": "saldo_inicial", "debitos": "debito", "creditos": "credito", "saldo final": "saldo_final"}


def _encabezado_balance(crudo):
    """(fila, {campo: columna}) de la primera fila con Saldo inicial / Débitos / Créditos / Saldo final."""
    for i in range(min(40, len(crudo))):
        encontradas = {}
        for j, v in enumerate(crudo.iloc[i]):
            if isinstance(v, str) and normalizar(v) in ETIQUETAS_BALANCE:
                encontradas[ETIQUETAS_BALANCE[normalizar(v)]] = j
        if len(encontradas) == 4:
            return i, encontradas
    return None, None


def leer_balance_world_office(contenido: bytes, max_filas=None):
    """Lee el balance de prueba jerárquico de World Office, o devuelve None si el archivo no tiene esa forma.

    Estructura: títulos arriba; luego el encabezado (Saldo inicial, Débitos, Créditos, Saldo final); filas de agrupación
    con código y nombre y sin cifras («1105 CAJA»); filas de detalle por tercero, con cifras y sin código; y filas
    «Total …» de subtotal. Solo se importa el detalle, con el código de la agrupación más cercana hacia arriba. Las
    filas «Total» se ignoran, salvo para comprobar que los débitos y créditos importados cuadran con el archivo.
    """
    try:
        crudo = pd.read_excel(io.BytesIO(contenido), header=None, dtype=object)
    except Exception:  # noqa: BLE001 - no es un Excel legible: que lo intente el lector genérico
        return None
    fila_enc, columnas = _encabezado_balance(crudo)
    if fila_enc is None:
        return None
    col_etiqueta = max(range(min(columnas.values())), key=lambda j: crudo.iloc[fila_enc + 1:, j].map(lambda v: isinstance(v, str)).sum(), default=None)
    if col_etiqueta is None:
        return None
    agrupacion = re.compile(r"^(\d+)\s+(.+)$")
    actual, filas, errores, totales_clase, total_general = None, [], [], {}, {}
    ignoradas = {"totales": 0, "agrupaciones": 0, "sin_movimiento": 0, "sin_agrupacion": 0, "vacias": 0}
    for i in range(fila_enc + 1, len(crudo)):
        fila = crudo.iloc[i]
        etiqueta = fila.iloc[col_etiqueta]
        etiqueta = etiqueta.strip() if isinstance(etiqueta, str) else ""
        numero_fila = i + 1
        try:
            valores = {campo: parse_numero_colombiano(fila.iloc[j]) for campo, j in columnas.items()}
        except ValueError as exc:
            errores.append({"fila": numero_fila, "problemas": [f"{etiqueta or 'fila'}: {exc}"]})
            continue
        hay_valor = any(v is not None for v in valores.values())
        n = normalizar(etiqueta)
        if re.match(r"^total\s+\d", etiqueta, flags=re.IGNORECASE) or n in ("total", "totales", "total general", "sumas iguales", "sumas"):
            ignoradas["totales"] += 1
            m = re.match(r"^total\s+(\d+)\b", etiqueta, flags=re.IGNORECASE)
            if m and len(m.group(1)) == 1 and hay_valor:
                totales_clase[m.group(1)] = valores
            elif n in ("total", "totales", "total general", "sumas iguales", "sumas") and hay_valor:
                total_general = valores
            continue
        m = agrupacion.match(etiqueta)
        if m and not hay_valor:
            actual = (m.group(1), m.group(2).strip())
            ignoradas["agrupaciones"] += 1
            continue
        if not etiqueta or not hay_valor:
            ignoradas["vacias"] += 1
            continue
        if actual is None:
            ignoradas["sin_agrupacion"] += 1
            continue
        if all((v or 0) == 0 for v in valores.values()):
            ignoradas["sin_movimiento"] += 1
            continue
        filas.append({
            "cuenta": actual[0], "nombre": actual[1], "tercero": etiqueta, "fila": numero_fila,
            **{campo: (v if v is not None else Decimal("0")) for campo, v in valores.items()},
        })
    importadas = len(filas)
    bloqueos, avisos = [], []
    deb = sum((f["debito"] for f in filas), Decimal("0"))
    cre = sum((f["credito"] for f in filas), Decimal("0"))
    referencia = total_general
    origen = "total general del archivo"
    if not referencia and totales_clase:
        referencia = {c: sum((t[c] or Decimal("0") for t in totales_clase.values()), Decimal("0")) for c in ("debito", "credito")}
        origen = "suma de los totales por clase (1 a 9) del archivo"
    cuadra = None
    if referencia and referencia.get("debito") is not None and referencia.get("credito") is not None:
        dif_d, dif_c = deb - referencia["debito"], cre - referencia["credito"]
        cuadra = abs(dif_d) <= 1 and abs(dif_c) <= 1
        if not cuadra:
            detalle = []
            for clase, t in sorted(totales_clase.items()):
                d_clase = sum((f["debito"] for f in filas if f["cuenta"].startswith(clase)), Decimal("0"))
                c_clase = sum((f["credito"] for f in filas if f["cuenta"].startswith(clase)), Decimal("0"))
                if t["debito"] is not None and abs(d_clase - t["debito"]) > 1 or t["credito"] is not None and abs(c_clase - t["credito"]) > 1:
                    detalle.append(f"clase {clase}: importado débitos {d_clase:,.2f} y créditos {c_clase:,.2f}; el archivo dice {t['debito'] or 0:,.2f} y {t['credito'] or 0:,.2f}")
            bloqueos.append(
                f"Los totales no cuadran con el archivo ({origen}). Débitos importados {deb:,.2f} vs {referencia['debito']:,.2f} "
                f"(diferencia {dif_d:,.2f}); créditos importados {cre:,.2f} vs {referencia['credito']:,.2f} (diferencia {dif_c:,.2f})."
                + (" Revisa: " + "; ".join(detalle) + "." if detalle else "")
                + " Puede haber filas de detalle sin agrupación, filas con cifras ilegibles o un archivo editado a mano."
            )
    else:
        avisos.append("No encontré filas «Total» para comprobar que los débitos y créditos cuadran con el archivo.")
    if ignoradas["sin_agrupacion"]:
        avisos.append(f"{ignoradas['sin_agrupacion']} fila(s) con cifras no tienen una agrupación con código arriba y se ignoraron.")
    info = {
        "formato": "balance World Office (jerárquico)", "filas_importadas": importadas,
        "filas_ignoradas": sum(ignoradas.values()), "ignoradas_detalle": ignoradas,
        "debitos_importados": str(deb), "creditos_importados": str(cre), "totales_cuadran": cuadra,
    }
    salida = filas[:max_filas] if max_filas is not None else filas
    return Lectura(
        columnas=["Cuenta", "Nombre", "Tercero", "Saldo inicial", "Débitos", "Créditos", "Saldo final"], filas=salida,
        errores=errores, total_filas=importadas + sum(ignoradas.values()) + len(errores), bloqueos=bloqueos, avisos=avisos, info=info,
    )


def _parece_numero(c):
    if isinstance(c, (int, float, Decimal)):
        return not pd.isna(c)
    return isinstance(c, str) and bool(re.fullmatch(r"\(?-?\$?\s?\d[\d.,]*\)?", c.strip()))


def detectar_fila_encabezado(contenido: bytes, nombre: str, hoja=""):
    """Número de fila (desde 1) del encabezado probable: texto en 3 o más celdas y cifras en las filas siguientes."""
    ext = nombre.lower().rsplit(".", 1)[-1]
    try:
        if ext in ("xlsx", "xlsm", "xls"):
            crudo = pd.read_excel(io.BytesIO(contenido), header=None, dtype=object, sheet_name=hoja or 0)
        else:
            crudo = pd.read_csv(io.BytesIO(contenido), header=None, dtype=object, encoding="utf-8-sig", sep=None, engine="python")
    except Exception:  # noqa: BLE001
        return 1
    for i in range(min(40, len(crudo))):
        celdas = [c for c in crudo.iloc[i] if not (c is None or (isinstance(c, float) and pd.isna(c)))]
        if len(celdas) >= 3 and all(isinstance(c, str) for c in celdas):
            siguientes = crudo.iloc[i + 1:i + 31].values.ravel()
            if any(_parece_numero(c) for c in siguientes):
                return i + 1
    return 1
