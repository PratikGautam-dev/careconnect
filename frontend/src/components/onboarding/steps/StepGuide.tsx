import Image from "next/image";
import { ArrowUpRight, Clock, Globe, Lock, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { CheckboxRow } from "@/components/ui/Checkbox";

export type GuideInstruction = {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  title: string;
  description: string;
};

type IllustrationProps = {
  iconA: GuideInstruction["icon"];
  iconB: GuideInstruction["icon"];
  headline: string;
  buttonLabel: string;
};

function StepIllustration({ iconA: IconA, iconB: IconB, headline, buttonLabel }: IllustrationProps) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-brand-50 to-paper p-space-5 pt-space-7">
      <div className="absolute top-space-5 left-space-4 flex flex-col gap-space-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-[#0668E1] shadow-[var(--shadow-sm)]">
          <IconA size={18} />
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-success shadow-[var(--shadow-sm)]">
          <IconB size={18} />
        </div>
      </div>
      <div className="ml-space-7 rounded-lg border border-line bg-card p-space-4 shadow-[var(--shadow-md)]">
        <div className="mb-space-3 flex gap-1">
          <span className="h-2 w-2 rounded-full bg-line" />
          <span className="h-2 w-2 rounded-full bg-line" />
          <span className="h-2 w-2 rounded-full bg-line" />
        </div>
        <p className="mb-space-3 text-[14.5px] leading-snug font-bold text-ink-900">{headline}</p>
        <div className="mb-space-3 space-y-1.5">
          <div className="h-2 w-4/5 rounded-full bg-line" />
          <div className="h-2 w-3/5 rounded-full bg-line" />
        </div>
        <span className="inline-block rounded-md bg-brand-600 px-space-3 py-1.5 text-[12px] font-semibold text-white">
          {buttonLabel}
        </span>
      </div>
      <div className="absolute right-space-4 bottom-space-3 flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-white shadow-[var(--shadow-md)]">
        <ShieldCheck size={16} strokeWidth={2} />
      </div>
    </div>
  );
}

type StepGuideProps = {
  stepNumber: number;
  title: string;
  description: string;
  duration: string;
  instructions: GuideInstruction[];
  /** Either a code-drawn icon mockup (illustration) or a real supplied
   * image (illustrationImageSrc, takes priority when both are present) --
   * the image already carries its own "your data is secure" messaging, so
   * the separate security banner below is skipped when it's used, rather
   * than showing near-duplicate reassurance text twice. */
  illustration?: IllustrationProps;
  illustrationImageSrc?: string;
  illustrationImageAlt?: string;
  /** Natural pixel size of illustrationImageSrc, for Next/Image's required
   * width/height (defaults match the 3:2 images used so far; pass real
   * values whenever a new image has a different aspect ratio). */
  illustrationImageWidth?: number;
  illustrationImageHeight?: number;
  resourceLink: { title: string; description: string; displayUrl: string; href: string };
  done: boolean;
  onDoneChange: (done: boolean) => void;
};

export function StepGuide({
  stepNumber,
  title,
  description,
  duration,
  instructions,
  illustration,
  illustrationImageSrc,
  illustrationImageAlt,
  illustrationImageWidth = 1536,
  illustrationImageHeight = 1024,
  resourceLink,
  done,
  onDoneChange,
}: StepGuideProps) {
  return (
    <div>
      <p className="text-eyebrow mb-space-2">Step {stepNumber} of 9</p>
      <h2 className="text-display mb-space-2">{title}</h2>
      <p className="text-body mb-space-3">{description}</p>
      <span className="mb-space-5 inline-flex items-center gap-space-1 rounded-full bg-brand-50 px-space-3 py-1 text-[12px] font-semibold text-brand-700">
        <Clock size={13} /> {duration}
      </span>

      <div className="grid grid-cols-1 gap-space-6 lg:grid-cols-2">
        <div>
          <div>
            {instructions.map((item, i) => (
              <div key={i} className="relative flex gap-space-3 pb-space-4 last:pb-0">
                {i < instructions.length - 1 && (
                  <span className="absolute top-7 bottom-0 left-[13px] w-px bg-line" aria-hidden />
                )}
                <span className="z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-brand-200 bg-card text-[11px] font-bold text-brand-700">
                  {i + 1}
                </span>
                <div className="flex flex-1 items-start gap-space-3 rounded-lg border border-line bg-paper p-space-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-brand-50 text-brand-600">
                    <item.icon size={16} strokeWidth={2} />
                  </div>
                  <div>
                    <p className="text-[13.5px] font-bold text-ink-900">{item.title}</p>
                    <p className="text-[12.5px] leading-relaxed text-ink-600">{item.description}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-space-4 rounded-lg border border-line bg-paper p-space-3">
            <CheckboxRow checked={done} onChange={onDoneChange}>
              I&apos;ve done this
            </CheckboxRow>
          </div>
        </div>

        <div>
          {illustrationImageSrc ? (
            <div className="overflow-hidden rounded-xl border border-line shadow-sm">
              <Image
                src={illustrationImageSrc}
                alt={illustrationImageAlt || ""}
                width={illustrationImageWidth}
                height={illustrationImageHeight}
                className="h-auto w-full"
                priority
              />
            </div>
          ) : (
            illustration && <StepIllustration {...illustration} />
          )}

          <div className="mt-space-4 flex flex-col items-start gap-space-3 rounded-lg border border-line bg-card p-space-4 sm:flex-row sm:items-center">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Globe size={18} strokeWidth={2} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[13.5px] font-bold text-ink-900">{resourceLink.title}</p>
              <p className="text-[12.5px] text-ink-600">{resourceLink.description}</p>
              <p className="text-[12.5px] font-medium text-brand-600">{resourceLink.displayUrl}</p>
            </div>
            <Button href={resourceLink.href} target="_blank" rel="noopener noreferrer" size="md" className="w-full shrink-0 sm:w-auto">
              Open Website <ArrowUpRight size={14} />
            </Button>
          </div>

          {!illustrationImageSrc && (
            <div className="mt-space-3 flex items-center gap-space-2 rounded-lg bg-brand-50 p-space-3 text-[12.5px] font-medium text-brand-700">
              <Lock size={14} strokeWidth={2} className="shrink-0" />
              Your data is secure and never shared with third parties.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
