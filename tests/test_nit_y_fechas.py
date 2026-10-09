from datetime import date

import pytest

from calendario.dias_habiles import dia_habil_n, festivos_calculados, pascua
from terceros.nit import calcular_dv, dv_valido, limpiar_nit, separar_nit_dv


def test_dv_conocidos():
    assert calcular_dv("900902549") == "7"  # NIT de la empresa según el RUT
    assert calcular_dv("800197268") == "4"  # DIAN
    assert calcular_dv("860034313") == "7"  # Davivienda
    assert dv_valido("900902549", "7")
    assert not dv_valido("900902549", "3")


def test_limpieza_nit():
    assert limpiar_nit("900.902.549-7") == "900902549"
    assert separar_nit_dv("900.902.549-7") == ("900902549", "7")
    assert separar_nit_dv("900902549") == ("900902549", "")
    with pytest.raises(ValueError):
        calcular_dv("")


def test_pascua():
    assert pascua(2026) == date(2026, 4, 5)
    assert pascua(2027) == date(2027, 3, 28)


def test_festivos_2026():
    f = {fecha: nombre for fecha, nombre in festivos_calculados(2026)}
    assert date(2026, 10, 12) in f      # Día de la Raza (ya lunes)
    assert date(2026, 11, 2) in f       # Todos los Santos, 1 nov domingo -> lunes
    assert date(2026, 11, 16) in f      # Independencia de Cartagena, 11 nov miércoles -> lunes
    assert date(2026, 5, 18) in f       # Ascensión
    assert date(2026, 6, 8) in f        # Corpus Christi
    assert date(2026, 6, 15) in f       # Sagrado Corazón
    assert date(2026, 4, 2) in f and date(2026, 4, 3) in f  # Jueves y Viernes Santo
    assert len(f) == 18


@pytest.mark.django_db
def test_dia_habil_15_coincide_con_el_plan():
    # Fechas verificadas en el plan para NIT terminado en 9 (15.º día hábil)
    assert dia_habil_n(2026, 10, 15) == date(2026, 10, 22)
    assert dia_habil_n(2026, 11, 15) == date(2026, 11, 24)
    assert dia_habil_n(2026, 12, 15) == date(2026, 12, 22)
    assert dia_habil_n(2027, 1, 15) == date(2027, 1, 25)
    assert dia_habil_n(2027, 5, 15) == date(2027, 5, 24)
    assert dia_habil_n(2027, 7, 15) == date(2027, 7, 23)
    assert dia_habil_n(2026, 7, 15) == date(2026, 7, 22)  # el plan: el cálculo con festivos da el 22
