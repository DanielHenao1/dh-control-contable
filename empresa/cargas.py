"""Servicio de cargas: guarda el archivo con su huella, previsualiza y confirma la importación."""
from django.core.files.base import ContentFile
from django.db import transaction

from . import importacion
from .models import ArchivoCargado, Periodo, RegistroAuditoria


class ConflictoDeMeses(Exception):
    """Cargar este archivo dejaría facturas duplicadas porque ya hay otro archivo vigente con esos meses."""


class ArchivoDuplicado(Exception):
    def __init__(self, existente):
        self.existente = existente
        super().__init__("Este archivo ya fue cargado.")


def _importadores():
    from conciliaciones.importadores import importar_extracto
    from contabilidad.importadores import importar_auxiliar, importar_balance
    from facturacion.importadores import importar_facturas
    from impuestos.importadores import importar_retenciones

    return {
        "balance": importar_balance,
        "auxiliar": importar_auxiliar,
        "facturas_dian": importar_facturas,
        "facturas_xml": importar_facturas,
        "retenciones": importar_retenciones,
        "extracto_banco": importar_extracto,
    }


TIPOS_CON_FILAS = {"balance", "auxiliar", "facturas_dian", "facturas_xml", "retenciones", "extracto_banco"}


def registrar_archivo(subido, tipo, periodo: Periodo, usuario, perfil=None, sentido="", formulario="", verificaciones=None, varios_meses=False):
    contenido = subido.read()
    huella = ArchivoCargado.calcular_hash(contenido)
    existente = ArchivoCargado.objects.filter(tipo=tipo, hash_sha256=huella).first()
    if existente:
        raise ArchivoDuplicado(existente)
    periodo.verificar_abierto()
    a = ArchivoCargado(
        tipo=tipo, nombre_original=subido.name, hash_sha256=huella, tamano=len(contenido),
        periodo=periodo, perfil=perfil, usuario=usuario, sentido=sentido, origen="web",
        formulario=formulario, verificaciones=verificaciones or {}, varios_meses=varios_meses,
    )
    a.archivo.save(subido.name, ContentFile(contenido), save=True)
    RegistroAuditoria.registrar(
        "carga", objeto=a, descripcion=f"Carga de {a.get_tipo_display()}: {a.nombre_original}",
        detalle={"hash": huella, "periodo": str(periodo)}, usuario=usuario,
    )
    return a


def verificar_subido(subido, tipo, periodo, perfil=None, sentido="", formulario="", varios_meses=False):
    """Revisión previa (tipo, empresa, periodo) del archivo que se va a subir. No guarda nada."""
    from .models import Empresa
    from .validacion_archivos import verificar

    contenido = subido.read()
    subido.seek(0)
    return verificar(tipo, subido.name, contenido, periodo, Empresa.actual(), perfil, sentido, formulario, varios_meses)


def leer_archivo(archivo: ArchivoCargado, max_filas=None):
    with archivo.archivo.open("rb") as f:
        contenido = f.read()
    if archivo.tipo == "facturas_xml":
        from facturacion.xml import parsear_archivo

        filas, errores = parsear_archivo(contenido, archivo.nombre_original)
        return importacion.Lectura(
            columnas=["(XML)"], filas=filas[:max_filas] if max_filas else filas, errores=errores,
            total_filas=len(filas) + len(errores),
        )
    if archivo.tipo not in TIPOS_CON_FILAS:
        return importacion.Lectura(columnas=[], filas=[], total_filas=0)
    return importacion.leer(contenido, archivo.nombre_original, archivo.tipo, archivo.perfil, max_filas)


def previsualizar(archivo, max_filas=20):
    return leer_archivo(archivo, max_filas=max_filas)


def _sentidos_y_meses(archivo, filas):
    """Pares (sentido, año, mes) que toca el archivo: el sentido sale de cada fila si el archivo trae esa columna."""
    from facturacion.importadores import _no_es_factura, _sentido_de

    por_defecto = archivo.sentido or "recibida"
    pares = set()
    for f in filas:
        if _no_es_factura(f.get("tipo_documento", "")):
            continue
        fecha = f["fecha"] if archivo.varios_meses else None
        anio, mes = (fecha.year, fecha.month) if fecha else (archivo.periodo.anio, archivo.periodo.mes)
        pares.add((_sentido_de(f.get("sentido"), por_defecto), anio, mes))
    return pares


def _verificar_conflicto_de_meses(archivo, filas):
    """Evita duplicar facturas entre un archivo de varios meses y los archivos mensuales (o entre dos de varios meses)."""
    from facturacion.models import Factura

    reemplazados = ArchivoCargado.objects.filter(
        tipo__in={"facturas_dian", "facturas_xml"}, periodo=archivo.periodo, sentido=archivo.sentido, vigente=True,
        varios_meses=archivo.varios_meses,
    ).exclude(pk=archivo.pk)
    ocupados = set()
    for sentido, anio, mes in sorted(_sentidos_y_meses(archivo, filas)):
        consulta = Factura.objects.filter(archivo__vigente=True, sentido=sentido, periodo__anio=anio, periodo__mes=mes)
        if not archivo.varios_meses:
            consulta = consulta.filter(archivo__varios_meses=True)  # entre archivos mensuales manda el reemplazo normal
        if consulta.exclude(archivo__in=reemplazados).exists():
            ocupados.add(f"{sentido}s {mes:02d}/{anio}")
    if ocupados:
        raise ConflictoDeMeses(
            f"Ya hay facturas de {', '.join(sorted(ocupados))} en otro archivo vigente: cargar este las duplicaría. "
            "Usa un solo archivo de varios meses o archivos mensuales, no ambos."
        )


def confirmar(archivo: ArchivoCargado, usuario, omitir_filas_con_error=False):
    """Importa en una transacción. El archivo no cambia; las filas quedan ligadas a él."""
    archivo.periodo.verificar_abierto()
    if archivo.estado == ArchivoCargado.Estado.IMPORTADO:
        return archivo
    if archivo.tipo not in TIPOS_CON_FILAS:
        archivo.estado = ArchivoCargado.Estado.IMPORTADO
        archivo.resumen = {"nota": "Soporte almacenado; no genera registros."}
        archivo.save(update_fields=["estado", "resumen"])
        return archivo
    lectura = leer_archivo(archivo)
    if lectura.faltantes or (lectura.errores and not omitir_filas_con_error) or not lectura.filas:
        archivo.estado = ArchivoCargado.Estado.ERROR
        archivo.errores = (
            [{"fila": 0, "problemas": [f"Falta mapear: {', '.join(lectura.faltantes)}"]}] if lectura.faltantes else []
        ) + lectura.errores[:200]
        if not lectura.filas and not lectura.errores and not lectura.faltantes:
            archivo.errores = [{"fila": 0, "problemas": ["El archivo no tiene filas con datos."]}]
        archivo.save(update_fields=["estado", "errores"])
        return archivo
    if archivo.tipo in ("facturas_dian", "facturas_xml"):
        _verificar_conflicto_de_meses(archivo, lectura.filas)
    with transaction.atomic():
        resumen = _importadores()[archivo.tipo](archivo, lectura.filas)
        resumen["filas_omitidas"] = len(lectura.errores)
        archivo.estado = ArchivoCargado.Estado.IMPORTADO
        archivo.resumen = resumen
        archivo.errores = lectura.errores[:200]
        archivo.save(update_fields=["estado", "resumen", "errores"])
        archivo.marcar_vigente()
        RegistroAuditoria.registrar(
            "importar", objeto=archivo, descripcion=f"Importación confirmada: {archivo}", detalle=resumen, usuario=usuario
        )
    return archivo
