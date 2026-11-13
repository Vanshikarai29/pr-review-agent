# PR Review Agent

An agentic code reviewer for GitHub pull requests, powered by **Google Gemini**. On every PR,
three specialist agents (bugs, security, style) review the diff, a validator removes
hallucinated findings, and the merged review is posted as one PR comment that is updated on
each push.

Runs as a **GitHub Action**, so it needs no server and costs nothing on a public repo with a
free Gemini API key.

## How it works

```
PR opened / updated
        |
        v
GitHub Action --> fetch diff (GitHub API)
        |
        v
parse diff --> skip lockfiles, binaries, deleted files --> chunk to fit the model
        |
        v
 +--------------+   +------------------+   +--------------+
 | bug agent    |   | security agent   |   | style agent  |   (same code, different prompts)
 +--------------+   +------------------+   +--------------+
        \                  |                   /
         v                 v                  v
   validate: file and line must be a real ADDED line (hallucinations dropped)
        |
        v
 dedupe + rank by severity --> summary agent --> one PR comment (updated, not duplicated)
```

**Reliability guardrails (talk about these in interviews):**
- Hard cap on model calls, files, chunks and findings per PR (`reviewer/config.py`)
- Retries with exponential backoff, request timeout, and a delay that respects free-tier rate limits
- One failing agent does not fail the review; the error is reported in the comment
- Findings must point at real added lines, so invented line numbers are dropped or snapped
- Prompt-injection defence: the diff is treated as untrusted data
- Idempotent comment: a hidden marker lets the bot update its own comment on each push
- Skips silently if no API key is present (fork PRs do not receive secrets)

## Setup (about 10 minutes, free)

1. Get a free API key at https://aistudio.google.com/apikey
2. Push this folder to a GitHub repo (it reviews PRs made against that repo).
3. In the repo: **Settings -> Secrets and variables -> Actions -> New repository secret**
   Name: `GEMINI_API_KEY`, value: your key.
4. Create a branch, change some code, open a pull request. The workflow in
   `.github/workflows/pr-review.yml` posts the review comment.

To review a different repo, copy `reviewer/`, `requirements.txt` and the workflow file into it.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                  # then put your key in it

# Review any unified diff without touching GitHub:
git diff main > my.diff
export GEMINI_API_KEY=...                             # Windows: set GEMINI_API_KEY=...
python -m reviewer.main --diff-file my.diff

# Run the unit tests (no API key or network needed):
python -m pytest
```

## Measure it (this gives you resume numbers)

```bash
python -m evaluation.run_eval
```

Runs the agents on 8 files with seeded bugs (SQL injection, hardcoded secret, off-by-one,
mutable default, swallowed exception, None dereference, resource leak, command injection) and
2 clean files. It reports the detection rate and false positives, and writes
`evaluation/results.json`. Add more cases in `evaluation/cases.py`; 20-30 is a more credible sample.

## Docker

```bash
docker build -t pr-review-agent .
docker run --rm -e GEMINI_API_KEY=... -e GITHUB_TOKEN=... pr-review-agent --repo owner/name --pr 1
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | none | Required |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Change if Google retires or renames the model |
| `REQUEST_DELAY_SECONDS` | `6` | Pause between calls to stay under free-tier limits |
| `MAX_LLM_CALLS` | `14` | Hard step limit per PR |
| `MAX_FILES` / `MAX_CHUNKS` / `MAX_FINDINGS` | `25` / `4` / `15` | Size limits |

## Project layout

```
reviewer/        agents.py (prompts + validation), orchestrator.py, diff_utils.py,
                 llm.py (Gemini wrapper), github_client.py, report.py, main.py
evaluation/      seeded-bug cases and the scoring script
tests/           unit tests with a fake LLM (no network)
.github/workflows/pr-review.yml
```

## Known limitations

- Reviews the diff only, not the whole repository, so it can miss cross-file problems.
- It can be wrong. Findings are suggestions, not gates; the Action never fails your build.
- Free-tier limits and model names change, so check Google's current docs if calls start failing.
- Fork PRs get no review, because GitHub withholds secrets from them.

## Ideas to extend it (good for a second iteration)

- Post inline comments on the exact lines through the PR review API
- Add a "tests" agent that suggests missing test cases
- Fetch surrounding file context for each finding
- Track token usage and cost per PR; add tracing with Langfuse or OpenTelemetry
- Auto-skip PRs labeled `no-review`

## Resume bullet (fill in your real numbers from `run_eval`)

> Built a multi-agent GitHub PR review bot (Python, Gemini API, GitHub Actions, Docker) with
> specialist bug, security and style agents, line-level hallucination validation and call/step
> limits; detected X of 8 seeded bugs (Y%) with Z false positives in evaluation.
