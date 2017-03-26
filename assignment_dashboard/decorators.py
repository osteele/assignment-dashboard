from functools import wraps
from typing import Callable

from flask import abort, g, redirect, request, url_for

from . import app
from .models import Assignment
from .viewmodel import get_source_repos


def login_required(f: Callable):
    """A view function decorator that requires the user is logged in."""
    if not app.config['REQUIRE_LOGIN']:
        return f

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def requires_access(model_name: str):
    """A view function decorator that guards access to a model.

    Args:
        model_name: The decorated function should take a keyword argument named `model_name` + "_id",
            whose value is database id of the model.
    """
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


def user_has_access(user, model_name: str, object_id: int) -> bool:
    """Determine whether user has access to the specified instance of model_name.

    Arguments:
        model_name: hardcoded to one of 'assignment' or 'repo'

    Returns:
        Return True iff user has access to instance of model_name

    Note:
        This function is used as a helper for `requires_access`on
    """
    if model_name == 'assignment':
        assignment = Assignment.query.get(object_id)
        model_name, object_id = 'repo', assignment.repo_id
    assert model_name == 'repo'
    return object_id in [repo.id for repo in get_source_repos(user)]
