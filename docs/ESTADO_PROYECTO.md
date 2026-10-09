# Estado del proyecto

Archivo de continuidad entre sesiones. Léelo junto con `CLAUDE.md`, `docs/PROGRESO.md` (checklist por fases) y `docs/decisiones.md`. **Actualízalo al cerrar cada sesión de trabajo.** Última actualización: 9-oct-2026 (decisiones de despliegue).

## Dónde estamos
- Fases F0–F5 del plan construidas y fusionadas en `main` (PR #1). Sistema Django completo con datos sintéticos; **nunca se ha ejecutado con datos reales ni en el VPS**.
- Rama de trabajo de la sesión: `claude/document-review-sd30p4` (reiniciada desde `main` tras el merge).
- **Decisiones del dueño (9-oct-2026):** proveedor VPS = Hostinger (plan por confirmar); subdominio = `contabilidad.dhtransstorage.com.co`; asistente de IA **apagado** hasta terminar las pruebas; **aún sin** proveedor de almacenamiento S3 ni SMTP.
- **Despliegue: pendiente de aprobación.** Plan en `docs/plan_despliegue_hostinger.md`; guía paso a paso en `docs/despliegue.md`. No se ha tocado ningún servidor ni se han pedido credenciales.

## Historial del CI (qué falló y por qué)
| Corrida | Commit | Resultado | Causa | Solución |
|---|---|---|---|---|
| 1 | `899989f` (rama) | ❌ ruff | Imports sin ordenar en archivos nuevos | Corregido con `ruff --fix` en `be7249d` |
| 2 y 3 | `be7249d` (rama y PR) | ✅ | — | — |
| 4 | `bb37121` (`main`, tras el merge) | ❌ pytest contra PostgreSQL | Prueba inestable `test_flujo_de_carga_y_vigencia`: generaba el `.xlsx` dos veces y el archivo lleva marca de tiempo, así que a veces los bytes (y la huella) diferían y no se detectaba el duplicado. Error de la prueba, no del producto | Se genera el contenido una sola vez (commit de esta rama) |

Nota: el merge se hizo viendo verdes las corridas del PR; la corrida sobre `main` falló después por la prueba inestable descrita. Lección: esperar también el CI de `main` antes de dar algo por cerrado.

## Pendiente (en orden)
1. Aprobación del plan de despliegue; confirmar que el plan de Hostinger es VPS. Elegir proveedor S3 y SMTP (S3 es obligatorio antes de datos reales). Ver `plan_despliegue_hostinger.md` §7.
2. Desplegar en el VPS y pasar P0 (HTTPS, 2FA, restauración de copia).
3. P1–P4 con datos reales: ver `docs/pendientes.md` (formatos de World Office/DIAN, parámetros del contador, tarifas, topes, prefijos de cuentas).
4. Tras las pruebas de aceptación con datos sintéticos: decidir si se activa el asistente de IA (`plan_despliegue_hostinger.md` §8).
5. Mejoras fuera del MVP: vendorizar Chart.js, importación asíncrona, API.

## Cómo retomar una sesión
```bash
git fetch origin && git checkout main && git pull
python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
export DJANGO_DEBUG=1
ruff check . && pytest            # debe quedar todo en verde
```
Comandos útiles: `python manage.py cargar_datos_iniciales`, `ejecutar_controles --anio 2026 --mes 9`, `verificar_calendario`, `generar_festivos 2028 2030`.

## Reglas que no se rompen
Ver `CLAUDE.md`. En especial: no inventar tarifas/normas, parámetros solo en tablas con vigencia, la IA nunca calcula, archivos nunca se sobrescriben, nada de datos reales ni secretos en el repositorio.

## Supuestos abiertos (validar con archivos reales)
- Saldo final del balance positivo en la naturaleza de la cuenta; Débitos/Créditos del mes y resultados acumulados (`docs/decisiones.md` #5).
- Prefijos de cuentas (`PUC_*`) con el PUC comercial estándar, por confirmar.
- Tarifa de renta 35 %, tasa mínima 15 % y UVT 2025: cargadas "por verificar".
