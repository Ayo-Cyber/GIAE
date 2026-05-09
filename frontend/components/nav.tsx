"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Dna, LayoutDashboard, FolderOpen, Database, Key, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: FolderOpen },
  { href: "/database", label: "Dark Matter", icon: Database },
  { href: "/keys", label: "API Keys", icon: Key },
];

const JOB_LIMIT = 5;

export function AppNav() {
  const path = usePathname();
  const { data: session } = useSession();
  const [jobCount, setJobCount] = useState<number | null>(null);

  useEffect(() => {
    api.listJobs().then((jobs) => setJobCount(jobs.length)).catch(() => {});
  }, []);
  const initials = session?.user?.name
    ? session.user.name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()
    : "?";

  return (
    <header className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-[#0a0a14]/85 backdrop-blur-xl">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
            <Dna size={14} className="text-white" />
          </div>
          <span className="font-semibold text-white tracking-tight">GIAE</span>
          <span className="mono text-xs text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-1.5 py-0.5 rounded">
            beta
          </span>
        </Link>

        {/* Nav items */}
        <nav className="hidden md:flex items-center gap-1">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = path.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors",
                  active
                    ? "bg-indigo-600/15 text-indigo-400 border border-indigo-500/20"
                    : "text-gray-400 hover:text-white hover:bg-white/5"
                )}
              >
                <Icon size={14} />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Right */}
        <div className="flex items-center gap-3">
          <div className="hidden md:flex items-center gap-1.5 text-xs mono text-gray-500 bg-white/4 border border-white/6 px-3 py-1.5 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            Free · {jobCount ?? "…"}/{JOB_LIMIT} jobs
          </div>
          <Link
            href="/upgrade"
            className="hidden md:inline text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg font-medium transition-colors"
          >
            Upgrade
          </Link>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-semibold text-white">
              {initials}
            </div>
            <button
              onClick={() => signOut({ callbackUrl: "/" })}
              className="text-gray-500 hover:text-gray-300 transition-colors"
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
