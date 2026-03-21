"""
HMMER integration via pyhmmer.

Provides high-sensitivity domain detection using profile HMMs.
"""

import logging
from pathlib import Path
from typing import Optional

from giae.engine.plugin import AnalysisPlugin
from giae.models.evidence import Evidence, EvidenceProvenance, EvidenceType
from giae.models.gene import Gene

logger = logging.getLogger(__name__)


class HmmerPlugin(AnalysisPlugin):
    """
    HMMER3-based domain scanner using pyhmmer.
    Requires 'hmmer' optional usage.
    """

    def __init__(self, database_path: Optional[Path] = None) -> None:
        self.db_path = database_path
        self._available = False
        self._lib = None

        try:
            import pyhmmer

            self._lib = pyhmmer
            self._available = True
        except ImportError:
            pass

    @property
    def name(self) -> str:
        return "hmmer_scanner"

    @property
    def version(self) -> str:
        return "0.1.0"

    def is_available(self) -> bool:
        return self._available

    def scan(self, gene: Gene) -> list[Evidence]:
        """Scan gene sequence against HMM database."""
        if not self._available or not self.db_path or not self.db_path.exists():
            return []

        if not (gene.protein and gene.protein.sequence):
            return []

        evidences = []
        try:
            # We use pyhmmer's easel to digitize the sequence
            alphabet = self._lib.easel.Alphabet.amino()  # type: ignore[union-attr]
            seq_bytes = gene.protein.sequence.encode("utf-8")  # type: ignore[union-attr]
            sequence = self._lib.easel.Sequence(name=gene.id.encode("utf-8"), sequence=seq_bytes)  # type: ignore[union-attr]
            digitized = sequence.digitize(alphabet)

            # Load HMM db
            with self._lib.plan7.HMMFile(self.db_path) as hmm_file:  # type: ignore[union-attr]
                pipeline = self._lib.plan7.Pipeline(alphabet)  # type: ignore[union-attr]

                # Iterate over HMMs in the database
                for hmm in hmm_file:
                    hits = pipeline.search_hmm(hmm, [digitized])

                    for hit in hits:
                        for domain in hit.domains:
                            if domain.score < 20.0:  # Minimum bit score
                                continue

                            evidences.append(
                                Evidence(
                                    gene_id=gene.id,
                                    evidence_type=EvidenceType.DOMAIN_HIT,
                                    description=f"HMM Hit: {hmm.name.decode('utf-8')}",
                                    confidence=min(domain.score / 50.0, 1.0),  # Rough normalization
                                    raw_data={
                                        "score": domain.score,
                                        "evalue": domain.evalue,
                                        "hmm_name": hmm.name.decode("utf-8"),
                                        "hmm_desc": hmm.description.decode("utf-8")
                                        if hmm.description
                                        else "",
                                    },
                                    provenance=EvidenceProvenance(
                                        tool_name="hmmer",
                                        tool_version=self._lib.__version__,  # type: ignore[union-attr]
                                        database=str(self.db_path),
                                    ),
                                )
                            )

        except Exception as e:
            logger.error(f"HMMER scan failed for {gene.id}: {e}")

        return evidences
