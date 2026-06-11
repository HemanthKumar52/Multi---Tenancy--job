import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import { Fraunces, Hanken_Grotesk, IBM_Plex_Mono } from "next/font/google";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});
const hanken = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-hanken",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Apply Co-Pilot — your job-search co-pilot",
  description: "Format-preserving, truthful resume tailoring + human-approved job applications.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${hanken.variable} ${plexMono.variable}`}>
      <body>
        <nav className="nav">
          <span className="brand">
            <span className="dot" />
            Apply&nbsp;Co-Pilot
          </span>
          <span className="status">
            <span className="pulse" />
            co-pilot engaged
          </span>
          <span className="links">
            <Link href="/">Dashboard</Link>
            <Link href="/profile">Profile</Link>
            <Link href="/jobs">Jobs</Link>
            <Link href="/applications">Applications</Link>
          </span>
        </nav>
        <div className="container">{children}</div>
      </body>
    </html>
  );
}
