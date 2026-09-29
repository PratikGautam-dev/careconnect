import React, { ReactNode } from "react";

type Props = {
  children: ReactNode;
  cols: 1 | 2 | 3 | 4 | 5 | 6;
  className?: string;
};

export function StatTileGrid({ children, cols, className }: Props) {
  return (
    <div className={className}>
      <div className="scrollbar-hide overflow-x-auto">
        <div className={`grid grid-cols-${cols} min-w-max gap-5`}>{children}</div>
      </div>
    </div>
  );
}
