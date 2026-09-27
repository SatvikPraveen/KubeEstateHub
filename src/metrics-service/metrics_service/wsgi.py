import logging
import os

from .app import create_app

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
app = create_app()
