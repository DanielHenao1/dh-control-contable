"""Lectores de exportes reales: libro auxiliar de World Office (jerárquico) y extracto de Bancolombia en PDF.

Ambos validan las cifras contra los totales que trae el propio archivo; si no cuadran, bloquean la importación.
"""
import io
import re
from datetime import date
from decimal import Decimal

import pandas as pd

from .importacion import Lectura, normalizar, parse_fecha, parse_numero_colombiano

CENTAVOS = Decimal("0.01")
TOLERANCIA = Decimal("1")  # un peso: redondeos del exporte


def _q(v):
    return (v if v is not None else Decimal("0")).quantize(CENTAVOS)


def _texto(v):
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


# ---------- Libro auxiliar de World Office ----------
_COLS_AUX = {"cuenta": "cuenta", "tercero": "tercero", "fecha": "fecha", "nota": "nota", "doc num": "doc",
             "debitos": "debito", "creditos": "credito"}


def _encabezado_auxiliar(crudo):
    for i in range(min(len(crudo), 30)):
        mapa = {}
        for j, v in enumerate(crudo.iloc[i]):
            clave = _COLS_AUX.get(normalizar(v)) if isinstance(v, str) else None
            if clave:
                mapa[clave] = j
        if {"cuenta", "fecha", "debito", "credito"} <= set(mapa):
            return i, mapa
    return None, {}


def leer_auxiliar_world_office(contenido: bytes, max_filas=None):
    """Libro auxiliar jerárquico: la cuenta aparece una vez («11050501 CAJA GENERAL», con su SALDO INICIAL) y los
    movimientos van debajo, por tercero, con la columna Cuenta vacía. Cada «Total <cuenta>» cierra la cuenta.

    Devuelve None si el archivo no tiene esa forma. El saldo inicial no es un movimiento: se omite, pero se usa para
    comprobar que cada cuenta cuadra con su «Total» (el total de débitos/créditos incluye el saldo inicial).
    """
    try:
        crudo = pd.read_excel(io.BytesIO(contenido), header=None, dtype=object)
    except Exception:  # noqa: BLE001
        return None
    fila_enc, c = _encabezado_auxiliar(crudo)
    if fila_enc is None:
        return None
    patron = re.compile(r"^(\d{4,})\s+(.+)$", flags=re.DOTALL)  # el nombre puede traer saltos de línea
    actual, filas, errores = None, [], []
    inicial = {}  # cuenta -> (débito, crédito) del saldo inicial
    mov = {}  # cuenta -> [débito, crédito] de los movimientos leídos
    totales = {}  # cuenta -> (débito, crédito) según la fila «Total»
    ignoradas = {"saldos_iniciales": 0, "totales": 0, "vacias": 0}
    gran_total = None
    for i in range(fila_enc + 1, len(crudo)):
        fila = crudo.iloc[i]
        etiqueta = _texto(fila.iloc[c["cuenta"]])
        if etiqueta and etiqueta.lower().startswith("total"):
            ignoradas["totales"] += 1
            m = re.match(r"^total\s+(\d{4,})\b", etiqueta, flags=re.IGNORECASE)
            try:
                d, k = (parse_numero_colombiano(fila.iloc[c[x]]) for x in ("debito", "credito"))
            except ValueError:
                continue
            if m:
                totales[m.group(1)] = (d or Decimal("0"), k or Decimal("0"))
            elif normalizar(etiqueta).startswith("total movimientos") and d is not None:
                gran_total = (d, k)
            continue
        if fila.isna().all():
            ignoradas["vacias"] += 1
            continue
        m = patron.match(etiqueta) if etiqueta else None
        if m:
            actual = (m.group(1), re.sub(r"(_x000D_|\s)+", " ", m.group(2)).strip())
        if actual is None:
            continue
        try:
            d = parse_numero_colombiano(fila.iloc[c["debito"]]) or Decimal("0")
            k = parse_numero_colombiano(fila.iloc[c["credito"]]) or Decimal("0")
        except ValueError as exc:
            errores.append({"fila": i + 1, "problemas": [str(exc)]})
            continue
        nota = _texto(fila.iloc[c["nota"]]) if "nota" in c else ""
        if normalizar(nota) == "saldo inicial":
            ignoradas["saldos_iniciales"] += 1
            prev = inicial.get(actual[0], (Decimal("0"), Decimal("0")))
            inicial[actual[0]] = (prev[0] + d, prev[1] + k)
            continue
        try:
            fecha = parse_fecha(fila.iloc[c["fecha"]])
        except ValueError as exc:
            errores.append({"fila": i + 1, "problemas": [f"Fecha: {exc}"]})
            continue
        doc = _texto(fila.iloc[c["doc"]]) if "doc" in c else ""
        doc = re.sub(r"\s+", " ", doc)
        comprobante = re.sub(r"\s*\d+\s*$", "", re.sub(r"^\([^)]*\)\s*", "", doc)).strip()
        filas.append({
            "fecha": fecha, "cuenta": actual[0], "cuenta_nombre": actual[1], "documento": doc, "comprobante": comprobante,
            "tercero_nombre": _texto(fila.iloc[c["tercero"]]) if "tercero" in c else "", "nit": "",
            "descripcion": nota, "debito": _q(d), "credito": _q(k), "fila": i + 1,
        })
        acum = mov.setdefault(actual[0], [Decimal("0"), Decimal("0")])
        acum[0] += d
        acum[1] += k
    lectura = Lectura(
        columnas=[str(v) for v in crudo.iloc[fila_enc] if _texto(v)], filas=filas, errores=errores,
        total_filas=len(filas) + len(errores),
    )
    # Cuadre por cuenta: saldo inicial + movimientos = Total de la cuenta.
    descuadres = []
    for cuenta, (td, tk) in totales.items():
        i0 = inicial.get(cuenta, (Decimal("0"), Decimal("0")))
        m0 = mov.get(cuenta, [Decimal("0"), Decimal("0")])
        dd, dk = i0[0] + m0[0] - td, i0[1] + m0[1] - tk
        if abs(dd) > TOLERANCIA or abs(dk) > TOLERANCIA:
            descuadres.append(f"{cuenta}: débitos {dd:+,.2f}, créditos {dk:+,.2f}")
    if descuadres:
        lectura.bloqueos.append(
            f"{len(descuadres)} cuenta(s) no cuadran con su fila «Total»: " + "; ".join(descuadres[:5])
            + ("…" if len(descuadres) > 5 else "")
        )
    deb = sum((f["debito"] for f in filas), Decimal("0"))
    cre = sum((f["credito"] for f in filas), Decimal("0"))
    cuadra_general = None
    if gran_total is not None:
        cuadra_general = abs(deb - gran_total[0]) <= TOLERANCIA and abs(cre - gran_total[1]) <= TOLERANCIA
        if not cuadra_general:
            lectura.bloqueos.append(
                f"Los movimientos leídos (débitos {deb:,.2f}; créditos {cre:,.2f}) no coinciden con «Total Movimientos» "
                f"del archivo (débitos {gran_total[0]:,.2f}; créditos {gran_total[1]:,.2f})."
            )
    if not filas:
        lectura.bloqueos.append("El libro auxiliar no tiene movimientos para importar.")
    if max_filas is not None:
        lectura.filas = filas[:max_filas]
    lectura.info = {
        "formato": "libro auxiliar World Office (jerárquico)", "movimientos_importados": len(filas),
        "cuentas": len(mov), "filas_ignoradas": sum(ignoradas.values()), "ignoradas_detalle": ignoradas,
        "debitos_importados": str(deb), "creditos_importados": str(cre), "totales_cuadran": not lectura.bloqueos,
    }
    return lectura


# ---------- Extracto de Bancolombia en PDF ----------
_MONTO = r"-?\d{1,3}(?:,\d{3})*\.\d{2}"
_LINEA_BANCO = re.compile(rf"^\s*(\d{{1,2}})/(\d{{2}})\s+(.+?)\s+({_MONTO})\s+({_MONTO})\s*$")
_ANIO_RANGO = re.compile(r"DESDE:\s*(\d{4})/(\d{2})/(\d{2})\s+HASTA:\s*(\d{4})/(\d{2})/(\d{2})")


def _monto(s):
    return Decimal(s.replace(",", ""))


def _resumen_extracto(texto):
    out = {}
    for clave, etiqueta in (("anterior", "SALDO ANTERIOR"), ("abonos", "TOTAL ABONOS"),
                            ("cargos", "TOTAL CARGOS"), ("actual", "SALDO ACTUAL")):
        m = re.search(rf"{etiqueta}\s+\$\s+(\d{{1,3}}(?:,\d{{3}})*\.\d{{2}})", texto)
        if m:
            out[clave] = _monto(m.group(1))
    return out


def leer_extracto_bancolombia_pdf(contenido: bytes, max_filas=None):
    """Extracto de cuenta corriente de Bancolombia en PDF. Devuelve None si el PDF no tiene esa forma.

    Las fechas del extracto no traen año (1/09): se toma del rango «DESDE … HASTA». Cada movimiento se verifica con su
    saldo (saldo anterior + valor = saldo) y el total con el resumen de la primera página.
    """
    try:
        from pypdf import PdfReader

        paginas = [p.extract_text(extraction_mode="layout") or "" for p in PdfReader(io.BytesIO(contenido)).pages]
    except Exception:  # noqa: BLE001 - PDF dañado o cifrado
        return None
    texto = "\n".join(paginas)
    rango = _ANIO_RANGO.search(texto)
    if not rango or "ESTADO DE CUENTA" not in texto.upper():
        return None
    desde = date(int(rango[1]), int(rango[2]), int(rango[3]))
    hasta = date(int(rango[4]), int(rango[5]), int(rango[6]))
    resumen = _resumen_extracto(texto)
    filas, errores = [], []
    for n, linea in enumerate(texto.splitlines(), start=1):
        m = _LINEA_BANCO.match(linea)
        if not m:
            continue
        dia, mes = int(m[1]), int(m[2])
        fecha = None
        for anio in {desde.year, hasta.year}:
            try:
                cand = date(anio, mes, dia)
            except ValueError:
                continue
            if desde <= cand <= hasta:
                fecha = cand
        if fecha is None:
            errores.append({"fila": n, "problemas": [f"Fecha {dia}/{mes:02d} fuera del rango del extracto"]})
            continue
        partes = re.split(r"\s{2,}", m[3].strip())
        filas.append({
            "fecha": fecha, "descripcion": partes[0], "referencia": " ".join(partes[1:])[:60],
            "valor": _monto(m[4]), "saldo": _monto(m[5]), "fila": n,
        })
    lectura = Lectura(columnas=["Fecha", "Descripción", "Valor", "Saldo"], filas=filas, errores=errores,
                      total_filas=len(filas) + len(errores))
    if not filas:
        lectura.bloqueos.append("No encontré movimientos en el PDF (¿es un extracto de Bancolombia con texto seleccionable?).")
        return lectura
    saldo = resumen.get("anterior")
    saltos = 0
    for f in filas:
        if saldo is not None and abs(saldo + f["valor"] - f["saldo"]) > Decimal("0.01"):
            saltos += 1
        saldo = f["saldo"]
    if saltos:
        lectura.bloqueos.append(
            f"{saltos} movimiento(s) no encadenan con su saldo: el PDF pudo leerse incompleto. Revisa el extracto."
        )
    abonos = sum((f["valor"] for f in filas if f["valor"] > 0), Decimal("0"))
    cargos = -sum((f["valor"] for f in filas if f["valor"] < 0), Decimal("0"))
    for clave, calculado, nombre in (("abonos", abonos, "total abonos"), ("cargos", cargos, "total cargos")):
        if clave in resumen and abs(resumen[clave] - calculado) > Decimal("0.01"):
            lectura.bloqueos.append(
                f"La suma de movimientos ({calculado:,.2f}) no coincide con el {nombre} del resumen ({resumen[clave]:,.2f})."
            )
    if "actual" in resumen and abs(filas[-1]["saldo"] - resumen["actual"]) > Decimal("0.01"):
        lectura.bloqueos.append(
            f"El último saldo ({filas[-1]['saldo']:,.2f}) no coincide con el saldo actual del resumen ({resumen['actual']:,.2f})."
        )
    if not resumen:
        lectura.avisos.append("No pude leer el resumen de la primera página; solo se verificó el encadenamiento de saldos.")
    if max_filas is not None:
        lectura.filas = filas[:max_filas]
    lectura.info = {
        "formato": "extracto Bancolombia (PDF)", "movimientos_importados": len(filas), "abonos": str(abonos),
        "cargos": str(cargos), "saldo_anterior": str(resumen.get("anterior", "")), "saldo_final": str(filas[-1]["saldo"]),
        "desde": desde.isoformat(), "hasta": hasta.isoformat(), "totales_cuadran": not lectura.bloqueos,
    }
    return lectura
