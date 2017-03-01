import github as pygithub
from flask import g, redirect, request, session, url_for

import flask_github

from . import app
from .models import User

# Globals
#


github = flask_github.GitHub(app)


@app.before_request
def before_request():
    g.user = None
    if 'gh_login' in session:
        g.user = User.query.filter(User.login == session['gh_login']).first()


# OAuth Routes
#


@app.route('/login')
def login():
    return github.authorize(scope='read:org')


@app.route('/logout')
def logout():
    session.pop('access_token', None)
    session.pop('gh_login', None)
    return redirect(url_for('index'))


@app.route('/oauth/github/callback')
@github.authorized_handler
def authorized(access_token):
    next_url = request.args.get('next') or url_for('index')
    if access_token is None:
        return redirect(next_url)

    gh = pygithub.Github(access_token)
    user = gh.get_user()
    session['access_token'] = access_token
    session['gh_login'] = user.login
    return redirect(next_url)


@app.route('/debug/user')
def user():
    return str(g.user.login)
    return repr(User.query.get(login=session['gh_login']))
    return str(session['gh_login'])
    from github import Github
    gh = Github(session['access_token'])
    return str(gh.get_user().login)


@app.route('/debug/teams')
def teams():
    gh = Github(session['access_token'])
    user = gh.get_user()
    return ', '.join(map(str, (t.name for t in user.get_orgs())))
