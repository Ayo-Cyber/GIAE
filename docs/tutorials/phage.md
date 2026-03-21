# Deep Tutorial: Phage Annotation with GIAE

In this tutorial, we will use GIAE to interpret the genome of **Escherichia phage Lambda** (NC_001416), one of the most well-studied organisms in virology. We will contrast GIAE's evidence-centric approach with traditional "label-only" annotators.

---

## 🧬 The Dataset

We will be using `lambda_phage.gb`, a 48.5 kb linear dsDNA genome containing 92 genes.

**Goal**: Identify structural proteins, regulatory elements, and "Dark Matter" genes that lack traditional homology.

---

## 🚀 Step 1: Running the Interpretation

Run GIAE with the interactive HTML report enabled for the best experience.

```bash
giae interpret case_studies/lambda_phage.gb --format html -o lambda_report.html
```

---

## 🔍 Step 2: Analyzing High-Confidence Signals

Open your `lambda_report.html` in a browser. You will see several genes marked as **HIGH CONFIDENCE**. Let's look at one example:

### Case Study: `nu1` (DNA Packaging)
GIAE assigned **90% Confidence** to this gene. 

**Why?**
- **Homology**: 98% identity to `nohD` in E. coli (Sp|P31062).
- **Reasoning**: GIAE detected a strong convergence between the sequence similarity and the expected location in the phage packaging module.

---

## 🧩 Step 3: Resolving Ambiguity (The "Explainability" Win)

Traditional tools might label `lambdap22` simply as "hypothetical protein" or guess a function without evidence. GIAE shows you the **Reasoning Chain**:

> "Primary evidence strongly suggests this gene encodes a **Protein with 2fe2s_fer_1 motif**. The identification is driven by the presence of conserved functional motifs... An alternative hypothesis (Protein with thiolase_3 motif) was also considered but had lower support."

By surfacing the **Alternative Hypotheses**, GIAE allows the virologist to make an informed decision rather than trusting a black-box label.

---

## 🌑 Step 4: Exploring Phage Dark Matter

Phages are notorious for having "ORFans" — genes with no known homologs. GIAE identifies these as **DARK MATTER**.

In the Lambda genome, GIAE flagged **44 genes** as Dark Matter.
For example, gene **B** (533 aa) is flagged as **HIGH PRIORITY** for research because:
1. It is exceptionally long for a phage gene.
2. It has **zero** detectable motifs or domain hits.
3. Its novelty score is **95%**.

**GIAE's Suggestion**: Since sequence-based methods failed, this gene is a prime candidate for **AlphaFold structural prediction** or biochemical screening.

---

## 💡 Summary

By the end of this tutorial, you should understand how to:
1. **Calibrate your trust** using GIAE's confidence scores.
2. **Investigate evidence** behind every functional assignment.
3. **Prioritize novel genes** for laboratory follow-up.

---

## 🛠️ Next Steps

- Try the **T4 Phage** tutorial for a larger, more complex genome (168 kb).
- Learn how to [Install Plugins](../api.md) for local HMMER and BLAST+ support.
