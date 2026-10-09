from .models import MovimientoBanco


def importar_extracto(archivo, filas):
    MovimientoBanco.objects.bulk_create(
        [
            MovimientoBanco(
                periodo=archivo.periodo, archivo=archivo, fecha=f["fecha"],
                descripcion=f.get("descripcion", "")[:300], referencia=f.get("referencia", "")[:60], valor=f["valor"],
            )
            for f in filas
        ]
    )
    return {"movimientos_banco": len(filas)}
