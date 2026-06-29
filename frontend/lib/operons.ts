import type { GeneRow } from "./types";

// Max intergenic gap (bp) for two consecutive same-strand genes to be
// considered part of the same operon. 150 bp covers the typical prokaryotic
// promoter-to-start window while separating independently regulated units.
const GAP_BP = 150;

// Minimum number of genes to call a cluster an operon (singleton = monocistronic)
const MIN_GENES = 2;

export interface Operon {
  id: number;        // 0-based index
  label: string;     // "OP-1", "OP-2", …
  genes: GeneRow[];
  start: number;
  end: number;
  strand: number;    // 1 or -1
  color: string;
}

// 12 perceptually distinct colours that don't clash with confidence colours
export const OPERON_PALETTE = [
  "#f472b6", // pink-400
  "#22d3ee", // cyan-400
  "#fb923c", // orange-400
  "#a78bfa", // violet-400
  "#4ade80", // green-400
  "#e879f9", // fuchsia-400
  "#38bdf8", // sky-400
  "#fdba74", // orange-300
  "#86efac", // green-300
  "#c4b5fd", // violet-300
  "#67e8f9", // cyan-300
  "#f9a8d4", // pink-300
];

function clusterStrand(genes: GeneRow[], startId: number): Operon[] {
  if (genes.length === 0) return [];

  const sorted = [...genes].sort((a, b) => (a.start as number) - (b.start as number));
  const operons: Operon[] = [];
  let group: GeneRow[] = [sorted[0]];

  for (let i = 1; i < sorted.length; i++) {
    const prev = group[group.length - 1];
    const gap  = (sorted[i].start as number) - (prev.end as number);
    if (gap <= GAP_BP) {
      group.push(sorted[i]);
    } else {
      if (group.length >= MIN_GENES) {
        const id = startId + operons.length;
        operons.push({
          id,
          label: `OP-${id + 1}`,
          genes: group,
          start: group[0].start as number,
          end:   group[group.length - 1].end as number,
          strand: group[0].strand ?? 1,
          color: OPERON_PALETTE[id % OPERON_PALETTE.length],
        });
      }
      group = [sorted[i]];
    }
  }
  if (group.length >= MIN_GENES) {
    const id = startId + operons.length;
    operons.push({
      id,
      label: `OP-${id + 1}`,
      genes: group,
      start: group[0].start as number,
      end:   group[group.length - 1].end as number,
      strand: group[0].strand ?? 1,
      color: OPERON_PALETTE[id % OPERON_PALETTE.length],
    });
  }
  return operons;
}

export function clusterOperons(genes: GeneRow[]): {
  operons: Operon[];
  geneToOperon: Map<string, Operon>;
} {
  const withCoords = genes.filter((g) => g.start != null && g.end != null);
  const fwd = withCoords.filter((g) => (g.strand ?? 1) !== -1);
  const rev = withCoords.filter((g) => g.strand === -1);

  const fwdOps = clusterStrand(fwd, 0);
  const revOps = clusterStrand(rev, fwdOps.length);
  const operons = [...fwdOps, ...revOps];

  const geneToOperon = new Map<string, Operon>();
  for (const op of operons) {
    for (const g of op.genes) geneToOperon.set(g.id, op);
  }

  return { operons, geneToOperon };
}
