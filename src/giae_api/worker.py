import json
import logging
import os

from celery import Celery
from celery.signals import worker_process_init

from .database import SessionLocal
from .models import Job, JobStatus
from giae.parsers.base import parse_genome
from giae.engine.interpreter import Interpreter
from giae.output.html_report import HTMLReportGenerator

logger = logging.getLogger(__name__)

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
        domains = []
        if r.aggregated_evidence:
            for ev in r.aggregated_evidence.get_top_evidence(5):
                tool = ev.provenance.tool_name if ev.provenance else ev.evidence_type.value
                evidence_list.append({
                    "label": ev.description,
                    "source": tool,
                    "conf": round(ev.confidence, 3),
                })
            # Domain architecture blocks — any evidence whose raw_data carries
            # amino-acid coordinates (PROSITE motifs, HMMER/Pfam domain hits).
            for evlist in r.aggregated_evidence.groups_by_type.values():
                for ev in evlist:
                    rd = ev.raw_data or {}
                    s, e = rd.get("start"), rd.get("end")
                    if isinstance(s, int) and isinstance(e, int) and e > s:
                        tool = ev.provenance.tool_name if ev.provenance else ev.evidence_type.value
                        domains.append({
                            "start": s,
                            "end": e,
                            "label": rd.get("motif_description") or rd.get("hmm_name") or ev.description,
                            "source": tool,
                            "kind": ev.evidence_type.value,
                        })

        # Amino-acid sequence for the sequence viewer. Prefer the stored
        # /translation; fall back to translating the (strand-corrected) coding
        # sequence so genes without a GenBank translation still show a protein.
        aa_seq = None
        if gene:
            if gene.protein and gene.protein.sequence:
                aa_seq = gene.protein.sequence.rstrip("*")
            elif getattr(gene, "sequence", None):
                nt = gene.sequence[: len(gene.sequence) // 3 * 3]
                if nt:
                    from Bio.Seq import Seq
                    aa_seq = str(Seq(nt).translate(to_stop=False)).rstrip("*") or None

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
            # Calibrated P(correct) — present only for homology-backed calls
            # (see ConfidenceCalibrator); null otherwise.
            "calibrated_confidence": meta.get("calibrated_confidence"),
            "calibration_model": meta.get("calibration_model"),
            "function": interp.hypothesis if interp else None,
            "normalized_product": normalized,
            "cog_category": meta.get("cog_category"),
            "cog_name": meta.get("cog_name"),
            "cog_source": meta.get("cog_source"),
            "go_terms": meta.get("go_terms") or [],
            "ec_number": meta.get("ec_number"),
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
            "aa_sequence": aa_seq,
            "aa_length": len(aa_seq) if aa_seq else None,
            "domains": domains,
        })
    return json.dumps(out)


# ── Interpreter lifecycle & fork-safety ──────────────────────────────────────
#
# The interpreters MUST be created inside each forked worker child, never at
# module import in the Celery parent. Celery's default prefork pool forks worker
# processes; C extensions that hold thread pools or global state (pyhmmer,
# torch/ESM) crash or deadlock when that state is inherited across a fork. By
# building interpreters lazily per process — warmed in the `worker_process_init`
# signal, which fires AFTER the fork — those libraries initialize fresh in each
# child and are never inherited across a fork, so they are safe to enable.
#
# Plugin toggles are env-controlled so a deployment can turn homology/domain
# search on without a code change:
#   GIAE_ENABLE_DIAMOND (default on)  — subprocess, fork-safe; no-ops if no DB
#   GIAE_ENABLE_HMMER   (default off) — pyhmmer; safe now that init is post-fork
#   GIAE_ENABLE_ESM     (default off) — torch; heavy, opt-in
#   GIAE_ENABLE_UNIPROT (default off) — network; off for offline/deterministic


def _flag(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# Per-process interpreter cache, keyed by phage_mode. Populated post-fork; the
# empty dict inherited across the fork is harmless.
_interpreters: dict = {}


def _build_interpreter(phage_mode: bool) -> Interpreter:
    return Interpreter(
        use_uniprot=_flag("GIAE_ENABLE_UNIPROT", False),
        use_interpro=False,
        use_local_blast=_flag("GIAE_ENABLE_BLAST", False),
        use_diamond=_flag("GIAE_ENABLE_DIAMOND", True),
        use_hmmer=_flag("GIAE_ENABLE_HMMER", False),
        use_esm=_flag("GIAE_ENABLE_ESM", False),
        phage_mode=phage_mode,
    )


def get_interpreter(phage_mode: bool) -> Interpreter:
    """Return this process's interpreter for the mode, building it on first use.

    Lazy so that even pools that do not emit worker_process_init (solo/threads)
    still construct the interpreter inside the worker process, never the parent.
    """
    key = bool(phage_mode)
    interp = _interpreters.get(key)
    if interp is None:
        interp = _build_interpreter(key)
        _interpreters[key] = interp
    return interp


@worker_process_init.connect
def _warm_interpreter(**_kwargs):
    """Build the default interpreter inside each forked child (post-fork), so
    fork-unsafe C extensions initialize in the child and are never inherited
    across a fork. The phage interpreter is built lazily on first phage job."""
    try:
        get_interpreter(False)
        logger.info(
            "Worker process warmed (diamond=%s hmmer=%s esm=%s uniprot=%s)",
            _flag("GIAE_ENABLE_DIAMOND", True), _flag("GIAE_ENABLE_HMMER", False),
            _flag("GIAE_ENABLE_ESM", False), _flag("GIAE_ENABLE_UNIPROT", False),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to warm interpreter in worker process")


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

        # 2. Interpret (interpreter built lazily inside this worker process)
        interpreter = get_interpreter(phage_mode)
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

        # 4b. Phage safety screen (lysogeny / AMR / virulence) — the therapeutic
        # safety gate ordinary annotation doesn't surface.
        safety_json = None
        try:
            from giae.analysis.safety import SafetyScreener
            report = SafetyScreener().screen_summary(summary, genome)
            safety_json = json.dumps({
                "verdict": report.verdict,
                "recommendation": report.recommendation,
                "lysogenic": report.lysogenic,
                "counts": report.counts(),
                "screened_genes": report.screened_genes,
                "flags": [
                    {"category": f.category, "severity": f.severity,
                     "gene_id": f.gene_id, "gene_name": f.gene_name,
                     "product": f.product, "signal": f.signal, "source": f.source}
                    for f in report.flags
                ],
            })
        except Exception:  # safety screen must never fail the job
            pass

        job.status = JobStatus.COMPLETED.value
        job.report_url = f"/reports/{job_id}.html"
        job.total_genes = summary.total_genes
        job.interpreted_genes = summary.interpreted_genes
        job.high_confidence_count = summary.high_confidence_count
        job.dark_count = dark_count
        job.processing_time_seconds = int(summary.processing_time_seconds)
        job.genes_json = genes_json
        job.safety_json = safety_json
        db.commit()

    except Exception as e:
        job.status = JobStatus.FAILED.value
        job.error_message = str(e)
        db.commit()
    finally:
        db.close()
