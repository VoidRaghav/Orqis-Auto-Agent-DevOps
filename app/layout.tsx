import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Orqis — Mission Control for Vibe-Built Agents",
  description:
    "Zero config DevOps and observability layer for AI agents. Narrative logs, live config hot-swap, cost guardrails, and self-healing loops.",
  openGraph: {
    title: "Orqis — Mission Control for Vibe-Built Agents",
    description: "Zero config. Self-healing. Always watching.",
    type: "website",
    url: "https://orqis.dev",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" style={{ scrollBehavior: "auto" }}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Anton — giant display/scroll text */}
        {/* DM Mono — code & data */}
        {/* Inter — body & UI */}
        <link
          href="https://fonts.googleapis.com/css2?family=Anton&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&family=Inter:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
