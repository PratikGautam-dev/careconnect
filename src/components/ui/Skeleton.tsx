import { cn } from "@/lib/cn";

/** Base pulsing placeholder block -- every skeleton layout in the app
 * composes this one primitive (a sized/rounded div) rather than each
 * page inventing its own shimmer styling. Pass width/height via
 * className (e.g. "h-4 w-32"). */
export function Skeleton({ className }: { className?: string }) {
  // bg-black/8 (a plain opacity modifier, not a design-system token) --
  // this app's own ink-* scale only defines ink-400/600/900 (see
  // globals.css), no ink-100/200 "light grey" step exists to reach for.
  return <div className={cn("bg-black/8 animate-pulse rounded-md", className)} />;
}

/** A row of stat-tile-shaped placeholders -- matches StatTile/StatTileGrid's
 * real layout (circular icon + two lines of text) closely enough that the
 * page doesn't visibly jump when real data replaces it. */
export function SkeletonStatTileRow({ count = 4 }: { count?: number }) {
  return (
    <div
      className="mb-space-4 grid gap-3"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(200px, 1fr))` }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="border-line bg-card p-space-4 gap-space-3 flex items-center rounded-lg border">
          <Skeleton className="h-14 w-14 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-6 w-12" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** A table-shaped placeholder -- a header bar + N row bars, matching
 * DataTable's own row height closely enough to avoid a layout jump. */
export function SkeletonTable({ rows = 6 }: { rows?: number }) {
  return (
    <div className="border-line overflow-hidden rounded-lg border">
      <div className="bg-black/2 p-space-3">
        <Skeleton className="h-4 w-32" />
      </div>
      <div className="divide-line divide-y">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="p-space-3 gap-space-4 flex items-center">
            <Skeleton className="h-9 w-9 shrink-0 rounded-full" />
            <Skeleton className="h-3 flex-1" />
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** A generic card-shaped placeholder -- a title line + a few body lines,
 * for cards whose real content isn't tabular (detail panels, summary
 * cards, form sections). */
export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="border-line bg-card p-space-4 rounded-lg border">
      <Skeleton className="mb-space-3 h-4 w-40" />
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-full" />
        ))}
      </div>
    </div>
  );
}
