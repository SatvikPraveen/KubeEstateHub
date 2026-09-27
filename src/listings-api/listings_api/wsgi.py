"""Gunicorn entry point: ``gunicorn listings_api.wsgi:app``."""

from .app import create_app

app = create_app()
