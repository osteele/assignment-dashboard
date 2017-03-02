from functools import wraps

from flask import g, redirect, request, url_for

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


def assignment_access_required(f):
    if not app.config['REQUIRE_LOGIN']:
        return f
    @wraps(f)
    def decorated_function(assignment_id, *args, **kwargs):
        if g.user is None or not user_can_read_assignment(g.user, assignment_id):
            return redirect(url_for('login', next=request.url))
        return f(assignment_id, *args, **kwargs)
    return decorated_function

def repo_access_required(f):
    if not app.config['REQUIRE_LOGIN']:
        return f
    @wraps(f)
    def decorated_function(repo_id, *args, **kwargs):
        if g.user is None or not user_can_read_repo(g.user, repo_id):
            return redirect(url_for('login', next=request.url))
        return f(repo_id, *args, **kwargs)
    return decorated_function

def user_can_read_assignment(user, assignment_id):
    assignment = Assignment.get(assignment_id)
    return user_can_read_repo(g.user, assignment.repo_id)

def user_can_read_repo(user, repo_id):
    return repo_id in [repo.id for repo in get_source_repos(user)]
