#!/usr/bin/env python3
"""Compatibility shim — this launcher moved to tools/jupyter_launch.py.

The one-liner published in earlier talks and READMEs points here:

    curl -sSL .../tutorials/jupyter_launch.py | python3 -

Rather than break it, this file fetches and runs the launcher from its new home.
Update your bookmarks to:

    curl -sSL https://raw.githubusercontent.com/adithya-s-k/HuggingEnvs/main/tools/jupyter_launch.py | python3 -
"""
import sys
import urllib.request

NEW_URL = (
    "https://raw.githubusercontent.com/adithya-s-k/HuggingEnvs/main/tools/jupyter_launch.py"
)

print("note: jupyter_launch.py moved to tools/ — fetching from its new home", file=sys.stderr)
with urllib.request.urlopen(NEW_URL) as r:
    source = r.read().decode("utf-8")

exec(compile(source, "jupyter_launch.py", "exec"), {"__name__": "__main__"})
