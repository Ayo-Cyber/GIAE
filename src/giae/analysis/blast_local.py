"""
Local BLAST+ integration.

Provides high-speed, offline homology search against local databases.
"""

import logging
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from giae.engine.plugin import AnalysisPlugin
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene

logger = logging.getLogger(__name__)


class BlastLocalPlugin(AnalysisPlugin):
    """
    Wrapper for local NCBI BLAST+ tools.
    Requires 'blastp' executable in PATH.
    """

    def __init__(self, database_path: Optional[Path] = None) -> None:
        if database_path is None:
            # Default to bundled or user-downloaded DB
            self.db_path = Path.home() / ".giae" / "blast" / "swissprot"
        else:
            self.db_path = database_path

        self._available = shutil.which("blastp") is not None
        if not self._available:
            logger.debug("blastp executable not found in PATH")

    @property
    def name(self) -> str:
        return "blast_local"

    @property
    def version(self) -> str:
        return "2.14.0"  # Approximating BLAST+ version

    def is_available(self) -> bool:
        # Check if binary exists AND database exists
        # We relax the DB check for initialization, but scan checks it.
        return self._available

    def scan(self, gene: Gene) -> list[Evidence]:
        """Run blastp locally."""
        if not self._available:
            return []

        # Check if DB files exist (extensions .phr, .pin, .psq)
        # Typically checking for .pin is enough proxy
        if not (self.db_path.parent / (self.db_path.name + ".pin")).exists():
            # DB not downloaded/made
            return []

        if not gene.protein or not gene.protein.sequence:
            return []

        evidences = []
        try:
            # Run blastp
            cmd = [
                "blastp",
                "-query",
                "-",
                "-db",
                str(self.db_path),
                "-outfmt",
                "5",  # XML output
                "-evalue",
                "1e-5",
                "-max_target_seqs",
                "10",
            ]

            process = subprocess.run(
                cmd, input=gene.protein.sequence, text=True, capture_output=True, check=True
            )

            # Parse XML
            root = ET.fromstring(process.stdout)

            for hit in root.findall(".//Hit"):
                hit_def = hit.find("Hit_def").text  # type: ignore[union-attr]
                hit_id = hit.find("Hit_id").text  # type: ignore[union-attr]
                hsp = hit.find(".//Hsp")

                evalue = float(hsp.find("Hsp_evalue").text)  # type: ignore[union-attr]
                identity = int(hsp.find("Hsp_identity").text)  # type: ignore[union-attr]
                align_len = int(hsp.find("Hsp_align-len").text)  # type: ignore[union-attr]
                identity_pct = identity / align_len

                # Filter weak hits
                if align_len < 30:  # Short alignment
                    continue

                evidences.append(
                    Evidence(
                        gene_id=gene.id,
                        evidence_type=EvidenceType.BLAST_HOMOLOGY,
                        description=hit_def or "",
                        confidence=min(identity_pct, 1.0),
                        raw_data={
                            "evalue": evalue,
                            "identity": identity_pct,
                            "hit_id": hit_id,
                            "align_len": align_len,
                        },
                        provenance=EvidenceProvenance(
                            tool_name="blastp", tool_version="local", database=self.db_path.name
                        ),
                    )
                )

        except subprocess.CalledProcessError as e:
            logger.error(f"BLAST execution failed: {e}")
        except Exception as e:
            logger.error(f"BLAST parsing failed for {gene.id}: {e}")

        return evidences
