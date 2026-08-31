import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TruthLens · 真相镜 — Can you trust your data?",
  description:
    "Data Forensics & Statistical Integrity Engine. Upload CSV or Excel to scan for suspicious patterns, anomalies and hidden structures.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
