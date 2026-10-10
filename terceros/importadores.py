"""Importación del maestro de terceros (World Office o plantilla): actualiza por NIT, llena solo lo vacío y no pisa lo editado."""
from .models import Tercero
from .nit import limpiar_nit, separar_nit_dv
from .servicios import vincular_movimientos

CAMPOS = ("razon_social", "tipo_persona", "regimen", "direccion", "ciudad", "email", "telefono", "ciiu", "dv")


def _tipo_persona(valor):
    v = (valor or "").strip().lower()
    if v.startswith(("j", "pj", "persona j")) or "juridic" in v or "jurídic" in v:
        return Tercero.TipoPersona.JURIDICA
    if v.startswith(("n", "pn", "persona n")) or "natural" in v:
        return Tercero.TipoPersona.NATURAL
    return ""


def importar_terceros(archivo, filas):
    nuevos = actualizados = sin_cambios = distintos = 0
    nit_invalido = []
    for f in filas:
        nit, dv_en_nit = separar_nit_dv(f.get("nit", ""))
        nit = limpiar_nit(nit)
        if not nit or len(nit) > 15:
            nit_invalido.append(str(f.get("nit", ""))[:20])
            continue
        datos = {c: (f.get(c) or "").strip() for c in CAMPOS}
        datos["dv"] = (datos["dv"] or dv_en_nit)[:1]
        datos["tipo_persona"] = _tipo_persona(f.get("tipo_persona"))
        datos["email"] = datos["email"] if "@" in datos["email"] else ""
        datos["ciiu"] = datos["ciiu"][:6]
        t, creado = Tercero.objects.get_or_create(nit=nit, defaults={**{k: v for k, v in datos.items() if v}, "origen": "maestro"})
        if creado:
            nuevos += 1
            continue
        cambios = []
        diferente = False
        for campo, valor in datos.items():
            if not valor:
                continue
            actual = getattr(t, campo)
            if not actual:
                setattr(t, campo, valor)
                cambios.append(campo)
            elif actual.strip().lower() != valor.lower():
                diferente = True
        distintos += int(diferente)
        if cambios:
            t.save(update_fields=cambios + ["actualizado"])
            actualizados += 1
        else:
            sin_cambios += 1
    vinculo = vincular_movimientos(archivo.usuario)
    resumen = {
        "terceros_nuevos": nuevos, "terceros_actualizados": actualizados, "sin_cambios": sin_cambios,
        "con_datos_distintos_no_cambiados": distintos, "nit_invalidos": len(nit_invalido),
        "movimientos_con_nit": vinculo["movimientos"],
    }
    if nit_invalido:
        resumen["ejemplos_nit_invalidos"] = nit_invalido[:10]
    return resumen
