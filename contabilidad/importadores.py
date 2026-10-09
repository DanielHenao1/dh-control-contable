from terceros.models import Tercero
from terceros.nit import limpiar_nit, separar_nit_dv

from .models import Cuenta, Movimiento, SaldoCuenta


def _cuenta(codigo, nombre="", cache=None):
    codigo = codigo.strip()
    if cache is not None and codigo in cache:
        c = cache[codigo]
        if nombre and not c.nombre:
            c.nombre = nombre
            c.save(update_fields=["nombre"])
        return c
    c, creada = Cuenta.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
    if not creada and nombre and c.nombre != nombre:
        c.nombre = nombre
        c.save(update_fields=["nombre"])
    if cache is not None:
        cache[codigo] = c
    return c


def importar_balance(archivo, filas):
    cache, vistos, objetos = {}, set(), []
    for f in filas:
        codigo = f["cuenta"].strip()
        if codigo in vistos:  # una fila por cuenta; las repetidas se suman para no perder valores
            for o in objetos:
                if o.cuenta.codigo == codigo:
                    o.debito += f["debito"]
                    o.credito += f["credito"]
                    o.saldo_final += f["saldo_final"]
                    o.saldo_inicial += f.get("saldo_inicial", 0)
            continue
        vistos.add(codigo)
        objetos.append(
            SaldoCuenta(
                periodo=archivo.periodo, archivo=archivo, cuenta=_cuenta(codigo, f.get("nombre", ""), cache),
                saldo_inicial=f.get("saldo_inicial", 0), debito=f["debito"], credito=f["credito"],
                saldo_final=f["saldo_final"],
            )
        )
    SaldoCuenta.objects.bulk_create(objetos)
    return {"cuentas": len(objetos)}


def importar_auxiliar(archivo, filas):
    cache, objetos, nuevos = {}, [], 0
    for f in filas:
        nit, _dv = separar_nit_dv(f.get("nit", ""))
        nit = limpiar_nit(nit)
        if nit:
            t, creado = Tercero.objects.get_or_create(
                nit=nit, defaults={"razon_social": f.get("tercero_nombre", ""), "origen": "auxiliar"}
            )
            nuevos += int(creado)
        objetos.append(
            Movimiento(
                periodo=archivo.periodo, archivo=archivo, fecha=f["fecha"],
                comprobante=f.get("comprobante", ""), documento=f.get("documento", ""),
                cuenta=_cuenta(f["cuenta"], f.get("cuenta_nombre", ""), cache=cache), nit=nit,
                tercero_nombre=f.get("tercero_nombre", "")[:250], descripcion=f.get("descripcion", "")[:300],
                debito=f["debito"], credito=f["credito"],
            )
        )
    Movimiento.objects.bulk_create(objetos, batch_size=2000)
    return {"movimientos": len(objetos), "terceros_nuevos": nuevos}
