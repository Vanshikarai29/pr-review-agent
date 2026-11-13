"""Seeded-bug test cases for measuring the reviewer.

Each case is a small new Python file. `bug_contains` is a snippet found on the buggy line;
the harness converts it to a line number. Cases with bug_contains=None are CLEAN: any
medium-or-higher finding on them counts as a false positive.
"""

CASES = [
    {
        "id": "sql_injection",
        "path": "app/db.py",
        "bug_contains": "SELECT * FROM users",
        "source": '''import sqlite3


def get_user(conn: sqlite3.Connection, username: str):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    return conn.execute(query).fetchall()
''',
    },
    {
        "id": "hardcoded_secret",
        "path": "app/client.py",
        "bug_contains": "API_KEY =",
        "source": '''import requests


API_KEY="my-hardcoded-api-key-12345"


def fetch_orders():
    headers = {"Authorization": API_KEY}
    return requests.get("https://api.example.com/orders", headers=headers, timeout=10).json()
''',
    },
    {
        "id": "off_by_one",
        "path": "app/stats.py",
        "bug_contains": "range(len(values) - window)",
        "source": '''def moving_average(values, window):
    """Return the moving average of `values` for every full window."""
    result = []
    for i in range(len(values) - window):
        result.append(sum(values[i:i + window]) / window)
    return result
''',
    },
    {
        "id": "mutable_default",
        "path": "app/tags.py",
        "bug_contains": "def add_tag",
        "source": '''def add_tag(item, tags=[]):
    tags.append(item)
    return tags
''',
    },
    {
        "id": "swallowed_exception",
        "path": "app/config.py",
        "bug_contains": "except:",
        "source": '''import json


def load_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        pass
''',
    },
    {
        "id": "none_dereference",
        "path": "app/users.py",
        "bug_contains": "email.split",
        "source": '''def email_domain(user: dict) -> str:
    email = user.get("email")
    return email.split("@")[1]
''',
    },
    {
        "id": "resource_leak",
        "path": "app/files.py",
        "bug_contains": "f = open(path)",
        "source": '''def count_lines(path):
    f = open(path)
    data = f.read()
    return len(data.splitlines())
''',
    },
    {
        "id": "command_injection",
        "path": "app/net.py",
        "bug_contains": "os.system",
        "source": '''import os


def ping(host):
    os.system("ping -c 1 " + host)
''',
    },
    {
        "id": "clean_parametrized_query",
        "path": "app/safe_db.py",
        "bug_contains": None,
        "source": '''import sqlite3


def get_user(conn: sqlite3.Connection, username: str) -> list[tuple]:
    """Fetch users by name using a parametrized query."""
    return conn.execute("SELECT id, name FROM users WHERE name = ?", (username,)).fetchall()
''',
    },
    {
        "id": "clean_context_manager",
        "path": "app/safe_files.py",
        "bug_contains": None,
        "source": '''def count_lines(path: str) -> int:
    """Count the lines in a text file."""
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)
''',
    },
]
