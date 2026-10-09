"""Pruebas contra PostgreSQL (CI). Usa DATABASE_URL_PG."""
import os

import dj_database_url  # noqa: E402

from .settings_test import *  # noqa: F403

DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL_PG"])}
