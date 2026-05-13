import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { themeBootstrapScript } from "@/components/theme";
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
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Set theme before first paint to avoid flash */}
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
