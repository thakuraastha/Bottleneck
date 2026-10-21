import "./globals.css";
import { Metadata } from "next";
import localFont from "next/font/local";

const rebelGrotesk = localFont({
  src: "../public/fonts/Rebels-Fett.woff2",
  variable: "--font-rebels",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("http://127.0.0.1:3000"),
  title: {
    template: "%s | Bottleneck",
    default: "Bottleneck Operations",
  },
  description: "Agentic supply-chain disruption response dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          rel="preload"
          href="/fonts/Rebels-Fett.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
      </head>
      <body className={`${rebelGrotesk.variable} antialiased`}>{children}</body>
    </html>
  );
}
