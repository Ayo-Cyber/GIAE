"use client";

import { useEffect, useState } from "react";
import { AppNav } from "@/components/nav";
import { Key, Plus, Trash2, Copy, Check, Eye, EyeOff, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import type { ApiKey, CreatedApiKey } from "@/lib/types";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function KeyRow({
  apiKey,
  onRevoke,
}: {
  apiKey: ApiKey;
  onRevoke: (id: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const isRevoked = !!apiKey.revoked_at;
  const isExpired = apiKey.expires_at ? new Date(apiKey.expires_at) < new Date() : false;

  return (
    <div className={cn("px-5 py-4 flex items-center gap-4", isRevoked && "opacity-50")}>
      <div className="w-8 h-8 rounded-lg bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
        <Key size={14} className="text-indigo-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <p className="text-sm font-medium text-white">{apiKey.name}</p>
          {isRevoked && (
            <span className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 px-1.5 py-0.5 rounded-full">revoked</span>
          )}
          {!isRevoked && isExpired && (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 rounded-full">expired</span>
          )}
        </div>
        <p className="text-xs text-gray-500 mono">{apiKey.key_prefix}••••••••••••••••</p>
      </div>
      <div className="hidden md:flex items-center gap-8 text-xs text-gray-500 shrink-0">
        <div className="text-right">
          <p className="text-gray-600 mb-0.5">Created</p>
          <p>{formatDate(apiKey.created_at)}</p>
        </div>
        <div className="text-right">
          <p className="text-gray-600 mb-0.5">Last used</p>
          <p>{formatDate(apiKey.last_used_at)}</p>
        </div>
        <div className="text-right">
          <p className="text-gray-600 mb-0.5">Expires</p>
          <p className={isExpired && !isRevoked ? "text-amber-400" : ""}>{formatDate(apiKey.expires_at)}</p>
        </div>
      </div>
      {!isRevoked && (
        <div className="shrink-0">
          {confirming ? (
            <div className="flex items-center gap-2">
              <button
                onClick={async () => {
                  setRevoking(true);
                  try {
                    await api.revokeApiKey(apiKey.id);
                    onRevoke(apiKey.id);
                    toast.success(`"${apiKey.name}" revoked.`);
                  } catch {
                    toast.error("Failed to revoke key.");
                  } finally {
                    setRevoking(false);
                    setConfirming(false);
                  }
                }}
                disabled={revoking}
                className="text-xs text-red-400 hover:text-red-300 transition-colors disabled:opacity-50"
              >
                {revoking ? "Revoking…" : "Confirm"}
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors"
              title="Revoke key"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function NewKeyBanner({ created, onDismiss }: { created: CreatedApiKey; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);
  const [visible, setVisible] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(created.key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-5 mb-6">
      <div className="flex items-start gap-3 mb-3">
        <AlertTriangle size={15} className="text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-emerald-300 mb-0.5">Copy your key now</p>
          <p className="text-xs text-gray-400">This is the only time it will be shown. Store it somewhere safe.</p>
        </div>
      </div>
      <div className="flex items-center gap-2 bg-[#0a0a14] border border-white/8 rounded-lg px-3 py-2.5">
        <code className="flex-1 text-xs text-gray-300 mono truncate">
          {visible ? created.key : created.key.replace(/./g, "•")}
        </code>
        <button onClick={() => setVisible((v) => !v)} className="text-gray-600 hover:text-gray-400 transition-colors shrink-0">
          {visible ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
        <button onClick={copy} className="text-gray-600 hover:text-emerald-400 transition-colors shrink-0">
          {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
        </button>
      </div>
      <button onClick={onDismiss} className="text-xs text-gray-600 hover:text-gray-400 transition-colors mt-3">
        I've saved it — dismiss
      </button>
    </div>
  );
}

function CreateKeyModal({ onClose, onCreate }: { onClose: () => void; onCreate: (k: CreatedApiKey) => void }) {
  const [name, setName] = useState("");
  const [expiry, setExpiry] = useState<string>("never");
  const [creating, setCreating] = useState(false);

  const expiryOptions = [
    { label: "Never", value: "never" },
    { label: "30 days", value: "30" },
    { label: "90 days", value: "90" },
    { label: "1 year", value: "365" },
  ];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const key = await api.createApiKey(
        name.trim(),
        expiry !== "never" ? Number(expiry) : undefined
      );
      onCreate(key);
      onClose();
    } catch {
      toast.error("Failed to create key.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
      <div className="bg-[#0f0f1e] border border-white/8 rounded-2xl w-full max-w-md p-6 shadow-xl">
        <h2 className="text-base font-semibold text-white mb-1">New API key</h2>
        <p className="text-xs text-gray-500 mb-6">Keys inherit your account permissions. Revoke them any time.</p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Key name</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. local dev, CI pipeline"
              maxLength={100}
              className="w-full bg-white/4 border border-white/8 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 outline-none focus:border-indigo-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Expiration</label>
            <div className="flex gap-2">
              {expiryOptions.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => setExpiry(o.value)}
                  className={cn(
                    "flex-1 text-xs py-1.5 rounded-lg border transition-colors",
                    expiry === o.value
                      ? "bg-indigo-600/20 border-indigo-500/30 text-indigo-300"
                      : "bg-white/4 border-white/8 text-gray-500 hover:text-gray-300"
                  )}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 text-sm text-gray-400 hover:text-white bg-white/4 hover:bg-white/8 border border-white/8 rounded-lg py-2 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || creating}
              className="flex-1 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg py-2 transition-colors"
            >
              {creating ? "Creating…" : "Create key"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newKey, setNewKey] = useState<CreatedApiKey | null>(null);

  useEffect(() => {
    api.listApiKeys()
      .then(setKeys)
      .catch(() => toast.error("Could not load API keys."))
      .finally(() => setLoading(false));
  }, []);

  const handleCreated = (key: CreatedApiKey) => {
    setNewKey(key);
    setKeys((prev) => [key, ...prev]);
  };

  const handleRevoked = (id: string) => {
    setKeys((prev) =>
      prev.map((k) => (k.id === id ? { ...k, revoked_at: new Date().toISOString() } : k))
    );
  };

  const activeKeys = keys.filter((k) => !k.revoked_at);
  const revokedKeys = keys.filter((k) => !!k.revoked_at);

  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      {showModal && (
        <CreateKeyModal onClose={() => setShowModal(false)} onCreate={handleCreated} />
      )}
      <div className="app-shell"><div className="max-w-3xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-white mb-1">API Keys</h1>
            <p className="text-gray-400 text-sm">Programmatic access to GIAE.</p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg transition-colors"
          >
            <Plus size={14} /> New key
          </button>
        </div>

        {newKey && (
          <NewKeyBanner created={newKey} onDismiss={() => setNewKey(null)} />
        )}

        {loading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 bg-[#0f0f1e] border border-white/6 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : keys.length === 0 ? (
          <div className="bg-[#0f0f1e] border border-white/6 rounded-2xl px-8 py-16 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center mb-4">
              <Key size={22} className="text-indigo-400" />
            </div>
            <p className="text-white font-medium mb-1">No API keys yet</p>
            <p className="text-sm text-gray-500 max-w-xs mb-5">
              Create a key to access GIAE programmatically via the REST API.
            </p>
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-2 text-sm bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <Plus size={14} /> Create your first key
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            {activeKeys.length > 0 && (
              <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden divide-y divide-white/5">
                {activeKeys.map((k) => (
                  <KeyRow key={k.id} apiKey={k} onRevoke={handleRevoked} />
                ))}
              </div>
            )}
            {revokedKeys.length > 0 && (
              <div>
                <p className="text-xs text-gray-600 uppercase tracking-wider mb-3">Revoked</p>
                <div className="bg-[#0f0f1e] border border-white/6 rounded-xl overflow-hidden divide-y divide-white/5">
                  {revokedKeys.map((k) => (
                    <KeyRow key={k.id} apiKey={k} onRevoke={handleRevoked} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
