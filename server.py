import os
import re

import arrow
from flask import Flask, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from models import FileCommit, Repo, Session, User

app = Flask(__name__)

session = Session()

source_repo = session.query(Repo).filter(Repo.source_id == None).first()
fork_dict = {fork.owner_id: fork for fork in source_repo.forks}  # FIXME abuse of the ORM

users = session.query(User).all()

assignment_files = sorted({file.path for file in source_repo.files if file.path.endswith('.ipynb')})
assignment_names = [re.sub(r'day(\d+)_reading_journal\.ipynb', r'Journal #\1', path) for path in assignment_files]

files = session.query(FileCommit).filter(FileCommit.path.in_(assignment_files)).options(joinedload(FileCommit.repo)).all()
user_path_files = {(file.repo.owner_id, file.path): file for file in files}

user_cells = {(user.login, user.fullname):
              {pathname: ('missing' if (user.id, pathname) not in user_path_files
                          else 'unchanged' if user_path_files[user.id, pathname] == user_path_files[source_repo.owner.id, pathname]
                          else arrow.get(user_path_files[user.id, pathname].mod_time).humanize())
               for pathname in assignment_files}
              for user in users if user.role == 'student'}


@app.route('/')
def home_page():
    rows = sorted((dict(login=login, fullname=fullname, status=val)
                   for (login, fullname), val in user_cells.items()),
                  key=lambda d: (d['fullname'] or d['login']).lower())
    return render_template('index.html', assignment_names=assignment_names, col_keys=assignment_files, rows=rows)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)
