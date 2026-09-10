import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Elyanivery",
  description: "Multi-role food delivery and logistics platform featuring Customer ordering, Courier fulfillment, Restaurant Partner management, Support ticketing, and Admin operations.",
  keywords: ["Elyanivery", "Food Delivery", "Courier", "Partner", "Support", "Admin"],
  icons: {
    icon: "/static/logo.png",
  },
  openGraph: {
    title: "Elyanivery",
    description: "Multi-role food delivery and logistics platform featuring Customer ordering, Courier fulfillment, Restaurant Partner management, Support ticketing, and Admin operations.",
    siteName: "Elyanivery",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Elyanivery",
    description: "Multi-role food delivery and logistics platform featuring Customer ordering, Courier fulfillment, Restaurant Partner management, Support ticketing, and Admin operations.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
