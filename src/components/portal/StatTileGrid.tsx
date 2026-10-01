import React, { ReactNode } from "react";

type Cols = 1 | 2 | 3 | 4 | 5 | 6;

type Props = {
  children: ReactNode;
  cols: Cols;
  className?: string;
};

const COLS_CLASS: Record<Cols, string> = {
  1: "grid-cols-1",
  2: "grid-cols-2",
  3: "grid-cols-3",
  4: "grid-cols-4",
  5: "grid-cols-5",
  6: "grid-cols-6",
};

export function StatTileGrid({ children, cols, className }: Props) {
  return (
    <div className={className}>
      <div className="scrollbar-hide overflow-x-auto">
        <div className={`grid ${COLS_CLASS[cols]} min-w-max gap-5`}>{children}</div>
      </div>
    </div>
  );
}
