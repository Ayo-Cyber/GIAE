"use client";

import { AppNav } from "@/components/nav";
import { Key } from "lucide-react";

export default function KeysPage() {
  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <div className="pt-14 max-w-5xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-white mb-1">API Keys</h1>
          <p className="text-gray-400 text-sm">Programmatic access to GIAE.</p>
        </div>

        <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-16 flex flex-col items-center text-center">
          <div className="w-12 h-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mb-4">
            <Key size={22} className="text-indigo-400" />
          </div>
          <p className="text-white font-medium mb-1">Coming soon</p>
          <p className="text-sm text-gray-500 max-w-xs">
            API key management will be available in an upcoming release.
            Upgrade to a paid plan to get early access.
          </p>
        </div>
      </div>
    </div>
  );
}
