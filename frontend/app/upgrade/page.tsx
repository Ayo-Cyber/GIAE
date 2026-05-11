"use client";

import Link from "next/link";
import { AppNav } from "@/components/nav";
import { Zap, Check } from "lucide-react";

const PLANS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    features: ["5 genome jobs", "Dark matter database access", "HTML reports"],
    current: true,
    cta: "Current plan",
  },
  {
    name: "Pro",
    price: "$29",
    period: "per month",
    features: [
      "Unlimited genome jobs",
      "API access",
      "Priority processing",
      "CSV / JSON export",
      "Email support",
    ],
    current: false,
    cta: "Coming soon",
  },
  {
    name: "Team",
    price: "$99",
    period: "per month",
    features: [
      "Everything in Pro",
      "Up to 10 seats",
      "Shared dark matter index",
      "SSO",
      "Dedicated support",
    ],
    current: false,
    cta: "Coming soon",
  },
];

export default function UpgradePage() {
  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="pt-14 max-w-5xl mx-auto px-6 py-10">
        <div className="text-center mb-10">
          <h1 className="text-2xl font-semibold text-white mb-2">Plans</h1>
          <p className="text-gray-400 text-sm">
            Paid plans are coming soon. You&apos;re on the free tier.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`bg-[#0f0f1e] border rounded-2xl p-6 flex flex-col ${
                plan.name === "Pro"
                  ? "border-indigo-500/40"
                  : "border-white/6"
              }`}
            >
              {plan.name === "Pro" && (
                <span className="self-start text-xs bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded-full mb-3">
                  Most popular
                </span>
              )}
              <p className="text-white font-semibold text-lg mb-0.5">{plan.name}</p>
              <p className="text-3xl font-bold text-white mono mb-0.5">{plan.price}</p>
              <p className="text-xs text-gray-500 mb-6">{plan.period}</p>
              <ul className="space-y-2 flex-1 mb-6">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-gray-300">
                    <Check size={13} className="text-emerald-400 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
              <button
                disabled={!plan.current && true}
                className={`w-full text-sm py-2 rounded-lg font-medium transition-colors ${
                  plan.current
                    ? "bg-white/5 text-gray-400 cursor-default border border-white/8"
                    : "bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 cursor-not-allowed"
                }`}
              >
                {plan.cta}
              </button>
            </div>
          ))}
        </div>

        <p className="text-center text-xs text-gray-600 mt-8">
          Want early access to Pro?{" "}
          <Link href="mailto:hello@giae.io" className="text-indigo-400 hover:underline">
            Get in touch
          </Link>
        </p>
      </div>
    </div>
  );
}
