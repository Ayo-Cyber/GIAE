# Quickstart Guide

Start interpreting genomes in minutes.

## 1. Installation

```bash
pip install giae
```

## 2. Basic Usage

Interpret a GenBank file with default settings:

```bash
giae interpret genome.gb
```

## 3. Options

*   **Output to file**: `giae interpret genome.gb -o report.md`
*   **JSON Format**: `giae interpret genome.gb -f json`
*   **Parallel Workers**: `giae interpret genome.gb --workers 4`
*   **Offline Mode**: `giae interpret genome.gb --no-uniprot --no-interpro`

## 4. Database Management

If you want to use local plugins (BLAST+, HMMER):

```bash
giae db status
giae db download prosite
giae db download pfam
```
