from reviewer.config import Config
from reviewer.llm import LLMError
from reviewer.orchestrator import dedupe, review_diff
from reviewer.models import Finding
from reviewer.report import MARKER, render_markdown

DIFF = "\n".join(
    [
        "diff --git a/app.py b/app.py",
        "--- a/app.py",
        "+++ b/app.py",
        "@@ -0,0 +1,4 @@",
        "+import sqlite3",
        "+def get(conn, name):",
        '+    q = "SELECT * FROM t WHERE n = \'" + name + "\'"',
        "+    return conn.execute(q).fetchall()",
    ]
)

CFG = Config(gemini_api_key="x", request_delay=0, use_llm_summary=False)


def finding(file="app.py", line=3, **kw):
    base = {
        "file": file,
        "line": line,
        "severity": "high",
        "title": "SQL injection",
        "explanation": "User input is concatenated into SQL.",
        "suggestion": "Use parameters.",
    }
    base.update(kw)
    return base


class FakeLLM:
    """Returns canned JSON. Behaviour is chosen from the ROLE line of the system prompt."""

    def __init__(self, per_role=None, fail_roles=()):
        self.per_role = per_role or {}
        self.fail_roles = set(fail_roles)
        self.calls = 0

    def generate_json(self, system, prompt):
        self.calls += 1
        role = system.split("\n", 1)[0].replace("ROLE: ", "").split()[0]
        if role in self.fail_roles:
            raise LLMError("boom")
        return self.per_role.get(role, {"findings": []})


def test_valid_finding_is_kept():
    llm = FakeLLM({"security": {"findings": [finding()]}})
    result = review_diff(DIFF, llm, CFG)
    assert len(result.findings) == 1
    assert result.findings[0].category == "security"
    assert result.files_reviewed == ["app.py"]
    assert result.llm_calls == 3  # bug + security + style


def test_hallucinated_file_and_line_are_dropped():
    llm = FakeLLM(
        {
            "bug": {
                "findings": [
                    finding(file="does_not_exist.py"),
                    finding(line=999),
                    finding(line="not-a-number"),
                    {"nonsense": True},
                ]
            }
        }
    )
    assert review_diff(DIFF, llm, CFG).findings == []


def test_line_number_snaps_to_nearest_added_line():
    llm = FakeLLM({"bug": {"findings": [finding(line=6)]}})  # 6 is off by one from line 5? snaps to 4
    result = review_diff(DIFF, llm, CFG)
    assert result.findings and result.findings[0].line in {4, 5}


def test_same_issue_from_several_agents_is_deduplicated():
    same = {"findings": [finding()]}
    llm = FakeLLM({"bug": same, "security": same, "style": same})
    assert len(review_diff(DIFF, llm, CFG).findings) == 1


def test_one_failing_agent_does_not_sink_the_review():
    llm = FakeLLM({"security": {"findings": [finding()]}}, fail_roles={"bug"})
    result = review_diff(DIFF, llm, CFG)
    assert len(result.findings) == 1
    assert any("bug agent failed" in e for e in result.errors)


def test_step_limit_is_enforced():
    cfg = Config(gemini_api_key="x", request_delay=0, use_llm_summary=False, max_llm_calls=2)
    llm = FakeLLM()
    result = review_diff(DIFF, llm, cfg)
    assert llm.calls == 2
    assert result.truncated


def test_unknown_severity_becomes_low():
    llm = FakeLLM({"bug": {"findings": [finding(severity="catastrophic")]}})
    assert review_diff(DIFF, llm, CFG).findings[0].severity == "low"


def test_dedupe_keeps_most_severe_and_sorts():
    a = Finding("a.py", 1, "low", "style", "x", "")
    b = Finding("a.py", 1, "high", "style", "x", "")
    c = Finding("b.py", 2, "critical", "security", "y", "")
    out = dedupe([a, b, c])
    assert [f.severity for f in out] == ["critical", "high"]


def test_report_contains_marker_and_findings():
    llm = FakeLLM({"security": {"findings": [finding()]}})
    md = render_markdown(review_diff(DIFF, llm, CFG), "test-model")
    assert md.startswith(MARKER)
    assert "app.py:3" in md and "SQL injection" in md


def test_report_for_clean_pr():
    md = render_markdown(review_diff(DIFF, FakeLLM(), CFG))
    assert "No issues found" in md
