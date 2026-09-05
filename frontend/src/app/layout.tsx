import type { Metadata } from "next";
import { Plus_Jakarta_Sans, IBM_Plex_Sans } from "next/font/google";
import { Toaster } from "@/components/ui/toast";
import "./globals.css";

// Plus Jakarta Sans: a warm, slightly rounded geometric sans for display/
// headings -- distinct from the Inter/Geist "safe default" look, still reads
// as clean and modern rather than quirky, which suits a healthcare-ops
// product. IBM Plex Sans for body/UI text: excellent legibility at small
// sizes (dashboards, tables, form labels), a bit more technical/precise than
// Jakarta, which is exactly the contrast a display/body pairing wants.
const displayFont = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700", "800"],
});

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "DAAP CareConnect — WhatsApp Appointment Booking & Reminder Platform for Hospitals",
  description:
    "Let patients book, reschedule and cancel appointments through WhatsApp, managed from one hospital dashboard.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${displayFont.variable} ${bodyFont.variable}`}>
      <body>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
