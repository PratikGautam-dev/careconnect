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

export function StepRail({
  steps,
  currentStep,
  maxUnlockedStep,
  onStepClick,
  className,
}: StepRailProps) {
  return (
    <nav className={cn("gap-space-1 flex flex-col", className)} aria-label="Onboarding steps">
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
              "gap-space-3 px-space-3 py-space-2 flex items-center rounded-md text-left text-[13.5px] transition-colors duration-150 ease-(--ease-standard)",
              isClickable && !isActive && "hover:bg-brand-50 cursor-pointer",
              !isClickable && "cursor-not-allowed opacity-50",
              isActive && "bg-brand-600 text-white shadow-sm",
            )}
          >
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                isActive && "text-brand-600 bg-white",
                !isActive && isDone && "bg-brand-100 text-brand-700",
                !isActive && !isDone && "text-ink-400 bg-black/[0.05]",
              )}
            >
              {isDone && !isActive ? <Check size={12} strokeWidth={3} /> : i}
            </span>
            <span
              className={cn(
                "font-medium",
                isActive ? "text-white" : isDone ? "text-ink-900" : "text-ink-600",
              )}
            >
              {step.title}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
