# Python library API

GIAE is a library first, a CLI second. Anything the CLI can do, you can
do programmatically with finer control.

```python
from giae.engine.interpreter import Interpreter
from giae.parsers.genbank import GenBankParser

genome = GenBankParser().parse("lambda_phage.gb")
summary = Interpreter().interpret_genome(genome)
```

This page documents the public surface — the classes, methods, and
extension points you should rely on.

---

## Quick orientation

```text
parsers/    GenBankParser, FastaParser, parse_genome()  →  Genome
models/     Genome, Gene, Protein, Evidence, Interpretation
analysis/   ORFFinder, MotifScanner, plugins, finders, FunctionalAnnotator
engine/     Interpreter, EvidenceAggregator, HypothesisGenerator,
            ConfidenceScorer, ConflictResolver, NoveltyScorer
output/     HTMLReportGenerator, ReportGenerator, JSONExporter
```

---

## Parsers

### `parse_genome(path)` — auto-detect

```python
from giae.parsers.base import parse_genome

genome = parse_genome("genome.gb")     # GenBankParser
genome = parse_genome("genome.fasta")  # FastaParser
```

The function dispatches by file extension and falls back to content
sniffing.

### `GenBankParser`

```python
from giae.parsers.genbank import GenBankParser
from pathlib import Path

genome = GenBankParser().parse(Path("lambda_phage.gb"))
```

Returns a `Genome` populated with `genes`, `sequence`, and metadata
(organism, accession, taxonomy if present).

### `FastaParser`

```python
from giae.parsers.fasta import FastaParser

genome = FastaParser().parse(Path("seq.fasta"))
```

`Genome.genes` is empty — pyrodigal will populate it during
interpretation.

---

## Core models

### `Genome`

```python
@dataclass
class Genome:
    id: str
    name: str
    sequence: str
    genes: list[Gene]
    metadata: dict[str, Any]
    file_format: str  # "genbank" or "fasta"
```

Key methods:

| Method | Returns | Purpose |
|---|---|---|
| `length` | `int` | Sequence length in bp |
| `gc_content` | `float` | GC ratio 0.0–1.0 |
| `add_gene(gene)` | `None` | Append a gene |
| `get_summary()` | `dict` | Stats dict for reports |

### `Gene`

```python
@dataclass
class Gene:
    id: str
    location: GeneLocation        # start, end, strand
    sequence: str | None          # nucleotide
    protein: Protein | None       # translation
    name: str | None              # GenBank /gene
    locus_tag: str | None
    source: str = "genbank"       # also "orf_prediction", "orf_rescue", "nested_orf", ...
    metadata: dict[str, Any]
    evidence: list[Evidence]      # populated during interpretation
    interpretations: list[Interpretation]
```

`Strand` is an `Enum`: `FORWARD = 1`, `REVERSE = -1`.

### `Evidence`

```python
@dataclass
class Evidence:
    id: str                       # auto-generated
    evidence_type: EvidenceType   # see below
    gene_id: str
    description: str
    confidence: float             # 0.0–1.0
    raw_data: dict[str, Any]
    provenance: EvidenceProvenance
    timestamp: datetime
```

`EvidenceType` values:

| Value | Source |
|---|---|
| `BLAST_HOMOLOGY` | UniProt / Diamond / BLAST+ hits |
| `MOTIF_MATCH` | PROSITE pattern hits |
| `ORF_PREDICTION` | pyrodigal output |
| `DOMAIN_HIT` | Pfam / HMMER hits |
| `SEQUENCE_FEATURE` | GenBank curator annotations |
| `STRUCTURAL_HOMOLOGY` | (reserved) Foldseek / structural matches |

### `Interpretation`

```python
@dataclass
class Interpretation:
    id: str
    gene_id: str
    hypothesis: str               # e.g. "DNA polymerase III alpha subunit"
    confidence_score: float       # 0.0–1.0
    confidence_level: ConfidenceLevel
    supporting_evidence_ids: list[str]
    reasoning_chain: list[str]    # human-readable steps
    competing_hypotheses: list[CompetingHypothesis]
    uncertainty_sources: list[str]
    metadata: dict[str, Any]      # cog_category, go_terms, normalized_product, ...
    timestamp: datetime
```

`ConfidenceLevel`: `HIGH`, `MODERATE`, `LOW`, `SPECULATIVE`, `NONE`.

The `metadata` dict, after Phase 6, always contains:

| Key | Type | Meaning |
|---|---|---|
| `category` | `str` | GIAE keyword category (replication, transcription, …) |
| `cog_category` | `str` | Single-letter COG code (J, K, L, …) |
| `cog_name` | `str` | Human-readable COG description |
| `cog_source` | `"pfam"` \| `"inferred"` | Whether COG came from Pfam lookup or category fallback |
| `go_terms` | `list[str]` | GO accessions (e.g. `["GO:0003677"]`) |
| `pfam_id` | `str \| None` | Pfam accession if available |
| `normalized_product` | `str` | Cleaned product name |
| `keyword` | `list[str]` | Keywords matched during categorisation |

Methods:

| Method | Returns | Purpose |
|---|---|---|
| `is_high_confidence` | `bool` | Convenience for `confidence_level == HIGH` |
| `has_competing_hypotheses` | `bool` | True if alternatives were considered |
| `get_summary()` | `str` | One-line summary |
| `get_explanation()` | `str` | Multi-line explanation with reasoning chain |

---

## The Interpreter

### Construction

```python
from giae.engine.interpreter import Interpreter

interpreter = Interpreter(
    # Online evidence sources
    use_uniprot=True,
    use_interpro=True,

    # Local plugins (silently skipped if binary / DB missing)
    use_diamond=True,
    use_local_blast=True,    # only registers when Diamond is unavailable
    use_hmmer=True,
    use_esm=True,

    # ncRNA detection
    use_aragorn=True,
    use_barrnap=True,

    # ORF rescue & nested detection
    use_rescue=True,
    phage_mode=False,

    # Ops
    use_cache=True,
    max_api_concurrent=3,
    conflict_threshold=0.15,
)
```

Every flag has a sensible default — the constructor with no arguments
runs the full online pipeline.

### Running interpretation

```python
summary = interpreter.interpret_genome(genome)
```

Returns a `GenomeInterpretationSummary`:

```python
@dataclass
class GenomeInterpretationSummary:
    genome_id: str
    genome_name: str
    total_genes: int
    interpreted_genes: int
    high_confidence_count: int
    moderate_confidence_count: int
    low_confidence_count: int
    failed_genes: int
    processing_time_seconds: float
    results: list[InterpretationResult]
    novel_gene_report: NovelGeneReport | None
    success_rate: float            # property
```

Each `InterpretationResult`:

```python
@dataclass
class InterpretationResult:
    gene_id: str
    gene_name: str | None
    interpretation: Interpretation | None  # None for dark-matter genes
    hypotheses: list[FunctionalHypothesis]
    confidence_reports: list[ConfidenceReport]
    aggregated_evidence: AggregatedEvidence | None
    success: bool
    error_message: str | None
    skipped_layers: list[str]
```

### Per-gene mode

You can also run interpretation gene-by-gene (e.g. inside a custom
loop):

```python
for gene in genome.genes:
    result = interpreter.interpret_gene(gene)
    if result.interpretation:
        print(result.interpretation.get_summary())
```

---

## Output generators

### Markdown / terminal report

```python
from giae.output.report import ReportGenerator

ReportGenerator().generate(genome, summary, output_path="report.md")
```

### JSON export

```python
from giae.output.json_export import JSONExporter

JSONExporter().export(genome, summary, output_path="results.json")
```

### Interactive HTML

```python
from giae.output.html_report import HTMLReportGenerator

generator = HTMLReportGenerator(title="My Genome Report")
html = generator.generate(genome, summary)
with open("report.html", "w") as f:
    f.write(html)
```

---

## Plugin protocol

Add a new evidence source by implementing `AnalysisPlugin`:

```python
from giae.engine.plugin import AnalysisPlugin
from giae.models.evidence import Evidence, EvidenceType, EvidenceProvenance
from giae.models.gene import Gene


class FoldseekPlugin(AnalysisPlugin):
    name = "foldseek"

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def is_available(self) -> bool:
        # Skip silently if the binary or DB is missing.
        import shutil
        return shutil.which("foldseek") is not None and self.db_path.exists()

    def scan(self, gene: Gene) -> list[Evidence]:
        # Run your analysis. Return typed Evidence objects.
        # Don't make decisions — just describe what you observed.
        ...
        return [
            Evidence(
                evidence_type=EvidenceType.STRUCTURAL_HOMOLOGY,
                gene_id=gene.id,
                description=f"Foldseek hit AF-{accession} ({similarity:.1%})",
                confidence=similarity,
                raw_data={"accession": accession, "similarity": similarity},
                provenance=EvidenceProvenance(
                    tool_name="foldseek",
                    tool_version="9.0",
                    database="afdb",
                ),
            )
        ]
```

Register in `Interpreter.__post_init__` (or supply via the
`plugin_manager` field). [Full guide →](extending.md)

---

## Functional annotation

If you need direct access to the COG/GO mapper without going through
the full interpreter:

```python
from giae.analysis.functional_annotator import FunctionalAnnotator
from giae.analysis.product_normalizer import ProductNormalizer

# Normalise a product name
ProductNormalizer().normalize("putative DNA polymerase [partial]")
# → "DNA polymerase"

# Look up a Pfam ID
annotator = FunctionalAnnotator()
annotator.pfam_table["PF00136"]
# → {"pfam_name": "DNA_pol_B", "cog": "L", "go_terms": ["GO:0003677", ...]}
```

You can swap the bundled table for a fuller one (e.g. the complete
Pfam2GO mapping):

```python
annotator = FunctionalAnnotator(pfam_table_path=Path("/data/full_pfam2go.tsv"))
```

The TSV format is documented in [`data/functional/pfam_categories.tsv`](https://github.com/Ayo-Cyber/giae/blob/main/data/functional/pfam_categories.tsv).

---

## Evidence aggregation & confidence scoring

If you want to bypass the Interpreter and drive the engine pieces
yourself:

```python
from giae.engine.aggregator import EvidenceAggregator
from giae.engine.hypothesis import HypothesisGenerator
from giae.engine.confidence import ConfidenceScorer
from giae.engine.conflict import ConflictResolver

aggregated = EvidenceAggregator().aggregate(evidence_list)
hypotheses = HypothesisGenerator().generate(aggregated)
reports = ConfidenceScorer().score_batch(hypotheses, aggregated)
conflict = ConflictResolver().check_conflicts(hypotheses)
```

This is the same flow `Interpreter.interpret_gene` runs internally — see
[architecture.md](architecture.md) for the full pipeline.

---

## Stability promise

Anything documented on this page is part of the **public API**.
Breaking changes will be flagged in the [CHANGELOG](changelog.md) under
"Changed" with at least one minor-version notice.

Internal modules (anything not documented here) may change without
notice.
