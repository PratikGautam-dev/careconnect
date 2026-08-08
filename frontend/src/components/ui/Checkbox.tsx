import { cn } from "@/lib/cn";

type CheckboxRowProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: React.ReactNode;
  className?: string;
};

export function CheckboxRow({ checked, onChange, children, className }: CheckboxRowProps) {
  return (
    <label className={cn("flex cursor-pointer items-start gap-space-2 text-[14px] text-ink-900 select-none", className)}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 accent-brand-600"
      />
      <span>{children}</span>
    </label>
  );
}
