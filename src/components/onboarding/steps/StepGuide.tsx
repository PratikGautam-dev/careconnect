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

function StepIllustration({
  iconA: IconA,
  iconB: IconB,
  headline,
  buttonLabel,
}: IllustrationProps) {
  return (
    <div className="from-brand-50 to-paper p-space-5 pt-space-7 relative overflow-hidden rounded-xl bg-gradient-to-br">
      <div className="top-space-5 left-space-4 gap-space-3 absolute flex flex-col">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-[#0668E1] shadow-[var(--shadow-sm)]">
          <IconA size={18} />
        </div>
        <div className="text-success flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-[var(--shadow-sm)]">
          <IconB size={18} />
        </div>
      </div>
      <div className="ml-space-7 border-line bg-card p-space-4 rounded-lg border shadow-[var(--shadow-md)]">
        <div className="mb-space-3 flex gap-1">
          <span className="bg-line h-2 w-2 rounded-full" />
          <span className="bg-line h-2 w-2 rounded-full" />
          <span className="bg-line h-2 w-2 rounded-full" />
        </div>
        <p className="mb-space-3 text-ink-900 text-[14.5px] leading-snug font-bold">{headline}</p>
        <div className="mb-space-3 space-y-1.5">
          <div className="bg-line h-2 w-4/5 rounded-full" />
          <div className="bg-line h-2 w-3/5 rounded-full" />
        </div>
        <span className="bg-brand-600 px-space-3 inline-block rounded-md py-1.5 text-[12px] font-semibold text-white">
          {buttonLabel}
        </span>
      </div>
      <div className="right-space-4 bottom-space-3 bg-brand-600 absolute flex h-9 w-9 items-center justify-center rounded-full text-white shadow-[var(--shadow-md)]">
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
      <span className="mb-space-5 gap-space-1 bg-brand-50 px-space-3 text-brand-700 inline-flex items-center rounded-full py-1 text-[12px] font-semibold">
        <Clock size={13} /> {duration}
      </span>

      <div className="gap-space-6 grid grid-cols-1 lg:grid-cols-2">
        <div>
          <div>
            {instructions.map((item, i) => (
              <div key={i} className="gap-space-3 pb-space-4 relative flex last:pb-0">
                {i < instructions.length - 1 && (
                  <span className="bg-line absolute top-7 bottom-0 left-[13px] w-px" aria-hidden />
                )}
                <span className="border-brand-200 bg-card text-brand-700 z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-[11px] font-bold">
                  {i + 1}
                </span>
                <div className="gap-space-3 border-line bg-paper p-space-3 flex flex-1 items-start rounded-lg border">
                  <div className="bg-brand-50 text-brand-600 flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px]">
                    <item.icon size={16} strokeWidth={2} />
                  </div>
                  <div>
                    <p className="text-ink-900 text-[13.5px] font-bold">{item.title}</p>
                    <p className="text-ink-600 text-[12.5px] leading-relaxed">{item.description}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-space-4 border-line bg-paper p-space-3 rounded-lg border">
            <CheckboxRow checked={done} onChange={onDoneChange}>
              I&apos;ve done this
            </CheckboxRow>
          </div>
        </div>

        <div>
          {illustrationImageSrc ? (
            <div className="border-line overflow-hidden rounded-xl border shadow-sm">
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

          <div className="mt-space-4 gap-space-3 border-line bg-card p-space-4 flex flex-col items-start rounded-lg border md:flex-row md:items-center">
            <div className="bg-brand-50 text-brand-600 flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
              <Globe size={18} strokeWidth={2} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-ink-900 text-[13.5px] font-bold">{resourceLink.title}</p>
              <p className="text-ink-600 text-[12.5px]">{resourceLink.description}</p>
              <p className="text-brand-600 text-[12.5px] font-medium">{resourceLink.displayUrl}</p>
            </div>
            <Button
              href={resourceLink.href}
              target="_blank"
              rel="noopener noreferrer"
              size="md"
              className="w-full shrink-0 md:w-auto"
            >
              Open Website <ArrowUpRight size={14} />
            </Button>
          </div>

          {!illustrationImageSrc && (
            <div className="mt-space-3 gap-space-2 bg-brand-50 p-space-3 text-brand-700 flex items-center rounded-lg text-[12.5px] font-medium">
              <Lock size={14} strokeWidth={2} className="shrink-0" />
              Your data is secure and never shared with third parties.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
