import os
from datetime import date

import arrow
import nbformat
import pandas as pd
from flask import g, make_response, redirect, render_template, url_for
from nbconvert import HTMLExporter

from . import app
from .database import session
from .decorators import login_required
from .globals import NBFORMAT_VERSION, PYNB_MIME_TYPE
from .models import Repo
from .viewmodel import (find_assignment, get_assignment_responses, get_collated_notebook_with_names,
                        get_combined_notebook, get_source_repos)


# Routes
#

@app.route('/')
@login_required
def index():
    repos = get_source_repos(g.user)
    if len(repos) == 1:
        return redirect(url_for('assignment_repo', repo_id=repos[0].id))
    else:
        return render_template('index.html', repos=repos)


@app.route('/assignment_repo/<int:repo_id>')
@login_required
def assignment_repo(repo_id):
    model = get_assignment_responses(repo_id)
    assignment_repo = model.assignment_repo

    oldest_update_t = session.query(Repo.refreshed_at).order_by(Repo.refreshed_at.asc()).first()
    repo_update_time = arrow.get(oldest_update_t[0]).to(app.config['TZ']) if oldest_update_t else None

    return render_template(
        'assignment_repo.html',
        classroom_owner=assignment_repo.owner,
        assignment_repo=assignment_repo,
        repo_update_time=repo_update_time,
        assignments=model.assignments,
        students=sorted(model.students, key=lambda u: u.display_name.lower()),
        responses=model.responses)


@app.route('/assignment_repo/<int:repo_id>/report.csv')
@login_required
def assignment_repo_csv(repo_id):
    model = get_assignment_responses(repo_id)
    df = pd.DataFrame({(assgn.name or assgn.path):
                       {student.display_name:
                        model.responses[assgn.id][student.user.id].get('status', None)
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
@login_required
def assignment(assignment_id):
    assignment = find_assignment(assignment_id)
    return render_template('assignment.html', assignment=assignment, classroom_owner=assignment.repo.owner)


@app.route('/assignment/<int:assignment_id>.ipynb.html')
@login_required
def assignment_notebook(assignment_id):
    assignment = find_assignment(assignment_id)
    content = assignment.content
    if isinstance(content, bytes):
        content = content.decode()
    nb = nbformat.reads(content, NBFORMAT_VERSION)
    return HTMLExporter().from_notebook_node(nb)


@app.route('/assignment/<int:assignment_id>/collated.ipynb.html')
@login_required
def collated_assignment(assignment_id):
    model = get_combined_notebook(assignment_id)
    return HTMLExporter().from_notebook_node(model.collated_nb)


@app.route('/assignment/<int:assignment_id>/named.ipynb.html')
@login_required
def collated_assignment_with_names(assignment_id):
    nb = get_collated_notebook_with_names(assignment_id)
    return HTMLExporter().from_notebook_node(nb)


@app.route('/assignment/<int:assignment_id>/collated.ipynb')
@login_required
def download_collated_assignment(assignment_id):
    model = get_combined_notebook(assignment_id)
    collated_nb_name = '%s-combined%s' % os.path.splitext(os.path.basename(model.assignment_path))

    response = make_response(nbformat.writes(model.collated_nb))
    response.headers['Content-Disposition'] = "attachment; filename*=utf-8''%s" % collated_nb_name
    response.headers['Content-Type'] = PYNB_MIME_TYPE
    return response


@app.route('/assignment/<int:assignment_id>/answer_status.html')
@login_required
def assignment_answer_status(assignment_id):
    status = get_combined_notebook(assignment_id).answer_status
    return render_template(
        '_answer_status.html',
        q_names=[a for a, _ in status],
        s_logins=sorted(status[0][1].keys() if status else []),
        q_status=status
    )
