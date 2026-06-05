"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Dna, LayoutDashboard, FolderOpen, Database, Key,
  LogOut, AlertTriangle, ChevronRight, BarChart2, Bookmark, GitCompare, Telescope,
} from "lucide-react";
import { NotificationCenter } from "./notification-center";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { ThemeToggle } from "./theme";

const WARN_MS = 5 * 60 * 1000;

function useSessionExpiry() {
  const { data: session } = useSession();
  const router = useRouter();
  const [msLeft, setMsLeft] = useState<number | null>(null);

  useEffect(() => {
    const expires = session?.accessTokenExpires;
    if (!expires) return;
    const tick = () => {
      const left = expires - Date.now();
      setMsLeft(left);
      if (left <= 0) signOut({ callbackUrl: "/login?expired=1" });
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [session?.accessTokenExpires, router]);

  return msLeft;
}

const navItems = [
  { href: "/dashboard",  label: "Dashboard",   icon: LayoutDashboard },
  { href: "/jobs",       label: "Jobs",         icon: FolderOpen      },
  { href: "/database",   label: "Dark Matter",  icon: Database        },
  { href: "/analytics",  label: "Analytics",    icon: BarChart2       },
  { href: "/bookmarks",  label: "Bookmarks",    icon: Bookmark        },
  { href: "/watchlist",  label: "Watchlist",    icon: Telescope       },
  { href: "/compare",    label: "Compare",      icon: GitCompare      },
  { href: "/keys",       label: "API Keys",     icon: Key             },
];

const JOB_LIMIT = 5;

export function AppNav() {
  const path = usePathname();
  const { data: session } = useSession();
  const [jobCount, setJobCount] = useState<number | null>(null);
  const msLeft = useSessionExpiry();

  useEffect(() => {
    api.listJobs().then((jobs) => setJobCount(jobs.length)).catch(() => {});
  }, []);

  const firstName = session?.user?.firstName || session?.user?.name?.split(" ")[0] || "";
  const initials = (firstName ? firstName[0] : session?.user?.email?.[0] ?? "?").toUpperCase();

  const showExpiry = msLeft !== null && msLeft > 0 && msLeft < WARN_MS;
  const minsLeft  = msLeft !== null ? Math.ceil(msLeft / 60_000) : 0;

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 h-screen z-50 flex flex-col",
        "w-14 lg:w-56",
        "sidebar-bg border-r sidebar-border transition-[width] duration-200",
      )}
    >
      {/* Logo */}
      <div className="h-14 flex items-center px-3.5 lg:px-4 border-b sidebar-border shrink-0">
        <Link href="/dashboard" className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shrink-0">
            <Dna size={14} className="text-white" />
          </div>
          <span className="hidden lg:block font-semibold tracking-tight sidebar-text truncate">GIAE</span>
          <span className="hidden lg:block mono text-[10px] text-indigo-400 bg-indigo-400/10 border border-indigo-400/20 px-1.5 py-0.5 rounded shrink-0">
            beta
          </span>
        </Link>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto min-h-0">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = path === href || (href !== "/dashboard" && path.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              title={label}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-2.5 py-2 transition-colors",
                active
                  ? "bg-indigo-600/15 text-indigo-400"
                  : "sidebar-muted hover:sidebar-text hover:bg-white/5"
              )}
            >
              <Icon size={16} className="shrink-0" />
              <span className="hidden lg:block text-sm font-medium truncate">{label}</span>
              {active && <ChevronRight size={12} className="hidden lg:block ml-auto shrink-0 text-indigo-500/50" />}
            </Link>
          );
        })}
      </nav>

      {/* Session expiry warning */}
      {showExpiry && (
        <div className="mx-2 mb-2 flex items-start gap-2 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2.5 py-2">
          <AlertTriangle size={12} className="text-amber-400 shrink-0 mt-0.5" />
          <div className="hidden lg:block min-w-0">
            <p className="text-[11px] text-amber-300 leading-tight">
              Session expires in {minsLeft}m
            </p>
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="text-[10px] text-amber-400/70 underline underline-offset-2 hover:text-amber-300 transition-colors"
            >
              Sign in again
            </button>
          </div>
        </div>
      )}

      {/* Bottom: plan + user */}
      <div className="px-2 py-3 border-t sidebar-border space-y-2 shrink-0">
        {/* Plan badge */}
        <div className="hidden lg:flex items-center gap-2 rounded-lg px-2.5 py-1.5 sidebar-surface">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
          <span className="text-xs mono sidebar-muted flex-1 truncate">
            Free · {jobCount ?? "…"}/{JOB_LIMIT} jobs
          </span>
          <Link
            href="/upgrade"
            className="text-[10px] font-medium text-indigo-400 hover:text-indigo-300 shrink-0 transition-colors"
          >
            Upgrade
          </Link>
        </div>

        {/* User row */}
        <div className="flex items-center gap-2 px-1">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-semibold text-white shrink-0">
            {initials}
          </div>
          <div className="hidden lg:flex flex-1 items-center gap-1.5 min-w-0">
            <span className="text-xs sidebar-muted truncate flex-1">
              {session?.user?.email}
            </span>
            <NotificationCenter />
            <ThemeToggle />
            <button
              onClick={() => signOut({ callbackUrl: "/" })}
              className="p-1 rounded sidebar-muted hover:sidebar-text transition-colors"
              title="Sign out"
            >
              <LogOut size={13} />
            </button>
          </div>
          {/* Mobile: just theme + logout */}
          <div className="flex lg:hidden items-center gap-1">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </aside>
  );
}
