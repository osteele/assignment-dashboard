# Contributing

## What to Work On

The [GitHub issues](https://github.com/osteele/assignment-dashboard/issues) lists bugs and enhancement requests.

## How to Work

`scripts/shell` starts a Python REPL with the globals in the `database` and
`models` imported at top-level. This script uses the techniques from
[preconfigured interactive shell](http://flask.pocoo.org/snippets/23/)
and [further improving the shell experience](http://flask.pocoo.org/docs/0.12/shell/#further-improving-the-shell-experience).

Data is stored in a sqlite database in `db/database.db`.
It's stored in the host filesystem, instead of a Docker volume, to make it easier to inspect during development.
To switch database engines, install the engine and Python driver, and set `DATABASE_URL`. The code should be database-agnostic, except that a datetime parsed from a non-ORM `SELECT` result may need to be generalized.
Search the source for `SQLITE3`.

Both the Docker and non-Docker strategies for running the application are set
to reload the application when files are changed. (`FLASK_DEBUG` is set to `1`
to set this for Flask. And, in Docker, the host directory is mounted to `/app`
inside the image.)

## Style

With exceptions listed in `setup.cfg`, code should conform to [PEP8](https://www.python.org/dev/peps/pep-0008/), [PEP257](https://www.python.org/dev/peps/pep-0257/), and the [Google Python Style Guide](http://google.github.io/styleguide/pyguide.html).

You can verify code against these style guides via:

    $ pip3 install -r requirements-dev.txt  # once
    $ flake8 scripts                        # before each commit

or by setting up a [git pre-commit hook](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks) to run the latter command.
