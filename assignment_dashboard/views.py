import os
from datetime import date, datetime

import arrow
import nbformat
import pandas as pd
import pytz
from babel.dates import format_timedelta
from flask import flash, g, make_response, redirect, render_template, request, url_for
from nbconvert import HTMLExporter

from . import app
from .database import session
from .decorators import login_required, requires_access
from .globals import NBFORMAT_VERSION, PYNB_MIME_TYPE
from .model_helpers import InvalidInput, update_names_from_csv
from .models import Repo
from .viewmodel import (find_assignment, get_assignment_due_date, get_assignment_responses, get_collated_notebook,
                        get_source_repos, update_assignment_responses)


# Filters
#

@app.template_filter()
def timesince(dt, t0=None):
    t0 = t0 or datetime.now(pytz.utc)
    return format_timedelta(dt - t0)


@app.template_filter()
def datetimeformat(dt, fmt):
    return dt.strftime(fmt)


# Routes
#

@app.route('/')
def index():
    if app.config.get('REQUIRE_LOGIN') and not g.user:
        return render_template('splash.html')

    repos = get_source_repos(g.user)
    if len(repos) == 1:
        return redirect(url_for('assignment_repo', repo_id=repos[0].id))
    else:
        return render_template('index.html', repos=repos)


@app.route('/health')
def health_check():
    return 'success'


@app.errorhandler(401)
def unauthorized_error(error):
    return render_template('401.html'), 401


@app.route('/upload_names', methods=['GET', 'POST'])
@login_required
def upload_names():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part", 'error')
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit a empty part without filename
        if file.filename == '':
            flash("No selected file", 'error')
            return redirect(request.url)
        if file:
            try:
                msgs = update_names_from_csv(file.stream)
                for msg in msgs:
                    flash(msg)
            except UnicodeDecodeError:
                flash("That does not appear to be a CSV file.", 'error')
            except InvalidInput as e:
                flash(str(e), 'error')
            return redirect(url_for('upload_names'))
    return render_template('upload_names.html')


@app.route('/assignment_repo/<int:repo_id>')
@requires_access('repo')
def assignment_repo(repo_id):
    model = get_assignment_responses(repo_id)
    assignment_repo = model.assignment_repo

    oldest_update, = (session.query(Repo.refreshed_at)
                      .filter(Repo.source_id == assignment_repo.id)
                      .order_by(Repo.refreshed_at.asc())
                      .first())
    repo_update_time = arrow.get(oldest_update).to(app.config['TZ']) if oldest_update else None
    # print('t', oldest_update, repo_update_time)

    for assgn in model.assignments:
        get_assignment_due_date(assgn)

    return render_template(
        'assignment_repo.html',
        classroom_owner=assignment_repo.owner,
        assignment_repo=assignment_repo,
        repo_update_time=repo_update_time,
        assignments=model.assignments,
        students=model.students,
        responses=model.responses)


@app.route('/assignment_repo/<int:repo_id>/report.csv')
@requires_access('repo')
def assignment_repo_csv(repo_id):
    model = get_assignment_responses(repo_id)
    df = pd.DataFrame({(assgn.name or assgn.path):
                       {student.display_name:
                        model.responses[assgn.id][student.user.id].get('status')
                        for student in model.students}
                       for assgn in model.assignments},
                      columns=[a.name or a.path for a in model.assignments])
    response = make_response(df.to_csv())
    now = date.today()
    filename = '%s Reading Journal Status.csv' % now.strftime('%Y-%m-%d')
    response.headers['Content-Disposition'] = "attachment; filename*=utf-8''%s" % filename
    response.headers['Content-Type'] = 'text/csv'
    return response


# HTML from HTMLExporter.from_notebook_node requests this
@app.route('/assignment/custom.css')
def empty():
    return ''


@app.route('/assignment/<int:assignment_id>')
@requires_access('assignment')
def assignment(assignment_id):
    assignment = find_assignment(assignment_id)
    return render_template('assignment.html', assignment=assignment, classroom_owner=assignment.repo.owner)


@app.route('/assignment/<int:assignment_id>.ipynb.html')
@requires_access('assignment')
def assignment_notebook(assignment_id):
    assignment = find_assignment(assignment_id)
    content = assignment.content
    if isinstance(content, bytes):
        content = content.decode()
    nb = nbformat.reads(content, NBFORMAT_VERSION)
    return HTMLExporter().from_notebook_node(nb)


@app.route('/assignment/<int:assignment_id>/collated.ipynb.html')
@requires_access('assignment')
def collated_assignment(assignment_id):
    nb = get_collated_notebook(assignment_id, include_usernames=False)
    return HTMLExporter().from_notebook_node(nb)


@app.route('/assignment/<int:assignment_id>/named.ipynb.html')
@requires_access('assignment')
def collated_assignment_with_names(assignment_id):
    nb = get_collated_notebook(assignment_id, include_usernames=True)
    return HTMLExporter().from_notebook_node(nb)


@app.route('/assignment/<int:assignment_id>/collated.ipynb')
@requires_access('assignment')
def download_collated_assignment(assignment_id):
    filename = '%s-combined%s' % os.path.splitext(os.path.basename(model.assignment_path))
    nb = get_collated_notebook(assignment_id, include_usernames=False)

    response = make_response(nbformat.writes(nb))
    response.headers['Content-Disposition'] = "attachment; filename*=utf-8''%s" % filename
    response.headers['Content-Type'] = PYNB_MIME_TYPE
    return response


@app.route('/assignment/<int:assignment_id>/answer_status.html')
@requires_access('assignment')
def assignment_answer_status(assignment_id):
    assignment = update_assignment_responses(assignment_id)
    status_map = [(question.question_name, {(response.user.fullname or response.user.login): response.status
                                            for response in question.responses})
                  for question in sorted(assignment.questions, key=lambda q: q.position)]
    students = status_map[0][1].keys() if status_map else []
    return render_template(
        '_answer_status.html',
        questions=[a for a, _ in status_map],
        students=students,
        status_map=status_map
    )
