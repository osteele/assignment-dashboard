import os


class BaseConfig(object):
    DEBUG_TB_INTERCEPT_REDIRECTS = False

    SECRET_KEY = os.environ.get('SECRET_KEY', 'change me in production')

    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/database.db'))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + db_path)
    SQLALCHEMY_ECHO = True if os.environ.get('SQLALCHEMY_ECHO', None) else False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    TZ = os.environ.get('TZ', 'US/Eastern')

    if 'GITHUB_CLIENT_ID' in os.environ:
        REQUIRE_LOGIN = True
        GITHUB_CLIENT_ID = os.environ['GITHUB_CLIENT_ID']
        GITHUB_CLIENT_SECRET = os.environ['GITHUB_CLIENT_SECRET']
    else:
        REQUIRE_LOGIN = False
