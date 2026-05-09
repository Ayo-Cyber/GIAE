"""Aragorn tRNA/tmRNA finder for GIAE.

Aragorn detects transfer RNAs and transfer-messenger RNAs in genomic sequences.
Install: conda install -c bioconda aragorn  (or brew install aragorn)
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from giae.models.gene import Gene, GeneLocation, Strand

logger = logging.getLogger(__name__)

# Matches lines like:
#   1.  tRNA-Ala(cgc)    [55,128]      74 bp
#   2.  tRNA-Pro(tgg)    c[1234,1307]  74 bp
#   3.  tmRNA            [500,630]     131 bp
_ARAGORN_LINE = re.compile(
    r"^\s*\d+\.\s+(\S+)\s+(c?)\[(\d+),(\d+)\]"
)


class AragornFinder:
    """
    Wrapper for the Aragorn tRNA/tmRNA finder.

    Skips silently when the 'aragorn' binary is not found in PATH.
    Detected tRNAs are returned as Gene objects with
    source='tRNA_prediction' and metadata['feature_type']='tRNA'.
    """

    def is_available(self) -> bool:
        return shutil.which("aragorn") is not None

    def find_trnas(self, genome_sequence: str, genome_name: str = "seq") -> list[Gene]:
        """
        Run Aragorn and return Gene objects for each detected tRNA/tmRNA.

        Args:
            genome_sequence: Full nucleotide sequence of the genome.
            genome_name: Sequence identifier used in the FASTA header.

        Returns:
            List of Gene objects; empty if Aragorn is unavailable or finds nothing.
        """
        if not self.is_available():
            return []

        with tempfile.NamedTemporaryFile(
            suffix=".fasta", mode="w", delete=False
        ) as fh:
            fh.write(f">{genome_name}\n{genome_sequence}\n")
            fasta_path = Path(fh.name)

        try:
            result = subprocess.run(
                [
                    "aragorn",
                    "-gcbact",  # bacterial genetic code
                    "-w",       # batch output (one result per line)
                    "-l",       # treat as linear (no circularisation)
                    str(fasta_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return self._parse_output(result.stdout, genome_sequence)
        except subprocess.CalledProcessError as e:
            logger.error("Aragorn failed: %s", e.stderr.strip())
            return []
        except Exception as e:
            logger.error("Aragorn error: %s", e)
            return []
        finally:
            fasta_path.unlink(missing_ok=True)

    def _parse_output(self, output: str, sequence: str) -> list[Gene]:
        genes: list[Gene] = []
        seq_len = len(sequence)

        for line in output.splitlines():
            m = _ARAGORN_LINE.match(line)
            if not m:
                continue

            product = m.group(1)
            is_rev = m.group(2) == "c"
            start = int(m.group(3)) - 1  # convert 1-based → 0-based
            end = int(m.group(4))        # 1-based inclusive → 0-based exclusive

            if start < 0 or end > seq_len or end <= start:
                continue

            strand = Strand.REVERSE if is_rev else Strand.FORWARD
            nuc_seq = sequence[start:end]

            gene_id = f"gene_{uuid4().hex[:12]}"
            genes.append(
                Gene(
                    id=gene_id,
                    location=GeneLocation(start=start, end=end, strand=strand),
                    sequence=nuc_seq,
                    name=product,
                    source="tRNA_prediction",
                    metadata={"feature_type": "tRNA", "product": product},
                )
            )

        return genes
