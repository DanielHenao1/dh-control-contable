"""Configuración de Django. Todo lo sensible viene de variables de entorno."""
import os
from pathlib import Path

import dj_database_url
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre, defecto=False):
    return os.environ.get(nombre, "1" if defecto else "0").lower() in ("1", "true", "si", "yes")


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "solo-desarrollo-no-usar-en-produccion"
    else:
        raise RuntimeError("Falta DJANGO_SECRET_KEY en el entorno.")

ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "empresa",
    "terceros",
    "contabilidad",
    "facturacion",
    "impuestos",
    "calendario",
    "conciliaciones",
    "controles",
    "analitica",
    "reportes",
    "asistente",
    "contratistas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "empresa.middleware.UsuarioActualMiddleware",
    "empresa.middleware.RequerirDobleFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "empresa.context_processors.global_",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60
    )
}

AUTH_USER_MODEL = "empresa.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = False  # con True los años salían como '2.026' y rompían enlaces y selectores

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "tablero"
LOGOUT_REDIRECT_URL = "login"

# Doble factor y sesión
OTP_OBLIGATORIO = env_bool("OTP_OBLIGATORIO", True)
OTP_TOTP_ISSUER = "DH Control Contable"
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", 30 * 60))  # cierre automático
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
LOGIN_INTENTOS_MAX = int(os.environ.get("LOGIN_INTENTOS_MAX", 5))
LOGIN_BLOQUEO_SEGUNDOS = int(os.environ.get("LOGIN_BLOQUEO_SEGUNDOS", 15 * 60))

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Celery / Redis
REDIS_URL = os.environ.get("REDIS_URL", "")
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "alertas-vencimiento-diarias": {
        "task": "calendario.tasks.enviar_alertas_vencimiento",
        "schedule": 60 * 60 * 24,
    },
    "resumen-semanal-pendientes": {
        "task": "calendario.tasks.resumen_semanal_pendientes",
        "schedule": crontab(day_of_week=1, hour=7, minute=0),  # lunes 7:00 (hora de Bogotá)
    },
    "vigencias-anuales-de-parametros": {
        "task": "empresa.tasks.asegurar_vigencias_anuales",
        "schedule": 60 * 60 * 24,
    },
    "generar-calendario": {
        "task": "calendario.tasks.generar_calendario_automatico",
        "schedule": 60 * 60 * 24,
    },
    "revision-calendario-diciembre": {
        "task": "calendario.tasks.recordar_revision_calendario",
        "schedule": 60 * 60 * 24,
    },
}
CACHES = (
    {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
    if REDIS_URL
    else {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)

# Correo
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if os.environ.get("EMAIL_HOST")
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)  # puerto 587 (STARTTLS)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)  # puerto 465 (SSL directo); no se puede combinar con TLS
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", 20))  # evita que un servidor SMTP mal configurado deje colgada la petición
PASSWORD_RESET_TIMEOUT = 3 * 24 * 3600  # vigencia de invitaciones y enlaces de recuperación (3 días)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "control@localhost")
ALERTAS_DESTINATARIOS = [e.strip() for e in os.environ.get("ALERTAS_DESTINATARIOS", "").split(",") if e.strip()]
# Resumen semanal de pendientes: si está vacío usa los mismos destinatarios de las alertas.
RESUMEN_SEMANAL_DESTINATARIOS = [e.strip() for e in os.environ.get("RESUMEN_SEMANAL_DESTINATARIOS", "").split(",") if e.strip()]
SITE_URL = os.environ.get("SITE_URL", "")  # para los enlaces de los correos; si falta se toma de DJANGO_CSRF_TRUSTED_ORIGINS

# Asistente de IA (opcional)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ASISTENTE_MODELO = os.environ.get("ASISTENTE_MODELO", "claude-sonnet-5-5")
ASISTENTE_PREGUNTAS_POR_HORA = int(os.environ.get("ASISTENTE_PREGUNTAS_POR_HORA", 30))
