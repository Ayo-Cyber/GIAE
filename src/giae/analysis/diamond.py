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
