import type { Job, GeneRow } from "./types";

// ── helpers ──────────────────────────────────────────────────────────────────

function escapeGff(s: string) {
  return s.replace(/[;\n\r=%&,]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);
}

function strandChar(g: GeneRow) {
  return g.strand === -1 ? "-" : "+";
}

function seqId(job: Job) {
  return job.filename.replace(/\.[^.]+$/, "");
}

// ── GFF3 ─────────────────────────────────────────────────────────────────────

export function toGff3(job: Job): string {
  const sid = seqId(job);
  const lines: string[] = [
    "##gff-version 3",
    `##source GIAE v0.2`,
    `##genome-build . ${sid}`,
  ];

  for (const g of job.genes) {
    if (g.start == null || g.end == null) continue;
    const type = g.is_dark ? "gene" : "CDS";
    const attrs: string[] = [
      `ID=${escapeGff(g.id)}`,
      `Name=${escapeGff(g.name)}`,
      `locus_tag=${escapeGff(g.locus)}`,
    ];
    if (g.normalized_product || g.function)
      attrs.push(`product=${escapeGff(g.normalized_product ?? g.function ?? "")}`);
    if (g.score != null) attrs.push(`score=${g.score.toFixed(3)}`);
    if (g.confidence)    attrs.push(`confidence=${g.confidence}`);
    if (g.is_dark)       attrs.push(`dark_matter=true`);
    if (g.pfam_id)       attrs.push(`Dbxref=Pfam:${escapeGff(g.pfam_id)}`);
    if (g.go_terms?.length) attrs.push(`Ontology_term=${g.go_terms.map(escapeGff).join(",")}`);

    lines.push(
      [sid, "GIAE", type, g.start, g.end, g.score?.toFixed(3) ?? ".", strandChar(g), ".", attrs.join(";")].join("\t")
    );
  }

  return lines.join("\n") + "\n";
}

// ── TSV ──────────────────────────────────────────────────────────────────────

const TSV_COLS = [
  "locus_tag", "name", "start", "end", "strand", "length_bp",
  "confidence", "score", "is_dark", "function", "product",
  "cog_category", "pfam_id", "go_terms", "reasoning",
];

export function toTsv(job: Job): string {
  const rows = [TSV_COLS.join("\t")];
  for (const g of job.genes) {
    rows.push([
      g.locus,
      g.name,
      g.start ?? "",
      g.end ?? "",
      g.strand ?? "",
      g.length ?? "",
      g.confidence ?? "",
      g.score?.toFixed(3) ?? "",
      g.is_dark ? "true" : "false",
      g.function ?? "",
      g.normalized_product ?? "",
      g.cog_category ?? "",
      g.pfam_id ?? "",
      (g.go_terms ?? []).join("|"),
      (g.reasoning ?? "").replace(/\t|\n/g, " "),
    ].join("\t"));
  }
  return rows.join("\n") + "\n";
}

// ── JSON ─────────────────────────────────────────────────────────────────────

export function toJson(job: Job): string {
  return JSON.stringify(
    {
      job_id: job.job_id,
      filename: job.filename,
      status: job.status,
      total_genes: job.total_genes,
      high_confidence_count: job.high_confidence_count,
      dark_count: job.dark_count,
      processing_time_seconds: job.processing_time_seconds,
      created_at: job.created_at,
      genes: job.genes,
    },
    null,
    2
  );
}

// ── GenBank feature table (simplified) ───────────────────────────────────────

export function toGenbank(job: Job): string {
  const sid = seqId(job);
  const lines: string[] = [
    `LOCUS       ${sid.padEnd(16)} bp    DNA`,
    `DEFINITION  ${sid} — annotated by GIAE v0.2`,
    `ACCESSION   .`,
    `VERSION     .`,
    `FEATURES             Location/Qualifiers`,
  ];

  for (const g of job.genes) {
    if (g.start == null || g.end == null) continue;
    const loc = g.strand === -1 ? `complement(${g.start}..${g.end})` : `${g.start}..${g.end}`;
    const feature = g.is_dark ? "gene" : "CDS";
    lines.push(`     ${feature.padEnd(16)}${loc}`);

    const qual = (key: string, val: string) =>
      lines.push(`                     /${key}="${val.replace(/"/g, "'")}"`);

    qual("locus_tag", g.locus);
    qual("gene", g.name);
    if (g.normalized_product || g.function) qual("product", g.normalized_product ?? g.function ?? "");
    if (g.confidence)  qual("note", `GIAE_confidence=${g.confidence}`);
    if (g.score != null) qual("note", `GIAE_score=${g.score.toFixed(3)}`);
    if (g.is_dark)     qual("note", "GIAE_dark_matter=true");
    if (g.pfam_id)     qual("db_xref", `Pfam:${g.pfam_id}`);
  }

  lines.push("//");
  return lines.join("\n") + "\n";
}

// ── trigger browser download ──────────────────────────────────────────────────

export function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
