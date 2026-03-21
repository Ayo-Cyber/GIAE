# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-19

### Added
- **Explainability Engine**: Every prediction now includes a reasoning chain and evidence aggregation.
- **Multi-layer Evidence Pipeline**:
    - PROSITE motif scanning (built-in 1,800+ patterns).
    - EBI HMMER/InterPro web API integration.
    - UniProt REST API lookup for reviewed entries.
- **Novel Gene Discovery**: New module to rank "Dark Matter" genes (no evidence) for research priority.
- **CLI Overhaul**: New `giae interpret`, `giae parse`, and `giae db` commands.
- **Parallel Processing**: Added `--workers` flag for multi-threaded genome interpretation.
- **Plugin System**: Support for local BLAST+ and HMMER plugins.
- **Rich Reporting**: Markdown and JSON output formats with stylized terminal tables.

### Improved
- Genome parsing logic for large GenBank and FASTA files.
- Confidence scoring calibration based on evidence convergence.

### Changed
- Moved source code to `src/` layout for better packaging compatibility.
- Switched to `hatchling` as the build backend.

## [0.1.0] - 2026-02-15
- Initial internal release.
- Basic motif scanning and GenBank parsing.
