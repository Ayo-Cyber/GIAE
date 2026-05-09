import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "GIAE — Genome Interpretation & Annotation Engine",
  description:
    "Explainable, evidence-centric genome annotation. Upload a genome. Get a full interactive report with confidence scores, reasoning chains, and dark matter discovery.",
  keywords: ["genome annotation", "bioinformatics", "genomics", "GIAE", "explainable AI"],
  openGraph: {
    title: "GIAE — Genome Interpretation & Annotation Engine",
    description: "The explainable genome annotation engine. Upload. Interpret. Discover.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <Providers>
      <html lang="en" className="dark">
        <body>{children}</body>
      </html>
    </Providers>
  );
}
