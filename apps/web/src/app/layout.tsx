import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KineticProof",
  description:
    "Investigate everyday physics with real observations and transparent measurements.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
