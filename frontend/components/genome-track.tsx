"use client";

import {
  useMemo,
  useState,
  useRef,
  useEffect,
  useCallback,
  WheelEvent,
  MouseEvent,
} from "react";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import type { GeneRow } from "@/lib/types";
import { cn } from "@/lib/utils";

interface GenomeTrackProps {
  genes: GeneRow[];
  selectedId?: string | null;
  onSelect: (gene: GeneRow) => void;
}

function confidenceFill(g: GeneRow): string {
  if (g.is_dark) return "#b45309"; // amber-700 (dark matter)
  switch (g.confidence) {
    case "HIGH": return "#34d399";       // emerald-400
    case "MODERATE": return "#f59e0b";   // amber-500
    case "LOW": return "#818cf8";        // indigo-400
    case "SPECULATIVE": return "#a78bfa"; // violet-400
    default: return "#4b5563";           // gray-600
  }
}

function formatBp(bp: number): string {
  const abs = Math.abs(bp);
  if (abs >= 1_000_000) return `${(bp / 1_000_000).toFixed(2)} Mb`;
  if (abs >= 1_000) return `${(bp / 1_000).toFixed(1)} kb`;
  return `${Math.round(bp)} bp`;
}

const MIN_VIEW_BP = 200;       // can't zoom in tighter than 200 bp
const MAIN_HEIGHT = 110;
const MINI_HEIGHT = 36;
const PAD_L = 12;
const PAD_R = 12;

export function GenomeTrack({ genes, selectedId, onSelect }: GenomeTrackProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [hovered, setHovered] = useState<GeneRow | null>(null);

  // Track container width
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(w);
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Compute genome bounds
  const { genomeStart, genomeEnd, withCoords } = useMemo(() => {
    const wc = genes.filter((g) => g.start != null && g.end != null);
    if (wc.length === 0) {
      return { genomeStart: 0, genomeEnd: 0, withCoords: [] };
    }
    return {
      genomeStart: Math.min(...wc.map((g) => g.start as number)),
      genomeEnd: Math.max(...wc.map((g) => g.end as number)),
      withCoords: wc,
    };
  }, [genes]);

  const fullSpan = genomeEnd - genomeStart;
  // viewport coordinates — start in full-genome view
  const [view, setView] = useState<{ start: number; end: number }>({
    start: 0,
    end: 0,
  });
  // Initialise + reset when genome changes
  useEffect(() => {
    setView({ start: genomeStart, end: genomeEnd });
  }, [genomeStart, genomeEnd]);

  // Auto-zoom to selected gene if it's not yet visible
  useEffect(() => {
    if (!selectedId) return;
    const g = withCoords.find((gn) => gn.id === selectedId);
    if (!g || g.start == null || g.end == null) return;
    if (g.start < view.start || g.end > view.end) {
      // pan to center the gene without changing zoom level
      const mid = (g.start + g.end) / 2;
      const half = (view.end - view.start) / 2;
      const ns = Math.max(genomeStart, mid - half);
      const ne = Math.min(genomeEnd, ns + (view.end - view.start));
      setView({ start: Math.max(genomeStart, ne - (view.end - view.start)), end: ne });
    }
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (fullSpan <= 0) {
    return (
      <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-5 text-center">
        <p className="text-xs text-gray-500">
          Genome coordinates unavailable for this job — re-run it to populate.
        </p>
      </div>
    );
  }

  const viewSpan = Math.max(view.end - view.start, MIN_VIEW_BP);
  const zoomPct = (fullSpan / viewSpan).toFixed(viewSpan === fullSpan ? 0 : 1);

  // ── projections ────────────────────────────────────────────────────────
  const innerW = Math.max(width - PAD_L - PAD_R, 100);
  const xOf = (bp: number) =>
    PAD_L + ((bp - view.start) / viewSpan) * innerW;
  const bpOf = (px: number) =>
    view.start + ((px - PAD_L) / innerW) * viewSpan;
  const xMini = (bp: number) =>
    PAD_L + ((bp - genomeStart) / fullSpan) * innerW;

  // Visible genes only (with a small over-render margin so partial-overlap genes are drawn)
  const margin = viewSpan * 0.02;
  const visibleGenes = withCoords.filter((g) => {
    const s = g.start as number;
    const e = g.end as number;
    return e >= view.start - margin && s <= view.end + margin;
  });
  const forwardGenes = visibleGenes.filter((g) => g.strand === 1 || g.strand == null);
  const reverseGenes = visibleGenes.filter((g) => g.strand === -1);

  // ── interactions ───────────────────────────────────────────────────────
  const zoomAt = useCallback(
    (centerBp: number, factor: number) => {
      setView((v) => {
        const span = Math.max(v.end - v.start, MIN_VIEW_BP);
        let newSpan = Math.max(MIN_VIEW_BP, Math.min(fullSpan, span * factor));
        // Re-anchor so centerBp stays at the same fractional position
        const frac = (centerBp - v.start) / span;
        let ns = centerBp - frac * newSpan;
        let ne = ns + newSpan;
        if (ns < genomeStart) {
          ns = genomeStart;
          ne = ns + newSpan;
        }
        if (ne > genomeEnd) {
          ne = genomeEnd;
          ns = ne - newSpan;
        }
        return { start: Math.max(genomeStart, ns), end: Math.min(genomeEnd, ne) };
      });
    },
    [fullSpan, genomeStart, genomeEnd]
  );

  const handleWheel = (e: WheelEvent<SVGSVGElement>) => {
    if (!e.ctrlKey && !e.metaKey && Math.abs(e.deltaY) < Math.abs(e.deltaX)) return;
    e.preventDefault();
    // Convert mouse X to bp
    const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const center = bpOf(mouseX);
    const factor = e.deltaY > 0 ? 1.18 : 1 / 1.18;
    zoomAt(center, factor);
  };

  // Drag-to-pan on main track
  const dragRef = useRef<{ startX: number; startView: { start: number; end: number } } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const onMainMouseDown = (e: MouseEvent<SVGSVGElement>) => {
    dragRef.current = { startX: e.clientX, startView: { ...view } };
    setIsDragging(true);
  };
  useEffect(() => {
    if (!isDragging) return;
    const onMove = (e: globalThis.MouseEvent) => {
      if (!dragRef.current) return;
      const dx = e.clientX - dragRef.current.startX;
      const dxBp = -(dx / innerW) * (dragRef.current.startView.end - dragRef.current.startView.start);
      let ns = dragRef.current.startView.start + dxBp;
      let ne = dragRef.current.startView.end + dxBp;
      const span = ne - ns;
      if (ns < genomeStart) { ns = genomeStart; ne = ns + span; }
      if (ne > genomeEnd) { ne = genomeEnd; ns = ne - span; }
      setView({ start: ns, end: ne });
    };
    const onUp = () => {
      setIsDragging(false);
      dragRef.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isDragging, innerW, genomeStart, genomeEnd]);

  // Brush on minimap
  const brushRef = useRef<{ mode: "move" | "resize-l" | "resize-r"; startX: number; startView: { start: number; end: number } } | null>(null);
  const [brushDragging, setBrushDragging] = useState(false);
  const onBrushDown = (e: MouseEvent<SVGRectElement>, mode: "move" | "resize-l" | "resize-r") => {
    e.stopPropagation();
    brushRef.current = { mode, startX: e.clientX, startView: { ...view } };
    setBrushDragging(true);
  };
  useEffect(() => {
    if (!brushDragging) return;
    const onMove = (e: globalThis.MouseEvent) => {
      if (!brushRef.current) return;
      const dxPx = e.clientX - brushRef.current.startX;
      const dxBp = (dxPx / innerW) * fullSpan;
      let ns = brushRef.current.startView.start;
      let ne = brushRef.current.startView.end;
      if (brushRef.current.mode === "move") {
        ns += dxBp;
        ne += dxBp;
        const span = ne - ns;
        if (ns < genomeStart) { ns = genomeStart; ne = ns + span; }
        if (ne > genomeEnd) { ne = genomeEnd; ns = ne - span; }
      } else if (brushRef.current.mode === "resize-l") {
        ns = Math.min(ne - MIN_VIEW_BP, Math.max(genomeStart, ns + dxBp));
      } else {
        ne = Math.max(ns + MIN_VIEW_BP, Math.min(genomeEnd, ne + dxBp));
      }
      setView({ start: ns, end: ne });
    };
    const onUp = () => {
      setBrushDragging(false);
      brushRef.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [brushDragging, innerW, fullSpan, genomeStart, genomeEnd]);

  const clickToSelect = (g: GeneRow) => onSelect(g);

  // Auto-tick step for current view
  const tickStep = (() => {
    const target = Math.max(4, Math.floor(innerW / 120));
    const rough = viewSpan / target;
    const mag = Math.pow(10, Math.floor(Math.log10(rough)));
    for (const m of [1, 2, 5, 10]) {
      if (m * mag >= rough) return m * mag;
    }
    return 10 * mag;
  })();
  const ticks: number[] = [];
  for (let v = Math.ceil(view.start / tickStep) * tickStep; v <= view.end; v += tickStep) {
    ticks.push(v);
  }

  // Strand-track positions
  const FWD_Y = 28;
  const REV_Y = 56;
  const TRACK_H = 18;
  const AXIS_Y = MAIN_HEIGHT - 16;

  // Tooltip placement
  const tooltipLeft = hovered && hovered.start != null && hovered.end != null
    ? Math.min(
        Math.max(xOf((hovered.start + hovered.end) / 2) - 90, 4),
        width - 184
      )
    : 0;

  // Reset / zoom button handlers
  const resetView = () => setView({ start: genomeStart, end: genomeEnd });
  const zoomCentred = (factor: number) => zoomAt((view.start + view.end) / 2, factor);

  return (
    <div className="bg-[#0f0f1e] border border-white/6 rounded-xl p-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-3 gap-4">
        <div className="min-w-0">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">
            Genome map
          </p>
          <p className="text-[11px] text-gray-600 mt-0.5">
            {withCoords.length} genes · viewing{" "}
            <span className="mono text-gray-400">
              {formatBp(view.start)}–{formatBp(view.end)}
            </span>{" "}
            of {formatBp(fullSpan)} · <span className="mono text-gray-400">{zoomPct}×</span>{" "}
            zoom
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="hidden md:flex items-center gap-2 text-[10px] text-gray-500 mr-2">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-400" /> HIGH</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-amber-500" /> MOD</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-indigo-400" /> LOW</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-amber-700" /> DARK</span>
          </div>
          <button
            onClick={() => zoomCentred(1 / 1.5)}
            className="w-7 h-7 rounded-md bg-white/4 hover:bg-white/8 border border-white/8 flex items-center justify-center text-gray-400 hover:text-white transition-colors"
            title="Zoom in"
          >
            <ZoomIn size={13} />
          </button>
          <button
            onClick={() => zoomCentred(1.5)}
            disabled={viewSpan >= fullSpan}
            className="w-7 h-7 rounded-md bg-white/4 hover:bg-white/8 border border-white/8 flex items-center justify-center text-gray-400 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Zoom out"
          >
            <ZoomOut size={13} />
          </button>
          <button
            onClick={resetView}
            disabled={view.start === genomeStart && view.end === genomeEnd}
            className="w-7 h-7 rounded-md bg-white/4 hover:bg-white/8 border border-white/8 flex items-center justify-center text-gray-400 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Reset view"
          >
            <Maximize2 size={12} />
          </button>
        </div>
      </div>

      <div ref={containerRef} className="relative">
        {/* MAIN TRACK */}
        <svg
          width="100%"
          height={MAIN_HEIGHT}
          className={cn(
            "block select-none",
            isDragging ? "cursor-grabbing" : "cursor-grab"
          )}
          onWheel={handleWheel}
          onMouseDown={onMainMouseDown}
          onMouseLeave={() => setHovered(null)}
        >
          {/* Strand labels */}
          <text x={2} y={FWD_Y + TRACK_H / 2 + 3} fontSize="10" fill="#6b7280" fontWeight="600">
            +
          </text>
          <text x={2} y={REV_Y + TRACK_H / 2 + 3} fontSize="10" fill="#6b7280" fontWeight="600">
            −
          </text>

          {/* Centre line */}
          <line
            x1={PAD_L}
            x2={width - PAD_R}
            y1={FWD_Y + TRACK_H + 4}
            y2={FWD_Y + TRACK_H + 4}
            stroke="rgba(255,255,255,0.05)"
            strokeWidth={1}
          />

          {/* Genes — forward strand */}
          {forwardGenes.map((g) => {
            const x1 = xOf(g.start as number);
            const x2 = xOf(g.end as number);
            const w = Math.max(x2 - x1, 1.5);
            const isSel = g.id === selectedId;
            const isHov = hovered?.id === g.id;
            return (
              <g key={g.id}>
                <rect
                  x={x1}
                  y={FWD_Y}
                  width={w}
                  height={TRACK_H}
                  rx={2}
                  fill={confidenceFill(g)}
                  opacity={selectedId == null || isSel || isHov ? 1 : 0.5}
                  stroke={isSel ? "#ffffff" : "transparent"}
                  strokeWidth={isSel ? 1.5 : 0}
                  className="cursor-pointer transition-opacity"
                  onMouseEnter={() => setHovered(g)}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={() => clickToSelect(g)}
                />
                {w >= 22 && (
                  <text
                    x={x1 + w / 2}
                    y={FWD_Y + TRACK_H / 2 + 3.5}
                    fontSize="9"
                    fill="#0a0a14"
                    textAnchor="middle"
                    fontWeight="600"
                    pointerEvents="none"
                  >
                    {g.name.length > Math.floor(w / 6) ? g.name.slice(0, Math.floor(w / 6) - 1) + "…" : g.name}
                  </text>
                )}
              </g>
            );
          })}

          {/* Genes — reverse strand */}
          {reverseGenes.map((g) => {
            const x1 = xOf(g.start as number);
            const x2 = xOf(g.end as number);
            const w = Math.max(x2 - x1, 1.5);
            const isSel = g.id === selectedId;
            const isHov = hovered?.id === g.id;
            return (
              <g key={g.id}>
                <rect
                  x={x1}
                  y={REV_Y}
                  width={w}
                  height={TRACK_H}
                  rx={2}
                  fill={confidenceFill(g)}
                  opacity={selectedId == null || isSel || isHov ? 1 : 0.5}
                  stroke={isSel ? "#ffffff" : "transparent"}
                  strokeWidth={isSel ? 1.5 : 0}
                  className="cursor-pointer transition-opacity"
                  onMouseEnter={() => setHovered(g)}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={() => clickToSelect(g)}
                />
                {w >= 22 && (
                  <text
                    x={x1 + w / 2}
                    y={REV_Y + TRACK_H / 2 + 3.5}
                    fontSize="9"
                    fill="#0a0a14"
                    textAnchor="middle"
                    fontWeight="600"
                    pointerEvents="none"
                  >
                    {g.name.length > Math.floor(w / 6) ? g.name.slice(0, Math.floor(w / 6) - 1) + "…" : g.name}
                  </text>
                )}
              </g>
            );
          })}

          {/* Axis */}
          <line
            x1={PAD_L}
            x2={width - PAD_R}
            y1={AXIS_Y}
            y2={AXIS_Y}
            stroke="rgba(255,255,255,0.12)"
            strokeWidth={1}
          />
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={xOf(t)}
                x2={xOf(t)}
                y1={AXIS_Y}
                y2={AXIS_Y + 4}
                stroke="rgba(255,255,255,0.18)"
                strokeWidth={1}
              />
              <text
                x={xOf(t)}
                y={AXIS_Y + 13}
                fontSize="9"
                fill="#6b7280"
                textAnchor="middle"
              >
                {formatBp(t)}
              </text>
            </g>
          ))}
        </svg>

        {/* MINIMAP */}
        <svg
          width="100%"
          height={MINI_HEIGHT}
          className="block mt-1 select-none"
        >
          {/* All-gene heatmap */}
          {withCoords.map((g) => {
            const x1 = xMini(g.start as number);
            const x2 = xMini(g.end as number);
            const w = Math.max(x2 - x1, 0.6);
            const y = g.strand === -1 ? 18 : 6;
            return (
              <rect
                key={g.id}
                x={x1}
                y={y}
                width={w}
                height={10}
                fill={confidenceFill(g)}
                opacity={0.7}
              />
            );
          })}

          {/* Dimmed mask outside brush */}
          <rect
            x={PAD_L}
            y={0}
            width={Math.max(xMini(view.start) - PAD_L, 0)}
            height={MINI_HEIGHT}
            fill="rgba(10,10,20,0.65)"
          />
          <rect
            x={xMini(view.end)}
            y={0}
            width={Math.max(width - PAD_R - xMini(view.end), 0)}
            height={MINI_HEIGHT}
            fill="rgba(10,10,20,0.65)"
          />

          {/* Brush window */}
          <rect
            x={xMini(view.start)}
            y={0}
            width={Math.max(xMini(view.end) - xMini(view.start), 2)}
            height={MINI_HEIGHT}
            fill="rgba(99,102,241,0.08)"
            stroke="rgba(129,140,248,0.6)"
            strokeWidth={1}
            className="cursor-grab"
            onMouseDown={(e) => onBrushDown(e, "move")}
          />
          {/* Resize handles */}
          <rect
            x={xMini(view.start) - 3}
            y={0}
            width={6}
            height={MINI_HEIGHT}
            fill="rgba(129,140,248,0.4)"
            className="cursor-ew-resize"
            onMouseDown={(e) => onBrushDown(e, "resize-l")}
          />
          <rect
            x={xMini(view.end) - 3}
            y={0}
            width={6}
            height={MINI_HEIGHT}
            fill="rgba(129,140,248,0.4)"
            className="cursor-ew-resize"
            onMouseDown={(e) => onBrushDown(e, "resize-r")}
          />
        </svg>

        {/* Hover tooltip */}
        {hovered && hovered.start != null && hovered.end != null && (
          <div
            className="absolute pointer-events-none z-10 bg-[#0a0a14] border border-white/10 rounded-md px-2.5 py-1.5 text-[11px] shadow-xl"
            style={{ left: tooltipLeft, top: -8 }}
          >
            <div className="flex items-center gap-2 mb-0.5">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: confidenceFill(hovered) }}
              />
              <span className="text-white font-medium">{hovered.name}</span>
              {hovered.confidence && !hovered.is_dark && (
                <span className="text-gray-500">· {hovered.confidence}</span>
              )}
              {hovered.is_dark && (
                <span className="text-amber-400">· DARK</span>
              )}
            </div>
            <p className="text-gray-500 mono text-[10px]">
              {hovered.start.toLocaleString()}–{hovered.end.toLocaleString()} ·{" "}
              {hovered.strand === -1 ? "−" : "+"} ·{" "}
              {hovered.length != null ? `${hovered.length} bp` : ""}
            </p>
          </div>
        )}

        {/* Hint */}
        <p className="text-[10px] text-gray-700 mt-1 text-center">
          Scroll to zoom · drag to pan · drag the indigo box below to navigate
        </p>
      </div>
    </div>
  );
}
