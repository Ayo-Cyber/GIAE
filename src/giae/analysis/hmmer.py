"""
HMMER integration via pyhmmer.

Provides high-sensitivity domain detection using profile HMMs.
"""

from pathlib import Path
from typing import List, Any
import logging

from giae.models.evidence import Evidence, EvidenceType, EvidenceProvenance
from giae.models.gene import Gene
from giae.engine.plugin import AnalysisPlugin

logger = logging.getLogger(__name__)


class HmmerPlugin(AnalysisPlugin):
    """
    HMMER3-based domain scanner using pyhmmer.
    Requires 'hmmer' optional usage.
    """

    def __init__(self, database_path: Path = None):
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

    def scan(self, gene: Gene) -> List[Evidence]:
        """Scan gene sequence against HMM database."""
        if not self._available or not self.db_path or not self.db_path.exists():
            return []

        if not gene.protein_sequence:
            return []

        evidences = []
        try:
            # We use pyhmmer's easel to digitize the sequence
            alphabet = self._lib.easel.Alphabet.amino()
            seq_bytes = gene.protein_sequence.encode("utf-8")
            sequence = self._lib.easel.Sequence(
                name=gene.id.encode("utf-8"), 
                sequence=seq_bytes
            )
            digitized = sequence.digitize(alphabet)

            # Load HMM db
            with self._lib.plan7.HMMFile(self.db_path) as hmm_file:
                pipeline = self._lib.plan7.Pipeline(alphabet)
                
                # Iterate over HMMs in the database
                for hmm in hmm_file:
                    hits = pipeline.search_hmm(hmm, [digitized])
                    
                    for hit in hits:
                        for domain in hit.domains:
                            if domain.score < 20.0:  # Minimum bit score
                                continue
                                
                            evidences.append(Evidence(
                                gene_id=gene.id,
                                evidence_type=EvidenceType.DOMAIN_HIT,
                                source="hmmer",
                                description=f"HMM Hit: {hmm.name.decode('utf-8')}",
                                confidence=min(domain.score / 50.0, 1.0),  # Rough normalization
                                raw_data={
                                    "score": domain.score,
                                    "evalue": domain.evalue,
                                    "hmm_name": hmm.name.decode("utf-8"),
                                    "hmm_desc": hmm.description.decode("utf-8") if hmm.description else ""
                                },
                                provenance=EvidenceProvenance(
                                    tool_name="hmmer",
                                    tool_version=self._lib.__version__,
                                    database=str(self.db_path)
                                )
                            ))

        except Exception as e:
            logger.error(f"HMMER scan failed for {gene.id}: {e}")
        
        return evidences
