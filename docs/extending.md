# Extending GIAE

GIAE is designed to be extended. The plugin protocol, the evidence
type system, and the hypothesis tier system are explicit extension
points — adding a new evidence source is a mechanical exercise once
you know the interfaces.

This page walks through three common extensions:

1. **Adding a new analysis plugin** (e.g. Foldseek, custom HMM library)
2. **Adding a new ORF / RNA finder**
3. **Adding a new evidence type**

---

## 1. Adding a new analysis plugin

Plugins are the most common extension. They scan a single gene and
return typed `Evidence` objects. The plugin protocol is in
[`src/giae/engine/plugin.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/plugin.py).

### Step 1 — Implement `AnalysisPlugin`

```python
# src/giae/analysis/foldseek.py
"""Foldseek structural-homology plugin."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from giae.engine.plugin import AnalysisPlugin
from giae.models.evidence import (
    Evidence, EvidenceProvenance, EvidenceType,
)
from giae.models.gene import Gene


class FoldseekPlugin(AnalysisPlugin):
    """Wraps `foldseek easy-search` against a local AFDB.

    Skips silently when the binary or database is not present.
    """
    name = "foldseek"

    def __init__(self, afdb_path: Path) -> None:
        self.afdb_path = afdb_path

    def is_available(self) -> bool:
        return (
            shutil.which("foldseek") is not None
            and self.afdb_path.exists()
        )

    def scan(self, gene: Gene) -> list[Evidence]:
        if not gene.protein or not gene.protein.sequence:
            return []

        with tempfile.NamedTemporaryFile("w", suffix=".fasta", delete=False) as fh:
            fh.write(f">{gene.id}\n{gene.protein.sequence}\n")
            query_path = Path(fh.name)

        try:
            result = subprocess.run(
                [
                    "foldseek", "easy-search",
                    str(query_path),
                    str(self.afdb_path),
                    "/tmp/foldseek.tsv",
                    "/tmp/foldseek_workdir",
                    "--format-output", "target,prob,evalue,bits",
                ],
                capture_output=True, text=True, check=True,
            )
            return self._parse_hits("/tmp/foldseek.tsv", gene)
        except subprocess.CalledProcessError:
            return []
        finally:
            query_path.unlink(missing_ok=True)

    def _parse_hits(self, tsv_path: str, gene: Gene) -> list[Evidence]:
        provenance = EvidenceProvenance(
            tool_name="foldseek",
            tool_version="9.0",
            database=str(self.afdb_path),
        )
        out: list[Evidence] = []
        for line in Path(tsv_path).read_text().splitlines():
            target, prob, evalue, bits = line.split("\t")
            prob = float(prob)
            if prob < 0.5:
                continue
            out.append(
                Evidence(
                    evidence_type=EvidenceType.STRUCTURAL_HOMOLOGY,
                    gene_id=gene.id,
                    description=f"Foldseek hit {target} (prob {prob:.1%})",
                    confidence=prob,
                    raw_data={
                        "target": target,
                        "probability": prob,
                        "evalue": float(evalue),
                        "bits": float(bits),
                    },
                    provenance=provenance,
                    timestamp=datetime.now(timezone.utc),
                )
            )
        return out
```

### Step 2 — Register the plugin in the Interpreter

Open [`src/giae/engine/interpreter.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/interpreter.py)
and add a flag, an init line, and a registration line.

```python
# Field
use_foldseek: bool = True

# In __post_init__:
if self.use_foldseek:
    afdb_path = Path.home() / ".giae" / "afdb"
    self.plugin_manager.register(FoldseekPlugin(afdb_path))
```

That's it — `is_available()` will silently skip the plugin if the
binary or DB isn't present, and the rest of the interpreter doesn't
need to know about it.

### Step 3 — Wire up the hypothesis path

If your evidence type already exists (`STRUCTURAL_HOMOLOGY` does), and
the existing hypothesis tiers handle it, you're done. If you need a
new tier, see [§3 below](#3-adding-a-new-evidence-type).

### Step 4 — Tests

```python
# tests/test_foldseek.py
def test_foldseek_skips_silently_when_unavailable():
    plugin = FoldseekPlugin(afdb_path=Path("/does/not/exist"))
    assert plugin.is_available() is False

def test_foldseek_returns_empty_for_unscored_gene():
    plugin = FoldseekPlugin(afdb_path=Path("/does/not/exist"))
    gene = Gene(...)
    assert plugin.scan(gene) == []
```

For real integration tests, mock `subprocess.run` and feed in
representative TSV output.

### Step 5 — Documentation

- Add a row to the **What's in the box** table in [`README.md`](https://github.com/Ayo-Cyber/GIAE/blob/main/README.md)
- Add a CLI flag mention in [`docs/cli.md`](cli.md) if it exposes one
- Add a CHANGELOG entry under `## [Unreleased]`

---

## 2. Adding a new ORF / RNA finder

ORF finders run *before* per-gene interpretation. They mutate the
`Genome.genes` list directly. Aragorn, Barrnap, ShortOrfRescue, and
NestedOrfFinder are all examples.

### Pattern

```python
# src/giae/analysis/my_finder.py
class MyFinder:
    def __init__(self, ...):
        ...

    def is_available(self) -> bool:
        # Return False if a required binary / DB is missing.
        ...

    def find(self, genome_sequence: str, existing_genes: list[Gene]) -> list[Gene]:
        # Return new Gene objects. Do NOT mutate `existing_genes`.
        # Set source="my_finder" and feature_type in metadata.
        ...
```

### Wiring

In [`Interpreter.interpret_genome`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/interpreter.py),
add a call somewhere appropriate in the discovery sequence:

```python
if self.use_my_finder and genome.sequence:
    new_genes = self.my_finder.find(genome.sequence, list(genome.genes))
    for gene in new_genes:
        # Apply your overlap policy here. Look at the existing rescue
        # block for a reference implementation.
        genome.add_gene(gene)
```

### Things to watch for

- **Coordinate convention.** GIAE uses 0-based, half-open coordinates
  internally. If your tool emits 1-based or inclusive-end output,
  convert at the boundary.
- **Strand.** `Strand.FORWARD` (1) or `Strand.REVERSE` (-1).
- **Reverse-complement coordinates.** If you scan the reverse
  complement of the genome, convert back to forward-strand coordinates
  before emitting `Gene` objects (`fwd_start = seq_len - rc_end`,
  `fwd_end = seq_len - rc_start`).
- **Overlap policy.** Decide explicitly — does your finder reject ORFs
  that overlap existing genes (like `ShortOrfRescue`), or specifically
  *seek* overlaps (like `NestedOrfFinder`)?

---

## 3. Adding a new evidence type

This is the heaviest extension because it touches three core engine
modules. Do it only when an existing type doesn't fit.

### Step 1 — Add the enum value

In [`src/giae/models/evidence.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/models/evidence.py):

```python
class EvidenceType(Enum):
    BLAST_HOMOLOGY = "blast_homology"
    MOTIF_MATCH = "motif_match"
    ORF_PREDICTION = "orf_prediction"
    DOMAIN_HIT = "domain_hit"
    SEQUENCE_FEATURE = "sequence_feature"
    STRUCTURAL_HOMOLOGY = "structural_homology"
    MY_NEW_TYPE = "my_new_type"      # ← add here
```

### Step 2 — Aggregator handling

In [`src/giae/engine/aggregator.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/aggregator.py),
make sure your new type is grouped correctly. The `groups_by_type` dict
is auto-populated, but you may want a convenience property like
`has_my_new_type` if your hypothesis tier needs it.

### Step 3 — Hypothesis generation tier

In [`src/giae/engine/hypothesis.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/hypothesis.py),
add a `_hypotheses_from_my_type()` method and call it from
`generate()` at the appropriate priority. Example pattern:

```python
def _hypotheses_from_my_type(
    self, aggregated: AggregatedEvidence,
) -> list[FunctionalHypothesis]:
    hypotheses = []
    evidence_list = aggregated.groups_by_type.get(
        EvidenceType.MY_NEW_TYPE, []
    )
    for evidence in evidence_list[:3]:  # top 3
        function = self._extract_function_from_description(evidence.description)
        category = self._categorize_function(function)
        reasoning = [
            f"My-new-type evidence: {evidence.description}",
            "...",
        ]
        hypotheses.append(
            FunctionalHypothesis(
                function=function,
                category=category,
                confidence=evidence.confidence,
                supporting_evidence_ids=[evidence.id],
                reasoning_steps=reasoning,
                source_type="MY_TYPE",
                keywords=self._extract_keywords(evidence.description),
            )
        )
    return hypotheses
```

Then in `generate()`:

```python
if EvidenceType.MY_NEW_TYPE in aggregated.groups_by_type:
    hypotheses.extend(self._hypotheses_from_my_type(aggregated))
```

Insert at the right priority — between existing tiers based on how
strong the new evidence is.

### Step 4 — Confidence weight

In [`src/giae/engine/confidence.py`](https://github.com/Ayo-Cyber/GIAE/blob/main/src/giae/engine/confidence.py),
add a default weight for your new type. The current weights are
documented in the docstring of `ConfidenceScorer`.

### Step 5 — Tests for all three engine layers

- A test for the aggregator that confirms your evidence groups correctly
- A test for hypothesis generation that confirms your tier produces
  the expected output
- A test for confidence scoring that exercises any new bonuses /
  penalties

---

## Style guidelines for extensions

### Do

- **Skip silently** when an external binary or DB is missing.
  `is_available()` returns `False`; nothing else fires.
- **Return typed Evidence** with full provenance. Don't make decisions
  inside the plugin; produce evidence for the engine to interpret.
- **Use 0-based, half-open coordinates** internally. Convert at the
  boundary only.
- **Add tests** for at least: not-available case, empty input, one
  representative real hit.
- **Document the new flag / capability** in `README.md`,
  `docs/cli.md`, and `CHANGELOG.md`.

### Don't

- **Don't print or log to stdout** in normal operation. Use the
  `logging` module.
- **Don't `eval`, `exec`, or `pickle.load`** user data.
- **Don't add a global** to the engine. New state goes on the
  `Interpreter` field list, initialised in `__post_init__`.
- **Don't assume an internet connection.** Online plugins (UniProt,
  InterPro) are explicit opt-ins via `--mode online`. Local plugins
  must work offline.
- **Don't catch and swallow `Exception`.** Catch the specific subclass
  you expect; let unknowns propagate so they're visible.

---

## Architectural escape hatches

If your extension doesn't fit any of the three patterns above, you
have two more options:

### Subclass `Interpreter`

```python
class MyInterpreter(Interpreter):
    def interpret_gene(self, gene: Gene) -> InterpretationResult:
        # Custom pre/post processing
        result = super().interpret_gene(gene)
        ...
        return result
```

### Run engine pieces directly

The `EvidenceAggregator`, `HypothesisGenerator`, `ConfidenceScorer`,
and `ConflictResolver` are usable independently. See the
[Python API doc → Evidence aggregation](python_api.md#evidence-aggregation-confidence-scoring)
for an example.

---

## Getting your extension merged

1. **Open a discussion** on GitHub before you start coding. We'll help
   you decide whether it belongs in core, as a plugin, or as a
   companion package.
2. **Follow the guidelines** above and in [CONTRIBUTING.md](https://github.com/Ayo-Cyber/GIAE/blob/main/CONTRIBUTING.md).
3. **Open a PR** with tests, docs, and a CHANGELOG entry.
4. **Be patient** — review of extensions that touch the engine is
   careful by design.

Welcome aboard.
