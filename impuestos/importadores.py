from terceros.models import Tercero
from terceros.nit import limpiar_nit

from .models import Retencion


def importar_retenciones(archivo, filas):
    objetos = []
    for f in filas:
        nit = limpiar_nit(f["nit"])
        Tercero.objects.get_or_create(nit=nit, defaults={"origen": "retencion"})
        objetos.append(
            Retencion(
                periodo=archivo.periodo, archivo=archivo, fecha=f["fecha"], documento=f.get("documento", ""),
                nit=nit, concepto=f["concepto"], base=f["base"],
                tarifa_aplicada=f.get("tarifa_aplicada", 0), retenido=f["retenido"],
            )
        )
    Retencion.objects.bulk_create(objetos, batch_size=2000)
    return {"retenciones": len(objetos)}
