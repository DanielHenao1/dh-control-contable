"""Genera las obligaciones por regla. Nunca copia fechas: las calcula o las toma de una regla verificada."""
from datetime import date

from django.db import models

from empresa.models import Empresa, Parametro

from .dias_habiles import dia_habil_n
from .models import Obligacion, ReglaVencimiento

MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _regla_dia_habil(obligacion, digito, fecha_ref):
    return (
        ReglaVencimiento.objects.filter(
            obligacion=obligacion, modo="dia_habil", digito=digito, vigente_desde__lte=fecha_ref
        )
        .filter(models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=fecha_ref))
        .order_by("-vigente_desde")
        .first()
    )


def calendario_desde():
    """Primera fecha que gestiona el sistema (parámetro CALENDARIO_DESDE). Nada anterior se crea."""
    valor = Parametro.obtener_o("CALENDARIO_DESDE")
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def tiene_empleados():
    """Parámetro TIENE_EMPLEADOS: sin contratos laborales no se generan cesantías ni primas. Por defecto, sí."""
    return (Parametro.obtener_o("TIENE_EMPLEADOS", "si") or "si").strip().lower() not in ("no", "0", "false")


def _crear(tipo, nombre, clave, periodo_texto, regla, anio_v, mes_v, laboral=False, minima=None, **extra):
    fecha, verif, fuente, nota = None, "no_verificada", "", ""
    if regla is not None:
        fecha = dia_habil_n(anio_v, mes_v, regla.dia_habil)
        verif, fuente = regla.verificacion, regla.fuente
    if fecha is not None and minima is not None and fecha < minima:
        return None, False
    else:
        nota = "Falta la regla de vencimiento para el último dígito del NIT; cárgala en Calendario > Reglas."
    obj, creada = Obligacion.objects.get_or_create(
        tipo=tipo, clave=clave,
        defaults=dict(nombre=nombre, periodo_texto=periodo_texto, fecha_limite=fecha, verificacion=verif,
                      fuente=fuente, laboral=laboral, notas=nota, **extra),
    )
    if not creada and obj.estado in ("pendiente", "en_preparacion"):
        # Recalcula fecha y verificación por si cambió la regla; no toca estado ni responsables.
        cambios = {}
        if obj.fecha_limite != fecha:
            cambios["fecha_limite"] = fecha
        if obj.verificacion != verif and obj.verificacion in ("regla", "no_verificada", "estimada"):
            cambios["verificacion"] = verif
        if cambios:
            for k, v in cambios.items():
                setattr(obj, k, v)
            obj.save(update_fields=list(cambios))
    return obj, creada


def generar_obligaciones(anio_desde, anio_hasta, empresa=None):
    empresa = empresa or Empresa.actual()
    if empresa is None:
        raise ValueError("Configura primero la empresa (NIT).")
    d = empresa.ultimo_digito
    creadas = 0
    minima = calendario_desde()

    def reg(*args, **kw):
        nonlocal creadas
        obj, c = _crear(*args, minima=minima, **kw)
        creadas += int(c)

    for anio in range(anio_desde, anio_hasta + 1):
        # Retención en la fuente: mensual, vence el mes siguiente
        for mes in range(1, 13):
            av, mv = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
            regla = _regla_dia_habil("retefuente", d, date(av, mv, 1))
            reg("retefuente", "Retención en la fuente", f"{anio}-{mes:02d}", f"{MESES[mes]} {anio}", regla, av, mv)

        # IVA: periodicidad como parámetro con vigencia
        periodicidad = Parametro.obtener_o("IVA_PERIODICIDAD", "cuatrimestral", fecha=date(anio, 6, 1))
        if periodicidad == "bimestral":
            tramos = [(1, 2, 3), (3, 4, 5), (5, 6, 7), (7, 8, 9), (9, 10, 11), (11, 12, 1)]
        else:
            tramos = [(1, 4, 5), (5, 8, 9), (9, 12, 1)]
        for i, (m1, m2, mv) in enumerate(tramos, start=1):
            av = anio + 1 if mv == 1 else anio
            regla = _regla_dia_habil("iva", d, date(av, mv, 1))
            reg("iva", "IVA", f"{anio}-P{i}", f"{MESES[m1]}-{MESES[m2]} {anio}", regla, av, mv)

        # Renta personas jurídicas: año gravable `anio`, se declara el año siguiente
        r1 = _regla_dia_habil("renta_c1", d, date(anio + 1, 5, 1))
        reg("renta_c1", "Renta personas jurídicas: declaración y 1.ª cuota", f"{anio}", f"AG {anio}", r1, anio + 1, 5)
        r2 = _regla_dia_habil("renta_c2", d, date(anio + 1, 7, 1))
        reg("renta_c2", "Renta personas jurídicas: 2.ª cuota", f"{anio}", f"AG {anio}", r2, anio + 1, 7)

        # Sin fecha publicada / sin verificar
        for tipo, nombre, nota in () if (minima and anio < minima.year) else (
            ("exogena", "Información exógena DIAN", "La DIAN fija las fechas por resolución a fin de año."),
            ("exogena_distrital", "Información exógena distrital (Bogotá)", "La Secretaría Distrital de Hacienda fija las fechas por resolución a mitad de año."),
            ("rub", "Registro de beneficiarios finales (RUB)", "Fecha y norma por confirmar con Ideako."),
        ):
            obj, c = Obligacion.objects.get_or_create(
                tipo=tipo, clave=f"{anio}", defaults=dict(nombre=nombre, periodo_texto=f"AG {anio}", notas=nota)
            )
            creadas += int(c)

        # Fechas laborales (norma laboral, no tributaria)
        laborales = [
            ("cesantias_intereses", "Intereses sobre cesantías", date(anio, 1, 31), f"{anio}-ene"),
            ("cesantias_consignacion", "Consignación de cesantías", date(anio, 2, 14), f"{anio}-feb"),
            ("prima_junio", "Prima de servicios (1.er semestre)", date(anio, 6, 30), f"{anio}-jun"),
            ("prima_diciembre", "Prima de servicios (2.º semestre)", date(anio, 12, 20), f"{anio}-dic"),
        ]
        for tipo, nombre, fecha, clave in laborales:
            if not tiene_empleados() or (minima and fecha < minima):
                continue
            obj, c = Obligacion.objects.get_or_create(
                tipo=tipo, clave=clave,
                defaults=dict(nombre=nombre, periodo_texto=str(anio), fecha_limite=fecha, laboral=True,
                              verificacion="una_fuente", fuente="Código Sustantivo del Trabajo; verificar con el responsable de nómina"),
            )
            creadas += int(c)

        # Renovación de matrícula mercantil
        if minima and date(anio, 3, 31) < minima:
            continue
        obj, c = Obligacion.objects.get_or_create(
            tipo="matricula", clave=f"{anio}",
            defaults=dict(nombre="Renovación de matrícula mercantil", periodo_texto=str(anio),
                          fecha_limite=date(anio, 3, 31), verificacion="una_fuente",
                          fuente="Plazo legal general; confirmar con la Cámara de Comercio"),
        )
        creadas += int(c)

    # Fechas fijas (ICA Bogotá, publicadas por resolución distrital)
    for r in ReglaVencimiento.objects.filter(modo="fecha_fija"):
        if not (anio_desde <= r.fecha.year <= anio_hasta + 1) or (minima and r.fecha < minima):
            continue
        obj, c = Obligacion.objects.get_or_create(
            tipo=r.obligacion, clave=r.periodo_clave,
            defaults=dict(nombre=r.descripcion or r.obligacion, periodo_texto=r.periodo_clave,
                          fecha_limite=r.fecha, verificacion=r.verificacion, fuente=r.fuente),
        )
        creadas += int(c)
    return creadas
