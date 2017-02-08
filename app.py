import os

import nbformat
from flask import Flask, make_response, render_template, url_for
from nbconvert import HTMLExporter

from globals import PYNB_MIME_TYPE
from viewmodel import get_assignment_notebook, get_combined_notebook, get_repo_forks_model

app = Flask(__name__, static_url_path='/static')


@app.route('/')
def home_page():
    data = get_repo_forks_model()
    return render_template(
        'index.html',
        classroom_owner=data.source_repo.owner,
        classroom_repo=data.source_repo,
        assignments=enumerate(data.assignment_names),
        student_responses=sorted(data.responses, key=lambda d: (d['user'].fullname or d['user'].login).lower()))


# HTML from HTMLExporter.from_notebook_node requests this
@app.route('/assignment/custom.css')
def empty():
    return ''


@app.route('/assignment/<assignment_id>')
def assignment(assignment_id):
    assignment_id = int(assignment_id)
    model = get_repo_forks_model()
    assignment_name = model.assignment_names[assignment_id]
    assignment_path = model.assignment_paths[assignment_id]
    # missing = [owner for owner, nb in nbs.items() if not nb]
    return render_template(
        'assignment.html',
        classroom_owner=model.source_repo.owner,
        classroom_repo=model.source_repo,
        assignment_name=assignment_name,
        assignment_path=assignment_path,
        assignment_id=assignment_id,
        assignment_nb_html_url=url_for('assignment_notebook', assignment_id=assignment_id),
        collated_nb_html_url=url_for('combined_assignment', assignment_id=assignment_id),
        collated_nb_download_url=url_for('download_combined_assignment', assignment_id=assignment_id),
    )


@app.route('/assignment/<assignment_id>.ipynb.html')
def assignment_notebook(assignment_id):
    return HTMLExporter().from_notebook_node(get_assignment_notebook(int(assignment_id)))


@app.route('/assignment/<assignment_id>/combined.ipynb.html')
def combined_assignment(assignment_id):
    model = get_combined_notebook(int(assignment_id))
    return HTMLExporter().from_notebook_node(model.collated_nb)


@app.route('/assignment/<assignment_id>/combined.ipynb')
def download_combined_assignment(assignment_id):
    model = get_combined_notebook(int(assignment_id))
    collated_nb_name = '%s-combined.%s' % os.path.splitext(os.path.basename(model.assignment_path))

    response = make_response(nbformat.writes(model.collated_nb))
    response.headers['Content-Disposition'] = "attachment; filename*=utf-8''%s" % collated_nb_name
    response.headers['Content-Type'] = PYNB_MIME_TYPE
    return response


@app.route('/assignment/<assignment_id>/answer_status.html')
def assignment_answer_status(assignment_id):
    assignment_id = int(assignment_id)
    status = get_combined_notebook(assignment_id).answer_status
    return render_template(
        '_answer_status.html',
        q_names=[a for a, _ in status],
        s_logins=sorted(status[0][1].keys() if status else []),
        q_status=status
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = 'PORT' not in os.environ
    app.run(host='127.0.0.1' if debug else '0.0.0.0', debug=debug, port=port)
