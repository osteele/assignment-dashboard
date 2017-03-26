import re
from typing import Tuple


def lexituples(s: str) -> Tuple[str]:
    """Return a tuple of strings and ints, for lexicographic comparison."""
    return tuple(int(s) if re.match(r'\d+', s) else s
                 for s in re.split(r'(\d+)', s)
                 if s)
