import re
from collections import defaultdict

import pandas as pd

from .database import session
from .models import User


def update_names_from_csv(csv):
    df = pd.DataFrame.from_csv(csv, index_col=None)
    name_col = next(col for col in df.columns if re.match(r'(user ?)?names?', col, re.I))
    github_col = next(col for col in df.columns if re.search(r'git', col, re.I))
    logins = set(df[github_col])
    users = {u.login: u for u in session.query(User).filter(User.login.in_(logins))}

    unknown = logins - set(users.keys())
    if unknown:
        print('not in the database:', unknown)

    counts = defaultdict(lambda: 0)
    for _, row in df.iterrows():
        login, name = row[github_col], row[name_col]
        if login not in users:
            counts['not in the database'] += 1
        elif users[login].fullname == name:
            counts['unchanged'] += 1
        else:
            users[login].fullname = name
            counts['updated'] += 1
    session.commit()
    return "; ".join("%d records %s" % (v, k) for k, v in counts.items())
