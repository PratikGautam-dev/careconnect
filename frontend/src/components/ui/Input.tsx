import { forwardRef } from "react";
import { cn } from "@/lib/cn";

const fieldStyle =
  "h-11 w-full rounded-md border border-line bg-card px-space-3 text-[14px] text-ink-900 shadow-[var(--shadow-sm)] " +
  "transition-[border-color,box-shadow] duration-150 ease-(--ease-standard) placeholder:text-ink-400 " +
  "focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 " +
  "disabled:cursor-not-allowed disabled:bg-paper disabled:text-ink-400";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean };

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(fieldStyle, invalid && "border-error focus:border-error focus:ring-error-tint", className)}
      {...props}
    />
  );
});

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean };

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, ...props },
  ref,
) {
  return (
    <textarea
      ref={ref}
      className={cn(
        fieldStyle,
        "h-auto resize-y py-space-2 leading-relaxed",
        invalid && "border-error focus:border-error focus:ring-error-tint",
        className,
      )}
      {...props}
    />
  );
});
