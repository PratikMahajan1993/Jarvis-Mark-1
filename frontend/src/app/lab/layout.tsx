import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Diarize lab — Jarvis",
};

export default function LabLayout({ children }: { children: React.ReactNode }) {
  return children;
}
