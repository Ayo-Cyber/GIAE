"""PROSITE database loader for GIAE.

Parses the PROSITE pattern database and converts patterns
to Python regex format for use with the motif scanner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from giae.analysis.motif import MotifPattern


@dataclass
class PROSITEEntry:
    """A single PROSITE database entry."""

    id: str
    accession: str
    description: str
    pattern: str  # Original PROSITE notation
    regex: str    # Converted Python regex
    skip_flag: bool = False  # High-frequency patterns to skip
    entry_type: str = "PATTERN"  # PATTERN, MATRIX, or RULE


def prosite_to_regex(pattern: str) -> str:
    """
    Convert PROSITE pattern notation to Python regex.

    PROSITE syntax:
    - x = any amino acid
    - [ABC] = any of A, B, C
    - {ABC} = any except A, B, C
    - x(3) = exactly 3 of any
    - x(2,4) = 2 to 4 of any
    - < = N-terminus
    - > = C-terminus
    - - = separator (ignored)
    - . = end of pattern

    Args:
        pattern: PROSITE pattern string.

    Returns:
        Python regex pattern string.
    """
    if not pattern or pattern == ".":
        return ""

    # Remove trailing period and newlines
    pattern = pattern.rstrip(".\n\r ")

    # Remove hyphens (separators)
    pattern = pattern.replace("-", "")

    result = []
    i = 0

    while i < len(pattern):
        char = pattern[i]

        if char == "x":
            # Any amino acid
            i += 1
            # Check for quantifier
            if i < len(pattern) and pattern[i] == "(":
                end = pattern.find(")", i)
                if end != -1:
                    quantifier = pattern[i + 1:end]
                    if "," in quantifier:
                        # Range: x(2,4) -> .{2,4}
                        result.append(f".{{{quantifier}}}")
                    else:
                        # Exact: x(3) -> .{3}
                        result.append(f".{{{quantifier}}}")
                    i = end + 1
                else:
                    result.append(".")
            else:
                result.append(".")

        elif char == "[":
            # Character class [ABC]
            end = pattern.find("]", i)
            if end != -1:
                char_class = pattern[i:end + 1]
                result.append(char_class)
                i = end + 1
            else:
                i += 1

        elif char == "{":
            # Negated class {ABC} -> [^ABC]
            end = pattern.find("}", i)
            if end != -1:
                chars = pattern[i + 1:end]
                result.append(f"[^{chars}]")
                i = end + 1
            else:
                i += 1

        elif char == "<":
            # N-terminus
            result.append("^")
            i += 1

        elif char == ">":
            # C-terminus
            result.append("$")
            i += 1

        elif char.isupper():
            # Single amino acid
            i += 1
            # Check for quantifier
            if i < len(pattern) and pattern[i] == "(":
                end = pattern.find(")", i)
                if end != -1:
                    quantifier = pattern[i + 1:end]
                    if "," in quantifier:
                        result.append(f"{char}{{{quantifier}}}")
                    else:
                        result.append(f"{char}{{{quantifier}}}")
                    i = end + 1
                else:
                    result.append(char)
            else:
                result.append(char)

        else:
            i += 1

    return "".join(result)


def parse_prosite_file(filepath: Path) -> Iterator[PROSITEEntry]:
    """
    Parse a PROSITE .dat file and yield entries.

    Args:
        filepath: Path to prosite.dat file.

    Yields:
        PROSITEEntry objects for each pattern.
    """
    current_id = ""
    current_ac = ""
    current_de = ""
    current_pa = ""
    skip_flag = False
    entry_type = "PATTERN"

    with open(filepath, "r", encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\n\r")

            if line.startswith("ID   "):
                # New entry
                parts = line[5:].split(";")
                current_id = parts[0].strip()
                if len(parts) > 1:
                    entry_type = parts[1].strip().rstrip(".")

            elif line.startswith("AC   "):
                current_ac = line[5:].rstrip(";").strip()

            elif line.startswith("DE   "):
                current_de = line[5:].strip()

            elif line.startswith("PA   "):
                current_pa += line[5:].strip()

            elif line.startswith("CC   "):
                if "/SKIP-FLAG=TRUE" in line:
                    skip_flag = True

            elif line.startswith("//"):
                # End of entry
                if current_id and current_pa and entry_type == "PATTERN":
                    try:
                        regex = prosite_to_regex(current_pa)
                        if regex:
                            yield PROSITEEntry(
                                id=current_id,
                                accession=current_ac,
                                description=current_de,
                                pattern=current_pa,
                                regex=regex,
                                skip_flag=skip_flag,
                                entry_type=entry_type,
                            )
                    except Exception:
                        # Skip patterns that fail to convert
                        pass

                # Reset
                current_id = ""
                current_ac = ""
                current_de = ""
                current_pa = ""
                skip_flag = False
                entry_type = "PATTERN"


@dataclass
class PROSITEDatabase:
    """
    PROSITE pattern database loader.

    Loads and caches PROSITE patterns for use with the motif scanner.

    Attributes:
        filepath: Path to prosite.dat file.
        include_skip: Whether to include high-frequency patterns (default: False).
        entries: Loaded PROSITE entries.

    Example:
        >>> db = PROSITEDatabase("data/prosite/prosite.dat")
        >>> db.load()
        >>> print(f"Loaded {len(db.entries)} patterns")
        >>> patterns = db.get_motif_patterns()
    """

    filepath: Path
    include_skip: bool = False
    entries: list[PROSITEEntry] = field(default_factory=list)
    _loaded: bool = field(default=False, repr=False)

    def load(self) -> int:
        """
        Load patterns from the database file.

        Returns:
            Number of patterns loaded.
        """
        self.entries = []

        for entry in parse_prosite_file(self.filepath):
            if self.include_skip or not entry.skip_flag:
                self.entries.append(entry)

        self._loaded = True
        return len(self.entries)

    def get_entry_by_id(self, entry_id: str) -> PROSITEEntry | None:
        """Find an entry by its ID."""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None

    def get_entry_by_accession(self, accession: str) -> PROSITEEntry | None:
        """Find an entry by its accession number."""
        for entry in self.entries:
            if entry.accession == accession:
                return entry
        return None

    def search_description(self, query: str) -> list[PROSITEEntry]:
        """Search entries by description keyword."""
        query_lower = query.lower()
        return [e for e in self.entries if query_lower in e.description.lower()]

    def get_motif_patterns(self) -> list[MotifPattern]:
        """
        Convert all entries to MotifPattern objects.

        Returns:
            List of MotifPattern objects for use with MotifScanner.
        """
        patterns = []

        for entry in self.entries:
            # Determine category based on description
            category = self._categorize_entry(entry)

            patterns.append(MotifPattern(
                name=entry.id.lower(),
                pattern=entry.regex,
                description=entry.description,
                category=category,
                confidence_weight=0.7 if entry.skip_flag else 0.85,
            ))

        return patterns

    def _categorize_entry(self, entry: PROSITEEntry) -> str:
        """Categorize an entry based on its description."""
        desc_lower = entry.description.lower()

        if any(kw in desc_lower for kw in ["phosphorylation", "kinase"]):
            return "modification"
        elif any(kw in desc_lower for kw in ["glycosylation", "glycan"]):
            return "modification"
        elif any(kw in desc_lower for kw in ["zinc", "metal", "iron", "copper"]):
            return "domain"
        elif any(kw in desc_lower for kw in ["dna", "rna", "nucleic"]):
            return "domain"
        elif any(kw in desc_lower for kw in ["membrane", "transmembrane"]):
            return "topology"
        elif any(kw in desc_lower for kw in ["signal", "targeting"]):
            return "signal"
        elif any(kw in desc_lower for kw in ["active site", "catalytic"]):
            return "active_site"
        else:
            return "domain"

    def get_summary(self) -> dict:
        """Get summary statistics about loaded patterns."""
        categories: dict[str, int] = {}
        for entry in self.entries:
            cat = self._categorize_entry(entry)
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_patterns": len(self.entries),
            "by_category": categories,
            "skip_patterns_included": self.include_skip,
        }


def load_prosite_patterns(
    filepath: Path | str,
    include_skip: bool = False,
) -> list[MotifPattern]:
    """
    Convenience function to load PROSITE patterns.

    Args:
        filepath: Path to prosite.dat file.
        include_skip: Whether to include high-frequency patterns.

    Returns:
        List of MotifPattern objects ready for use.
    """
    db = PROSITEDatabase(Path(filepath), include_skip=include_skip)
    db.load()
    return db.get_motif_patterns()
