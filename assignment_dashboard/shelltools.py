"""Scripts/shell imports this module.

It uses the technique from http://flask.pocoo.org/docs/0.12/shell/#further-improving-the-shell-experience
"""

# flake8: noqa

from flask import *

from . import *
from .database import *
from .models import *
from .viewmodel import *
