from reviewer.diff_utils import chunk_files, parse_diff, should_review, split_file

SAMPLE = "\n".join(
    [
        "diff --git a/app.py b/app.py",
        "index 111..222 100644",
        "--- a/app.py",
        "+++ b/app.py",
        "@@ -1,4 +1,5 @@",
        " import os",
        "+import sys",
        " ",
        " def main():",
        "-    pass",
        '+    print("hi")',
        "@@ -20,3 +21,4 @@ def other():",
        "     x = 1",
        "+    y = 2",
        "     return x",
        "diff --git a/poetry.lock b/poetry.lock",
        "--- a/poetry.lock",
        "+++ b/poetry.lock",
        "@@ -1,1 +1,2 @@",
        " a",
        "+b",
        "diff --git a/old.py b/old.py",
        "deleted file mode 100644",
        "--- a/old.py",
        "+++ /dev/null",
        "@@ -1,1 +0,0 @@",
        "-gone",
    ]
)


def test_parses_files_and_added_line_numbers():
    files = parse_diff(SAMPLE)
    assert [f.path for f in files] == ["app.py", "poetry.lock", "old.py"]
    assert files[0].added_line_numbers == {2, 5, 22}


def test_skips_lockfiles_and_deleted_files():
    files = parse_diff(SAMPLE)
    assert [should_review(f) for f in files] == [True, False, False]


def test_render_prefixes_new_line_numbers():
    rendered = parse_diff(SAMPLE)[0].render()
    assert "    2 + import sys" in rendered
    assert "   22 +     y = 2" in rendered
    assert "      -     pass" in rendered  # deleted lines carry no number
    assert "   ..." in rendered            # gap between hunks


def test_content_that_looks_like_headers_is_not_misparsed():
    diff = "\n".join(
        [
            "diff --git a/n.txt b/n.txt",
            "--- a/n.txt",
            "+++ b/n.txt",
            "@@ -1,2 +1,2 @@",
            "--- removed line that starts with dashes",
            "+++ added line that starts with pluses",
        ]
    )
    f = parse_diff(diff)[0]
    assert f.path == "n.txt"
    assert f.added_line_numbers == {1}


def test_split_and_chunk_respect_size_limit():
    big = "\n".join(
        ["diff --git a/big.py b/big.py", "--- a/big.py", "+++ b/big.py", "@@ -0,0 +1,200 @@"]
        + [f"+line_{i} = {i}" for i in range(200)]
    )
    fd = parse_diff(big)[0]
    pieces = split_file(fd, 1500)
    assert len(pieces) > 1
    assert all(len(p.render()) <= 1700 for p in pieces)
    chunks = chunk_files(pieces, 1500)
    assert sum(len(c) for c in chunks) == len(pieces)
