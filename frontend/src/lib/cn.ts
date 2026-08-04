import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names AND resolve conflicting Tailwind utility
 * classes (e.g. a caller passing `p-4` to override a component's own
 * `p-space-6`) so the last one wins predictably instead of both landing in
 * the DOM and fighting on CSS specificity/source order. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
