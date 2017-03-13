import os

from flask import Flask
from werkzeug.contrib.cache import RedisCache, SimpleCache

from .config import BaseConfig

app = Flask(__name__)
app.config.from_object(BaseConfig)

if os.environ.get('FLASK_DEBUG'):
    from flask_debugtoolbar import DebugToolbarExtension
    toolbar = DebugToolbarExtension(app)

app.cache = RedisCache(host=app.config['REDIS_HOST']) if 'REDIS_HOST' in app.config else SimpleCache()
