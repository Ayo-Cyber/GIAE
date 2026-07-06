"""Diamond BLASTP plugin for GIAE.

Diamond is ~10x faster than NCBI BLAST+ and produces ~3x smaller databases.
Install: conda install -c bioconda diamond  (or brew install diamond)
Build DB: giae db download swissprot-diamond
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from giae.engine.plugin import AnalysisPlugin
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene

logger = logging.getLogger(__name__)


class DiamondPlugin(AnalysisPlugin):
    """
    Wrapper for Diamond BLASTP.

    Requires the 'diamond' executable in PATH and a .dmnd database at
    ~/.giae/diamond/swissprot.dmnd (built via 'giae db download swissprot-diamond').
    """

    def __init__(self, database_path: Optional[Path] = None) -> None:
        if database_path is None:
            self.db_path = Path.home() / ".giae" / "diamond" / "swissprot"
        else:
            self.db_path = database_path

        self._binary_available = shutil.which("diamond") is not None
        if not self._binary_available:
            logger.debug("diamond executable not found in PATH")

    @property
    def name(self) -> str:
        return "diamond"

    @property
    def version(self) -> str:
        return "2.1"

    def is_available(self) -> bool:
        return self._binary_available and self._db_path().exists()

    def _db_path(self) -> Path:
        """Resolve the .dmnd file path."""
        explicit = self.db_path.with_suffix(".dmnd")
        if explicit.exists():
            return explicit
        return Path(str(self.db_path) + ".dmnd")

    def supports_batch(self) -> bool:
        """Diamond reloads the whole database per invocation, so one call for
        the entire genome is dramatically faster than one call per gene."""
        return True

    def scan_batch(self, genes) -> dict:
        """Run a single diamond blastp over every gene's protein at once.

        Diamond loads its (large) database once per process, so batching turns
        an O(genes) sequence of subprocess launches — each re-reading the DB —
        into a single scan. Query ids are the gene ids, so hits map straight
        back to their gene.
        """
        results: dict[str, list[Evidence]] = {gene.id: [] for gene in genes}
        if not self.is_available():
            return results

        # One FASTA with each gene id as the query id (diamond needs
        # whitespace-free ids; gene ids like 'gene_9781af6' satisfy this).
        chunks = []
        for gene in genes:
            if gene.protein and gene.protein.sequence:
                chunks.append(f">{gene.id}\n{gene.protein.sequence}\n")
        if not chunks:
            return results

        try:
            process = subprocess.run(
                self._cmd(),
                input="".join(chunks),
                text=True,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Diamond batch execution failed: %s", e)
            return results
        except Exception as e:  # noqa: BLE001
            logger.error("Diamond batch failed: %s", e)
            return results

        for line in process.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            qseqid, sseqid, stitle, pident_str, evalue_str, _, length_str = parts[:7]
            ev = self._make_evidence(qseqid, sseqid, stitle, pident_str, evalue_str, length_str)
            if ev is not None and qseqid in results:
                results[qseqid].append(ev)
        return results

    def _cmd(self, query_id: str = "-") -> list:
        """Diamond blastp command reading FASTA from stdin."""
        return [
            "diamond", "blastp",
            "--query", query_id,
            "--db", str(self._db_path()),
            "--outfmt", "6", "qseqid", "sseqid", "stitle",
            "pident", "evalue", "bitscore", "length",
            "--evalue", "1e-5",
            "--max-target-seqs", "10",
            "--quiet",
        ]

    def _make_evidence(self, gene_id, sseqid, stitle, pident_str, evalue_str, length_str):
        """Build one BLAST_HOMOLOGY Evidence from a diamond outfmt-6 row."""
        try:
            pident = float(pident_str) / 100.0
            evalue = float(evalue_str)
            align_len = int(length_str)
        except ValueError:
            return None
        if align_len < 30:
            return None
        return Evidence(
            gene_id=gene_id,
            evidence_type=EvidenceType.BLAST_HOMOLOGY,
            description=stitle or sseqid,
            confidence=min(pident, 1.0),
            raw_data={
                "evalue": evalue,
                "identity": pident,
                "hit_id": sseqid,
                "align_len": align_len,
            },
            provenance=EvidenceProvenance(
                tool_name="diamond",
                tool_version="local",
                database=self.db_path.name,
            ),
        )

    def scan(self, gene: Gene) -> list[Evidence]:
        """Run diamond blastp on the gene's protein sequence."""
        if not self.is_available():
            return []

        if not gene.protein or not gene.protein.sequence:
            return []

        fasta_input = f">query\n{gene.protein.sequence}\n"
        evidences: list[Evidence] = []

        try:
            cmd = [
                "diamond",
                "blastp",
                "--query",
                "-",
                "--db",
                str(self._db_path()),
                "--outfmt",
                "6",
                "qseqid",
                "sseqid",
                "stitle",
                "pident",
                "evalue",
                "bitscore",
                "length",
                "--evalue",
                "1e-5",
                "--max-target-seqs",
                "10",
                "--quiet",
            ]

            process = subprocess.run(
                cmd,
                input=fasta_input,
                text=True,
                capture_output=True,
                check=True,
            )

            for line in process.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) < 7:
                    continue

                _, sseqid, stitle, pident_str, evalue_str, _, length_str = parts[:7]
                pident = float(pident_str) / 100.0
                evalue = float(evalue_str)
                align_len = int(length_str)

                if align_len < 30:
                    continue

                evidences.append(
                    Evidence(
                        gene_id=gene.id,
                        evidence_type=EvidenceType.BLAST_HOMOLOGY,
                        description=stitle or sseqid,
                        confidence=min(pident, 1.0),
                        raw_data={
                            "evalue": evalue,
                            "identity": pident,
                            "hit_id": sseqid,
                            "align_len": align_len,
                        },
                        provenance=EvidenceProvenance(
                            tool_name="diamond",
                            tool_version="local",
                            database=self.db_path.name,
                        ),
                    )
                )

        except subprocess.CalledProcessError as e:
            logger.error("Diamond execution failed: %s", e)
        except Exception as e:
            logger.error("Diamond parsing failed for %s: %s", gene.id, e)

        return evidences
