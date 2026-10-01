// Shared money formatting -- was reimplemented per-page/component as
// `₹${value.toLocaleString("en-IN")}`, each with its own rounding behavior
// (some truncated to whole rupees, some rendered the raw paise with no
// grouping at all). Consolidated here so every amount renders consistently:
// whole rupees print without decimals, a fractional amount keeps up to 2
// decimal places.

/** "₹1,234" or "₹1,234.56" (never more than 2 decimal places). */
export function formatINR(val: string | number | null | undefined): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(Number(val ?? 0));
}
