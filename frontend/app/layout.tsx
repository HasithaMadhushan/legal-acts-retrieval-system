import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { AuthAwareShell } from "@/components/auth/auth-aware-shell";
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/sonner";

/** Self-hosted so `next build` works offline (no fonts.googleapis.com). */
const sourceSans = localFont({
  src: "./fonts/source-sans-3-latin.woff2",
  variable: "--font-sans",
  weight: "200 900",
  display: "swap",
});

const newsreader = localFont({
  src: "./fonts/newsreader-latin.woff2",
  variable: "--font-serif",
  weight: "200 800",
  display: "swap",
});

export const metadata: Metadata = {
  title: "LexAtlas — Statute & citation retrieval",
  description: "Search and browse verified Sri Lankan Legal Acts",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("font-sans", sourceSans.variable, newsreader.variable)}>
      <body>
        <AuthAwareShell>{children}</AuthAwareShell>
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
