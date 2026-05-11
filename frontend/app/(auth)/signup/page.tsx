"use client";

import { signIn } from "next-auth/react";
import { Dna } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function SignUpPage() {
  const router = useRouter();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      // Register via FastAPI
      const res = await fetch("/api/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ first_name: firstName, last_name: lastName, email, password }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail ?? "Registration failed.");
        setLoading(false);
        return;
      }
      // Auto sign in after register
      const result = await signIn("credentials", { email, password, redirect: false });
      if (result?.ok) {
        router.push("/dashboard");
      } else {
        setError("Account created — please sign in.");
        router.push("/login");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a14] grid-bg flex flex-col items-center justify-center px-6">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-indigo-600/8 blur-[100px] rounded-full pointer-events-none" />

      <div className="relative w-full max-w-sm">
        <Link href="/" className="flex items-center justify-center gap-2.5 mb-8">
          <div className="w-8 h-8 rounded-xl bg-indigo-600 flex items-center justify-center">
            <Dna size={16} className="text-white" />
          </div>
          <span className="font-semibold text-white text-lg tracking-tight">GIAE</span>
        </Link>

        <div className="text-center mb-6">
          <h1 className="text-xl font-bold text-white mb-1">Create your account</h1>
          <p className="text-gray-400 text-sm">Free tier — 5 genomes/month, no credit card</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-[#0f0f1e] border border-white/8 rounded-2xl p-6 space-y-4">
          {error && (
            <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</p>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1.5">First name</label>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Ada"
                required
                className="w-full bg-white/5 border border-white/10 text-white placeholder-gray-600 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500/50 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1.5">Last name</label>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Lovelace"
                className="w-full bg-white/5 border border-white/10 text-white placeholder-gray-600 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500/50 transition-colors"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="w-full bg-white/5 border border-white/10 text-white placeholder-gray-600 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500/50 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              required
              minLength={8}
              className="w-full bg-white/5 border border-white/10 text-white placeholder-gray-600 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500/50 transition-colors"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="block w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white py-2.5 rounded-xl text-sm font-medium transition-colors"
          >
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="text-center text-xs text-gray-600 mt-5">
          Already have an account?{" "}
          <Link href="/login" className="text-indigo-400 hover:text-indigo-300 transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
