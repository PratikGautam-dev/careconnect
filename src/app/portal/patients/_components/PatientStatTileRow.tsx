"use client";

import type { ReactNode } from "react";

/** The Patient Details page's own stat-tile row -- a 200px-minimum grid
 * (repeat(auto-fit, minmax(200px, 1fr))) so every tile is always the same
 * width as its neighbors (a longer label like "Tele-consultations" never
 * leaves that one tile wider) AND the row always fills its container
 * (no leftover blank space trailing the last tile on a 4-5 tile row),
 * unlike a plain flex-wrap row where each tile's own natural/fixed width
 * leaves a gap once the tiles don't divide the row evenly. Still wraps
 * onto a second line on a narrow viewport once tiles can't fit at
 * 200px each. This is deliberately not the shared StatTileGrid (used
 * everywhere else -- Billing page, Pharmacy dashboard, etc., each already
 * matched to its own reference design and left untouched); this one is
 * specific to the Patient Details page's own tabs. */
export function PatientStatTileRow({ children }: { children: ReactNode }) {
  return (
    <div
      className="mb-space-4 grid gap-3"
      style={{ gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}
    >
      {children}
    </div>
  );
}
