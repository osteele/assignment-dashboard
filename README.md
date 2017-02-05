# Assignment Dashboard

Dispaly the forks of files in a GitHub repository (currently hardwired to `sd17spring/ReadingJournal`), in a web
browser, in tabular format.


## Status

It works for me :-)

The next major steps are to deploy to Heroku, and to hide it behind OAuth so it's safe on the open wave Heroku.

(This doesn't technically reveal FERPA information or anything that's not already discoverable; but it promotes
the information too high for my taste.)


## Setup

### 1. Install Python

Install Python 3.5 or greater. (Lesser versions of Python 3 will likely work but are untested. Python 2 is right out.)

### 2. Install required Python packages

Install sqlite3.

Then:

    $ pip3 install -r requirements.txt

Depending on how Python is installed, you may need to prefix `pip3 install …` by `sudo`.

### 3. Retrieve a GitHub personal API token

[Create a personal GitHub API token](https://github.com/blog/1509-personal-api-tokens)
and set the `GITHUB_API_TOKEN` environment variable to this value.

### 4. Initialize the database

    $ python models.py


## Usage

### Updte the database

    $ python update_database.py

This picks up new commits.

### Run the Web App

    $ python3 server.py

Then browse to <http://localhost:4000>.


## Contributing

## Style

With exceptions listed in `setup.cfg`, code should conform to [PEP8](https://www.python.org/dev/peps/pep-0008/), [PEP257](https://www.python.org/dev/peps/pep-0257/), and the [Google Python Style Guide](http://google.github.io/styleguide/pyguide.html).

You can verify code against these style guides via:

    $ pip3 install -r requirements-dev.txt  # once
    $ flake8 scripts                        # before each commit

or by setting up a [git pre-commit hook](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks) to run the latter command.

The update script are written in a Jupyter-notebook-like style, for easy development with the
[Hydrogen Atom plugin-in](https://atom.io/packages/hydrogen) and the
[Python Visual Studio Code extension](https://github.com/DonJayamanne/pythonVSCode/wiki/Jupyter-(IPython)).

Specifically, it is light on functions and heavy on global variables.

This is an experiment, and may not have legs.
