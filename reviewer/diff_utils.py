"""Parse unified diffs and prepare them for an LLM.

Every line sent to the model is prefixed with its line number in the NEW version of the
file. That lets the model cite exact lines, and lets us verify those citations later.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

SKIP_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "go.sum",
}
SKIP_SUFFIXES = (
    ".lock", ".min.js", ".min.css", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf", ".zip", ".woff", ".woff2", ".ttf", ".snap",
)


@dataclass
class DiffLine:
    kind: str            # "add" | "del" | "ctx" | "gap"
    new_no: int | None   # line number in the new file (None for deleted lines and gaps)
    text: str


@dataclass
class FileDiff:
    path: str
    lines: list[DiffLine] = field(default_factory=list)
    is_deleted: bool = False
    is_binary: bool = False

    @property
    def added_line_numbers(self) -> set[int]:
        return {l.new_no for l in self.lines if l.kind == "add" and l.new_no is not None}

    def render(self) -> str:
        out = [f"### FILE: {self.path}"]
        for l in self.lines:
            if l.kind == "gap":
                out.append("   ...")
            elif l.kind == "add":
                out.append(f"{l.new_no:>5} + {l.text}")
            elif l.kind == "ctx":
                out.append(f"{l.new_no:>5}   {l.text}")
            else:
                out.append(f"      - {l.text}")
        return "\n".join(out)


def _path_from_header(line: str) -> str:
    # "diff --git a/foo/bar.py b/foo/bar.py" -> "foo/bar.py"
    return line.split(" b/", 1)[-1].strip() if " b/" in line else line.split()[-1]


def parse_diff(text: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    current: FileDiff | None = None
    in_hunk = False
    new_no = 0

    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            current = FileDiff(path=_path_from_header(raw))
            files.append(current)
            in_hunk = False
            continue
        if current is None:
            continue

        m = HUNK_RE.match(raw)
        if m:
            if current.lines:
                current.lines.append(DiffLine("gap", None, ""))
            new_no = int(m.group(3))
            in_hunk = True
            continue

        if not in_hunk:  # file header lines
            if raw.startswith("deleted file mode"):
                current.is_deleted = True
            elif raw.startswith("Binary files") or raw.startswith("GIT binary patch"):
                current.is_binary = True
            elif raw.startswith("+++ "):
                p = raw[4:].strip()
                if p == "/dev/null":
                    current.is_deleted = True
                else:
                    current.path = p[2:] if p.startswith("b/") else p
            continue

        if raw.startswith("+"):
            current.lines.append(DiffLine("add", new_no, raw[1:]))
            new_no += 1
        elif raw.startswith("-"):
            current.lines.append(DiffLine("del", None, raw[1:]))
        elif raw.startswith("\\"):  # "\ No newline at end of file"
            continue
        else:
            current.lines.append(DiffLine("ctx", new_no, raw[1:] if raw.startswith(" ") else raw))
            new_no += 1

    return files


def should_review(fd: FileDiff) -> bool:
    if fd.is_deleted or fd.is_binary or not fd.added_line_numbers:
        return False
    name = fd.path.rsplit("/", 1)[-1]
    if name in SKIP_NAMES or fd.path.lower().endswith(SKIP_SUFFIXES):
        return False
    return True


def split_file(fd: FileDiff, max_chars: int) -> list[FileDiff]:
    """Split one very large file diff into pieces that each fit in max_chars."""
    if len(fd.render()) <= max_chars:
        return [fd]
    pieces: list[FileDiff] = []
    cur = FileDiff(path=fd.path)
    size = len(fd.path) + 12
    for line in fd.lines:
        n = len(line.text) + 10
        if cur.lines and size + n > max_chars:
            pieces.append(cur)
            cur, size = FileDiff(path=fd.path), len(fd.path) + 12
        cur.lines.append(line)
        size += n
    if cur.lines:
        pieces.append(cur)
    return [p for p in pieces if p.added_line_numbers]


def chunk_files(files: list[FileDiff], max_chars: int) -> list[list[FileDiff]]:
    """Greedily pack file diffs into chunks that fit one LLM call."""
    chunks: list[list[FileDiff]] = []
    cur: list[FileDiff] = []
    size = 0
    for fd in files:
        n = len(fd.render())
        if cur and size + n > max_chars:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(fd)
        size += n
    if cur:
        chunks.append(cur)
    return chunks
