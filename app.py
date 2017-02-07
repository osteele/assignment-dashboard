import os

import nbformat
from flask import Flask, make_response, render_template, url_for
from nbconvert import HTMLExporter

from viewmodel import get_assignment_data, get_combined_notebook

PYNB_MIME_TYPE = 'application/x-ipynb+json'

app = Flask(__name__)


@app.route('/')
def home_page():
    data = get_assignment_data()
    return render_template(
        'index.html',
        org_fullname=data.source_repo.owner.fullname,
        org_login=data.source_repo.owner.login,
        repo_name=data.source_repo.name,
        assignments=enumerate(data.assignment_names),
        col_keys=data.assignment_paths,
        rows=data.responses)


@app.route('/assignment/<assignment_id>')
def assignment(assignment_id):
    data = get_assignment_data()
    assignment_name = data.assignment_names[int(assignment_id)]
    assignment_path = data.assignment_paths[int(assignment_id)]
    # missing = [owner for owner, nb in nbs.items() if not nb]
    return render_template(
        'assignment.html',
        classroom_repo=data.source_repo,
        classroom_owner=data.source_repo.owner,
        assignment_name=assignment_name,
        assignment_path=assignment_path,
        collated_html_url=url_for('combined_assignment', assignment_id=assignment_id),
        collated_nb_download_url=url_for('download_combined_assignment', assignment_id=assignment_id),
    )


@app.route('/assignment/<assignment_id>/combined')
def combined_assignment(assignment_id):
    combined_nb, _ = get_combined_notebook(int(assignment_id))
    return HTMLExporter().from_notebook_node(combined_nb)


@app.route('/assignment/<assignment_id>/combined.ipynb')
def download_combined_assignment(assignment_id):
    combined_nb, assignment_path = get_combined_notebook(int(assignment_id))
    combined_nb_name = '%s-combined.%s' % os.path.splitext(os.path.basename(assignment_path))

    response = make_response(nbformat.writes(combined_nb))
    response.headers['Content-Disposition'] = "attachment; filename*=utf-8''%s" % combined_nb_name
    response.headers['Content-Type'] = PYNB_MIME_TYPE
    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = 'PORT' not in os.environ
    app.run(host='127.0.0.1' if debug else '0.0.0.0', debug=debug, port=port)
