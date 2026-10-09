# Conciliación bancaria (extracto vs auxiliar de la cuenta de banco)

Es un control interno, no un cálculo tributario: no hay norma tributaria que fije el método. Se apoya en el principio de partida doble y en la práctica de conciliar mensualmente el extracto con el libro auxiliar de bancos (Decreto 2420 de 2015, marco técnico NIIF). **Confirma el método con el contador.**

Convención de signos: valor del extracto positivo = ingreso = débito en libros; negativo = egreso = crédito en libros.

Pasos, en orden (`conciliaciones/servicios.py::conciliar_banco`):
1. **Exactas**: mismo valor (± `CONCILIAR_BANCO_PESOS`, por redondeos) y fecha ± `CONCILIAR_BANCO_DIAS`.
2. **Misma cifra, fecha lejana**: el valor coincide pero la fecha no; queda «para revisar».
3. **Gastos bancarios agrupados**: el banco cobra 4x1000, comisiones, IVA, cuotas e intereses partida por partida y en libros se causan en un solo asiento. Si la suma de los cobros (identificados por `CONCILIAR_BANCO_GASTOS`) iguala el asiento de libros (identificado por `CONCILIAR_LIBROS_GASTOS`), se concilian juntos; queda «para revisar».
4. **Sumas**: una partida de un lado es la suma de 2 o 3 del otro (mismo signo); queda «para revisar».

Lo que no cruza se muestra como «solo en el extracto» o «solo en libros».

Parámetros (tabla `Parametro`, con estos valores por defecto si faltan): `CONCILIAR_BANCO_DIAS`=3, `CONCILIAR_BANCO_PESOS`=1, `CONCILIAR_BANCO_GASTOS` y `CONCILIAR_LIBROS_GASTOS` (listas de palabras).

Caso real (septiembre de 2026, DH TRANS-STORAGE): 48 exactas y 23 para revisar —entre ellas 43 cobros del banco por $971.780,88 contra un asiento de gravamen de $971.781,67—, y ningún pendiente.
