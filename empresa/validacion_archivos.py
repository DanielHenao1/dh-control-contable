"""Revisión previa de un archivo antes de guardarlo: ¿es del tipo, la empresa y el periodo que se dijo?

Son heurísticas sobre el contenido: los errores bloquean la carga (quien puede, la fuerza con una casilla
y queda en la auditoría); los avisos se guardan con el archivo y se muestran. No sustituyen la revisión
del contador: un archivo escaneado o con columnas de otro formato solo puede dar un aviso.
"""
import io
import re
from dataclasses import dataclass, field

from .importacion import CAMPOS_POR_TIPO, ErrorImportacion, leer, leer_dataframe, sugerir_mapeo

TABULARES = ("balance", "auxiliar", "facturas_dian", "retenciones", "extracto_banco")
EXTENSIONES = {
    **{t: (".xlsx", ".xlsm", ".xls", ".csv", ".txt") for t in TABULARES},
    "facturas_xml": (".xml", ".zip"),
    "declaracion": (".pdf",),
}
NOMBRES = {
    "balance": "balance de prueba", "auxiliar": "auxiliares", "facturas_dian": "facturas electrónicas (Excel DIAN)",
    "retenciones": "retenciones practicadas", "extracto_banco": "extracto bancario",
}

# Formularios de la DIAN que se pueden subir como declaración (número, nombre y texto que debe aparecer).
FORMULARIOS = {
    "300": ("Formulario 300 · IVA", ("impuesto sobre las ventas", "ventas")),
    "350": ("Formulario 350 · Retención en la fuente", ("retenci",)),
    "110": ("Formulario 110 · Renta personas jurídicas", ("renta",)),
    "ica": ("ICA Bogotá (Secretaría de Hacienda)", ("industria y comercio", "ica")),
    "otro": ("Otra declaración", ()),
}


@dataclass
class Resultado:
    errores: list = field(default_factory=list)  # impiden la carga
    avisos: list = field(default_factory=list)  # se guardan y se muestran

    @property
    def ok(self):
        return not self.errores


def _solo_digitos(valor):
    return re.sub(r"\D", "", str(valor or ""))


def _nit_de(valor):
    """NIT sin DV: quita puntos y guion; si trae DV (10 dígitos con guion) lo descarta."""
    texto = str(valor or "").strip()
    if "-" in texto:
        texto = texto.rsplit("-", 1)[0]
    return _solo_digitos(texto)


def _revisar_extension(tipo, nombre, res):
    esperadas = EXTENSIONES.get(tipo)
    if esperadas and not nombre.lower().endswith(esperadas):
        res.errores.append(
            f"Un archivo de tipo «{tipo.replace('_', ' ')}» debe ser {' / '.join(esperadas)}; subiste «{nombre}»."
        )
        return False
    return True


def _tipos_probables(columnas):
    probables = []
    for t in TABULARES:
        mapeo = sugerir_mapeo(t, columnas)
        if all(c.nombre in mapeo for c in CAMPOS_POR_TIPO[t] if c.requerido):
            probables.append(t)
    return probables


def _revisar_tabular(tipo, nombre, contenido, perfil, periodo, sentido, empresa, res, varios_meses=False):
    try:
        df = leer_dataframe(contenido, nombre, perfil)
    except (ErrorImportacion, ValueError, OSError) as exc:
        res.errores.append(f"No se pudo leer el archivo ({exc}). ¿Está dañado o es de otro formato?")
        return
    except Exception as exc:  # noqa: BLE001 - pandas/openpyxl lanzan tipos variados con archivos dañados
        res.errores.append(f"No se pudo leer el archivo ({type(exc).__name__}). ¿Está dañado o es de otro formato?")
        return
    columnas = [str(c).strip() for c in df.columns]
    if df.dropna(how="all").empty:
        res.errores.append("El archivo no tiene filas con datos.")
        return
    if not (perfil and perfil.mapeo):
        probables = _tipos_probables(columnas)
        if probables and tipo not in probables:
            res.errores.append(
                f"Este archivo parece un {NOMBRES[probables[0]]}, no un {NOMBRES[tipo]}. "
                "Revisa el tipo que elegiste o sube el archivo correcto."
            )
            return
        if not probables:
            res.avisos.append(
                f"No reconocí las columnas como {NOMBRES[tipo]}: tendrás que mapearlas a mano antes de importar."
            )
    try:
        lectura = leer(contenido, nombre, tipo, perfil, max_filas=500)
    except Exception:  # noqa: BLE001 - la lectura completa se vuelve a intentar al previsualizar
        return
    if lectura.faltantes or not lectura.filas:
        return
    if not varios_meses:
        _revisar_periodo(lectura.filas, periodo, res)
    if tipo == "facturas_dian":
        _revisar_nit_facturas(lectura.filas, sentido, empresa, res)


def _revisar_periodo(filas, periodo, res):
    fechas = [f["fecha"] for f in filas if f.get("fecha")]
    if not fechas or periodo is None:
        return
    fuera = sum(1 for d in fechas if (d.year, d.month) != (periodo.anio, periodo.mes))
    if fuera / len(fechas) > 0.5:
        d = min(fechas)
        res.avisos.append(
            f"La mayoría de las fechas ({fuera} de {len(fechas)} revisadas, desde {d:%d/%m/%Y}) no son de "
            f"{periodo.mes:02d}/{periodo.anio}, el periodo que elegiste. Confirma que es el periodo correcto."
        )


def _revisar_nit_facturas(filas, sentido, empresa, res):
    if empresa is None:
        return
    mio = empresa.nit
    if any(f.get("sentido") for f in filas):  # el archivo trae Emitido/Recibido en cada fila
        ajenas = incoherentes = 0
        for f in filas:
            etiqueta = (f.get("sentido") or "").strip().lower()
            es_emisor = _nit_de(f.get("nit_emisor")) == mio
            es_receptor = _nit_de(f.get("nit_receptor")) == mio
            if not (es_emisor or es_receptor):
                ajenas += 1
            elif (etiqueta.startswith("emit") and not es_emisor) or (etiqueta.startswith("recib") and not es_receptor):
                incoherentes += 1
        if ajenas == len(filas):
            res.errores.append(
                f"Ninguna factura revisada pertenece a {empresa.razon_social} (NIT {empresa.nit_formateado}). "
                "Parece un archivo de otra empresa."
            )
        elif ajenas or incoherentes:
            res.avisos.append(
                f"{ajenas + incoherentes} de {len(filas)} filas revisadas no coinciden con su columna Emitido/Recibido "
                "o con el NIT de la empresa."
            )
        return
    emisor = sum(1 for f in filas if _nit_de(f.get("nit_emisor")) == mio)
    receptor = sum(1 for f in filas if _nit_de(f.get("nit_receptor")) == mio)
    if emisor == 0 and receptor == 0:
        res.errores.append(
            f"Ninguna factura revisada pertenece a {empresa.razon_social} (NIT {empresa.nit_formateado}). "
            "Parece un archivo de otra empresa."
        )
    elif sentido == "emitida" and emisor < receptor:
        res.errores.append("Marcaste «emitidas (ventas)» pero la mayoría de las facturas son recibidas (compras).")
    elif sentido == "recibida" and receptor < emisor:
        res.errores.append("Marcaste «recibidas (compras)» pero la mayoría de las facturas son emitidas (ventas).")


def _revisar_xml(nombre, contenido, sentido, empresa, res):
    from facturacion.xml import parsear_archivo

    try:
        filas, errores = parsear_archivo(contenido, nombre)
    except Exception as exc:  # noqa: BLE001
        res.errores.append(f"No se pudo leer el XML o el .zip ({exc}).")
        return
    if not filas:
        res.errores.append("No se encontró ninguna factura electrónica válida en el archivo.")
        return
    if errores:
        res.avisos.append(f"{len(errores)} archivo(s) XML del conjunto no se pudieron leer.")
    _revisar_nit_facturas(filas[:500], sentido, empresa, res)


def _texto_pdf(contenido):
    from pypdf import PdfReader

    try:
        lector = PdfReader(io.BytesIO(contenido))
        return " ".join((p.extract_text() or "") for p in lector.pages[:6]).lower()
    except Exception:  # noqa: BLE001 - PDF dañado o cifrado
        return None


def _revisar_declaracion(contenido, formulario, empresa, res):
    if not contenido.startswith(b"%PDF"):
        res.errores.append("El archivo no es un PDF válido.")
        return
    if not formulario:
        res.errores.append("Elige qué declaración es (formulario 300, 350, 110, ICA u otra).")
        return
    texto = _texto_pdf(contenido)
    if texto is None:
        res.avisos.append("No pude abrir el PDF (¿está cifrado o dañado?): verifica a mano que sea el formulario correcto.")
        return
    if len(texto.strip()) < 40:
        res.avisos.append("El PDF no tiene texto legible (parece escaneado): no pude verificar el formulario ni el NIT.")
        return
    nombre, palabras = FORMULARIOS[formulario]
    if formulario in ("300", "350", "110"):
        otros = [n for n in ("300", "350", "110") if n != formulario and re.search(rf"\bformulario\W+{n}\b|\b{n}\b.*declaraci", texto)]
        propio = re.search(rf"\b{formulario}\b", texto)
        if otros and not propio:
            res.errores.append(
                f"Elegiste {nombre}, pero el PDF parece ser el {FORMULARIOS[otros[0]][0]}. Sube el formulario correcto."
            )
            return
        if not propio:
            res.avisos.append(f"No encontré «{formulario}» en el PDF: confirma que es el {nombre}.")
    if palabras and not any(p in texto for p in palabras):
        res.avisos.append(f"El PDF no menciona «{palabras[0]}»: confirma que es el {nombre}.")
    if empresa is not None and empresa.nit not in _solo_digitos(texto):
        res.avisos.append(f"No encontré el NIT {empresa.nit_formateado} en el PDF: confirma que es de la empresa.")


def verificar(tipo, nombre, contenido, periodo, empresa, perfil=None, sentido="", formulario="", varios_meses=False):
    res = Resultado()
    if not _revisar_extension(tipo, nombre, res):
        return res
    if tipo in TABULARES:
        _revisar_tabular(tipo, nombre, contenido, perfil, periodo, sentido, empresa, res, varios_meses)
    elif tipo == "facturas_xml":
        _revisar_xml(nombre, contenido, sentido, empresa, res)
    elif tipo == "declaracion":
        _revisar_declaracion(contenido, formulario, empresa, res)
    return res
