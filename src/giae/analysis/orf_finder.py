"""ORF (Open Reading Frame) finder for GIAE.

Detects potential coding sequences in unannotated genomes
by scanning for open reading frames.

When pyrodigal is installed (`pip install giae[annotation]`), it is used as
the primary gene-finder because it applies Prodigal's dynamic-programming
model with proper RBS scoring and GC-content-aware start codon weighting.
If pyrodigal is not available the naive six-frame ATG scanner is used as a
fallback — same interface, lower accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from giae.models.gene import Gene, GeneLocation, Strand
from giae.models.protein import Protein

# Standard genetic code (codon -> amino acid)
CODON_TABLE = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}

START_CODONS = {"ATG", "GTG", "TTG"}  # Common bacterial start codons
STOP_CODONS = {"TAA", "TAG", "TGA"}


@dataclass
class ORFResult:
    """Result of ORF detection."""

    start: int  # 0-based position
    end: int  # 0-based, exclusive
    strand: Strand
    frame: int  # Reading frame (0, 1, or 2)
    nucleotide_sequence: str
    protein_sequence: str

    @property
    def length_bp(self) -> int:
        """Length in base pairs."""
        return self.end - self.start

    @property
    def length_aa(self) -> int:
        """Length in amino acids."""
        return len(self.protein_sequence.rstrip("*"))


@dataclass
class ORFFinder:
    """
    Find Open Reading Frames in nucleotide sequences.

    Uses pyrodigal (Prodigal port) when installed, falling back to a
    six-frame ATG scanner otherwise.  Both backends expose the same
    public interface so callers do not need to know which is active.

    Attributes:
        min_length: Minimum ORF length in base pairs (default: 100).
        start_codons: Set of valid start codons (naive backend only).
        include_partial: Whether to include ORFs at sequence boundaries
            (naive backend only).
        use_pyrodigal: Try pyrodigal before the naive scanner (default True).

    Example:
        >>> finder = ORFFinder(min_length=150)
        >>> orfs = finder.find_orfs("ATGAAACGTACG...TAA...")
        >>> for orf in orfs:
        ...     print(f"ORF at {orf.start}-{orf.end}, {orf.length_aa} aa")
    """

    min_length: int = 100
    start_codons: set[str] = field(default_factory=lambda: START_CODONS.copy())
    include_partial: bool = False
    use_pyrodigal: bool = True

    def find_orfs(self, sequence: str) -> list[ORFResult]:
        """
        Find all ORFs in a sequence.

        Tries pyrodigal first when `use_pyrodigal` is True and the package
        is installed.  Falls back to the six-frame naive scanner otherwise.

        Args:
            sequence: DNA sequence (uppercase ATGC).

        Returns:
            List of ORFResult objects for all detected ORFs.
        """
        sequence = sequence.upper()
        if self.use_pyrodigal:
            try:
                return self._pyrodigal_find_orfs(sequence)
            except ImportError:
                pass  # pyrodigal not installed — fall through
        return self._naive_find_orfs(sequence)

    # ------------------------------------------------------------------
    # Pyrodigal backend
    # ------------------------------------------------------------------

    def _pyrodigal_find_orfs(self, sequence: str) -> list[ORFResult]:
        """Use pyrodigal (Prodigal) for gene prediction."""
        import pyrodigal  # ImportError propagates to find_orfs caller

        # meta=True: no training step — works on phage genomes and single
        # contigs without needing a training sequence.
        # We don't pass min_gene because it must be > max_overlap (default 60)
        # and callers may set min_length < 60 in tests.  Instead we post-filter.
        gf = pyrodigal.GeneFinder(meta=True)
        predictions = gf.find_genes(sequence.encode())

        results: list[ORFResult] = []
        for gene in predictions:
            # pyrodigal uses 1-based inclusive coordinates.
            start = gene.begin - 1  # 0-based inclusive
            end = gene.end          # 0-based exclusive (== 1-based inclusive end)
            if end - start < self.min_length:
                continue
            strand = Strand.FORWARD if gene.strand == 1 else Strand.REVERSE
            nuc_seq = gene.sequence().upper()
            prot_seq = gene.translate().rstrip("*")
            results.append(
                ORFResult(
                    start=start,
                    end=end,
                    strand=strand,
                    frame=start % 3,
                    nucleotide_sequence=nuc_seq,
                    protein_sequence=prot_seq,
                )
            )
        results.sort(key=lambda o: o.start)
        return results

    # ------------------------------------------------------------------
    # Naive six-frame scanner (fallback)
    # ------------------------------------------------------------------

    def _naive_find_orfs(self, sequence: str) -> list[ORFResult]:
        """Six-frame ATG scanner — fallback when pyrodigal is unavailable."""
        orfs: list[ORFResult] = []

        for frame in range(3):
            orfs.extend(self._find_orfs_in_frame(sequence, frame, Strand.FORWARD))

        rev_comp = self._reverse_complement(sequence)
        for frame in range(3):
            rev_orfs = self._find_orfs_in_frame(rev_comp, frame, Strand.REVERSE)
            for orf in rev_orfs:
                new_start = len(sequence) - orf.end
                new_end = len(sequence) - orf.start
                orfs.append(
                    ORFResult(
                        start=new_start,
                        end=new_end,
                        strand=Strand.REVERSE,
                        frame=orf.frame,
                        nucleotide_sequence=orf.nucleotide_sequence,
                        protein_sequence=orf.protein_sequence,
                    )
                )

        orfs.sort(key=lambda o: o.start)
        return orfs

    def _find_orfs_in_frame(
        self,
        sequence: str,
        frame: int,
        strand: Strand,
    ) -> list[ORFResult]:
        """Find ORFs in a specific reading frame."""
        orfs: list[ORFResult] = []
        seq_len = len(sequence)
        pos = frame

        while pos < seq_len - 2:
            codon = sequence[pos : pos + 3]

            if codon in self.start_codons:
                orf_start = pos
                orf_seq = []

                i = pos
                while i < seq_len - 2:
                    c = sequence[i : i + 3]
                    if len(c) < 3:
                        break

                    aa = CODON_TABLE.get(c, "X")
                    orf_seq.append(aa)

                    if c in STOP_CODONS:
                        orf_end = i + 3
                        if orf_end - orf_start >= self.min_length:
                            orfs.append(
                                ORFResult(
                                    start=orf_start,
                                    end=orf_end,
                                    strand=strand,
                                    frame=frame,
                                    nucleotide_sequence=sequence[orf_start:orf_end],
                                    protein_sequence="".join(orf_seq),
                                )
                            )
                        break
                    i += 3
                else:
                    if self.include_partial:
                        orf_end = (seq_len - frame) // 3 * 3 + frame
                        if orf_end - orf_start >= self.min_length:
                            orfs.append(
                                ORFResult(
                                    start=orf_start,
                                    end=orf_end,
                                    strand=strand,
                                    frame=frame,
                                    nucleotide_sequence=sequence[orf_start:orf_end],
                                    protein_sequence="".join(orf_seq),
                                )
                            )

            pos += 3

        return orfs

    def _reverse_complement(self, sequence: str) -> str:
        """Get the reverse complement of a DNA sequence."""
        complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
        return "".join(complement.get(base, "N") for base in reversed(sequence))

    # ------------------------------------------------------------------
    # Gene model conversion
    # ------------------------------------------------------------------

    def orfs_to_genes(self, orfs: list[ORFResult], prefix: str = "ORF") -> list[Gene]:
        """
        Convert ORF results to Gene objects.

        Args:
            orfs: List of ORFResult from find_orfs().
            prefix: Prefix for gene locus tags.

        Returns:
            List of Gene objects with Protein attached.
        """
        genes: list[Gene] = []

        for i, orf in enumerate(orfs, 1):
            gene_id = f"gene_{uuid4().hex[:12]}"

            location = GeneLocation(
                start=orf.start,
                end=orf.end,
                strand=orf.strand,
            )

            gene = Gene(
                id=gene_id,
                locus_tag=f"{prefix}_{i:04d}",
                location=location,
                sequence=orf.nucleotide_sequence,
                source="orf_prediction",
            )

            protein = Protein(
                gene_id=gene_id,
                sequence=orf.protein_sequence,
                product_name="hypothetical protein",
            )
            gene.protein = protein

            genes.append(gene)

        return genes
