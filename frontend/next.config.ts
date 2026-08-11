import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-hosted Docker deployment (frontend/Dockerfile): traces only the
  // files each page actually needs into .next/standalone, so the runtime
  // image doesn't need to ship node_modules at all. No effect on `next dev`
  // or Vercel (Vercel ignores this and does its own tracing).
  output: "standalone",
};

export default nextConfig;
