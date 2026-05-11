<p align="center">
  <img src="../assets/logo.png" alt="GIAE Logo" width="200"/>
</p>

# Tutorial: Annotating a Phage Genome from Scratch

> **Time to complete:** ~20 minutes | **Skill level:** Beginner  
> **What you will learn:** How to run a full annotation, understand confidence scores, read the HTML report, and identify genes worth following up on.

---

## 🧬 What we're doing — and why it matters

We'll annotate the **Lambda phage genome** (NC_001416), one of the most-studied viruses in biology. It's 48.5 kb with 92 genes — small enough to finish quickly, complex enough to be interesting.

Lambda phage is a great teaching example because:

- Some genes have very well-known functions (e.g., the repressor `cI`)
- Some have weak or ambiguous annotations
- Some are completely unknown — "Dark Matter" genes

By the end of this tutorial you'll see exactly how GIAE handles all three cases and how to decide what to do next.

!!! note "Don't have GIAE installed yet?"
    Run `pip install giae` and come back. See the [Quickstart](../quickstart.md) for help.

---

## Step 1 — Download the genome

Open your terminal and run:

```bash
curl -o lambda_phage.gb "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_001416&rettype=gb&retmode=text"
```

This downloads the Lambda phage GenBank file from NCBI. You should see a file called `lambda_phage.gb` appear in your current folder.

**Quick check** — make sure the file is there:

```bash
ls -lh lambda_phage.gb
```

Expected output:

```
-rw-r--r--  1 you  staff  185K Mar 21 14:00 lambda_phage.gb
```

If the file exists and has a size around 185 KB, you're good.

---

## Step 2 — Run GIAE

Now run the full annotation with the HTML report (this is the richest output format):

```bash
giae interpret lambda_phage.gb --format html -o lambda_report.html
```

You'll see a progress bar in your terminal:

```
🔬 GIAE — Genome Interpretation and Annotation Engine
   Genome: Lambda phage (NC_001416)  |  48,502 bp  |  92 genes

   Analysing...
   [■■■■■■■■■■■■■■■■■■■■     ] 78/92 (85%)

   Fetching homology data from UniProt...
   Running motif scan (PROSITE)...
   Scoring hypotheses...

✅ Complete — 92 genes interpreted in 41s

   📄 Report: lambda_report.html
   🟢 High confidence:   51 genes (55%)
   🟡 Medium confidence: 22 genes (24%)
   🔴 Low confidence:    11 genes (12%)
   🌑 Novel / Dark Matter: 8 genes (9%)
```

!!! tip "This takes 30–60 seconds on a normal laptop"
    Most of the time is spent fetching UniProt data. Use `--no-uniprot --no-interpro`
    for a faster offline run (fewer evidence sources, but instant results).

---

## Step 3 — Open the HTML report

Open `lambda_report.html` in your browser (double-click it, or drag it into Chrome/Firefox).

You'll see a page like this:

```
┌─────────────────────────────────────────────────┐
│  GIAE — Lambda phage (NC_001416)                │
│  92 genes  |  41s  |  Generated 2025-03-21      │
│                                                 │
│  ████████████████████░░░░░░░░░░░░░░░           │
│  55% HIGH   24% MEDIUM   12% LOW   9% NOVEL    │
├─────────────────────────────────────────────────┤
│  [🟢 cI]  Repressor protein CI             87% │
│  [🟢 O]   Replication protein O            91% │
│  [🟢 P]   Replication protein P            83% │
│  [🟡 ren] Putative regulatory protein      61% │
│  [🌑 B]   Unknown function              NOVEL  │
│  ...                                           │
└─────────────────────────────────────────────────┘
```

Each gene is colour-coded:
- 🟢 **Green** = HIGH confidence — you can trust this annotation
- 🟡 **Yellow** = MEDIUM confidence — probably right, but double-check
- 🔴 **Red** = LOW confidence — treat as a hypothesis, not a fact
- 🌑 **Black/Dark** = NOVEL — no known function found

**Click any gene** to expand its full evidence panel.

---

## Step 4 — Understanding a HIGH confidence gene

Click on **`cI`** (the first gene). You'll see:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 cI  |  Lambda repressor protein CI  |  87% ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Evidence collected:
  ✔  UniProt P03034 — 96% identity (Lambda repressor CI)
  ✔  Motif: HTH_3 (Helix-Turn-Helix DNA binding domain)
  ✔  Domain: cl21500 (Lambda repressor N-terminal domain)

Reasoning:
  "Three independent evidence sources (sequence homology,
   structural motif, and domain classification) all agree.
   This gene is the lysogeny repressor. HIGH confidence."

Alternative hypotheses considered:
  ✗  Cro-like repressor (23%) — same HTH motif, lower UniProt match
```

### What to look for here:

1. **Multiple evidence sources agree** — this is the gold standard. When UniProt homology, a motif hit, AND a domain classification all point to the same function, you can be very confident.

2. **The reasoning is transparent** — GIAE tells you *why* it made this call, not just *what* it decided.

3. **Alternative hypotheses are shown** — it considered Cro-like repressor but rejected it. This means GIAE actively ruled out other possibilities.

**✅ No action needed for this gene.** You can record it as confirmed.

---

## Step 5 — Understanding a MEDIUM confidence gene

Now click on **`ren`** (rendered as yellow). You'll see something like:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ren  |  Putative regulatory protein  |  61% 🟡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Evidence collected:
  ✔  UniProt P03040 — 71% identity (Phage ren protein — "putative")
  ✗  No motif hits found
  ✗  No conserved domain

Reasoning:
  "Sequence similarity to a protein of unknown function in UniProt.
   The match is significant but the reference protein is itself
   not well characterised. Function is inferred, not confirmed."

Alternative hypotheses considered:
  ✗  Transcriptional activator (38%) — weak, rejected
```

### What to look for here:

1. **Only one evidence source** — when GIAE only has UniProt homology with no motif or domain support, it can't be as confident.

2. **The source itself is "putative"** — the UniProt entry it matched uses the word *putative*, which means even the reference database isn't sure. GIAE flags this.

3. **No motif or domain hit** — these would normally add more confidence.

**What to do with this gene:**
- If you're writing it up, say "putative regulatory protein, 61% confidence" — not "confirmed"
- Consider running HMMER locally (`giae db download pfam`) for extra domain evidence
- If you have lab access, this is a candidate for functional assays

---

## Step 6 — Understanding Dark Matter genes

Click on gene **`B`** (shown as 🌑 NOVEL). This is where it gets interesting:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 B  |  Unknown function  |  NOVEL 🌑
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Gene length: 533 amino acids (long for a phage gene)
Novelty score: 94%

Evidence collected:
  ✗  No UniProt homology found (e-value > 1e-5)
  ✗  No motif hits found
  ✗  No domain detected

Reasoning:
  "No sequence-based evidence available. This gene has no
   detectable homologs in current databases. It may represent
   a genuinely novel protein class."

GIAE Suggestions:
  🔬  Run AlphaFold2 on this sequence for structural prediction
  🔬  Check expression data — is this gene expressed at all?
  🔬  Candidate for wet-lab biochemical screening
```

### What does "Dark Matter" mean?

Phage genomes are notorious for containing genes that have **no detectable relationship** to anything in current databases. These "ORFans" make up 9–40% of phage gene content.

GIAE calls these **Dark Matter** because:
- It genuinely doesn't know what they do
- The tools to answer the question go beyond sequence comparison
- Structure prediction (AlphaFold) or laboratory experiments are the next step

**Why is this useful?**
Most annotation tools would either skip these genes or label them "hypothetical protein" and move on. GIAE gives you:
- A **novelty score** to prioritise which ones to investigate
- A **suggested next step** based on gene length and properties
- Explicit confirmation that sequence methods have been exhausted

Gene B is flagged as **HIGH PRIORITY** novelty because at 533 amino acids, it's unusually large for a phage gene. Long unknown proteins are often worth structural investigation.

---

## Step 7 — Exporting results for downstream analysis

You can also get the results as JSON for computational downstream use:

```bash
giae interpret lambda_phage.gb --format json -o lambda_results.json
```

The JSON output includes all evidence, scores, and reasoning in a structured format:

```json
{
  "genome_id": "NC_001416",
  "genes": [
    {
      "gene_id": "cI",
      "interpretation": "Repressor protein CI",
      "confidence": 0.87,
      "confidence_label": "HIGH",
      "evidence": [
        {
          "type": "uniprot_homology",
          "description": "P03034 — 96% identity",
          "confidence": 0.96
        },
        {
          "type": "motif",
          "description": "HTH_3 domain detected",
          "confidence": 0.82
        }
      ],
      "reasoning": "Three independent evidence sources agree...",
      "novel": false,
      "novelty_score": 0.03
    }
  ]
}
```

---

## Summary — What to do with your results

| Gene type | What GIAE tells you | Recommended action |
|-----------|--------------------|--------------------|
| 🟢 HIGH confidence | Strong multi-source evidence | Accept annotation, cite the evidence |
| 🟡 MEDIUM confidence | Some uncertainty | Note as "putative", consider extra validation |
| 🔴 LOW confidence | Weak single-source evidence | Treat as hypothesis only, do not cite as fact |
| 🌑 NOVEL / Dark Matter | No known function | Structural prediction or lab follow-up |

---

## Next Steps

- 🔌 **Install Diamond** for fast local homology: `giae db download swissprot-diamond`
- 🔌 **Install HMMER/Pfam** for domain detection: `giae db download pfam`
- 📖 **[Python API Reference](../python_api.md)** — use GIAE in your scripts
- 🌐 **[REST API Reference](../rest_api.md)** — submit jobs over HTTP
- 🏛️ **[Architecture](../architecture.md)** — how the evidence model and confidence scoring work
- 📊 **[Benchmarks](../benchmarks.md)** — head-to-head vs Bakta
- 🗺️ **[Roadmap](../roadmap.md)** — what's coming next
