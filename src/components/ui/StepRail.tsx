import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

export type StepRailItem = {
  title: string;
};

type StepRailProps = {
  steps: StepRailItem[];
  currentStep: number;
  maxUnlockedStep: number;
  onStepClick: (step: number) => void;
  className?: string;
};

export function StepRail({ steps, currentStep, maxUnlockedStep, onStepClick, className }: StepRailProps) {
  return (
    <nav className={cn("flex flex-col gap-space-1", className)} aria-label="Onboarding steps">
      {steps.map((step, i) => {
        const isDone = i < maxUnlockedStep;
        const isActive = i === currentStep;
        const isClickable = i <= maxUnlockedStep;
        return (
          <button
            key={step.title}
            type="button"
            disabled={!isClickable}
            onClick={() => onStepClick(i)}
            className={cn(
              "flex items-center gap-space-3 rounded-md px-space-3 py-space-2 text-left text-[13.5px] transition-colors duration-150 ease-(--ease-standard)",
              isClickable && !isActive && "cursor-pointer hover:bg-brand-50",
              !isClickable && "cursor-not-allowed opacity-50",
              isActive && "bg-brand-600 text-white shadow-sm",
            )}
          >
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                isActive && "bg-white text-brand-600",
                !isActive && isDone && "bg-brand-100 text-brand-700",
                !isActive && !isDone && "bg-black/[0.05] text-ink-400",
              )}
            >
              {isDone && !isActive ? <Check size={12} strokeWidth={3} /> : i}
            </span>
            <span className={cn("font-medium", isActive ? "text-white" : isDone ? "text-ink-900" : "text-ink-600")}>
              {step.title}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
