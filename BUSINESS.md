# GIAE — Business Case

**Positioning:** GIAE is *auditable, calibrated genome interpretation for
high-stakes decisions* — starting with phage therapy. We don't sell the
algorithm; we sell the confidence to act on the answer.

A pitch-ready visual version of this is published as a Claude artifact.

---

## 1. The honest starting point

**The tension — the core is a commodity.** Bakta, Prokka, PGAP and DFAST are
free, open-source and excellent. Our own 35-genome benchmark showed GIAE's
*gene finding is Prodigal* — the same engine everyone runs. You cannot sell
"annotation"; the market price of the algorithm is **$0**.

**The answer — sell what free tools structurally can't.** A free CLI hands you
a label with no confidence and no reasoning. GIAE adds **calibrated confidence**
(out-of-sample ECE 0.004), **auditable provenance**, and **honest abstention**.
In high-stakes work, a *confident wrong answer costs more than "I don't know."*

## 2. Beachhead — win one vertical where trust is worth money

Academics won't pay for annotation they get free on their cluster; they are the
**credibility channel**, not the customer. The wedge is a market that is funded,
underserved by tooling, and where a wrong call has consequences.

- **Phage therapy (primary).** Companies putting phages into patients need
  annotation **plus safety screening** — lysogeny, AMR, toxin and virulence
  genes — with an auditable, reproducible, regulatory-defensible report. Real
  pain, real budget, almost no good tooling. GIAE is already phage-aware.
- **Biosecurity & biosurveillance (adjacent).** Government / public-health
  screening for hazards and novel organisms; calibrated, auditable calls are
  exactly what agencies require. Deeper pockets, longer procurement.

## 3. Who pays, and for what

| Segment | Pays for | Willingness |
|---|---|---|
| Phage-therapy companies | Safety screening + auditable reports | High |
| Biosecurity / gov / public health | Calibrated, auditable hazard screening | High · slow procurement |
| Clinical micro / diagnostics | Validated, reproducible AMR calls + support | High · regulated |
| Biotech / pharma R&D · CROs | Hosted API, integration, SLAs, no ops | Medium |
| Academic labs | Adoption & citations (not revenue) | Channel, not customer |

## 4. Business model — open-core

Give away the engine, monetize the layer. The free tools' own moat is
open-source adoption; match it, then charge for what a lab can't get from a CLI
on a cluster. GIAE already ships the account, team, API-key and job-history
plumbing this requires.

- **Free — the engine.** Open-source CLI + library. Adoption, trust, citations.
- **SaaS (usage) — hosted platform.** API + UI, teams, audit logs, calibrated
  confidence. Per-genome or subscription for labs that don't run pipelines.
- **Enterprise — vertical + on-prem.** Phage safety product, validation docs,
  SLAs, on-prem for gov/pharma. High-ACV contracts.

## 5. Moat — it compounds; a CLI tool's doesn't

1. **The trust layer.** Calibration, provenance and abstention are architectural,
   hard to retrofit onto a batch CLI. This is the product and the thing free
   tools structurally lack.
2. **Phage-specific depth.** Dark-gene function, safety knowledge, phage-aware
   ORF detection — domain expertise competitors would have to rebuild.
3. **A data flywheel.** Every genome annotated on the platform improves
   calibration and dark-gene models. A laptop CLI builds no flywheel; a hosted
   platform does.

## 6. Risks — named, not hidden

- **The $0 price anchor.** Free incumbents set the expectation → verticalize on
  trust and safety, never compete on "annotation."
- **The functional layer is still maturing.** The calibration story leans on it;
  near-term paid value is trust + safety + UX, with product-name annotation
  improving on the roadmap (see ROADMAP.md).
- **Regulated verticals sell slowly.** Biosecurity and clinical have long cycles
  → a self-serve SaaS tier carries cash flow while enterprise deals bake.

## 7. The one line

> **Not a faster annotation tool — the trust layer for genome interpretation.**
> Starting with phage therapy, where a wrong call reaches a patient.

---

*Figures cited (ECE 0.004, Prodigal parity, 35-genome benchmark) are engineering
results from this repo's benchmark + calibration work (see BENCHMARK_METHODOLOGY.md),
not market projections. No TAM figures are asserted without a defensible source.*
