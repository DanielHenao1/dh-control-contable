# DH Control Contable

Aplicación web (Django + PostgreSQL) que actúa como **segunda verificación independiente** de la contabilidad de DH TRANS-STORAGE SAS. Recibe exportes de World Office y de la DIAN, detecta errores, concilia IVA y retención, calcula borradores propios de impuestos para contrastar, proyecta los impuestos del año y avisa los vencimientos.

**No** reemplaza a World Office, **no** causa ni factura y **no** presenta declaraciones. Todo cálculo es determinista y trazable a una regla; la IA solo redacta explicaciones.

- Plan completo: [`docs/plan.md`](docs/plan.md)
- Reglas y convenciones: [`CLAUDE.md`](CLAUDE.md)
- Decisiones tomadas durante la construcción: [`docs/decisiones.md`](docs/decisiones.md)
- Avance por fases: [`docs/PROGRESO.md`](docs/PROGRESO.md)
- Despliegue en el VPS: [`docs/despliegue.md`](docs/despliegue.md)
- Qué falta validar con datos reales y con el contador: [`docs/pendientes.md`](docs/pendientes.md)
- Fuente normativa de cada regla: [`docs/reglas/`](docs/reglas/)

## Correrlo en local

Requisitos: Python 3.12 o superior. No necesita PostgreSQL ni Redis (usa SQLite y Celery en modo inmediato).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1                 # en Windows PowerShell: $env:DJANGO_DEBUG=1
export OTP_OBLIGATORIO=0              # opcional en local: salta el doble factor
python manage.py migrate
python manage.py cargar_datos_iniciales   # empresa, parámetros (por verificar), calendario, contratista
python manage.py createsuperuser          # luego, en /admin/, ponle rol "Dueño" (campo Rol)
python manage.py runserver
```

Abre <http://127.0.0.1:8000/>. Con el doble factor activo (valor por defecto), el primer ingreso muestra un código QR para tu aplicación de autenticación.

PDF con WeasyPrint necesita las librerías del sistema Pango/HarfBuzz; si faltan, el informe se entrega como HTML imprimible.

Para probar con PostgreSQL y Redis locales: `docker compose -f docker-compose.dev.yml up -d` y
`export DATABASE_URL=postgres://control:control@localhost:5432/control REDIS_URL=redis://localhost:6379/0`.

### Pruebas y estilo

```bash
pytest          # todas las pruebas (datos sintéticos)
ruff check .
```

### Datos de prueba

Solo hay datos sintéticos (`tests/helpers.py`). Para probar la interfaz sube un CSV de ejemplo desde **Cargas**:

```csv
cuenta,debito,credito,saldo_final
1105,1000000,0,1000000
2205,0,900000,900000
4135,0,5000000,5000000
```

## Flujo de uso

1. **Cargas**: subir balance de prueba, auxiliares, facturas DIAN (Excel o XML/zip), retenciones o extracto. Se guarda con huella; ves una vista previa; si los nombres de columna no coinciden, mapeas las columnas una sola vez y queda un perfil reutilizable. Confirmas y el sistema ejecuta los controles.
2. **Tablero**: semáforo del mes, 10 indicadores, vencimientos y gráficos.
3. **Hallazgos**: bandeja con estados (abierto, explicado, corregido), evidencia y fuente normativa.
4. **IVA y retención / Conciliaciones / Renta, ICA, exógena**: propio vs contabilidad vs declarado.
5. **Proyección y simulador**: impuesto estimado al cierre del año con escenarios y “qué pasa si”.
6. **Calendario**: vencimientos calculados por regla, responsables y evidencia de presentación.
7. **Informes**: PDF y Excel mensual. **Contratista**: entregas e informes de Ideako.
