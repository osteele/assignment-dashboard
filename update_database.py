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

import arrow
from github import Github
from sqlalchemy.sql.expression import func

from models import Commit, FileCommit, FileContent, Repo, Session, User
from utils import find_or_create, upsert_all

# Globals
#

REPO_LIMIT = int(os.environ.get('REPO_LIMIT', 0))
COMMIT_LIMIT = int(os.environ.get('COMMIT_LIMIT', 0))

GITHUB_API_TOKEN = os.environ.get('GITHUB_API_TOKEN', None)
if not GITHUB_API_TOKEN:
    print("warning: GITHUB_API_TOKEN is not defined. API calls are rate-limited.", file=sys.stderr)

gh = Github(GITHUB_API_TOKEN)

session = Session()

source_repo_name = os.environ.get('REPO', 'sd17spring/ReadingJournal')
organization_name = source_repo_name.split('/')[0]


# read the repos
#

print('fetching team logins')
instructor_logins = {user.login for team in gh.get_organization(organization_name).get_teams() for user in team.get_members()}

print('fetching repos')
source_repo = gh.get_repo(source_repo_name)
student_repos = [repo for repo in source_repo.get_forks()
                 if repo.owner.login not in instructor_logins]
repos = [source_repo] + student_repos
if REPO_LIMIT:
    repos = repos[:REPO_LIMIT]

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

print('updating repos')
source_repo_instance = find_or_create(session, Repo, owner_id=user_instance_map[source_repo.owner.login].id, name=source_repo.name)
session.commit()
assert source_repo_instance.id

repo_instances = [Repo(owner_id=user_instance_map[repo.owner.login].id, name=repo.name, source_id=source_repo_instance.id)
                  for repo in repos
                  if repo != source_repo]
upsert_all(session, [source_repo_instance] + repo_instances, Repo.owner_id, Repo.name)
session.commit()

repo_instance_map = {(instance.owner_id, instance.name): instance for instance in session.query(Repo)}


# update file contents
#

def get_file_content(repo, item):
    blob = repo.get_git_blob(item.url.split('/')[-1])
    content = blob.content
    if blob.encoding == 'base64':
        content = base64.b64decode(content)
    return content


def is_downloadable(item):
    return any(item.path.endswith(suffix) for suffix in ['.ipynb', '.py', '.md', '.txt'])


print('updating file content')

file_hashes = {item.sha: (repo, item)
               for repo in repos
               for item in repo.get_git_tree(repo.get_commits()[0].sha, recursive=True).tree
               if item.type == 'blob'}

db_file_contents = dict(session.query(FileContent.sha, func.length(FileContent.content)).filter(FileContent.sha.in_(file_hashes)))

file_contents = [FileContent(sha=item.sha, content=get_file_content(repo, item) if is_downloadable(item) else None)
                 for repo, item in file_hashes.values()
                 if item.sha not in db_file_contents or is_downloadable(item) and db_file_contents[item.sha] is None]
print('downloaded %d files' % sum(bool(fc.content) for fc in file_contents))

upsert_all(session, file_contents, FileContent.sha)
session.commit()


# update file commits
#


def parse_git_datetime(s):
    return arrow.get(s, 'ddd, DD MMM YYYY HH:mm:ss ZZZ').datetime


def own_commit(repo, commit):
    return not commit.author or commit.author == repo.owner or commit.author.login == 'web-flow'


logged_commit_shas = {sha for sha, in session.query(Commit.sha)}  # TODO restrict to fetched timespan
print('fetching commits')

repo_commits = [(repo, commit)
                for repo in repos
                for commit in repo.get_commits()
                if commit.sha not in logged_commit_shas]

if COMMIT_LIMIT:
    repo_commits = repo_commits[:COMMIT_LIMIT]

print('processing %d commits; ignoring %d previously processed' % (len(repo_commits), len(logged_commit_shas)))

# Use a dict, to record only the latest commit for each file
file_commit_recs = {(instance_for_repo(repo).id, item.filename): (item.sha, parse_git_datetime(commit.last_modified))
                    for repo, commit in reversed(repo_commits)
                    if repo == source_repo or own_commit(repo, commit)
                    for item in commit.files}
print('processing %d file commits' % len(file_commit_recs))


file_commits = [FileCommit(repo_id=repo_id, path=path, mod_time=mod_time, sha=sha)
                for (repo_id, path), (sha, mod_time) in file_commit_recs.items()]

upsert_all(session, file_commits, FileCommit.repo_id, FileCommit.path)
session.commit()


# update repo commits
#

commit_instances = [Commit(repo_id=instance_for_repo(repo).id, sha=commit.sha, commit_date=parse_git_datetime(commit.last_modified))
                    for repo, commit in repo_commits]
upsert_all(session, commit_instances, Commit.repo_id, Commit.sha)
session.commit()
