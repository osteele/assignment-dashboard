"""
Update the database.

This depends on the database already having been created.

The code is meant to be run as a script.
It's written in notebook format rather than packaged into a function that can be run on demand.
See the README for a discussion.
"""

import base64
import os
import sys
from collections import namedtuple
from datetime import timedelta

import arrow
from github import Github

from .database import session
from .models import Commit, FileCommit, FileContent, Repo, User
from .sql_alchemy_helpers import find_or_create, upsert_all

# globals
#

REPO_LIMIT = int(os.environ.get('REPO_LIMIT', 0))
COMMIT_LIMIT = int(os.environ.get('COMMIT_LIMIT', 0))

REPROCESS_COMMITS = False
REPORT_FILE_SHAS = None  # e.g. 'day3_reading_journal.ipynb'

GITHUB_API_TOKEN = os.environ.get('GITHUB_API_TOKEN', None)
if not GITHUB_API_TOKEN:
    print("warning: GITHUB_API_TOKEN is not defined. API calls are rate-limited.", file=sys.stderr)

gh = Github(GITHUB_API_TOKEN)

source_repo_name = os.environ.get('REPO', 'sd17spring/ReadingJournal')


# helpers
#

RepoCommitFile = namedtuple('RepoCommitItem', 'repo commit file')


def unique_by(iter):
    """Return a list of items with distinct keys. iter yields (item, key)."""
    # return a list rather than a set, because items might not be hashable
    return list({key: item for item, key in iter}.values())


def get_file_content(repo, blob_url):
    blob = repo.get_git_blob(blob_url.split('/')[-1])
    content = blob.content
    if blob.encoding == 'base64':
        content = base64.b64decode(content)
    return content


def is_downloadable_path(path):
    return any(path.endswith(suffix) for suffix in ['.ipynb', '.py', '.md', '.txt'])


def parse_git_datetime(s):
    return arrow.get(s, 'ddd, DD MMM YYYY HH:mm:ss ZZZ').datetime


def own_commit(repo, commit):
    """Return true iff commit appears to be from the repo owner."""
    return not commit.author or commit.author == repo.owner or commit.author.login == 'web-flow'


# read the repos
#

def get_repos(source_repo):
    print('fetching instructor logins')
    organization_name = source_repo_name.split('/')[0]
    instructor_logins = {user.login for team in gh.get_organization(organization_name).get_teams()
                         for user in team.get_members()}

    print('fetching repos')
    student_repos = [repo for repo in source_repo.get_forks()
                     if repo.owner.login not in instructor_logins]
    repos = [source_repo] + student_repos
    if REPO_LIMIT:
        repos = repos[:REPO_LIMIT]
    return repos

source_repo = gh.get_repo(source_repo_name)
repos = get_repos(source_repo)


# read and update students
#

print('updating students')
students = [User(login=repo.owner.login,
                 fullname=repo.owner.name,
                 avatar_url=repo.owner.avatar_url or repo.owner.gravatar_url,
                 role='organization' if repo == source_repo else 'student')
            for repo in repos]
upsert_all(session, students, User.login)
session.commit()

user_instances = list(session.query(User).filter(User.login.in_([repo.owner.login for repo in repos])))
user_instance_map = {instance.login: instance for instance in user_instances}  # FIXME there's surely some way to do this within the ORM


# update repos
#

def instance_for_repo(repo):
    owner = user_instance_map[repo.owner.login]
    return repo_instance_map[owner.id, repo.name]


def update_repos(source_repo):
    print('updating repos')
    source_repo_instance = find_or_create(session, Repo, owner_id=user_instance_map[source_repo.owner.login].id, name=source_repo.name)
    session.commit()
    assert source_repo_instance.id

    repo_instances = [Repo(owner_id=user_instance_map[repo.owner.login].id, name=repo.name, source_id=source_repo_instance.id)
                      for repo in repos
                      if repo != source_repo]
    upsert_all(session, [source_repo_instance] + repo_instances, Repo.owner_id, Repo.name)
    session.commit()

update_repos(source_repo)

repo_instance_map = {(instance.owner_id, instance.name): instance for instance in session.query(Repo)}


# record file commits
#

def get_new_repo_commits(repos):
    logged_commit_shas = {sha for sha, in session.query(Commit.sha)}
    print('fetching commits')

    def compute_since(repo):
        date_tuple = (session.query(FileCommit.mod_time).
                      filter(FileCommit.repo_id == Repo.id).
                      filter(Repo.owner_id == User.id).
                      filter(User.login == repo.owner.login).
                      order_by(FileCommit.mod_time.desc()).
                      first())
        return {'since': date_tuple[0] + timedelta(weeks=-1)} if date_tuple else {}

    repo_commits = [(repo, commit)
                    for repo in repos
                    for commit in repo.get_commits(**compute_since(repo))
                    if REPROCESS_COMMITS or commit.sha not in logged_commit_shas]

    if COMMIT_LIMIT:
        repo_commits = repo_commits[:COMMIT_LIMIT]

    if REPORT_FILE_SHAS:
        print('commits for %s:' % REPORT_FILE_SHAS,
              [item.sha for repo, commit in reversed(repo_commits)
               for item in commit.files
               if item.filename == REPORT_FILE_SHAS])

    print('processing %d new commits; ignoring %d previously processed' % (len(repo_commits), len(logged_commit_shas)))

    return repo_commits

repo_commits = get_new_repo_commits(repos)

file_commit_recs = unique_by(
    (RepoCommitFile(repo, commit, item), (repo.full_name, item.filename))
    for repo, commit in reversed(repo_commits)
    if repo == source_repo or own_commit(repo, commit)
    for item in commit.files)

print('processing %d file commits' % len(file_commit_recs))

if REPORT_FILE_SHAS:
    print('filtered commits for %s:' % REPORT_FILE_SHAS,
          [item.file.sha for item in file_commit_recs if item.file.filename == REPORT_FILE_SHAS])


def download_files(repo_commits, file_commit_recs):
    incoming_file_shas = {item.file.sha for item in file_commit_recs}
    print('incoming_file_shas', incoming_file_shas)
    if not incoming_file_shas:
        return

    db_file_content_shas = {sha for sha, in session.query(FileContent.sha).filter(FileContent.sha.in_(incoming_file_shas))}
    print('db_file_content_shas', db_file_content_shas)
    missing_shas = incoming_file_shas - db_file_content_shas
    print('missing_shas', missing_shas)
    if not missing_shas:
        return

    print('downloading %d files' % len(missing_shas))

    download_commits = ((repo, commit, {item.file.filename
                                        for item in file_commit_recs if item.commit == commit
                                        if item.file.sha not in db_file_content_shas})
                        for repo, commit in repo_commits)

    download_commits = ((repo, commit, paths)
                        for (repo, commit, paths) in download_commits
                        if paths)

    seen = set()
    for repo, commit, paths in download_commits:
        items = [item
                 for item in repo.get_git_tree(repo.get_commits()[0].sha, recursive=True).tree
                 if item.path in paths and item.sha not in seen]
        for item in items:
            print('downloading %s/%s (sha=%s)' % (repo.full_name, item.path, item.sha))
            content = get_file_content(repo, item.url) if is_downloadable_path(item.path) else None
            fc = FileContent(sha=item.sha, content=content)
            session.add(fc)
            session.commit()
            seen |= {item.sha}


def update_file_commits(file_commit_recs):
    file_commits = [FileCommit(repo_id=item.repo.id,
                               path=item.file.filename,
                               mod_time=parse_git_datetime(item.commit.last_modified),
                               sha=item.file.sha)
                    for item in file_commit_recs]
    upsert_all(session, file_commits, FileCommit.repo_id, FileCommit.path)
    session.commit()

download_files(repo_commits, file_commit_recs)
update_file_commits(file_commit_recs)


# record repo commits
#

commit_instances = [Commit(repo_id=instance_for_repo(repo).id, sha=commit.sha, commit_date=parse_git_datetime(commit.last_modified))
                    for repo, commit in repo_commits]
upsert_all(session, commit_instances, Commit.repo_id, Commit.sha)
session.commit()
