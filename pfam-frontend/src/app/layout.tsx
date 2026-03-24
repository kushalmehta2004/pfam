import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { ReactNode } from "react";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "PFAM",
  description: "Profit-First Ad Manager",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body><Providers>{children}</Providers></body>
      </html>
    </ClerkProvider>
  );
}

