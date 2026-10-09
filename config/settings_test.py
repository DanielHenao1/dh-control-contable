import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
os.environ["DJANGO_DEBUG"] = "1"
os.environ["DATABASE_URL"] = "sqlite://:memory:"

from .settings import *  # noqa: E402,F403

OTP_OBLIGATORIO = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
import tempfile  # noqa: E402

MEDIA_ROOT = tempfile.mkdtemp(prefix="dh-media-")
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
ANTHROPIC_API_KEY = ""
