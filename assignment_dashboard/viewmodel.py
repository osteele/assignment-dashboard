""""
"Implements the View-Model of an MVVM architecture.
"""

import hashlib
import pickle
import re
from collections import namedtuple

import arrow
import nbformat
from sqlalchemy.orm import joinedload

from .database import session
from .globals import NBFORMAT_VERSION, PYNB_MIME_TYPE
from .helpers import lexituples
from .models import Assignment, AssignmentQuestion, AssignmentQuestionResponse, FileCommit, Repo
from .nb_helpers import safe_read_notebook
from .nbcollate import NotebookCollator

AssignmentViewModel = namedtuple('AssignmentViewModel', 'assignment_path collated_nb answer_status')
StudentViewModel = namedtuple('StudentViewModel', 'user repo display_name')
AssignmentResponseViewModel = namedtuple('AssignmentResponseViewModel', 'assignment_repo assignments students responses')


def get_source_repos():
    return session.query(Repo).options(joinedload(Repo.owner)).filter(Repo.source_id.is_(None)).all()


def update_content_types(file_contents):
    for fc in file_contents:
        if fc.content_type is None:
            try:
                nbformat.reads(fc.content, as_version=NBFORMAT_VERSION)  # for effect
                fc.content_type = PYNB_MIME_TYPE
            except nbformat.reader.NotJSONError:
                fc.content_type = ''


def compute_assignment_name(path):
    NOTEBOOK_ASSIGNMENT_PATH_RE = r'day(\d+)_reading_journal\.ipynb'
    NOTEBOOK_ASSIGNMENT_PATH_TITLE_TEMPLATE = r'Journal #\1'
    return re.sub(NOTEBOOK_ASSIGNMENT_PATH_RE, NOTEBOOK_ASSIGNMENT_PATH_TITLE_TEMPLATE, path)


def get_assignment_responses(repo_id):
    """Update the repo.assignments from its list of files. Returns a pair (assignment_repo, response_status)."""
    assignment_repo = (session.query(Repo).
                       options(joinedload(Repo.assignments)).
                       options(joinedload(Repo.files)).
                       filter(Repo.id == repo_id).first())
    assert assignment_repo

    # refresh the list of assignments
    assignment_paths = {f.path for f in assignment_repo.files if f.path.endswith('.ipynb')}
    saved_assignments = {assignment.path: assignment for assignment in assignment_repo.assignments}
    if assignment_paths != set(saved_assignments):
        map(session.delete, (assignment for assignment in assignment_repo.assignments if assignment.path not in assignment_paths))
        assignment_repo.assignments = [(saved_assignments.get(path, None) or
                                        Assignment(repo_id=assignment_repo.id, path=path, name=compute_assignment_name(path)))
                                       for path in assignment_paths]
        session.commit()

    # instead of assignment_repo.files, to avoid 1 + N
    # TODO filter to forks of source
    file_commits = session.query(FileCommit).filter(FileCommit.path.in_(assignment_paths)).all()
    user_path_files = {(fc.repo.owner_id, fc.path): fc for fc in file_commits if fc.repo}
    update_content_types([fc.file_content for fc in file_commits if fc.file_content])
    session.commit()

    def file_presentation(file, path):
        if not file:
            return dict(path=path, css_class='danger', status='missing', text='missing', hover='Missing')

        d = dict(path=path, status='done', text=arrow.get(file.mod_time).humanize(), hover=file.mod_time)
        if file.sha == user_path_files[assignment_repo.owner.id, file.path].sha:
            d.update(dict(css_class='danger', status='unchanged', text='unchanged', hover='Unchanged from original'))
        elif not file.file_content:
            d.update(dict(css_class='danger', status='empty', text='empty'))
        elif file.file_content.content_type != PYNB_MIME_TYPE:
            d.update(dict(css_class='warning', status='invalid', text='invalid', hover='Invalid notebook'))
        return d

    assignments = assignment_repo.assignments
    student_repos = assignment_repo.forks
    responses = {assignment.id:
                 {fork.owner.id: file_presentation(user_path_files.get((fork.owner.id, assignment.path), None), assignment.path)
                  for fork in student_repos}
                 for assignment in assignments}

    return AssignmentResponseViewModel(
        assignment_repo,
        sorted(assignments, key=lambda a: lexituples(a.name or a.path)),
        [StudentViewModel(repo.owner, repo, repo.owner.fullname or repo.owner.login)
         for repo in student_repos],
        responses)


def find_assignment(assignment_id):
    """Return an Assignment. The associated repo and repo owner are eagerly loaded."""
    assignment = session.query(Assignment).options(joinedload(Assignment.repo)).filter(Assignment.id == assignment_id).first()
    assert assignment, "no assignment id=%s" % assignment_id
    return assignment


def get_assignment(assignment_id):
    """Update an assignment's related AssignmentQuestions and AssignmentQuestionResponess.

    Returns the assignment.
    """
    assignment = session.query(Assignment). \
        options(joinedload(Assignment.questions)). \
        options(joinedload(Assignment.repo).joinedload(Repo.owner)). \
        filter(Assignment.id == assignment_id). \
        first()
    assert assignment, "no assignment id=%s" % assignment_id

    files = session.query(FileCommit).filter(FileCommit.path == assignment.path)
    files_hash = hashlib.md5(pickle.dumps(sorted(fc.sha for fc in files))).hexdigest()

    if assignment and assignment.md5 == files_hash:
        return assignment

    # .options(undefer(FileCommit.file_content.content)) \
    file_commits = [fc for fc in (session.query(FileCommit)
                                  .options(joinedload(FileCommit.repo))
                                  .options(joinedload(FileCommit.file_content))
                                  .filter(FileCommit.path == assignment.path))
                    if fc.repo]

    notebooks = {fc.repo.owner.login: safe_read_notebook(fc.content.decode())
                 for fc in file_commits
                 if fc.file_content}

    student_nbs = {owner: nb for owner, nb in notebooks.items() if nb and owner != assignment.repo.owner.login}
    assert assignment.repo.owner.login in notebooks, "%s: %s is not in %s" % (assignment.path, assignment.repo.owner.login, notebooks.keys())
    owner_nb = notebooks[assignment.repo.owner.login]

    collation = NotebookCollator(owner_nb, student_nbs)
    answer_status = collation.report_missing_answers()

    student_login_ids = {fc.repo.owner.login: fc.repo.owner.id for fc in file_commits}
    questions = [AssignmentQuestion(assignment_id=assignment_id,
                                    position=position,
                                    question_name=question_name,
                                    responses=[AssignmentQuestionResponse(user_id=student_login_ids[login],
                                                                          status=status)
                                               for login, status in d.items()])
                 for position, (question_name, d) in enumerate(answer_status)]

    assignment.questions = []
    session.commit()

    assignment.nb_content = nbformat.writes(collation.get_combined_notebook(clear_outputs=True))
    assignment.questions = questions
    assignment.md5 = files_hash

    session.add(assignment)
    session.commit()

    return assignment


def get_combined_notebook(assignment_id):
    assignment = get_assignment(assignment_id)
    answer_status = [(question.question_name, {response.user.login: response.status for response in question.responses})
                     for question in sorted(assignment.questions, key=lambda q: q.position)]
    return AssignmentViewModel(assignment.path, nbformat.reads(assignment.nb_content, 4), answer_status)
