import json
import os

from celery import Celery

from .database import SessionLocal
from .models import Job, JobStatus
from giae.parsers.base import parse_genome
from giae.engine.interpreter import Interpreter
from giae.output.html_report import HTMLReportGenerator

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "giae_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)


def _serialize_genes(results, genome) -> str:
    """Serialize gene interpretation results to a JSON string for the API."""
    gene_map = {g.id: g for g in genome.genes}
    out = []
    for r in results:
        gene = gene_map.get(r.gene_id)
        interp = r.interpretation
        is_dark = interp is None

        evidence_list = []
        if r.aggregated_evidence:
            for ev in r.aggregated_evidence.get_top_evidence(5):
                tool = ev.provenance.tool_name if ev.provenance else ev.evidence_type.value
                evidence_list.append({
                    "label": ev.description,
                    "source": tool,
                    "conf": round(ev.confidence, 3),
                })

        # confidence_level values are lowercase ("high") — uppercase for the frontend
        conf_value = interp.confidence_level.value.upper() if interp else None

        # Phase 6 functional annotation metadata
        meta = (interp.metadata or {}) if interp else {}
        normalized = meta.get("normalized_product")

        loc = gene.location if gene else None
        out.append({
            "id": r.gene_id,
            "name": r.gene_name or (gene.name if gene else None) or r.gene_id,
            "locus": (gene.locus_tag if gene else None) or r.gene_id,
            "start": loc.start if loc else None,
            "end": loc.end if loc else None,
            "strand": loc.strand.value if loc else None,
            "length": (loc.end - loc.start) if loc else None,
            "is_dark": is_dark,
            "confidence": conf_value,
            "score": round(interp.confidence_score, 3) if interp else None,
            "function": interp.hypothesis if interp else None,
            "normalized_product": normalized,
            "cog_category": meta.get("cog_category"),
            "cog_name": meta.get("cog_name"),
            "cog_source": meta.get("cog_source"),
            "go_terms": meta.get("go_terms") or [],
            "pfam_id": meta.get("pfam_id"),
            "category": meta.get("category"),
            "reasoning": " ".join(interp.reasoning_chain) if interp else None,
            "reasoning_steps": list(interp.reasoning_chain) if interp else [],
            "competing_hypotheses": [
                {
                    "hypothesis": ch.hypothesis,
                    "confidence": round(ch.confidence, 3),
                    "reason_not_preferred": ch.reason_not_preferred,
                }
                for ch in (interp.competing_hypotheses if interp else [])
            ],
            "uncertainty_sources": list(interp.uncertainty_sources) if interp else [],
            "evidence": evidence_list,
        })
    return json.dumps(out)


# Default Interpreter shared across jobs — PROSITE patterns parsed once,
# plugins loaded once. Phase 6 (functional annotator) is always on; rescue
# is on by default; phage_mode is opt-in per job.
_default_interpreter = Interpreter(
    use_uniprot=False,
    use_interpro=False,
    use_local_blast=False,
    use_hmmer=False,   # pyhmmer is a C extension — not fork-safe with Celery prefork
    use_esm=False,     # torch is not fork-safe either
)

_phage_interpreter = Interpreter(
    use_uniprot=False,
    use_interpro=False,
    use_local_blast=False,
    use_hmmer=False,
    use_esm=False,
    phage_mode=True,
)


@celery_app.task(name="process_genome")
def process_genome_task(job_id: str, file_path: str, filename: str, phage_mode: bool = False):
    """Background task: run the GIAE interpretation pipeline on an uploaded genome.

    Args:
        job_id: Job UUID to update in the database.
        file_path: Path to the uploaded genome file (FASTA or GenBank).
        filename: Original filename (used in the report title).
        phage_mode: If True, enable phage-aware nested ORF detection.
    """
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        db.close()
        return

    job.status = JobStatus.RUNNING.value
    db.commit()

    try:
        # Abort if cancelled before the worker picked it up
        db.refresh(job)
        if job.status == JobStatus.CANCELLED.value:
            db.close()
            return

        # 1. Parse – auto-detects GenBank vs FASTA
        genome = parse_genome(file_path)

        # 2. Interpret
        interpreter = _phage_interpreter if phage_mode else _default_interpreter
        summary = interpreter.interpret_genome(genome)

        # 3. Generate interactive HTML report
        os.makedirs("public_reports", exist_ok=True)
        report_path = f"public_reports/{job_id}.html"

        generator = HTMLReportGenerator(title=f"GIAE Report — {filename}")
        html_content = generator.generate(genome, summary)
        with open(report_path, "w") as f:
            f.write(html_content)

        # 4. Persist summary stats + structured gene data
        dark_count = sum(1 for r in summary.results if r.interpretation is None)
        genes_json = _serialize_genes(summary.results, genome)

        job.status = JobStatus.COMPLETED.value
        job.report_url = f"/reports/{job_id}.html"
        job.total_genes = summary.total_genes
        job.interpreted_genes = summary.interpreted_genes
        job.high_confidence_count = summary.high_confidence_count
        job.dark_count = dark_count
        job.processing_time_seconds = int(summary.processing_time_seconds)
        job.genes_json = genes_json
        db.commit()

    except Exception as e:
        job.status = JobStatus.FAILED.value
        job.error_message = str(e)
        db.commit()
    finally:
        db.close()
