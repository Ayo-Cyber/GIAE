"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell, CheckCircle2, XCircle, Eye, Zap, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Notification } from "@/lib/types";
import { cn } from "@/lib/utils";

const SEEN_KEY = "giae:notifications:seen_at";

function getSeen(): number {
  if (typeof window === "undefined") return 0;
  return Number(localStorage.getItem(SEEN_KEY) ?? "0");
}

function markSeen() {
  localStorage.setItem(SEEN_KEY, String(Date.now()));
}

function NotifIcon({ type }: { type: Notification["type"] }) {
  if (type === "completed")  return <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />;
  if (type === "failed")     return <XCircle      size={13} className="text-red-400 shrink-0"     />;
  if (type === "watch_hit")  return <Zap          size={13} className="text-amber-400 shrink-0"   />;
  return                            <XCircle      size={13} className="text-gray-500 shrink-0"    />;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins  = Math.floor(diff / 60_000);
  const hours = Math.floor(diff / 3_600_000);
  const days  = Math.floor(diff / 86_400_000);
  if (mins < 1)   return "just now";
  if (mins < 60)  return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

export function NotificationCenter() {
  const [open, setOpen]               = useState(false);
  const [notifs, setNotifs]           = useState<Notification[]>([]);
  const [unread, setUnread]           = useState(0);
  const ref                           = useRef<HTMLDivElement>(null);

  const load = async () => {
    try {
      const all  = await api.getNotifications();
      const seen = getSeen();
      setNotifs(all);
      setUnread(all.filter((n) => n.created_at && new Date(n.created_at).getTime() > seen).length);
    } catch { /* silent */ }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, []);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggle = () => {
    if (!open) { markSeen(); setUnread(0); }
    setOpen((v) => !v);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={toggle}
        title="Notifications"
        className={cn(
          "relative flex items-center justify-center w-7 h-7 rounded-lg transition-colors",
          open ? "bg-white/8 text-white" : "text-gray-500 hover:text-white hover:bg-white/5"
        )}
      >
        <Bell size={15} />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-indigo-500 text-[8px] font-bold text-white flex items-center justify-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute left-full ml-2 top-0 z-50 w-80 bg-[#0f0f1e] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/6">
            <p className="text-xs font-semibold text-white">Notifications</p>
            <button onClick={() => setOpen(false)} className="text-gray-600 hover:text-gray-400 transition-colors">
              <X size={13} />
            </button>
          </div>

          {notifs.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <Bell size={22} className="text-gray-700 mx-auto mb-2" />
              <p className="text-xs text-gray-600">No notifications yet.</p>
            </div>
          ) : (
            <div className="max-h-80 overflow-y-auto divide-y divide-white/[0.04]">
              {notifs.map((n) => (
                <Link
                  key={n.id}
                  href={`/jobs/${n.job_id}`}
                  onClick={() => setOpen(false)}
                  className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.03] transition-colors"
                >
                  <NotifIcon type={n.type} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-300 leading-snug line-clamp-2">{n.message}</p>
                    <p className="text-[10px] text-gray-600 mono mt-0.5 truncate">{n.filename}</p>
                  </div>
                  <span className="text-[10px] text-gray-600 shrink-0 mt-0.5">{timeAgo(n.created_at)}</span>
                </Link>
              ))}
            </div>
          )}

          <div className="px-4 py-2 border-t border-white/6">
            <button
              onClick={() => { markSeen(); setUnread(0); setOpen(false); }}
              className="flex items-center gap-1.5 text-[11px] text-gray-500 hover:text-gray-300 transition-colors"
            >
              <Eye size={11} /> Mark all as read
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
