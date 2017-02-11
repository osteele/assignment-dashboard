import os

import click
import nbformat
from flask import Flask, make_response, redirect, render_template, url_for
from nbconvert import HTMLExporter

import database
from globals import PYNB_MIME_TYPE
from viewmodel import (find_assignment, get_assignment_notebook, get_combined_notebook, get_source_repos,
                       update_repo_assignments)

app = Flask(__name__, static_url_path='/static')


# Commands
#

@app.cli.command()
def initdb():
    click.echo('Initialize the database.')
    database.initdb()


@app.cli.command()
@click.option('--repo-limit', help='Limit the number of repos.')
@click.option('--commit-limit', help='Limit the number of commits.')
@click.option('--repo', help='The name of the repo in org/name format')
def updatedb(**kwargs):
    click.echo('Update database.')
    for k, v in kwargs.items():
        if v is not None:
            os.environ[k.upper()] = v
    # TODO turn update_database.py into a module function, and call that instead
    import update_database  # noqa: F401


# Routes
#

@app.route('/')
def index():
    repos = get_source_repos()
    if len(repos) == 1:
        return redirect(url_for('source', repo_id=repos[0].id))
    else:
        return render_template('index.html', repos=repos)


@app.route('/source/<repo_id>')
def source(repo_id):
    assignment_repo, responses = update_repo_assignments(repo_id)
    return render_template(
        'source.html',
        classroom_owner=assignment_repo.owner,
        classroom_repo=assignment_repo,
        assignments=sorted(assignment_repo.assignments, key=lambda a: a.name or ''),
        student_responses=sorted(responses, key=lambda d: (d['user'].fullname or d['user'].login).lower()))


# HTML from HTMLExporter.from_notebook_node requests this
@app.route('/assignment/custom.css')
def empty():
    return ''


@app.route('/assignment/<assignment_id>')
def assignment(assignment_id):
    assignment = find_assignment(assignment_id)
    assignment_repo = assignment.repo
    return render_template(
        'assignment.html',
        classroom_owner=assignment_repo.owner,
        classroom_repo=assignment_repo,
        assignment_name=assignment.name,
        assignment_path=assignment.path,
        assignment_id=assignment.id,
        assignment_nb_html_url=url_for('assignment_notebook', assignment_id=assignment.id),
        collated_nb_html_url=url_for('combined_assignment', assignment_id=assignment.id),
        collated_nb_download_url=url_for('download_combined_assignment', assignment_id=assignment.id),
    )


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
