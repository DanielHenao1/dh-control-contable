# Progreso

Actualizado al terminar cada tarea. Para retomar: leer este archivo, `CLAUDE.md` y `docs/decisiones.md`.

## F0 Base y despliegue — P0
- [x] Proyecto Django, configuración por entorno, modelos base (Usuario con roles, Empresa, Periodo, Parámetro con vigencia)
- [x] Login con doble factor (TOTP + códigos de recuperación), cierre automático de sesión, bloqueo de intentos
- [x] RegistroAuditoria de solo inserción (cambios, logins, lecturas sensibles, cierres)
- [x] Docker Compose (Django/gunicorn, PostgreSQL, Redis, Celery, Caddy), `deploy/bootstrap.sh`, copias cifradas
- [x] GitHub Actions con pytest (PostgreSQL) y ruff
- [ ] P0 con datos reales: HTTPS con dominio y restauración de copia (requiere el VPS)

## F1 Cargas y control básico — P1
- [x] Cargas con huella, vista previa, perfiles de mapeo, vigencia, periodos cerrados
- [x] Importadores: balance, auxiliares, facturas (Excel/XML/zip), retenciones, extracto bancario
- [x] Terceros con NIT/DV; reglas de integridad y de terceros; tablero inicial
- [ ] P1 con un balance real de World Office

## F2 Facturas, IVA, retención y calendario — P2
- [x] Cruces DIAN vs contabilidad, conciliación de IVA y retención
- [x] Calendario por regla con festivos, alertas por correo, fechas laborales
- [x] Proyección inicial de renta, IVA y retención
- [ ] P2 con un mes real

## F3 Hallazgos, informes y contratista — P3
- [x] Bandeja de hallazgos con estados, informe mensual PDF/Excel, módulo del contratista
- [ ] P3: primer informe compartido con Ideako

## F4 Renta, ICA y exógena — P4
- [x] Borradores y conciliación fiscal, validación anticipada de exógena, ajuste de la proyección
- [ ] P4: contraste con el contador

## F5 Analítica, predicción e IA
- [x] Indicadores, anomalías (IQR, MAD, Benford), proyecciones con banda, escenarios, simulador de cierre, asistente
- [ ] Revisión con el contador

## Endurecimiento y cierre (última pasada)
- [x] XML de facturas con parser sin entidades externas y límites de tamaño (XXE / zip bomb)
- [x] Excel con neutralización de fórmulas; sesión de 30 min; HSTS; `check --deploy` sin alertas relevantes
- [x] Reglas de cierre (depreciación, provisiones laborales) y comparativo de estados financieros con notas de apoyo
- [x] 100 pruebas (`pytest`) y `ruff check` limpios; migraciones al día

Pendiente solo lo que exige datos reales o decisiones del contador: ver `docs/pendientes.md`.
