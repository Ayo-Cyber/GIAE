# GIAE Post — Data Handoff

**Generated:** 2026-04-19
**Mode:** Truly offline (no UniProt, no InterPro, no local BLAST, no
HMMER, no ESM) — matches what a `pip install giae` reader gets.
**Driver:** [post_assets/run_offline.py](run_offline.py) calls
`Interpreter(use_uniprot=False, use_interpro=False, use_local_blast=False,
use_hmmer=False, use_esm=False)`. The CLI's `--no-uniprot --no-interpro`
flags are NOT enough — they leave local BLAST/HMMER/ESM enabled, which
inflates results vs. a fresh-install reader. **See section 7.**

---

## 1. phiX174 numbers

**Genome:** NC_001422 (Escherichia phage phiX174), 5,386 bp, GC 44.76%

| Stat | Value |
|---|---|
| Total genes | **11** |
| Interpreted | **10 (90.9%)** |
| High confidence | 7 |
| Moderate confidence | 0 |
| Low confidence | 3 |
| Failed | 0 |
| Dark-matter genes | **1** |

### Top dark-matter gene (verbatim from report)

> ⚠️ **Note:** The post draft asks for the "#1 HIGH-PRIORITY" dark-matter
> gene, but phiX174 only has ONE dark-matter gene and it is flagged
> **MEDIUM PRIORITY**, not high. Use the wording below.

```
#### phiX174p04 — MEDIUM PRIORITY

**Category:** Dark Matter Gene
**Protein length:** 56 aa
**Novelty score:** 75%
**Reason flagged:** No sequence homology, domains, or motifs detected

**Suggested experiments:**
- Gene deletion to assess essentiality
- Protein interaction screen (co-immunoprecipitation or Y2H)
- RNA-seq profiling across conditions to check expression pattern
```

Source: [post_assets/phiX174/phiX174.md](phiX174/phiX174.md) lines 192–202.

---

## 2. Lambda numbers

**Genome:** NC_001416 (Escherichia phage Lambda), 48,502 bp, GC 49.86%

| Stat | Value |
|---|---|
| Total genes | **92** |
| Interpreted | **84 (91.3%)** |
| High confidence | **81** |
| Moderate confidence | **2** |
| Low confidence | **1** |
| Failed | **0** |
| Dark-matter genes | 7 (plus 1 poorly characterised) |

### nu1 block (verbatim)

```
#### nu1

**Predicted Function:** Terminase small subunit
**Confidence:** 80% (high)

**Narrative Explanation:**
Primary evidence strongly suggests this gene encodes a **Terminase
small subunit**. This is based primarily on sequence homology to known
proteins in the database.

**Specific Evidence:**
1. BLAST homology hit: terminase small subunit
2. Sequence identity supports functional similarity
3. E-value indicates statistical significance

**Uncertainty Notes:**
- Single Evidence Type
- Limited Evidence
```

Source: [post_assets/lambda/lambda.md](lambda/lambda.md) lines 91–106.

> ⚠️ **Heads-up:** The "BLAST homology hit" wording is a labelling
> artifact in the report template — no BLAST actually ran. The
> evidence comes from the GenBank `/product` qualifier (curator
> annotation), which the engine routes through the `BLAST_HOMOLOGY`
> evidence type. If your post emphasises that GIAE ran "without BLAST,"
> the report still says "BLAST homology hit" in the bullets; consider
> calling that out or paraphrasing the bullets in the prose.

---

## 3. Lambda ambiguous gene

**Pick:** `lambdap79` — moderate (77%) confidence, has an explicit
**Alternative Hypotheses** section.

**Why this one:** It is the only gene in the lambda report that
satisfies BOTH criteria simultaneously — moderate-or-low confidence
*and* a rendered "Alternative Hypotheses" block. The other candidate,
`bor`, is low confidence with an "Ambiguous interpretation" string in
its summary line, but the markdown renderer only includes Alternative
Hypotheses sections for HIGH/MODERATE blocks; `bor` appears only as a
one-line bullet under Low Confidence and never gets a full block.

```
#### lambdap79

**Predicted Function:** Lipoprotein
**Confidence:** 77% (moderate)

**Narrative Explanation:**
This gene is likely a **Lipoprotein**, though some uncertainty remains.
The identification is driven by the presence of conserved functional
motifs, characteristic of this protein family. An alternative
hypothesis (Predicted by GeneMark) was also considered but had lower
support.

**Specific Evidence:**
1. Detected gram_negative_lipobox motif pattern
2. Motif suggests Lipoprotein function
3. Supported by 1 motif match(es)

**Alternative Hypotheses:**
- Predicted by GeneMark (60%)

**Uncertainty Notes:**
- Limited Evidence
- No Experimental Validation
```

Source: [post_assets/lambda/lambda.md](lambda/lambda.md) lines 228–246.

> ⚠️ **Optional alternate pick:** If you want a higher-stakes example
> for the post, `bor` (low confidence, 80% score) is flagged as
> "Ambiguous interpretation: 'Bor-like outer membrane protein' vs
> 'confers serum resistance upon the host'" — a real biological
> ambiguity (the same protein has both labels in different sources).
> The full evidence chain is in [post_assets/lambda/lambda.json](lambda/lambda.json)
> — search for `"name": "bor"`. It just lacks a rendered "Alternative
> Hypotheses" block in the markdown.

---

## 4. Bakta DB size verification

**Draft claim:** "backed by a database of 350 million protein sequences"
**Verdict: ACCURATE** (when describing the unique-sequence layer).

Bakta v6.0 ([github.com/oschwengers/bakta](https://github.com/oschwengers/bakta))
ships a tiered protein database. The numbers from the project README:

| Layer | Count | Source |
|---|---|---|
| **UPS** (Unique Protein Sequences) | **350,631,327** | UniParc / UniProtKB |
| IPS (Identical Protein Sequences) | 330,865,009 | UniRef100 |
| PSC (Protein Sequence Clusters) | 135,274,518 | UniRef90 |
| PSCC (Cluster Clusters) | 37,008,138 | UniRef50 |

So **"350 million" is correct** as a description of the UPS layer
(unique exact-sequence dedup). If you want to be more precise without
losing the round number, "350 million unique protein sequences"
(rather than "protein sequences") is technically more accurate. The
clustered/searchable layer Bakta actually does ortholog assignment
against is PSC at 135M — different, smaller number.

**Source URL:** https://github.com/oschwengers/bakta

---

## 5. Screenshot paths

- [post_assets/screenshots/phiX174_dark_matter.png](screenshots/phiX174_dark_matter.png)
  — stat cards (11 genes / 90.9% / 7 high / 1 dark) + Gene Explorer
  filtered to Dark Matter, showing the single phiX174p04 row.
- [post_assets/screenshots/lambda_nu1_reasoning.png](screenshots/lambda_nu1_reasoning.png)
  — Gene Explorer table cropped to the single `nu1` row (locus,
  "Terminase small subunit", HIGH badge, score 0.8, 3-bullet
  reasoning chain).
- [post_assets/screenshots/lambda_confidence_distribution.png](screenshots/lambda_confidence_distribution.png)
  — top dashboard with the 4 stat cards (92 / 91.3% / 81 / 7).

> ⚠️ **HTML report does not render Uncertainty Notes per gene.** The
> markdown report has them; the interactive HTML's Gene Explorer table
> only shows Locus / Interpretation / Confidence badge / Reasoning
> Chain. The `lambda_nu1_reasoning.png` screenshot therefore shows
> the 3 reasoning bullets but NOT the "Single Evidence Type / Limited
> Evidence" notes. If you want those visible in a screenshot, you'll
> need to grab the markdown rendering instead.

Capture script: [post_assets/screenshot.py](screenshot.py) (Playwright,
Chromium, 1400×900 viewport, device-scale 2).

---

## 6. GIAE version + git commit

| | |
|---|---|
| `pyproject.toml` version | **0.2.2** |
| Installed package version (`giae --version`) | **0.2.0** (from `src/giae/__init__.py`) |
| Git commit | **75b140b** |
| Branch | `veta-version-1` |

> ⚠️ Version drift: pyproject says 0.2.2 but `__init__.py` still says
> 0.2.0 — the bump didn't propagate. Worth fixing before publishing
> the post if you reference a version number.

---

## 7. Anything surprising

### 7a. Numbers diverge sharply from the prior `case_studies/*_offline.md`

The historical offline reports your editor was working from were
generated with a **different** plugin configuration than what a fresh
`pip install` user gets:

| Genome | Prior `case_studies/*_offline.md` | This run (true offline) |
|---|---|---|
| Lambda | 45/92 interpreted (48.9%), 29 high, 6 mod, 10 low | **84/92 (91.3%), 81 high, 2 mod, 1 low** |
| phiX174 | 0/11 interpreted (0.0%), zero everything | **10/11 (90.9%), 7 high, 0 mod, 3 low** |

**Why the gap?** The CLI's `--no-uniprot --no-interpro` flags only
disable the two API-based plugins. The Interpreter still runs
**local BLAST**, **HMMER**, and **ESM** if those plugins find their
backing files (`~/.giae/blast/swissprot`, `~/.giae/hmmer/pfam.hmm`,
torch weights). The historical lambda_offline.md *did* call BLAST
locally — its evidence bullets are full of `BLAST homology hit:
sp|P31062|NOHD_ECOLI ...` UniProt accessions that only come from a
local Swiss-Prot DB.

A fresh reader running `pip install giae` will not have that DB and
will see the numbers in this handoff (91.3% / 90.9%), driven by:
- GenBank `/product` annotation extraction (free, no DB),
- PROSITE motif scanning (bundled in the package).

The phiX174 prior result of 0/11 is especially surprising — it
implies that run also failed to extract GenBank annotations, which
the current code does extract. Worth a note in the post if you
contrast "before / after" runs.

### 7b. Report uses `BLAST homology hit:` wording even when BLAST is off

When the engine pulls a function from the GenBank `/product` qualifier
and routes it through the homology evidence type, the report template
labels it `BLAST homology hit: <product>`. So the lambda report says
"BLAST homology hit: terminase small subunit" for nu1 even though no
BLAST plugin ran. **If your post says "GIAE ran without BLAST," the
screenshot evidence chain still says "BLAST homology hit" — paraphrase
in prose or expect a reader to flag it.**

### 7c. Lambda dark-matter spotlight: `orf206b`

You may want to feature `orf206b` (HIGH PRIORITY, 206 aa, novelty
score 85%) as the lambda equivalent of phiX174p04. It is the only
HIGH-priority dark-matter gene in the lambda run. Suggested
experiments per report: recombinant expression + activity screen,
structural characterization (X-ray / cryo-EM), deletion phenotyping.

### 7d. Per-genome runtime is now ~0.6s for lambda, ~0.0s for phiX174

The historical lambda_offline.md reports 156 seconds. With all
network/plugin layers off, it's 0.6 seconds. Worth mentioning if
you're pitching speed.

---

## File map

```
post_assets/
├── HANDOFF.md                       (this file)
├── run_offline.py                   (true-offline driver)
├── screenshot.py                    (Playwright capture)
├── lambda/
│   ├── lambda.md                    (full markdown report)
│   ├── lambda.html                  (interactive HTML)
│   └── lambda.json                  (machine-readable)
├── phiX174/
│   ├── phiX174.md
│   ├── phiX174.html
│   └── phiX174.json
└── screenshots/
    ├── phiX174_dark_matter.png
    ├── lambda_nu1_reasoning.png
    └── lambda_confidence_distribution.png
```
