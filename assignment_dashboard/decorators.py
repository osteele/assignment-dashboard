from functools import wraps

from flask import abort, g, redirect, request, url_for

from . import app
from .models import Assignment
from .viewmodel import get_source_repos


def login_required(f):
    if not app.config['REQUIRE_LOGIN']:
        return f

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def requires_access(model_name):
    def wrapper(f):
        if not app.config['REQUIRE_LOGIN']:
            return f

        @wraps(f)
        def decorated_function(*args, **kwargs):
            object_id = kwargs[model_name + '_id']
            if g.user is None:
                return redirect(url_for('login', next=request.url))
            if not user_has_access(g.user, model_name, object_id):
                abort(401)
            return f(*args, **kwargs)
        return decorated_function
    return wrapper


def user_has_access(user, model_name, object_id):
    if model_name == 'assignment':
        assignment = Assignment.query.get(object_id)
        model_name, object_id = 'repo', assignment.repo_id
    assert model_name == 'repo'
    return object_id in [repo.id for repo in get_source_repos(user)]
