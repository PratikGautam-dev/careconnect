import { cn } from "@/lib/cn";

type FieldProps = {
  label?: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
};

export function Field({ label, htmlFor, hint, error, required, className, children }: FieldProps) {
  return (
    <div className={cn("mb-space-4", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-label mb-space-1 block">
          {label}
          {required && <span className="text-error"> *</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="mt-space-1 text-[12.5px] font-medium text-error">{error}</p>
      ) : hint ? (
        <p className="text-hint mt-space-1">{hint}</p>
      ) : null}
    </div>
  );
}
