# GIAE Roadmap — Product · Paper · Tool

**Strategic bet:** don't out-annotate Bakta — *out-trust* it. Gene finding is
Prodigal in every tool (GIAE and Bakta both wrap pyrodigal), so parity there is
table stakes, not a moat. GIAE's defensible edge is the layer on top:
**calibrated confidence, auditable provenance, honest abstention, and
zero-config robustness** (e.g. auto genetic-code detection). Every phase below
hardens that edge.

Interactive board (tick as you go): published as a Claude artifact.
Full scientific rationale: [`post_assets/BENCHMARK_METHODOLOGY.md`](post_assets/BENCHMARK_METHODOLOGY.md).

Legend: `[x]` done · `[ ]` open · **(P)** Product · **(S)** Paper/Science · **(T)** Tool/Engine · **(B)** Business

---

## Phase 0 — Pitch-ready  ·  *now → pitch day*
Goal: walk in with a defensible, honest story reviewers respect.

- [ ] **(P)** Pitch deck that leads with trust & auditability, not coverage
- [ ] **(P)** Bulletproof live demo — pre-baked job + offline fallback
- [ ] **(P)** "Say this, not that" claims one-pager for Q&A (from the methodology doc)
- [x] **(S)** Benchmark methodology + honest caveats doc
- [x] **(S)** 35-genome GIAE vs Bakta benchmark (F1, Wilcoxon p=0.11)
- [x] **(S)** Confidence calibration — AUC + Wilson CIs (n=8,026)
- [ ] **(S)** Methods-paper thesis outline (one page)
- [x] **(T)** Batch Diamond homology scan — 63× faster
- [x] **(T)** Fix motif DNA false-positive class (translate CDS first)
- [x] **(T)** Confidence recalibration (isotonic/Platt) on the 8,026-call set — fixed the over-confidence: out-of-sample ECE 0.301 → 0.004

## Phase 1 — Trust hardening  ·  *0–3 months*
Goal: make the deployed product as good as the benchmark (the good config only runs offline today).

- [ ] **(P)** Auth refresh tokens — end the 401 session expiry
- [ ] **(P)** Ship the homology config to the deployed worker
- [ ] **(P)** GO/EC ID output — synonym-invariant & machine-readable (also fixes product-name benchmarking)
- [ ] **(P)** Surface abstention explicitly in the UI ("no confident call")
- [ ] **(S)** Expand benchmark to 50+ genomes across phyla (powers the significance test past n=6 bacteria)
- [ ] **(S)** Add Prokka + DFAST to the multi-tool comparison
- [ ] **(S)** Per-tool significance table (Wilcoxon, bootstrap CIs)
- [ ] **(T)** Fix Celery fork-safety → run HMMER/ESM in production (subprocess pool or separate service)
- [ ] **(T)** Bake the calibrated confidence mapping into the engine
- [ ] **(T)** Surface the auto-detected genetic code in output (the zero-config win that took Mycoplasma)

## Phase 2 — Research front  ·  *3–12 months*
Goal: lead where nobody else does — calibrated, hedged function on the dark genes no tool annotates.

- [ ] **(T)** Structure-based function for dark genes (ESM-2 / Foldseek)
- [ ] **(T)** Calibrated, hedged hypotheses on unannotated ORFs (phages are full of dark matter — GIAE can lead here, not match)
- [ ] **(S)** Draft: "Calibrated, abstention-aware functional annotation with provenance"
- [ ] **(S)** Submit (Bioinformatics / NAR)
- [ ] **(P)** Dark-gene explorer — browse what nothing else annotates

## Phase 3 — Niche & scale  ·  *6–18 months*
Goal: own phage biology and become the trust layer other pipelines call to audit themselves.

- [ ] **(P)** Phage safety screen — lysogeny, AMR, toxin genes
- [ ] **(P)** Trust/QC API — flag overconfident calls in other pipelines
- [ ] **(P)** Batch / multi-genome pipeline mode
- [ ] **(B)** Design partners in phage therapy / biosecurity
- [ ] **(B)** API + SaaS pricing model

---

### Why this shape
- **P0** is nearly done — the science is already in the repo; what's left is *framing* for the pitch.
- **P1** closes the gap between "benchmark GIAE" (homology config, strong) and "deployed GIAE" (offline config, conservative). The single highest-leverage fix is Celery fork-safety, which unblocks the real functional layer in production.
- **P2** is the genuine research contribution: uncertainty-quantified, provenance-backed annotation — most tools have none.
- **P3** turns the trust story into a market: phage biology is underserved and values auditability.
