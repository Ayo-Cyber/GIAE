# Project Roadmap

GIAE is an evolving platform. Our goal is to move from sequence-based annotation to a multi-modal structural and functional interpretation engine.

---

## 📅 Short-Term (v0.3.0)

### 🔬 Foldseek / AlphaFold Integration
- **Feature**: Use Foldseek to scan the AlphaFold Database (AFDB) for structural homologs.
- **Why**: Many phage proteins have zero sequence similarity but conserved 3D folds.
- **Status**: Researching [Foldseek API](https://search.foldseek.com/search) integration.

### 🧪 Bacterial Genome Scaling
- **Feature**: Optimized parallel processing for 4–6 Mb genomes.
- **Why**: Currently benchmarked on phages; needs better memory management for large bacterial contigs.
- **Status**: In development.

---

## 📅 Mid-Term (v0.4.0)

### 🕸️ Evidence Network Visualization
- **Feature**: A web-based graph view showing how different evidence types (homology, motifs, domains) conflict or converge for each gene.
- **Status**: Prototyping in Javascript.

### 📊 Comparative Genomics Mode
- **Feature**: Diff two interpretations side-by-side to highlight functional divergence between strains.
- **Status**: Planned.

---

## 📂 Long-Term (v1.0.0)

### 🧬 Autonomous Annotation Refinement
- **Feature**: A self-correcting engine that re-interprets old annotations as new structural data or UniProt reviews become available.
- **Status**: Concept phase.
