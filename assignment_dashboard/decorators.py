from functools import wraps

from flask import g, redirect, request, url_for

from . import app


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if app.config['REQUIRE_LOGIN'] and g.user is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
