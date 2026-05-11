"""Barrnap rRNA finder for GIAE.

Barrnap predicts ribosomal RNA genes in bacterial, archaeal, and eukaryotic genomes.
Install: conda install -c bioconda barrnap  (or brew install barrnap)
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

_PRODUCT_RE = re.compile(r"product=([^;]+)")


class BarrnapFinder:
    """
    Wrapper for Barrnap rRNA prediction.

    Skips silently when the 'barrnap' binary is not found in PATH.
    Detected rRNAs are returned as Gene objects with
    source='rRNA_prediction' and metadata['feature_type']='rRNA'.
    """

    def __init__(self, kingdom: str = "bac") -> None:
        # kingdom: bac, arc, euk, mito
        self.kingdom = kingdom

    def is_available(self) -> bool:
        return shutil.which("barrnap") is not None

    def find_rrnas(self, genome_sequence: str, genome_name: str = "seq") -> list[Gene]:
        """
        Run Barrnap and return Gene objects for each detected rRNA.

        Args:
            genome_sequence: Full nucleotide sequence of the genome.
            genome_name: Sequence identifier used in the FASTA header.

        Returns:
            List of Gene objects; empty if Barrnap is unavailable or finds nothing.
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
                    "barrnap",
                    "--kingdom",
                    self.kingdom,
                    "--quiet",
                    str(fasta_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return self._parse_gff(result.stdout, genome_sequence)
        except subprocess.CalledProcessError as e:
            logger.error("Barrnap failed: %s", e.stderr.strip())
            return []
        except Exception as e:
            logger.error("Barrnap error: %s", e)
            return []
        finally:
            fasta_path.unlink(missing_ok=True)

    def _parse_gff(self, gff: str, sequence: str) -> list[Gene]:
        genes: list[Gene] = []
        seq_len = len(sequence)

        for line in gff.splitlines():
            if line.startswith("#") or not line.strip():
                continue

            parts = line.split("\t")
            if len(parts) < 9:
                continue

            try:
                start = int(parts[3]) - 1  # 1-based inclusive → 0-based
                end = int(parts[4])        # 1-based inclusive → 0-based exclusive
                strand_char = parts[6]
                attrs = parts[8]
            except (ValueError, IndexError):
                continue

            if start < 0 or end > seq_len or end <= start:
                continue

            strand = Strand.REVERSE if strand_char == "-" else Strand.FORWARD

            product = "rRNA"
            m = _PRODUCT_RE.search(attrs)
            if m:
                product = m.group(1).strip()

            nuc_seq = sequence[start:end]
            gene_id = f"gene_{uuid4().hex[:12]}"
            genes.append(
                Gene(
                    id=gene_id,
                    location=GeneLocation(start=start, end=end, strand=strand),
                    sequence=nuc_seq,
                    name=product,
                    source="rRNA_prediction",
                    metadata={"feature_type": "rRNA", "product": product},
                )
            )

        return genes
