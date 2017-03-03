import os

from flask import Flask

from .config import BaseConfig

app = Flask(__name__)
app.config.from_object(BaseConfig)

if os.environ.get('FLASK_DEBUG', None):
    from flask_debugtoolbar import DebugToolbarExtension
    toolbar = DebugToolbarExtension(app)
