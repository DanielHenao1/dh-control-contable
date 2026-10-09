"""NIT colombiano: limpieza y dígito de verificación (módulo 11, pesos DIAN)."""
import re

PESOS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def limpiar_nit(valor):
    """Devuelve solo dígitos del NIT sin DV si viene con guion ('900.902.549-7' -> '900902549')."""
    s = str(valor or "").strip()
    if "-" in s:
        s = s.rsplit("-", 1)[0]
    return re.sub(r"\D", "", s)


def separar_nit_dv(valor):
    """('900902549', '7') a partir de '900.902.549-7' o '900902549'. dv es '' si no viene."""
    s = str(valor or "").strip()
    if "-" in s:
        base, dv = s.rsplit("-", 1)
        return re.sub(r"\D", "", base), re.sub(r"\D", "", dv)
    return re.sub(r"\D", "", s), ""


def calcular_dv(nit):
    digitos = re.sub(r"\D", "", str(nit))
    if not digitos or len(digitos) > len(PESOS):
        raise ValueError("NIT inválido para calcular el DV")
    total = sum(int(d) * PESOS[i] for i, d in enumerate(reversed(digitos)))
    resto = total % 11
    return str(resto if resto in (0, 1) else 11 - resto)


def dv_valido(nit, dv):
    try:
        return calcular_dv(nit) == str(dv)
    except ValueError:
        return False
