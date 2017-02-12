import os

import nbformat
from flask import make_response, redirect, render_template, url_for
from nbconvert import HTMLExporter

from . import app
from .globals import PYNB_MIME_TYPE
from .viewmodel import (find_assignment, get_assignment_notebook, get_combined_notebook, get_source_repos,
                        update_repo_assignments)


# Routes
#

@app.route('/')
def index():
    repos = get_source_repos()
    if len(repos) == 1:
        return redirect(url_for('assignment_repo', repo_id=repos[0].id))
    else:
        return render_template('index.html', repos=repos)


@app.route('/assignment_repo/<repo_id>')
def assignment_repo(repo_id):
    assignment_repo, responses = update_repo_assignments(repo_id)
    return render_template(
        'assignment_repo.html',
        classroom_owner=assignment_repo.owner,
        assignment_repo=assignment_repo,
        assignments=sorted(assignment_repo.assignments, key=lambda a: a.name or ''),
        student_responses=sorted(responses, key=lambda d: (d['user'].fullname or d['user'].login).lower()))


# HTML from HTMLExporter.from_notebook_node requests this
@app.route('/assignment/custom.css')
def empty():
    return ''


@app.route('/assignment/<assignment_id>')
def assignment(assignment_id):
    assignment = find_assignment(assignment_id)
    return render_template('assignment.html', assignment=assignment, classroom_owner=assignment.repo.owner)


@app.route('/assignment/<assignment_id>.ipynb.html')
def assignment_notebook(assignment_id):
    return HTMLExporter().from_notebook_node(get_assignment_notebook(assignment_id))


@app.route('/assignment/<assignment_id>/combined.ipynb.html')
def combined_assignment(assignment_id):
    model = get_combined_notebook(assignment_id)
    return HTMLExporter().from_notebook_node(model.collated_nb)


@app.route('/assignment/<assignment_id>/combined.ipynb')
def download_combined_assignment(assignment_id):
    model = get_combined_notebook(assignment_id)
    collated_nb_name = '%s-combined.%s' % os.path.splitext(os.path.basename(model.assignment_path))

    response = make_response(nbformat.writes(model.collated_nb))
    response.headers['Content-Disposition'] = "attachment; filename*=utf-8''%s" % collated_nb_name
    response.headers['Content-Type'] = PYNB_MIME_TYPE
    return response


@app.route('/assignment/<assignment_id>/answer_status.html')
def assignment_answer_status(assignment_id):
    status = get_combined_notebook(assignment_id).answer_status
    return render_template(
        '_answer_status.html',
        q_names=[a for a, _ in status],
        s_logins=sorted(status[0][1].keys() if status else []),
        q_status=status
    )
