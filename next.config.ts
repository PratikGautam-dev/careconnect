import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-hosted Docker deployment ONLY (frontend/Dockerfile): traces only
  // the files each page actually needs into .next/standalone, so the
  // runtime image doesn't need to ship node_modules at all.
  //
  // MUST be disabled on Vercel -- this is a correction, not a guess: an
  // earlier version of this comment claimed "Vercel ignores this and does
  // its own tracing," which was never actually verified against a live
  // Vercel deploy and turned out to be wrong. Vercel's build pipeline
  // expects .next/next-server.js.nft.json; `output: "standalone"` moves
  // that trace file to .next/standalone/next-server.js.nft.json instead,
  // which broke Vercel's own onBuildComplete step with a literal ENOENT on
  // the path it expected ("no such file or directory,
  // .next/next-server.js.nft.json") -- a real production deploy failure,
  // not a hypothetical. Vercel sets VERCEL=1 automatically during its own
  // builds (never during `docker build`), so that's what this switches on.
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
