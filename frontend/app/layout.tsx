import type { Metadata } from "next";
import { Newsreader, Source_Sans_3 } from "next/font/google";
import "./globals.css";
import { AuthAwareShell } from "@/components/auth/auth-aware-shell";
import { cn } from "@/lib/utils";

const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-sans",
});

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-serif",
});

export const metadata: Metadata = {
  title: "Legal Acts Retrieval System",
  description: "Search and browse verified Sri Lankan Legal Acts",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("font-sans", sourceSans.variable, newsreader.variable)}>
      <body>
        <AuthAwareShell>{children}</AuthAwareShell>
      </body>
    </html>
  );
}
