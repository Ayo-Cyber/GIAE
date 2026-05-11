<!--
Thanks for contributing to GIAE! A few minutes filling this out makes review faster.
Please make sure you've read CONTRIBUTING.md before opening.
-->

## Summary

<!-- 1-3 sentences: what changed and why. Link the issue this resolves if there is one. -->

Fixes #

## Type of change

<!-- Check all that apply. -->

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (existing behaviour, API, or output changes)
- [ ] New plugin / evidence source
- [ ] Performance improvement
- [ ] Documentation update
- [ ] Refactor / internal cleanup (no user-facing change)

## What this PR does

<!--
Brief technical summary. If you changed scoring, evidence flow, or any
behaviour the user can observe, describe the before/after.
-->

## Test plan

<!--
- What did you run locally?
- For prediction-quality changes: did you run post_assets/phase4_validation.py
  before and after? Paste the F1 numbers.
- For new code: list the new tests you added.
-->

```bash
# Commands you ran
pytest tests/ -q
ruff check src/ tests/
mypy src/ --ignore-missing-imports
```

## Validation suite numbers

<!-- Required for changes that could affect prediction accuracy. Delete this section otherwise. -->

| Genome | F1 before | F1 after | Δ |
|---|---|---|---|
| phiX174 |  |  |  |
| λ phage |  |  |  |
| T7 |  |  |  |

## Documentation

<!-- Check what you've updated. PRs without doc updates for user-facing changes will be asked to add them. -->

- [ ] `README.md` — if a top-line capability changed
- [ ] `CHANGELOG.md` — under `## [Unreleased]`
- [ ] `docs/cli.md` — if a CLI flag was added/changed
- [ ] `docs/rest_api.md` — if an endpoint was added/changed
- [ ] `docs/architecture.md` — if scoring or evidence flow changed
- [ ] `docs/extending.md` — if you added a plugin
- [ ] Docstrings — for new public functions / classes
- [ ] Not applicable — this PR is internal-only

## Checklist

- [ ] CI is green (ruff, mypy, pytest on Python 3.9 / 3.10 / 3.12)
- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] I agree this contribution will be released under the project's [MIT license](../LICENSE)
- [ ] I'm available to address review feedback within a reasonable time

## Screenshots / output

<!-- For UI / report / output changes. Drag and drop images directly. -->
