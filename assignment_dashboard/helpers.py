import re


def lexituples(s):
    """Return a tuple of strings and ints, for lexicographic comparison."""
    return tuple(int(s) if re.match(r'\d+', s) else s
                 for s in re.split(r'(\d+)', s)
                 if s)
