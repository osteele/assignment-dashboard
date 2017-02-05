import os
import sys

from github import Github

# Globals
#

GITHUB_API_TOKEN = os.environ.get('GITHUB_API_TOKEN', None)
if not GITHUB_API_TOKEN:
    print("warning: GITHUB_API_TOKEN is not defined. API calls are rate-limited.", file=sys.stderr)

gh = Github(GITHUB_API_TOKEN)

source_repo_name = 'sd17spring/ReadingJournal'
organization_name = source_repo_name.split('/')[0]


# get the repos
#

instructor_logins = {user.login for team in gh.get_organization(organization_name).get_teams() for user in team.get_members()}

source_repo = gh.get_repo(source_repo_name)
student_repos = sorted((repo for repo in source_repo.get_forks()
                        if repo.owner.login not in instructor_logins),
                       key=lambda repo: repo.owner.login.lower())
all_repos = [source_repo] + student_repos
[repo.owner.login for repo in all_repos]


# get file hashes
#

file_hashes = {item.sha: (repo, item)
               for repo in all_repos
               for item in repo.get_git_tree(repo.get_commits()[0].sha, recursive=True).tree
               if item.type == 'blob'}
len(file_hashes)


# get file commits
#

repo_commits = [(repo, commit)
                for repo in all_repos
                for commit in repo.get_commits()
                if repo == source_repo or (commit.author == repo.owner and len(commit.parents) == 1)]
len(repo_commits)

# Use a dict, to record only the latest commit for each file
file_commits = {(repo.owner.login, item.filename): (item.sha, commit.last_modified)
                for repo, commit in reversed(repo_commits)
                for item in commit.files}
len(file_commits)
