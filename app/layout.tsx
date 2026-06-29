import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jan Aushadi Finder",
  description: "Find likely generic medicine name matches and nearby Jan Aushadi Kendras.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
