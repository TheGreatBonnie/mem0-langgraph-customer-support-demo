import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Memory-First Support Agent",
  description: "Support console frontend for the Mem0 and LangGraph agent.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
