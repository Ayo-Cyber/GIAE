import { AppNav } from "@/components/nav";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#0a0a14]">
      <AppNav />
      <main className="app-shell">{children}</main>
    </div>
  );
}
