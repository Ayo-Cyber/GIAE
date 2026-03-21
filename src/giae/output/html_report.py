"""Interactive HTML report generator for GIAE."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from giae.models.genome import Genome
    from giae.engine.interpreter import GenomeInterpretationSummary


class HTMLReportGenerator:
    """Generates interactive HTML reports for genome interpretations."""

    def __init__(self, title: str = "GIAE Interpretation Report"):
        self.title = title

    def generate(self, genome: Genome, summary: GenomeInterpretationSummary) -> str:
        """Generate HTML report content."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Prepare data for JS
        results_data = []
        for res in summary.results:
            interpretation = ""
            confidence = "NONE"
            confidence_score = 0.0
            evidence_count = 0
            reasoning = []
            category = "unknown"
            
            if res.interpretation:
                interpretation = res.interpretation.functional_label
                confidence = res.interpretation.confidence_level.value
                confidence_score = res.interpretation.confidence_score
                evidence_count = len(res.interpretation.evidence_list)
                reasoning = res.interpretation.reasoning_chain
                category = res.interpretation.category or "unknown"
            
            results_data.append({
                "id": res.gene_id,
                "name": res.gene_name or res.gene_id,
                "interpretation": interpretation,
                "confidence": confidence,
                "score": round(confidence_score, 2),
                "evidence_count": evidence_count,
                "reasoning": reasoning,
                "category": category,
                "success": res.success,
            })

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title} - {genome.name}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #0d9488;
            --primary-hover: #0f766e;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --high-conf: #10b981;
            --mod-conf: #f59e0b;
            --low-conf: #ef4444;
            --spec-conf: #8b5cf6;
            --dark-matter: #475569;
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #0f172a;
                --card-bg: #1e293b;
                --text: #f1f5f9;
                --text-muted: #94a3b8;
                --border: #334155;
            }}
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.5;
            padding-bottom: 40px;
        }}

        header {{
            background: linear-gradient(135deg, #134e4a 0%, #0d9488 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            margin-bottom: 30px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }}

        .dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            background: var(--card-bg);
            padding: 24px;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
            text-align: center;
            transition: transform 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-4px);
        }}

        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 4px;
        }}

        .stat-label {{
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .section-title {{
            font-size: 1.5rem;
            font-weight: 700;
            margin: 40px 0 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .section-title::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border);
        }}

        .search-bar {{
            margin-bottom: 20px;
            display: flex;
            gap: 12px;
        }}

        input[type="text"] {{
            flex: 1;
            padding: 12px 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--card-bg);
            color: var(--text);
            font-family: inherit;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        input:focus {{
            border-color: var(--primary);
        }}

        .controls {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .filter-btn {{
            padding: 8px 16px;
            border-radius: 9999px;
            border: 1px solid var(--border);
            background: var(--card-bg);
            color: var(--text-muted);
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .filter-btn.active {{
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }}

        .gene-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: var(--card-bg);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            border: 1px solid var(--border);
        }}

        .gene-table th {{
            background: var(--bg);
            padding: 16px 20px;
            text-align: left;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            border-bottom: 1px solid var(--border);
        }}

        .gene-table td {{
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}

        .gene-row:hover {{
            background: rgba(13, 148, 136, 0.05);
        }}

        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .badge-HIGH {{ background: rgba(16, 185, 129, 0.15); color: #059669; }}
        .badge-MODERATE {{ background: rgba(245, 158, 11, 0.15); color: #d97706; }}
        .badge-LOW {{ background: rgba(239, 68, 68, 0.15); color: #dc2626; }}
        .badge-SPECULATIVE {{ background: rgba(139, 92, 246, 0.15); color: #7c3aed; }}
        .badge-NONE {{ background: rgba(71, 85, 105, 0.15); color: #475569; }}

        .reasoning-list {{
            margin-top: 8px;
            padding-left: 20px;
            font-size: 0.875rem;
            color: var(--text-muted);
        }}

        .evidence-tag {{
            display: inline-block;
            margin-right: 4px;
            background: var(--bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
        }}

        footer {{
            margin-top: 60px;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}

        .glass-card {{
            backdrop-filter: blur(8px);
            background: rgba(255, 255, 255, 0.8);
        }}

        @media (prefers-color-scheme: dark) {{
            .glass-card {{
                background: rgba(30, 41, 59, 0.8);
            }}
        }}

        /* Animations */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .stat-card, .gene-table, .search-bar {{
            animation: fadeIn 0.4s ease-out forwards;
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>{genome.name}</h1>
            <p style="opacity: 0.8; margin-top: 8px;">GIAE Genome Interpretation Report</p>
            <div style="margin-top: 20px; font-size: 0.875rem; opacity: 0.7;">
                Generated on {now} • Version {summary.results[0].gene_id if summary.results else "N/A"}
            </div>
        </div>
    </header>

    <div class="container">
        <div class="dashboard">
            <div class="stat-card">
                <div class="stat-value">{summary.total_genes}</div>
                <div class="stat-label">Total Genes</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary.success_rate:.1f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: var(--high-conf)">{summary.high_confidence_count}</div>
                <div class="stat-label">High Confidence</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: var(--dark-matter)">{summary.novel_gene_report.dark_matter_count if summary.novel_gene_report else 0}</div>
                <div class="stat-label">Dark Matter</div>
            </div>
        </div>

        <div class="section-title">Gene Explorer</div>

        <div class="search-bar">
            <input type="text" id="searchInput" placeholder="Search by gene ID, product, or evidence..." onkeyup="filterTable()">
            <div class="controls">
                <button class="filter-btn active" onclick="setFilter('ALL', this)">All</button>
                <button class="filter-btn" onclick="setFilter('HIGH', this)">High</button>
                <button class="filter-btn" onclick="setFilter('MODERATE', this)">Moderate</button>
                <button class="filter-btn" onclick="setFilter('LOW', this)">Low/Spec</button>
                <button class="filter-btn" onclick="setFilter('DARK', this)">Dark Matter</button>
            </div>
        </div>

        <table class="gene-table" id="geneTable">
            <thead>
                <tr>
                    <th style="width: 15%">Locus / ID</th>
                    <th style="width: 35%">Interpretation</th>
                    <th style="width: 15%">Confidence</th>
                    <th style="width: 35%">Reasoning Chain</th>
                </tr>
            </thead>
            <tbody>
                <!-- Populated by JS -->
            </tbody>
        </table>

        <footer>
            <p>Generated by <strong>GIAE</strong> — Genome Interpretation & Annotation Engine</p>
            <p style="margin-top: 8px;">© 2026 GIAE Contributors • <a href="https://github.com/Ayo-Cyber/GIAE" style="color: var(--primary); text-decoration: none;">GitHub</a></p>
        </footer>
    </div>

    <script>
        const data = {json.dumps(results_data)};
        let currentFilter = 'ALL';

        function renderTable() {{
            const tbody = document.querySelector('#geneTable tbody');
            const search = document.getElementById('searchInput').value.toLowerCase();
            tbody.innerHTML = '';

            data.forEach(gene => {{
                // Filter logic
                const matchesSearch = gene.id.toLowerCase().includes(search) || 
                                     gene.interpretation.toLowerCase().includes(search) ||
                                     gene.reasoning.some(r => r.toLowerCase().includes(search));
                
                let matchesFilter = true;
                if (currentFilter === 'HIGH') matchesFilter = gene.confidence === 'HIGH';
                else if (currentFilter === 'MODERATE') matchesFilter = gene.confidence === 'MODERATE';
                else if (currentFilter === 'LOW') matchesFilter = gene.confidence === 'LOW' || gene.confidence === 'SPECULATIVE';
                else if (currentFilter === 'DARK') matchesFilter = gene.confidence === 'NONE';

                if (matchesSearch && matchesFilter) {{
                    const row = document.createElement('tr');
                    row.className = 'gene-row';
                    
                    const reasoningHtml = gene.reasoning.length > 0 
                        ? `<ul class="reasoning-list">${{gene.reasoning.map(r => `<li>${{r}}</li>`).join('')}}</ul>`
                        : '<span style="color: var(--text-muted); font-style: italic;">No detectable signal</span>';

                    row.innerHTML = `
                        <td style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${{gene.name}}</td>
                        <td>
                            <div style="font-weight: 600;">${{gene.interpretation || 'hypothetical protein'}}</div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">Category: ${{gene.category}}</div>
                        </td>
                        <td>
                            <span class="badge badge-${{gene.confidence}}">${{gene.confidence}}</span>
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">Score: ${{gene.score}}</div>
                        </td>
                        <td>${{reasoningHtml}}</td>
                    `;
                    tbody.appendChild(row);
                }}
            }});
        }}

        function filterTable() {{
            renderTable();
        }}

        function setFilter(filter, btn) {{
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderTable();
        }}

        // Initial render
        renderTable();
    </script>
</body>
</html>
"""
        return html_template
