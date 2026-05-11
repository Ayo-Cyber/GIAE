# Contributing to GIAE

Thanks for considering a contribution! GIAE welcomes:

- **Bug reports** with a reproducer
- **Feature proposals** with a clear use case
- **Pull requests** for fixes, features, plugins, docs, benchmark genomes
- **Plugin ideas** — new evidence types, new analysis tools, new databases
- **Real-world genome reports** that show edge cases we haven't seen

If you're unsure whether something is in scope, **open a discussion or issue first** rather than spending hours on a PR that might not land. We'd rather chat upstream than reject downstream.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Development setup

### 1. Fork and clone

```bash
git clone git@github.com:YOUR-USERNAME/GIAE.git
cd GIAE
git remote add upstream git@github.com:Ayo-Cyber/GIAE.git
```

### 2. Install in editable mode with dev extras

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev,annotation]"
```

The `dev` extra pulls `pytest`, `pytest-cov`, `mypy`, and `ruff`. The
`annotation` extra pulls `pyrodigal`, which the validation suite uses.

### 3. Confirm the test suite is green before you change anything

```bash
pytest tests/ -q
# Expected: 166 passed
```

If this fails on a clean checkout, something is wrong with the
environment — please open an issue with the full error before pushing
changes.

### 4. (Optional) Install the API extras

If you're working on the REST API, FastAPI side, or worker:

```bash
pip install -e ".[api]"
```

You'll also want Redis and Postgres locally — easiest via Docker:

```bash
docker compose up -d postgres redis
```

---

## Branching & commits

- **Branch from `main`.** Use a descriptive name:
  `fix/conflict-detection-tie-breaker`,
  `feature/foldseek-plugin`,
  `docs/architecture-confidence`.
- **Commit style:** [Conventional Commits](https://www.conventionalcommits.org/)
  is preferred but not enforced.
  ```
  fix(conflict): tie-break on evidence count when scores match
  feat(plugin): add Foldseek structural homology plugin
  docs(architecture): document confidence scoring formula
  test(rescue): cover edge cases for short ORF on circular genomes
  ```
- **Keep commits focused.** One logical change per commit makes review
  faster and history readable.
- **Sign off your commits** if you're contributing on behalf of an
  organisation: `git commit -s -m "..."` (DCO-style).

---

## Code standards

### Style

- **Formatter & linter:** `ruff` (config in [`pyproject.toml`](pyproject.toml)).
- **Type checker:** `mypy` with `strict = true`.
- **Line length:** 100 (set by ruff config).

Run all three before pushing:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/ --ignore-missing-imports
```

CI runs the same commands — fix locally, push green.

### Patterns we use

- **Dataclasses** for value objects (`Evidence`, `Gene`, `Interpretation`).
- **Plugin protocol** for evidence sources — see
  [`src/giae/engine/plugin.py`](src/giae/engine/plugin.py).
- **Field-init dependencies** in the `Interpreter` — finders / scanners
  initialised in `__post_init__`, not on every gene.
- **Explicit confidence math.** Anywhere a score is computed or
  adjusted, the *reason* lives in the reasoning chain.
- **Skip-don't-fail for optional binaries.** Aragorn / Barrnap / Diamond
  / BLAST+ all silently no-op when the binary or DB is absent.

### What to avoid

- Adding **error handling for impossible cases** — trust the type
  system and validate at boundaries only.
- Adding **comments that restate the code.** Comments explain *why*
  (constraint, invariant, workaround). Code explains *what*.
- **Half-finished implementations.** Better to ship a smaller change
  that's complete than a big one with TODOs.
- **Backwards-compat shims for code that didn't ship yet.** If you're
  changing pre-release behaviour, change it.
- **New top-level dependencies** without discussion — open an issue
  first.

---

## Testing

We use **pytest** for everything.

```bash
# Run everything
pytest tests/ -q

# Run a single file
pytest tests/test_nested_orf_finder.py -v

# Run with coverage
pytest --cov=giae --cov-report=term-missing

# Run only the API tests (no Redis needed — TestClient + in-mem SQLite)
pytest tests/test_api.py -v
```

### What to test

| Code change | Tests required |
|---|---|
| New analysis module / plugin | Unit tests for the public API + at least one integration test that calls it from the Interpreter |
| New evidence type | Tests covering aggregation, hypothesis generation, confidence scoring with the new type |
| Confidence-scoring change | Numeric tests showing the *exact* before/after for at least three representative cases |
| New REST endpoint | Tests covering 200, auth-required (401), wrong-user (403), and 404 cases |
| Bug fix | A regression test that fails on `main` and passes on your branch |

### Validation suite

For changes that affect prediction accuracy, run the validation suite
before and after:

```bash
.venv/bin/python post_assets/phase4_validation.py
```

Numbers should match or improve. If F1 drops on any genome, explain why
in the PR description.

---

## Documentation

Docs live in [`docs/`](docs/) and are built with mkdocs-material.

```bash
pip install mkdocs-material
mkdocs serve  # http://localhost:8000
```

**You must update the docs** when you:
- Add or change a CLI flag → [`docs/cli.md`](docs/cli.md)
- Add or change an API endpoint → [`docs/rest_api.md`](docs/rest_api.md)
- Change a confidence-scoring rule → [`docs/architecture.md`](docs/architecture.md)
- Ship a new plugin → [`docs/extending.md`](docs/extending.md) + plugin entry in `README.md`
- Hit a new benchmark milestone → [`docs/benchmarks.md`](docs/benchmarks.md)

PRs that land code without doc updates will be asked to add them.

---

## Pull request process

1. **Branch** from `main`.
2. **Make focused, well-tested changes.** Run lint + type-check + tests
   locally.
3. **Update the [`CHANGELOG.md`](CHANGELOG.md)** under an `## [Unreleased]` heading
   if you don't see one (create it; we'll roll it into the next release).
4. **Open the PR** with:
   - **Summary** — what changed and why (1–3 sentences)
   - **Test plan** — what you ran and what passed
   - **Screenshots / output** — for any user-visible change
   - **Linked issue** — `Fixes #123` if applicable
5. **CI must be green.** ruff, mypy, pytest all pass on Python 3.9 / 3.10 / 3.12.
6. **Address review feedback.** Push more commits; we'll squash on merge.
7. **One reviewer's approval** is enough for most PRs. Architectural
   changes (new evidence types, scoring rule changes, new public APIs)
   need a maintainer's sign-off and usually a discussion issue first.

---

## Adding a plugin

GIAE has a plugin protocol so adding a new evidence source is a
mechanical exercise. The full guide is in
[`docs/extending.md`](docs/extending.md). Highlights:

```python
from giae.engine.plugin import AnalysisPlugin
from giae.models.evidence import Evidence, EvidenceType

class MyPlugin(AnalysisPlugin):
    name = "my_plugin"

    def is_available(self) -> bool:
        # Skip silently if the dependency / DB / binary isn't present.
        ...

    def scan(self, gene) -> list[Evidence]:
        # Return typed evidence. Don't make decisions — just describe what you saw.
        ...
```

Register it in [`src/giae/engine/interpreter.py`](src/giae/engine/interpreter.py)
inside `__post_init__`. Add tests. Add a row to the README "What's in
the box" table. Done.

---

## Reporting bugs

Open an issue using the **Bug report** template. Include:

- **What you ran** — the exact command, the genome size, the flags
- **What you expected** to happen
- **What actually happened** — full traceback if any, output if not
- **Environment** — `giae --version`, Python version, OS
- **A minimal reproducer** if possible — a small genome file or
  sequence that triggers the bug

---

## Proposing a feature

Open an issue using the **Feature request** template. Cover:

- **The problem** you're trying to solve, ideally with a real biology
  scenario
- **What you'd want the API / CLI / output to look like**
- **Why it belongs in core** vs. as a plugin (some features are better
  as plugins; we'll help you decide)

---

## Security issues

Please don't open public issues for security vulnerabilities — see
[SECURITY.md](SECURITY.md) for the disclosure path.

---

## Recognition

Every contributor is added to the project's contributors list. Significant contributions (new evidence types, major performance improvements, novel algorithms) earn co-authorship on the application-note manuscript currently in preparation.

---

## Maintainers

Open source projects are easier to contribute to when you know who to
ping. The current maintainers are listed in
[`pyproject.toml`](pyproject.toml) under `[project.authors]`.
