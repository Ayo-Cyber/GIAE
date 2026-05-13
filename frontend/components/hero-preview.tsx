"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  Sparkles,
  GitBranch,
  Database,
  ArrowUpRight,
} from "lucide-react";

/**
 * Hero product-preview card. A stylised mock of the gene-detail view —
 * confidence donut + evidence chain + reasoning. Designed to read as
 * "this is what you get" in two seconds.
 */
export function HeroPreview() {
  // Animated score counter
  const [score, setScore] = useState(0);
  useEffect(() => {
    let raf = 0;
    const target = 0.87;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, Math.max(0, (t - start - 600) / 1100));
      const eased = 1 - Math.pow(1 - p, 3);
      setScore(eased * target);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const dash = 2 * Math.PI * 38;
  const offset = dash - (score / 1) * dash;

  const sources = [
    { label: "UniProt", pct: 41, colour: "#818cf8" },
    { label: "Pfam HMMER", pct: 32, colour: "#34d399" },
    { label: "PROSITE motif", pct: 18, colour: "#fbbf24" },
    { label: "Codon usage", pct: 9, colour: "#f472b6" },
  ];

  const reasoning = [
    "UniProt P03034 matched at 96% sequence identity",
    "Helix-Turn-Helix DNA-binding motif (HTH_3) detected",
    "Pfam domain cl21500 — lambda repressor N-terminal",
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 30, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
      className="relative"
    >
      {/* Floating ambient glow */}
      <motion.div
        className="absolute -inset-4 bg-gradient-to-tr from-indigo-600/15 via-transparent to-violet-500/15 blur-2xl rounded-3xl pointer-events-none"
        animate={{ opacity: [0.6, 1, 0.6] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="relative surface rounded-2xl overflow-hidden shadow-2xl shadow-indigo-950/40">
        {/* Window chrome */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 bg-white/[0.02]">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/60" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/60" />
          </div>
          <p className="mono text-[10px] text-gray-600">
            lambda_phage.gb · gene cI
          </p>
          <span className="text-[10px] text-gray-700">●●●</span>
        </div>

        {/* Gene header */}
        <motion.div
          className="px-5 pt-5 pb-3"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <div className="flex items-start justify-between gap-4 mb-2">
            <div>
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-white font-semibold text-sm">cI</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                  HIGH
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded-full border bg-indigo-500/10 text-indigo-400 border-indigo-500/20">
                  COG K
                </span>
                <span className="text-[10px] mono px-1.5 py-0.5 rounded-full border bg-purple-500/10 text-purple-400 border-purple-500/20">
                  PF01381
                </span>
              </div>
              <p className="text-[11px] text-gray-500 mono">
                lambdap88 · 1.07 kb · + strand
              </p>
            </div>
          </div>
          <p className="text-xs text-gray-300 leading-relaxed">
            Lambda repressor protein CI — lysogeny maintenance transcription
            factor
          </p>
        </motion.div>

        {/* Confidence composition */}
        <div className="px-5 pb-4">
          <div className="flex items-center gap-2 mb-3">
            <Database size={11} className="text-gray-500" />
            <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
              Confidence composition
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* Donut */}
            <div className="relative w-[92px] h-[92px] shrink-0">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle
                  cx="50"
                  cy="50"
                  r="38"
                  fill="none"
                  stroke="rgba(255,255,255,0.05)"
                  strokeWidth="10"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="38"
                  fill="none"
                  stroke="url(#heroGrad)"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={dash}
                  strokeDashoffset={offset}
                />
                <defs>
                  <linearGradient id="heroGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#34d399" />
                    <stop offset="100%" stopColor="#10b981" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <p className="text-xl font-bold text-emerald-400 mono tabular-nums">
                  {score.toFixed(2)}
                </p>
                <p className="text-[8px] text-gray-500 uppercase tracking-wider">
                  HIGH
                </p>
              </div>
            </div>

            {/* Sources — staggered bar fills */}
            <div className="flex-1 min-w-0 space-y-1.5">
              {sources.map((s, i) => (
                <motion.div
                  key={s.label}
                  initial={{ opacity: 0, x: 6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, delay: 0.7 + i * 0.12 }}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="flex items-center gap-1.5">
                      <span
                        className="w-1.5 h-1.5 rounded-sm"
                        style={{ backgroundColor: s.colour }}
                      />
                      <span className="text-[10px] text-gray-300">{s.label}</span>
                    </div>
                    <span className="text-[10px] mono text-gray-500 tabular-nums">
                      {s.pct}%
                    </span>
                  </div>
                  <div className="h-[3px] bg-white/[0.04] rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      style={{ backgroundColor: s.colour }}
                      initial={{ width: 0 }}
                      animate={{ width: `${s.pct}%` }}
                      transition={{
                        duration: 0.9,
                        delay: 0.9 + i * 0.12,
                        ease: [0.22, 1, 0.36, 1],
                      }}
                    />
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="h-px bg-white/5 mx-5" />

        {/* Reasoning */}
        <div className="px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <GitBranch size={11} className="text-gray-500" />
            <p className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">
              Reasoning chain
            </p>
          </div>
          <ol className="space-y-2.5">
            {reasoning.map((step, i) => (
              <motion.li
                key={i}
                className="flex items-start gap-2.5"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 1.4 + i * 0.18 }}
              >
                <div className="flex flex-col items-center mt-0.5">
                  <div className="w-4 h-4 rounded-full bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center shrink-0">
                    <span className="mono text-[8px] font-semibold text-indigo-400">
                      {i + 1}
                    </span>
                  </div>
                  {i < reasoning.length - 1 && (
                    <div className="w-px h-2.5 bg-gradient-to-b from-indigo-500/25 to-transparent mt-0.5" />
                  )}
                </div>
                <p className="text-[11px] text-gray-300 leading-relaxed">{step}</p>
              </motion.li>
            ))}
          </ol>
        </div>

        {/* Verdict footer */}
        <motion.div
          className="px-5 py-3 border-t border-white/5 bg-emerald-500/[0.04] flex items-center gap-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 2.05 }}
        >
          <CheckCircle2 size={12} className="text-emerald-400 shrink-0" />
          <p className="text-[11px] text-emerald-300/90">
            Three independent sources agree.{" "}
            <span className="text-gray-500">
              No competing hypothesis above 25%.
            </span>
          </p>
        </motion.div>
      </div>

      {/* Floating chip top-right */}
      <motion.div
        className="absolute -top-3 -right-3 hidden sm:flex items-center gap-1.5 bg-[#0f0f1e] border border-indigo-500/30 rounded-full pl-2 pr-3 py-1.5 shadow-xl shadow-indigo-950/40"
        initial={{ opacity: 0, y: -10, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, delay: 1.1 }}
      >
        <motion.div
          animate={{ y: [0, -3, 0] }}
          transition={{ duration: 3.6, repeat: Infinity, ease: "easeInOut" }}
          className="flex items-center gap-1.5"
        >
          <Sparkles size={11} className="text-indigo-400" />
          <span className="text-[11px] text-gray-300 font-medium">
            Explainable by design
          </span>
        </motion.div>
      </motion.div>

      {/* Floating chip bottom-left — moved further down so it doesn't overlap the verdict */}
      <motion.div
        className="absolute -bottom-5 left-4 hidden sm:flex items-center gap-1.5 bg-[#0f0f1e] border border-amber-500/30 rounded-full pl-2 pr-3 py-1.5 shadow-xl shadow-amber-950/30"
        initial={{ opacity: 0, y: 10, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, delay: 2.4 }}
      >
        <motion.div
          animate={{ y: [0, 3, 0] }}
          transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
          className="flex items-center gap-1.5"
        >
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          <span className="text-[11px] text-gray-300 font-medium">
            44 dark-matter genes flagged
          </span>
          <ArrowUpRight size={10} className="text-amber-400" />
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
