"use client";

import { Children, type ReactNode } from "react";

/** The Patient Details page's own compact stat-tile row -- unlike the
 * shared StatTileGrid (equal-width grid columns stretched to fill the
 * whole row, used everywhere else in the app: Billing page, Pharmacy
 * dashboard, etc., each already matched to its own reference design and
 * left untouched), these tiles keep their natural content width and wrap,
 * so a 4-5 tile row stays small instead of stretching across the page. */
export function PatientStatTileRow({ children }: { children: ReactNode }) {
  return (
    <div className="mb-space-4 flex flex-wrap gap-3">
      {Children.map(children, (child) => (
        <div className="w-fit min-w-[170px] shrink-0">{child}</div>
      ))}
    </div>
  );
}
