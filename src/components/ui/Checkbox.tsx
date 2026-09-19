import { cn } from "@/lib/cn";

type CheckboxRowProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: React.ReactNode;
  className?: string;
};

export function CheckboxRow({ checked, onChange, children, className }: CheckboxRowProps) {
  return (
    <label
      className={cn(
        "gap-space-2 text-ink-900 flex cursor-pointer items-start text-[14px] select-none",
        className,
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-brand-600 mt-0.5 h-4 w-4 shrink-0"
      />
      <span>{children}</span>
    </label>
  );
}
