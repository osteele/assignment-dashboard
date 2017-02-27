# Usage without Docker

These are the setup and usage instructions without Docker.

See the project README for instructions using Docker.

## Setup

### 1. Install Python

Install Python 3.5 or greater. (Lesser versions of Python 3 will likely work but are untested. Python 2 is right out.)

### 2. Install required packages

Install [sqlite3](https://www.sqlite.org).

Then:

    $ pip3 install -r requirements.txt
    $ pip3 install --process-dependency-links -e .

Depending on how Python is installed, you may need to prefix `pip3 install …` by `sudo`.


### 3. Retrieve a GitHub personal API token

[Create a personal GitHub API token](https://github.com/blog/1509-personal-api-tokens)
and set the `GITHUB_API_TOKEN` environment variable to this value.


### 4. Initialize the database

    $ env FLASK_APP=assignment_dashboard flask initdb

### 5. Add an assignment repository

    $ env FLASK_APP=assignment_dashboard add_repo repo_owner/repo_name


## Usage

The admin tasks update the project database from GitHub.
The web application browses the data in this database.

### Admin Tasks

#### Update the database

    $ env FLASK_APP=assignment_dashboard flask updatedb

This picks up new commits.

This will take a while to run the first time.
The next time it will skip commits that have already been ingested*, and will run faster.
It also saves its work one repository at a time (and after each downloaded file),
so if it is interrupted in the middle, it will pick up close to where it left off.


#### Set User Names

      $ env FLASK_APP=assignment_dashboard flask set_usernames usernames.csv

Update user names in the database from the rows in `usernames.csv`.

`usernames.csv` should be a CSV file with a column named "name" or "username",
and a column that contains the string "git" (or mixed-case versions of these
strings).

A subsequent call to `flask updatedb` will replace usernames in the database
by the user's GitHub name if the GitHub name is not empty.


### Run the Web Application

    $ env FLASK_APP=assignment_dashboard flask run

Then browse to <http://localhost:5000>.
