import type { LucideIcon } from "lucide-react";

/** Small tinted-icon + title heading at the top of an account card. */
export function AccountCardHeading({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="mb-space-3 gap-space-2 flex items-center">
      <span className="bg-brand-50 text-brand-600 flex h-8 w-8 shrink-0 items-center justify-center rounded-md">
        <Icon size={15} />
      </span>
      <h3 className="text-ink-900 text-[13.5px] font-bold">{title}</h3>
    </div>
  );
}
