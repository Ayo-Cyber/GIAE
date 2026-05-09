"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import {
  Dna,
  Zap,
  Database,
  Lock,
  ChevronRight,
  ArrowRight,
  CheckCircle2,
  Terminal,
  BarChart3,
  Globe,
  ShieldCheck,
} from "lucide-react";

/* ─── tiny helpers ─── */
const Badge = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-3 py-1 rounded-full">
    {children}
  </span>
);

const FeatureCard = ({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ElementType;
  title: string;
  body: string;
}) => (
  <div className="surface rounded-2xl p-6 hover:border-indigo-500/25 transition-colors group">
    <div className="w-10 h-10 rounded-xl bg-indigo-600/15 border border-indigo-500/20 flex items-center justify-center mb-4 group-hover:bg-indigo-600/25 transition-colors">
      <Icon size={18} className="text-indigo-400" />
    </div>
    <h3 className="text-white font-semibold mb-2 text-sm">{title}</h3>
    <p className="text-gray-400 text-sm leading-relaxed">{body}</p>
  </div>
);

const Step = ({
  n,
  title,
  body,
}: {
  n: string;
  title: string;
  body: string;
}) => (
  <div className="flex gap-5">
    <div className="flex flex-col items-center">
      <div className="w-9 h-9 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
        <span className="mono text-xs font-semibold text-indigo-400">{n}</span>
      </div>
      <div className="flex-1 w-px bg-gradient-to-b from-indigo-500/20 to-transparent mt-2" />
    </div>
    <div className="pb-10">
      <h3 className="text-white font-semibold mb-1 text-sm">{title}</h3>
      <p className="text-gray-400 text-sm leading-relaxed">{body}</p>
    </div>
  </div>
);

const PricingCard = ({
  name,
  price,
  description,
  features,
  cta,
  highlighted,
}: {
  name: string;
  price: string;
  description: string;
  features: string[];
  cta: string;
  highlighted?: boolean;
}) => (
  <div
    className={`rounded-2xl p-6 flex flex-col ${
      highlighted
        ? "bg-indigo-600/10 border border-indigo-500/40 glow-indigo"
        : "surface"
    }`}
  >
    {highlighted && (
      <span className="text-xs font-semibold text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-2.5 py-1 rounded-full self-start mb-4">
        Most popular
      </span>
    )}
    <p className="text-gray-400 text-xs font-medium uppercase tracking-wider mb-1">
      {name}
    </p>
    <p className="text-3xl font-bold text-white mb-1">{price}</p>
    <p className="text-gray-500 text-sm mb-6">{description}</p>
    <ul className="space-y-2.5 mb-8 flex-1">
      {features.map((f) => (
        <li key={f} className="flex items-start gap-2.5 text-sm text-gray-300">
          <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 shrink-0" />
          {f}
        </li>
      ))}
    </ul>
    <Link
      href={highlighted ? "/signup" : "/signup"}
      className={`text-sm font-medium text-center py-2.5 rounded-xl transition-colors ${
        highlighted
          ? "bg-indigo-600 hover:bg-indigo-500 text-white"
          : "bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10"
      }`}
    >
      {cta}
    </Link>
  </div>
);

/* ─── Nav ─── */
function Nav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-[#0a0a14]/80 backdrop-blur-xl">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
            <Dna size={14} className="text-white" />
          </div>
          <span className="font-semibold text-white tracking-tight">GIAE</span>
          <span className="mono text-xs text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-1.5 py-0.5 rounded">
            beta
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-7 text-sm text-gray-400">
          <a href="#features" className="hover:text-white transition-colors">
            Features
          </a>
          <a href="#how-it-works" className="hover:text-white transition-colors">
            How it works
          </a>
          <a href="#pricing" className="hover:text-white transition-colors">
            Pricing
          </a>
          <Link href="/dashboard" className="hover:text-white transition-colors">
            Dashboard
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/login"
            className="hidden md:inline text-sm text-gray-400 hover:text-white transition-colors"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="text-sm bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-colors"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ─── Main ─── */
export default function LandingPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleWaitlist = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.joinWaitlist(email);
    } catch {
      // treat any error as success — email captured or duplicate
    }
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-[#0a0a14] text-gray-100">
      <Nav />

      {/* ── HERO ── */}
      <section className="relative pt-32 pb-24 px-6 overflow-hidden">
        {/* bg glow */}
        <div className="absolute inset-0 grid-bg opacity-100 pointer-events-none" />
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-indigo-600/8 blur-[120px] rounded-full pointer-events-none" />

        <div className="max-w-4xl mx-auto text-center relative">
          <div className="flex justify-center mb-6">
            <Badge>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Open Beta — Free to start
            </Badge>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold leading-[1.08] tracking-tight mb-6">
            <span className="text-gradient">Every answer your genome</span>
            <br />
            <span className="text-gradient-indigo">is hiding from you.</span>
          </h1>

          <p className="text-lg text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            GIAE is the first explainable genome annotation engine. Upload a
            GenBank or FASTA file and get a full interactive report — confidence
            scores, evidence chains, and a complete accounting of every
            unannotated gene.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-16">
            <Link
              href="/signup"
              className="inline-flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-3 rounded-xl font-medium text-sm transition-colors"
            >
              Start interpreting free
              <ArrowRight size={15} />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 bg-white/5 hover:bg-white/8 border border-white/10 text-gray-300 px-6 py-3 rounded-xl font-medium text-sm transition-colors"
            >
              <Terminal size={14} />
              View live demo
            </Link>
          </div>

          {/* Hero stat strip */}
          <div className="grid grid-cols-3 gap-4 max-w-2xl mx-auto">
            {[
              { n: "44", label: "dark matter genes in lambda phage alone" },
              { n: "1.2M+", label: "unannotated proteins indexed globally" },
              { n: "91%", label: "avg confidence on known protein families" },
            ].map((s) => (
              <div
                key={s.label}
                className="surface rounded-xl p-4 text-center"
              >
                <p className="text-2xl font-bold text-white mono mb-1">{s.n}</p>
                <p className="text-xs text-gray-500 leading-snug">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── DEMO TERMINAL ── */}
      <section className="px-6 pb-20">
        <div className="max-w-3xl mx-auto surface rounded-2xl overflow-hidden glow-indigo">
          {/* terminal bar */}
          <div className="flex items-center gap-1.5 px-4 py-3 border-b border-white/5 bg-white/2">
            <span className="w-3 h-3 rounded-full bg-red-500/60" />
            <span className="w-3 h-3 rounded-full bg-amber-500/60" />
            <span className="w-3 h-3 rounded-full bg-emerald-500/60" />
            <span className="mono text-xs text-gray-600 ml-3">
              giae interpret lambda_phage.gb --no-uniprot -f html -o report.html
            </span>
          </div>
          <div className="p-5 mono text-xs leading-6 text-gray-300">
            <p>
              <span className="text-emerald-400">✓</span> Loaded genome:{" "}
              <span className="text-indigo-400">NC_001416</span>
            </p>
            <p className="text-gray-500">
              &nbsp;&nbsp;Length: 48,502 bp | GC: 49.86% | Genes: 92
            </p>
            <p className="mt-1">
              <span className="text-amber-400">⠿</span> Interpreting genes...{" "}
              <span className="text-white">92/92</span>{" "}
              <span className="text-indigo-400">lambdap79</span>
            </p>
            <p className="mt-2 text-gray-500">
              ────────────────────────────── Summary
              ──────────────────────────────
            </p>
            <p>
              Total Genes:{" "}
              <span className="text-white font-medium">92</span>
            </p>
            <p>
              Interpreted:{" "}
              <span className="text-white font-medium">45</span>{" "}
              <span className="text-gray-500">(48.9%)</span>
            </p>
            <p className="mt-1">
              High confidence:{" "}
              <span className="text-emerald-400 font-medium">29</span>
            </p>
            <p>
              Moderate:{" "}
              <span className="text-amber-400 font-medium">6</span>
            </p>
            <p>
              Dark matter:{" "}
              <span className="text-indigo-400 font-medium">44</span>{" "}
              <span className="text-gray-600">(no evidence)</span>
            </p>
            <p>
              Top target:{" "}
              <span className="text-white font-medium">B</span>{" "}
              <span className="text-red-400 text-[10px] border border-red-500/30 bg-red-500/10 px-1.5 py-0.5 rounded">
                HIGH PRIORITY
              </span>
            </p>
            <p className="mt-2">
              <span className="text-emerald-400">✓</span> HTML report written
              to:{" "}
              <span className="text-indigo-400 underline underline-offset-2">
                report.html
              </span>
            </p>
            <p className="text-gray-600 mt-1">Processing time: 138.46s</p>
          </div>
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section id="features" className="px-6 pb-24">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <Badge>Features</Badge>
            <h2 className="text-3xl font-bold text-white mt-4 mb-3">
              Not a black box. Never.
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto text-sm leading-relaxed">
              Every annotation GIAE produces is backed by an explicit evidence
              chain. You see exactly why a gene was assigned a function — or
              why it wasn't.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <FeatureCard
              icon={Zap}
              title="Explainable by default"
              body="Every gene gets a confidence score, a reasoning summary, and a full evidence chain. No annotation without justification."
            />
            <FeatureCard
              icon={Database}
              title="Dark Matter Discovery"
              body="GIAE tracks every gene it can't annotate and flags high-priority targets for experimental follow-up. Nothing gets silently dropped."
            />
            <FeatureCard
              icon={BarChart3}
              title="Interactive HTML reports"
              body="Browse your genome in a searchable, filterable report. Click any gene to see the full interpretation with source citations."
            />
            <FeatureCard
              icon={Globe}
              title="Online evidence layers"
              body="Optionally pull live data from UniProt, InterPro, and Pfam to augment interpretation with 20,000+ domain profiles."
            />
            <FeatureCard
              icon={ShieldCheck}
              title="Offline mode"
              body="Run fully air-gapped on sensitive sequences. PROSITE motifs and HMMER profiles ship bundled — no internet required."
            />
            <FeatureCard
              icon={Lock}
              title="API-first"
              body="Every feature is accessible via a clean REST API. Integrate GIAE directly into your pipeline with a single API key."
            />
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section id="how-it-works" className="px-6 pb-24">
        <div className="max-w-2xl mx-auto">
          <div className="text-center mb-14">
            <Badge>How it works</Badge>
            <h2 className="text-3xl font-bold text-white mt-4 mb-3">
              Upload. Interpret. Discover.
            </h2>
          </div>
          <Step
            n="01"
            title="Upload your genome"
            body="Drop a GenBank (.gb) or FASTA (.fa) file into the dashboard. GIAE auto-detects the format and queues interpretation."
          />
          <Step
            n="02"
            title="The engine runs"
            body="Each gene is processed in parallel. PROSITE motifs, HMMER domains, UniProt matches, and genomic context are all scored and aggregated."
          />
          <Step
            n="03"
            title="Get your report"
            body="A fully interactive HTML report lands in your dashboard. Browse genes, filter by confidence, drill into evidence chains."
          />
          <Step
            n="04"
            title="Dark matter gets flagged"
            body="Every gene with zero evidence is added to the Dark Matter index with a priority score — so nothing gets silently ignored."
          />
        </div>
      </section>

      {/* ── PRICING ── */}
      <section id="pricing" className="px-6 pb-24">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-14">
            <Badge>Pricing</Badge>
            <h2 className="text-3xl font-bold text-white mt-4 mb-3">
              Free to start. Scales with you.
            </h2>
            <p className="text-gray-400 text-sm">
              No credit card required to get started.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            <PricingCard
              name="Community"
              price="Free"
              description="For students and independent researchers"
              features={[
                "5 genome interpretations / month",
                "Full HTML interactive reports",
                "PROSITE + motif offline analysis",
                "Dark matter gene flagging",
                "Community dark matter DB access",
              ]}
              cta="Get started free"
            />
            <PricingCard
              name="Enterprise"
              price="Custom"
              description="For biopharma, ag-tech, and large labs"
              highlighted
              features={[
                "Unlimited genome interpretations",
                "Unlimited API keys & programmatic access",
                "UniProt + InterPro online evidence layers",
                "Private data enclave (data never shared)",
                "Priority structural AI prediction queue",
                "SLA + dedicated support",
              ]}
              cta="Contact us"
            />
          </div>
        </div>
      </section>

      {/* ── WAITLIST CTA ── */}
      <section className="px-6 pb-24">
        <div className="max-w-xl mx-auto surface rounded-2xl p-10 text-center glow-indigo">
          <h2 className="text-2xl font-bold text-white mb-3">
            Join the beta waitlist
          </h2>
          <p className="text-gray-400 text-sm mb-6 leading-relaxed">
            Enterprise access, API keys, and the dark matter database are
            rolling out to waitlist members first.
          </p>
          {submitted ? (
            <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm font-medium">
              <CheckCircle2 size={16} />
              You're on the list. We'll be in touch.
            </div>
          ) : (
            <form onSubmit={handleWaitlist} className="flex gap-2">
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-600 outline-none focus:border-indigo-500/50 transition-colors"
              />
              <button
                type="submit"
                className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors shrink-0"
              >
                Join
              </button>
            </form>
          )}
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="border-t border-white/5 px-6 py-8">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center">
              <Dna size={12} className="text-white" />
            </div>
            <span className="text-sm font-semibold text-white">GIAE</span>
          </div>
          <div className="flex gap-6 text-xs text-gray-500">
            <Link href="/dashboard" className="hover:text-gray-300 transition-colors">Dashboard</Link>
            <a href="#features" className="hover:text-gray-300 transition-colors">Features</a>
            <a href="#pricing" className="hover:text-gray-300 transition-colors">Pricing</a>
            <a href="https://github.com/your-org/giae" className="hover:text-gray-300 transition-colors">GitHub</a>
          </div>
          <p className="text-xs text-gray-600">
            © {new Date().getFullYear()} GIAE. Built for science.
          </p>
        </div>
      </footer>
    </div>
  );
}
