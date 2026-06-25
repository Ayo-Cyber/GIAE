"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { CheckCircle2 } from "lucide-react";
import { HeroPreview } from "@/components/hero-preview";
import { ThemeToggle } from "@/components/theme";

// ── Scrolling sequence background rows ───────────────────────────────────────
const BASES = "ATCG";
const SEQ_ROWS = Array.from({ length: 13 }, (_, i) => {
  let s = "";
  for (let j = 0; j < 120; j++) s += BASES[(i * 7 + j * 3 + (j % 5)) % 4];
  return {
    text: s + s,
    top: i * 46 + 6,
    color: `rgba(129,140,248,${(0.025 + (i % 3) * 0.012).toFixed(3)})`,
    dur: 48 + i * 4,
    delay: -(i * 3),
  };
});

// ── Benchmark data (exact F1 scores from design file) ────────────────────────
type BenchRow = {
  genome: string; f1: string; delta: string; result: "W" | "T" | "L";
  verdict: string; accent: string; border: string; chipBg: string;
  deltaColor: string; backBg: string; f1pct: number; baktaPct: number; baktaText: string;
};
const BENCHMARK: BenchRow[] = (
  [
    ["λ phage", 79.2, 6.6], ["T7", 88.1, 2.9], ["T4", 71.4, 0.5], ["phiX174", 60.0, 0.0],
    ["T3", 84.7, 3.5], ["P1", 66.3, -1.8], ["P2", 73.9, 2.9], ["P22", 80.5, 0.7],
    ["Mu", 69.2, 0.0], ["SPP1", 77.6, 3.2], ["T5", 82.0, 1.9], ["N4", 64.8, -1.7],
    ["φKZ", 58.3, 3.3], ["HK97", 85.9, 2.2], ["SP6", 86.4, 2.4], ["PRD1", 75.1, 0.0],
    ["φ29", 90.2, 2.6], ["G4", 62.5, -2.4],
  ] as [string, number, number][]
).map(([genome, f1, d]) => {
  const bakta = f1 - d;
  const dd = Math.abs(d);
  const common = { genome, f1: f1.toFixed(1) + "%", f1pct: Math.round(f1), baktaPct: Math.round(bakta), baktaText: bakta.toFixed(1) + "%" };
  if (d > 0)   return { ...common, delta: "+" + dd.toFixed(1), result: "W" as const, verdict: "GIAE wins",  accent: "#34d399", border: "rgba(52,211,153,0.28)",   chipBg: "rgba(52,211,153,0.12)",   deltaColor: "#10b981", backBg: "rgba(52,211,153,0.06)" };
  if (d === 0) return { ...common, delta: "0.0",               result: "T" as const, verdict: "Tie",        accent: "#818cf8", border: "rgba(129,140,248,0.28)", chipBg: "rgba(129,140,248,0.12)", deltaColor: "#6366f1", backBg: "rgba(129,140,248,0.06)" };
  return              { ...common, delta: "−" + dd.toFixed(1), result: "L" as const, verdict: "Bakta wins", accent: "#fb7185", border: "rgba(251,113,133,0.28)", chipBg: "rgba(251,113,133,0.12)", deltaColor: "#fb7185", backBg: "rgba(251,113,133,0.06)" };
});

// ── Pipeline evidence sources ─────────────────────────────────────────────────
const PIPELINE_SOURCES = [
  { label: "PROSITE",    color: "#facc15", bg: "rgba(250,204,21,0.1)",   border: "rgba(250,204,21,0.25)"  },
  { label: "HMMER/Pfam", color: "#34d399", bg: "rgba(52,211,153,0.1)",   border: "rgba(52,211,153,0.25)"  },
  { label: "UniProt",    color: "#818cf8", bg: "rgba(129,140,248,0.1)",  border: "rgba(129,140,248,0.25)" },
  { label: "InterPro",   color: "#a78bfa", bg: "rgba(167,139,250,0.1)",  border: "rgba(167,139,250,0.25)" },
  { label: "ESM-2",      color: "#f472b6", bg: "rgba(244,114,182,0.1)",  border: "rgba(244,114,182,0.25)" },
];

// ── Feature cards ─────────────────────────────────────────────────────────────
const FEATURES = [
  { icon: "annot", title: "Explainable by default",  body: "Every gene gets a confidence score, a reasoning summary, and a full evidence chain. No annotation without justification.", iconColor: "#818cf8", iconBg: "rgba(99,102,241,0.12)",  iconBorder: "rgba(99,102,241,0.25)"  },
  { icon: "dark",  title: "Dark-matter discovery",   body: "GIAE tracks every gene it can't annotate and flags high-priority targets for experimental follow-up. Nothing gets silently dropped.", iconColor: "#fbbf24", iconBg: "rgba(245,158,11,0.1)",   iconBorder: "rgba(245,158,11,0.25)"  },
  { icon: "evid",  title: "Full evidence chain",     body: "PROSITE, HMMER/Pfam, UniProt, InterPro and ESM-2 each contribute a weighted, traceable signal — shown as a scientific figure.", iconColor: "#34d399", iconBg: "rgba(52,211,153,0.1)",   iconBorder: "rgba(52,211,153,0.25)"  },
  { icon: "disc",  title: "Interactive reports",     body: "Browse your genome in a searchable, filterable report. Click any gene for its interpretation, domain architecture and source citations.", iconColor: "#22d3ee", iconBg: "rgba(34,211,238,0.1)",   iconBorder: "rgba(34,211,238,0.25)"  },
  { icon: "offln", title: "Runs fully offline",      body: "Air-gap sensitive sequences. PROSITE motifs and HMMER profiles ship bundled — no internet, no data leaving your machine.", iconColor: "#a78bfa", iconBg: "rgba(167,139,250,0.1)",  iconBorder: "rgba(167,139,250,0.25)" },
  { icon: "api",   title: "API-first",               body: "Every feature is accessible via a clean REST API, CLI and Python library. Drop GIAE straight into your pipeline with one key.", iconColor: "#818cf8", iconBg: "rgba(99,102,241,0.12)",  iconBorder: "rgba(99,102,241,0.25)"  },
];

// ── Steps ─────────────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", title: "Upload your genome",    body: "Drop a GenBank (.gb) or FASTA (.fa) file into the dashboard. GIAE auto-detects the format and queues interpretation." },
  { n: "02", title: "The engine runs",       body: "Each gene is processed in parallel. PROSITE motifs, HMMER domains, UniProt matches and genomic context are scored and aggregated." },
  { n: "03", title: "Get your report",       body: "A fully interactive report lands in your dashboard. Browse genes, filter by confidence, drill into evidence chains and sequences." },
  { n: "04", title: "Dark matter gets flagged", body: "Every gene with zero evidence joins the Dark-Matter index with a priority score — so nothing is silently ignored." },
];

// ── SVG feature icons ─────────────────────────────────────────────────────────
function FIcon({ id, color }: { id: string; color: string }) {
  const p = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: color, strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (id === "annot") return <svg {...p}><line x1={4} y1={7}  x2={20} y2={7}  /><line x1={4} y1={12} x2={14} y2={12} /><line x1={4} y1={17} x2={17} y2={17} /></svg>;
  if (id === "dark")  return <svg {...p}><circle cx={12} cy={12} r={8} strokeDasharray="3 2.5" /><circle cx={12} cy={12} r={2.5} fill={color} stroke="none" /></svg>;
  if (id === "evid")  return <svg {...p}><circle cx={6} cy={6} r={2} /><circle cx={6} cy={12} r={2} /><circle cx={6} cy={18} r={2} /><line x1={10} y1={6} x2={20} y2={6} /><line x1={10} y1={12} x2={17} y2={12} /><line x1={10} y1={18} x2={14} y2={18} /></svg>;
  if (id === "disc")  return <svg {...p}><circle cx={10} cy={10} r={6} /><line x1={14.5} y1={14.5} x2={20} y2={20} /></svg>;
  if (id === "offln") return <svg {...p}><polygon points="12,3 21,12 12,21 3,12" /><polyline points="8.5,12 11,14.5 15.5,9.5" /></svg>;
  return                     <svg {...p}><polyline points="9,8 5,12 9,16" /><polyline points="15,8 19,12 15,16" /></svg>;
}

// ── Genome browser preview (Lambda phage ~48.5 kb) ───────────────────────────
function GenomePreview() {
  type Gene = { s: number; e: number; st: 1 | -1; c: string; n?: string; dark?: true; trna?: true };
  const G: Gene[] = [
    { s: 206,   e: 787,   st: 1,  c: "#f59e0b" },
    { s: 790,   e: 2917,  st: 1,  c: "#34d399", n: "A"    },
    { s: 3100,  e: 4400,  st: 1,  c: "#34d399", n: "B"    },
    { s: 4500,  e: 5200,  st: 1,  c: "#818cf8"             },
    { s: 5400,  e: 6900,  st: 1,  c: "#34d399", n: "C"    },
    { s: 7100,  e: 8600,  st: 1,  c: "#f59e0b"             },
    { s: 8780,  e: 9199,  st: 1,  c: "#818cf8"             },
    { s: 9400,  e: 11200, st: 1,  c: "#34d399", n: "E"    },
    { s: 11800, e: 11876, st: 1,  c: "#2dd4bf", trna: true },
    { s: 15240, e: 15731, st: -1, c: "#4b5563", dark: true },
    { s: 18900, e: 19700, st: -1, c: "#ef4444", n: "aadA1" },
    { s: 22910, e: 23412, st: -1, c: "#4b5563", dark: true },
    { s: 24100, e: 26800, st: 1,  c: "#34d399", n: "D"    },
    { s: 27840, e: 28937, st: -1, c: "#34d399", n: "int"  },
    { s: 30100, e: 31600, st: 1,  c: "#f59e0b"             },
    { s: 32600, e: 32890, st: 1,  c: "#f97316", n: "bor"  },
    { s: 34980, e: 35141, st: -1, c: "#f59e0b"             },
    { s: 36100, e: 39492, st: 1,  c: "#34d399", n: "J"    },
    { s: 40200, e: 40900, st: -1, c: "#818cf8"             },
    { s: 41140, e: 41569, st: 1,  c: "#4b5563", dark: true },
    { s: 42100, e: 44600, st: 1,  c: "#34d399", n: "H"    },
    { s: 44972, e: 45331, st: 1,  c: "#34d399", n: "S"    },
    { s: 45333, e: 45887, st: 1,  c: "#34d399", n: "R"    },
    { s: 46200, e: 48100, st: 1,  c: "#f59e0b"             },
  ];

  const GS = 0, GE = 48502, SPAN = GE - GS;
  const VW = 1600, H = 132, PAD = 20, IW = VW - 2 * PAD;
  const xOf = (bp: number) => PAD + ((bp - GS) / SPAN) * IW;
  const FWD_Y = 24, REV_Y = 70, TH = 22, CEN = 58, AX_Y = H - 18;

  // CSS vars don't apply to SVG presentation attributes — use inline style.
  const trackStroke = { stroke: "var(--lp-track)" };
  const faintFill = { fill: "var(--lp-faint)" };

  function arrow(x: number, w: number, y: number, st: 1 | -1) {
    const hd = Math.min(11, Math.max(w * 0.35, 2));
    if (st === -1) return `M${x+w},${y} L${x+hd},${y} L${x},${y+TH/2} L${x+hd},${y+TH} L${x+w},${y+TH} Z`;
    return `M${x},${y} L${x+w-hd},${y} L${x+w},${y+TH/2} L${x+w-hd},${y+TH} L${x},${y+TH} Z`;
  }

  return (
    <svg viewBox={`0 0 ${VW} ${H}`} width="100%" preserveAspectRatio="xMidYMid meet" style={{ display: "block", height: "auto" }}>
      <line x1={PAD} x2={VW-PAD} y1={CEN} y2={CEN} strokeWidth={1} style={trackStroke} />
      <text x={4} y={FWD_Y+TH/2+4} fontSize={12} fontWeight={700} fontFamily="'JetBrains Mono',monospace" style={faintFill}>+</text>
      <text x={4} y={REV_Y+TH/2+4} fontSize={12} fontWeight={700} fontFamily="'JetBrains Mono',monospace" style={faintFill}>−</text>
      {G.map((g, i) => {
        const x1 = xOf(g.s), x2 = xOf(g.e), w = Math.max(x2 - x1, 2.5);
        const y = g.st === -1 ? REV_Y : FWD_Y;
        if (g.trna) {
          const cx = (x1+x2)/2, ty = y+TH/2;
          return <polygon key={i} points={`${cx-6},${ty+6} ${cx+6},${ty+6} ${cx},${ty-6}`} fill={g.c}><title>tRNA-Arg</title></polygon>;
        }
        return (
          <g key={i}>
            <path d={arrow(x1, w, y, g.st)} fill={g.c} stroke={g.dark?"#6b7280":"none"} strokeWidth={g.dark?1:0} strokeDasharray={g.dark?"3 2":undefined}>
              <title>{g.n||"hypothetical"}</title>
            </path>
            {w >= 30 && g.n && (
              <text x={x1+w/2} y={y+TH/2+4} fontSize={10} fill="#0a0a14" textAnchor="middle" fontWeight={700} fontFamily="'JetBrains Mono',monospace">{g.n}</text>
            )}
          </g>
        );
      })}
      <line x1={PAD} x2={VW-PAD} y1={AX_Y} y2={AX_Y} strokeWidth={1} style={trackStroke} />
      {Array.from({ length: 10 }, (_, i) => i * 5000).map((t) => {
        const x = xOf(t);
        return (
          <g key={t}>
            <line x1={x} x2={x} y1={AX_Y} y2={AX_Y+4} strokeWidth={1} style={trackStroke} />
            <text x={x} y={AX_Y+15} fontSize={10} textAnchor="middle" fontFamily="'JetBrains Mono',monospace" style={faintFill}>{t/1000} kb</text>
          </g>
        );
      })}
    </svg>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function LandingPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleWaitlist = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await api.joinWaitlist(email); } catch { /* treat as success */ }
    setSubmitted(true);
  };

  // Scroll-reveal: fade .giae-rv blocks up as they enter the viewport.
  // Anything already on/near screen is revealed immediately so it never
  // gets stuck hidden, and a no-IntersectionObserver fallback reveals all.
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>(".giae-rv"));
    if (els.length === 0) return;
    const reveal = (el: HTMLElement) => el.classList.add("giae-in");
    const reduce = window.matchMedia?.("(prefers-reduced-motion:reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) {
      els.forEach(reveal);
      return;
    }
    const vh = window.innerHeight || 800;
    els.forEach((el) => { if (el.getBoundingClientRect().top < vh * 0.92) reveal(el); });
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) { reveal(e.target as HTMLElement); io.unobserve(e.target); }
      }),
      { threshold: 0.1, rootMargin: "0px 0px -6% 0px" }
    );
    els.forEach((el) => { if (!el.classList.contains("giae-in")) io.observe(el); });
    return () => io.disconnect();
  }, []);

  return (
    <div style={{ background: "var(--lp-bg)", color: "var(--lp-text2)", fontFamily: "'Inter',system-ui,sans-serif", minHeight: "100vh", overflowX: "hidden", transition: "background .35s ease, color .35s ease" }}>

      {/* ── NAV ──────────────────────────────────────────────────────────── */}
      <header style={{ position: "sticky", top: 0, zIndex: 50, borderBottom: "1px solid var(--lp-border)", background: "var(--lp-nav)", backdropFilter: "blur(16px)" }}>
        <div style={{ maxWidth: 1152, margin: "0 auto", padding: "0 24px", height: 56, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 28, height: 28, borderRadius: 8, background: "linear-gradient(135deg,#6366f1,#818cf8)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 13, color: "#fff" }}>G</div>
            <span style={{ fontWeight: 700, color: "var(--lp-text)", letterSpacing: "-.01em" }}>GIAE</span>
            <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, color: "#818cf8", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", padding: "1px 6px", borderRadius: 5 }}>beta</span>
          </div>
          <nav style={{ display: "flex", alignItems: "center", gap: 28, fontSize: 13, color: "var(--lp-muted)" }}>
            <a href="#features"  style={{ color: "var(--lp-muted)", textDecoration: "none" }}>Features</a>
            <a href="#pipeline"  style={{ color: "var(--lp-muted)", textDecoration: "none" }}>Pipeline</a>
            <a href="#benchmark" style={{ color: "var(--lp-muted)", textDecoration: "none" }}>Benchmark</a>
            <a href="#pricing"   style={{ color: "var(--lp-muted)", textDecoration: "none" }}>Pricing</a>
          </nav>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <ThemeToggle />
            <Link href="/login"  style={{ fontSize: 13, color: "var(--lp-muted)", textDecoration: "none" }}>Sign in</Link>
            <Link href="/signup" style={{ fontSize: 13, background: "#6366f1", color: "#fff", padding: "7px 15px", borderRadius: 9, fontWeight: 500, whiteSpace: "nowrap", textDecoration: "none" }}>Get started</Link>
          </div>
        </div>
      </header>

      {/* ── HERO ─────────────────────────────────────────────────────────── */}
      <section style={{ position: "relative", padding: "72px 24px 80px", overflow: "hidden" }}>
        {/* scrolling DNA sequence background */}
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden", maskImage: "linear-gradient(to bottom,transparent,#000 18%,#000 82%,transparent)" }}>
          {SEQ_ROWS.map((r, i) => (
            <div key={i} style={{ position: "absolute", left: 0, top: r.top, whiteSpace: "nowrap", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, letterSpacing: 4, color: r.color, animation: `giaeSeq ${r.dur}s linear infinite`, animationDelay: `${r.delay}s` }}>
              {r.text}
            </div>
          ))}
        </div>
        {/* ambient glow */}
        <div style={{ position: "absolute", top: -180, left: "8%", width: 560, height: 460, background: "rgba(99,102,241,0.12)", filter: "blur(140px)", borderRadius: "50%", pointerEvents: "none", animation: "giaeGlow 8s ease-in-out infinite" }} />
        <div style={{ position: "absolute", top: 120, right: -100, width: 480, height: 480, background: "rgba(139,92,246,0.09)", filter: "blur(140px)", borderRadius: "50%", pointerEvents: "none", animation: "giaeGlow 10s ease-in-out infinite 1s" }} />

        <div style={{ maxWidth: 1152, margin: "0 auto", position: "relative" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1.05fr 1fr", gap: 60, alignItems: "center" }}>

            {/* copy */}
            <div style={{ maxWidth: 560 }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12, fontWeight: 500, color: "#818cf8", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", padding: "5px 12px", borderRadius: 999 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#34d399", animation: "giaePulse 2s infinite", display: "inline-block" }} />
                v0.2.3 · Open Beta — free to start
              </div>
              <h1 style={{ fontSize: 58, fontWeight: 800, lineHeight: 1.04, letterSpacing: "-.025em", margin: "24px 0 20px" }}>
                <span style={{ background: "var(--lp-head-grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>The genome annotator </span>
                <span style={{ background: "var(--lp-accent-grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>that shows its work.</span>
              </h1>
              <p style={{ fontSize: 18, color: "var(--lp-muted)", lineHeight: 1.6, margin: "0 0 32px" }}>
                Every gene gets a confidence score, an evidence chain, and a reasoning trace. No black-box predictions — and no gene gets silently dropped.
              </p>
              <div style={{ display: "flex", gap: 12, marginBottom: 32, flexWrap: "wrap" }}>
                <Link href="/signup" style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "#6366f1", color: "#fff", padding: "13px 20px", borderRadius: 12, fontWeight: 500, fontSize: 14, textDecoration: "none", boxShadow: "0 10px 30px -8px rgba(99,102,241,0.5)" }}>
                  Start interpreting free →
                </Link>
                <Link href="/dashboard" style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "var(--lp-bg3)", border: "1px solid var(--lp-border2)", color: "var(--lp-text2)", padding: "13px 20px", borderRadius: 12, fontWeight: 500, fontSize: 14, textDecoration: "none" }}>
                  ▸ See a live demo
                </Link>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "10px 24px", fontSize: 12, color: "var(--lp-muted2)" }}>
                {["Open source · MIT", "Runs offline · data never leaves your laptop", "REST API + CLI + Python"].map((t) => (
                  <span key={t} style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ color: "#34d399" }}>✓</span> {t}</span>
                ))}
              </div>
            </div>

            {/* hero preview card — self-contained: animated count-up donut,
                pulsing glow, and floating chips all live inside HeroPreview */}
            <HeroPreview />
          </div>
        </div>
      </section>

      {/* ── GENOME BROWSER PREVIEW ───────────────────────────────────────── */}
      <section style={{ padding: "8px 24px 72px" }}>
        <div style={{ maxWidth: 1152, margin: "0 auto" }}>
          <div className="giae-rv" style={{ background: "var(--lp-bg2)", border: "1px solid var(--lp-border)", borderRadius: 18, padding: "22px 24px 18px", boxShadow: "var(--lp-card-shadow)" }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20, flexWrap: "wrap", marginBottom: 6 }}>
              <div>
                <div style={{ fontSize: 13, color: "var(--lp-text)", fontWeight: 600 }}>Browse your genome like a real genome browser</div>
                <div style={{ fontSize: 12, color: "var(--lp-muted2)", marginTop: 3 }}>Genes drawn as strand-aware arrows, colored by interpretation confidence — IGV / JBrowse-style, right in your report.</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                {[["#34d399","HIGH"],["#f59e0b","MOD"],["#818cf8","LOW"]].map(([c,l]) => (
                  <span key={l} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--lp-muted2)" }}>
                    <span style={{ width: 9, height: 9, borderRadius: 2, background: c, display: "inline-block" }} />{l}
                  </span>
                ))}
                <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--lp-muted2)" }}>
                  <span style={{ width: 9, height: 9, borderRadius: 2, background: "#4b5563", border: "1px dashed #6b7280", display: "inline-block" }} />DARK
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--lp-muted2)" }}>
                  <span style={{ width: 9, height: 9, borderRadius: 2, background: "#ef4444", display: "inline-block" }} />AMR
                </span>
              </div>
            </div>
            <GenomePreview />
          </div>
        </div>
      </section>

      {/* ── BENCHMARK ────────────────────────────────────────────────────── */}
      <section id="benchmark" style={{ padding: "0 24px 80px" }}>
        <div style={{ maxWidth: 1152, margin: "0 auto" }}>
          <div className="giae-rv" style={{ textAlign: "center", marginBottom: 14 }}>
            <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".2em", color: "var(--lp-muted2)" }}>Full reference benchmark · F1 score vs Bakta</span>
            <h2 style={{ fontSize: 30, fontWeight: 700, color: "var(--lp-text)", margin: "12px 0 0", letterSpacing: "-.02em" }}>
              GIAE wins or ties on <span style={{ color: "#34d399" }}>15 of 18</span> phage genomes
            </h2>
            <div style={{ display: "flex", justifyContent: "center", gap: 18, marginTop: 14, flexWrap: "wrap" }}>
              {[["#34d399","12 wins"],["#818cf8","3 ties"],["#fb7185","3 losses"]].map(([c,l]) => (
                <span key={l} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--lp-muted)" }}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: c, display: "inline-block" }} />{l}
                </span>
              ))}
              <span style={{ fontSize: 12, color: "var(--lp-faint)" }}>·</span>
              <span style={{ fontSize: 12, color: "var(--lp-muted2)" }}>hover a tile to compare ⇄</span>
            </div>
          </div>

          <div className="giae-rv" style={{ display: "grid", gridTemplateColumns: "repeat(6,1fr)", gap: 10 }}>
            {BENCHMARK.map((b) => (
              <div key={b.genome} style={{ perspective: 900, height: 96 }}>
                <div className="giae-flip">
                  {/* FRONT */}
                  <div className="giae-face" style={{ background: "var(--lp-bg2)", border: `1px solid ${b.border}`, borderRadius: 11, padding: "11px 12px 11px 14px", overflow: "hidden", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: b.accent }} />
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
                      <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "var(--lp-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{b.genome}</span>
                      <span style={{ flexShrink: 0, fontSize: 8, fontWeight: 700, letterSpacing: ".04em", padding: "1px 5px", borderRadius: 4, background: b.chipBg, color: b.accent, border: `1px solid ${b.border}` }}>{b.result}</span>
                    </div>
                    <div>
                      <div style={{ fontSize: 8, color: "var(--lp-faint)", textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 1 }}>GIAE F1</div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                        <span style={{ fontSize: 19, fontWeight: 700, fontFamily: "'JetBrains Mono',monospace", color: "var(--lp-text)" }}>{b.f1}</span>
                        <span style={{ fontSize: 10, fontFamily: "'JetBrains Mono',monospace", color: b.deltaColor }}>{b.delta}</span>
                      </div>
                    </div>
                  </div>
                  {/* BACK */}
                  <div className="giae-face" style={{ transform: "rotateY(180deg)", background: b.backBg, border: `1px solid ${b.border}`, borderRadius: 11, padding: "10px 12px", overflow: "hidden", display: "flex", flexDirection: "column", justifyContent: "center", gap: 7 }}>
                    <div style={{ fontSize: 9, fontFamily: "'JetBrains Mono',monospace", color: "var(--lp-muted)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span>{b.genome}</span><span style={{ color: b.accent, fontWeight: 700 }}>{b.verdict}</span>
                    </div>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 2 }}>
                        <span style={{ fontSize: 9, color: b.accent, fontWeight: 600 }}>GIAE</span>
                        <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono',monospace", color: "var(--lp-text2)" }}>{b.f1}</span>
                      </div>
                      <div style={{ height: 5, background: "var(--lp-track)", borderRadius: 999, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${b.f1pct}%`, background: b.accent, borderRadius: 999 }} />
                      </div>
                    </div>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 2 }}>
                        <span style={{ fontSize: 9, color: "var(--lp-muted2)", fontWeight: 600 }}>Bakta</span>
                        <span style={{ fontSize: 9, fontFamily: "'JetBrains Mono',monospace", color: "var(--lp-muted)" }}>{b.baktaText}</span>
                      </div>
                      <div style={{ height: 5, background: "var(--lp-track)", borderRadius: 999, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${b.baktaPct}%`, background: "var(--lp-faint)", borderRadius: 999 }} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="giae-rv" style={{ textAlign: "center", marginTop: 20 }}>
            <span style={{ fontSize: 11, color: "var(--lp-muted2)" }}>
              Reference set: 18 curated phage genomes · F1 against RefSeq annotation ·{" "}
              <a href="https://github.com/Ayo-Cyber/GIAE" style={{ color: "#818cf8", textDecoration: "none" }}>reproduce in repo →</a>
            </span>
          </div>
        </div>
      </section>

      {/* ── PIPELINE ─────────────────────────────────────────────────────── */}
      <section id="pipeline" style={{ padding: "0 24px 88px" }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          <div className="giae-rv" style={{ textAlign: "center", marginBottom: 40 }}>
            <span style={{ display: "inline-flex", fontSize: 12, fontWeight: 500, color: "#818cf8", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", padding: "5px 12px", borderRadius: 999 }}>The engine</span>
            <h2 style={{ fontSize: 30, fontWeight: 700, color: "var(--lp-text)", margin: "16px 0 8px", letterSpacing: "-.02em" }}>A multi-source evidence pipeline</h2>
            <p style={{ fontSize: 14, color: "var(--lp-muted)", maxWidth: 520, margin: "0 auto", lineHeight: 1.6 }}>Every gene flows through four stages. Each evidence source is weighted independently, then aggregated into a single explainable score.</p>
          </div>
          <div className="giae-rv" style={{ display: "flex", alignItems: "stretch", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
            <div style={{ flex: 1, minWidth: 180, background: "var(--lp-bg2)", border: "1px solid var(--lp-border)", borderRadius: 14, padding: 18, boxShadow: "var(--lp-card-shadow)" }}>
              <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#818cf8", marginBottom: 8 }}>01</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--lp-text)", marginBottom: 6 }}>ORF prediction</div>
              <p style={{ fontSize: 12, color: "var(--lp-muted2)", lineHeight: 1.5, margin: 0 }}>Open reading frames called; start/stop coordinates and strand assigned per gene.</p>
            </div>
            <div style={{ display: "flex", alignItems: "center", color: "var(--lp-faint)", fontSize: 18 }}>→</div>
            <div style={{ flex: 1.3, minWidth: 220, background: "var(--lp-bg2)", border: "1px solid rgba(99,102,241,0.25)", borderRadius: 14, padding: 18, boxShadow: "var(--lp-card-shadow)" }}>
              <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#818cf8", marginBottom: 8 }}>02</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--lp-text)", marginBottom: 10 }}>Evidence extraction</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {PIPELINE_SOURCES.map((s) => (
                  <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 5, fontFamily: "'JetBrains Mono',monospace", fontSize: 10, padding: "3px 8px", borderRadius: 6, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, display: "inline-block" }} />{s.label}
                  </span>
                ))}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", color: "var(--lp-faint)", fontSize: 18 }}>→</div>
            <div style={{ flex: 1, minWidth: 180, background: "var(--lp-bg2)", border: "1px solid var(--lp-border)", borderRadius: 14, padding: 18, boxShadow: "var(--lp-card-shadow)" }}>
              <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#818cf8", marginBottom: 8 }}>03</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--lp-text)", marginBottom: 6 }}>Aggregation</div>
              <p style={{ fontSize: 12, color: "var(--lp-muted2)", lineHeight: 1.5, margin: 0 }}>Weighted evidence merge; competing hypotheses ranked, best assignment selected.</p>
            </div>
            <div style={{ display: "flex", alignItems: "center", color: "var(--lp-faint)", fontSize: 18 }}>→</div>
            <div style={{ flex: 1, minWidth: 180, background: "var(--lp-bg2)", border: "1px solid rgba(52,211,153,0.25)", borderRadius: 14, padding: 18, boxShadow: "var(--lp-card-shadow)" }}>
              <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, color: "#10b981", marginBottom: 8 }}>04</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--lp-text)", marginBottom: 8 }}>Confidence score</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                {[["HIGH","#34d399","rgba(52,211,153,0.12)"],["MOD","#f59e0b","rgba(245,158,11,0.12)"],["LOW","#818cf8","rgba(129,140,248,0.12)"],["DARK","#9ca3af","rgba(75,85,99,0.25)"]].map(([l,c,bg]) => (
                  <span key={l} style={{ fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 5, background: bg, color: c }}>{l}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FEATURES ─────────────────────────────────────────────────────── */}
      <section id="features" style={{ padding: "0 24px 88px" }}>
        <div style={{ maxWidth: 1152, margin: "0 auto" }}>
          <div className="giae-rv" style={{ textAlign: "center", marginBottom: 48 }}>
            <span style={{ display: "inline-flex", fontSize: 12, fontWeight: 500, color: "#818cf8", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", padding: "5px 12px", borderRadius: 999 }}>Features</span>
            <h2 style={{ fontSize: 30, fontWeight: 700, color: "var(--lp-text)", margin: "16px 0 8px", letterSpacing: "-.02em" }}>Not a black box. Never.</h2>
            <p style={{ fontSize: 14, color: "var(--lp-muted)", maxWidth: 540, margin: "0 auto", lineHeight: 1.6 }}>Every annotation GIAE produces is backed by an explicit evidence chain. You see exactly why a gene was assigned a function — or why it wasn't.</p>
          </div>
          <div className="giae-rv" style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }}>
            {FEATURES.map((f) => (
              <div key={f.title} style={{ background: "var(--lp-bg2)", border: "1px solid var(--lp-border)", borderRadius: 16, padding: 24, boxShadow: "var(--lp-card-shadow)" }}>
                <div style={{ width: 42, height: 42, borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, background: f.iconBg, border: `1px solid ${f.iconBorder}` }}>
                  <FIcon id={f.icon} color={f.iconColor} />
                </div>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--lp-text)", margin: "0 0 7px" }}>{f.title}</h3>
                <p style={{ fontSize: 13, color: "var(--lp-muted)", lineHeight: 1.6, margin: 0 }}>{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ─────────────────────────────────────────────────── */}
      <section style={{ padding: "0 24px 88px" }}>
        <div className="giae-rv" style={{ maxWidth: 600, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 44 }}>
            <span style={{ display: "inline-flex", fontSize: 12, fontWeight: 500, color: "#818cf8", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", padding: "5px 12px", borderRadius: 999 }}>How it works</span>
            <h2 style={{ fontSize: 30, fontWeight: 700, color: "var(--lp-text)", margin: "16px 0 0", letterSpacing: "-.02em" }}>Upload. Interpret. Discover.</h2>
          </div>
          {STEPS.map((s, i) => (
            <div key={s.n} style={{ display: "flex", gap: 18 }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div style={{ width: 36, height: 36, borderRadius: "50%", background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, fontWeight: 600, color: "#818cf8" }}>{s.n}</div>
                {i < STEPS.length - 1 && <div style={{ flex: 1, width: 1, background: "linear-gradient(to bottom,rgba(99,102,241,0.25),transparent)", marginTop: 8 }} />}
              </div>
              <div style={{ paddingBottom: 36 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--lp-text)", margin: "0 0 5px" }}>{s.title}</h3>
                <p style={{ fontSize: 13, color: "var(--lp-muted)", lineHeight: 1.6, margin: 0 }}>{s.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── PRICING ──────────────────────────────────────────────────────── */}
      <section id="pricing" style={{ padding: "0 24px 88px" }}>
        <div className="giae-rv" style={{ maxWidth: 820, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginBottom: 44 }}>
            <span style={{ display: "inline-flex", fontSize: 12, fontWeight: 500, color: "#818cf8", background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)", padding: "5px 12px", borderRadius: 999 }}>Pricing</span>
            <h2 style={{ fontSize: 30, fontWeight: 700, color: "var(--lp-text)", margin: "16px 0 8px", letterSpacing: "-.02em" }}>Free to start. Scales with you.</h2>
            <p style={{ fontSize: 14, color: "var(--lp-muted)", margin: 0 }}>No credit card required to get started.</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
            <div style={{ background: "var(--lp-bg2)", border: "1px solid var(--lp-border)", borderRadius: 16, padding: 24, display: "flex", flexDirection: "column", boxShadow: "var(--lp-card-shadow)" }}>
              <p style={{ fontSize: 11, color: "var(--lp-muted2)", textTransform: "uppercase", letterSpacing: ".1em", margin: "0 0 6px" }}>Community</p>
              <p style={{ fontSize: 30, fontWeight: 700, color: "var(--lp-text)", margin: "0 0 4px" }}>Free</p>
              <p style={{ fontSize: 13, color: "var(--lp-muted2)", margin: "0 0 22px" }}>For students and independent researchers</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 11, flex: 1, marginBottom: 24 }}>
                {["5 genome interpretations / month","Full interactive reports","PROSITE + motif offline analysis","Dark-matter gene flagging","Community dark-matter DB access"].map((f) => (
                  <span key={f} style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: 13, color: "var(--lp-text2)" }}><span style={{ color: "#34d399", marginTop: 1 }}>✓</span>{f}</span>
                ))}
              </div>
              <Link href="/signup" style={{ textAlign: "center", fontSize: 13, fontWeight: 500, padding: 11, borderRadius: 11, background: "var(--lp-bg3)", border: "1px solid var(--lp-border2)", color: "var(--lp-text2)", textDecoration: "none", display: "block" }}>Get started free</Link>
            </div>
            <div style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.4)", borderRadius: 16, padding: 24, display: "flex", flexDirection: "column", boxShadow: "0 0 40px -12px rgba(99,102,241,0.4)" }}>
              <span style={{ alignSelf: "flex-start", fontSize: 11, fontWeight: 600, color: "#818cf8", background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)", padding: "3px 9px", borderRadius: 999, marginBottom: 14 }}>Most popular</span>
              <p style={{ fontSize: 11, color: "var(--lp-muted2)", textTransform: "uppercase", letterSpacing: ".1em", margin: "0 0 6px" }}>Enterprise</p>
              <p style={{ fontSize: 30, fontWeight: 700, color: "var(--lp-text)", margin: "0 0 4px" }}>Custom</p>
              <p style={{ fontSize: 13, color: "var(--lp-muted2)", margin: "0 0 22px" }}>For biopharma, ag-tech, and large labs</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 11, flex: 1, marginBottom: 24 }}>
                {["Unlimited genome interpretations","Unlimited API keys & programmatic access","UniProt + InterPro online evidence layers","Private data enclave — never shared","Priority ESM-2 structural prediction queue","SLA + dedicated support"].map((f) => (
                  <span key={f} style={{ display: "flex", alignItems: "flex-start", gap: 9, fontSize: 13, color: "var(--lp-text2)" }}><span style={{ color: "#34d399", marginTop: 1 }}>✓</span>{f}</span>
                ))}
              </div>
              <Link href="/signup" style={{ textAlign: "center", fontSize: 13, fontWeight: 500, padding: 11, borderRadius: 11, background: "#6366f1", color: "#fff", textDecoration: "none", display: "block" }}>Contact us</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── WAITLIST ─────────────────────────────────────────────────────── */}
      <section style={{ padding: "0 24px 88px" }}>
        <div className="giae-rv" style={{ maxWidth: 540, margin: "0 auto", background: "var(--lp-bg2)", border: "1px solid var(--lp-border)", borderRadius: 18, padding: 40, textAlign: "center", boxShadow: "0 0 50px -16px rgba(99,102,241,0.35)" }}>
          <h2 style={{ fontSize: 24, fontWeight: 700, color: "var(--lp-text)", margin: "0 0 12px" }}>Join the beta waitlist</h2>
          <p style={{ fontSize: 14, color: "var(--lp-muted)", lineHeight: 1.6, margin: "0 0 24px" }}>Enterprise access, API keys, and the dark-matter database are rolling out to waitlist members first.</p>
          {submitted ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, color: "#34d399", fontSize: 14, fontWeight: 500 }}>
              <CheckCircle2 size={16} /> You&apos;re on the list. We&apos;ll be in touch.
            </div>
          ) : (
            <form onSubmit={handleWaitlist} style={{ display: "flex", gap: 10 }}>
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                style={{ flex: 1, background: "var(--lp-bg3)", border: "1px solid var(--lp-border2)", borderRadius: 10, padding: "11px 15px", fontSize: 14, color: "var(--lp-text)", outline: "none", fontFamily: "'Inter',sans-serif" }} />
              <button type="submit" style={{ background: "#6366f1", color: "#fff", padding: "11px 20px", borderRadius: 10, fontSize: 14, fontWeight: 500, cursor: "pointer", border: "none", whiteSpace: "nowrap" }}>Join</button>
            </form>
          )}
        </div>
      </section>

      {/* ── FOOTER ───────────────────────────────────────────────────────── */}
      <footer style={{ borderTop: "1px solid var(--lp-border)", padding: "28px 24px" }}>
        <div style={{ maxWidth: 1152, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <div style={{ width: 24, height: 24, borderRadius: 7, background: "linear-gradient(135deg,#6366f1,#818cf8)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 11, color: "#fff" }}>G</div>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--lp-text)" }}>GIAE</span>
          </div>
          <div style={{ display: "flex", gap: 24, fontSize: 12, color: "var(--lp-muted2)" }}>
            <a href="#features"  style={{ color: "var(--lp-muted2)", textDecoration: "none" }}>Features</a>
            <a href="#pipeline"  style={{ color: "var(--lp-muted2)", textDecoration: "none" }}>Pipeline</a>
            <a href="#pricing"   style={{ color: "var(--lp-muted2)", textDecoration: "none" }}>Pricing</a>
            <a href="https://github.com/Ayo-Cyber/GIAE" style={{ color: "var(--lp-muted2)", textDecoration: "none" }}>GitHub</a>
          </div>
          <p style={{ fontSize: 12, color: "var(--lp-faint)", margin: 0 }}>© 2026 GIAE. Built for science.</p>
        </div>
      </footer>
    </div>
  );
}
