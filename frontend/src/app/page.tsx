import Image from "next/image";
import { CircleCheck, ListChecks, Tag } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { PhoneMockup } from "@/components/marketing/PhoneMockup";

const FEATURES = [
  { title: "No app for patients", desc: "Works directly on WhatsApp", Icon: CircleCheck },
  { title: "Simple & guided", desc: "Menu-driven booking that just works", Icon: ListChecks },
  { title: "Transparent pricing", desc: "Meta messaging charges may apply", Icon: Tag },
];

export default function LandingPage() {
  return (
    <main className="relative isolate overflow-hidden">
      <Image
        src="/homepage-bg.png"
        alt=""
        fill
        priority
        aria-hidden
        className="-z-10 object-cover object-right"
      />
      {/* Readability wash: on narrow screens the photo runs full-bleed behind
          the text instead of sitting off to the side, so bump contrast back
          up over the copy without hiding the image entirely. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-linear-to-br from-paper via-paper/75 to-paper/10 sm:from-paper/95 sm:via-paper/55 sm:to-transparent"
      />

      <div className="mx-auto max-w-[1440px] px-space-4 pt-space-5 pb-space-8 sm:pt-space-6 md:px-space-7 lg:px-space-9 lg:pt-space-7 lg:pb-space-9">
        <div className="grid grid-cols-1 items-center gap-space-7 lg:grid-cols-[1.15fr_0.85fr] lg:gap-space-9">
          <div>
            {/* Logo */}
            <div className="mb-space-4 flex items-center gap-space-3">
              <div className="flex h-13 w-13 shrink-0 items-center justify-center rounded-md bg-brand-600 font-display text-2xl font-extrabold text-white">
                H
              </div>
              <div>
                <span className="block text-eyebrow">DAAP</span>
                <span className="font-display text-[34px] leading-tight font-extrabold text-ink-900">
                  Care<span className="text-brand-600">Connect</span>
                </span>
              </div>
            </div>

            {/* Tagline */}
            <p className="mb-space-3 text-[14.5px] text-ink-600">
              WhatsApp Appointment Booking &amp; Reminder Platform for Hospitals
            </p>

            {/* Heading */}
            <h1 className="text-display-lg mb-space-5 max-w-[650px]">
              Appointments on <span className="text-brand-600">WhatsApp</span>. Managed from one hospital dashboard.
            </h1>

            {/* Description */}
            <p className="text-body mb-space-6 max-w-[620px]">
              Let patients book, reschedule and cancel appointments through WhatsApp. Use this platform&apos;s own
              booking database, connect your existing hospital system, or activate directly inside your hospital
              ERP.
            </p>

            {/* Feature row */}
            <div className="mb-space-7 flex flex-wrap gap-space-5">
              {FEATURES.map(({ title, desc, Icon }) => (
                <div key={title} className="flex flex-1 basis-40 items-start gap-space-3 py-space-1">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-success-tint text-success">
                    <Icon size={18} strokeWidth={2} />
                  </div>
                  <div>
                    <strong className="block text-[15px] text-ink-900">{title}</strong>
                    <span className="mt-space-1 block text-[13px] text-ink-600">{desc}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* CTAs */}
            <div className="mb-space-3 flex flex-wrap gap-space-3">
              <Button href="/admin/onboard-hospital" variant="primary" size="lg">
                Set up your hospital
              </Button>
              <Button
                href="mailto:hello@example.com?subject=DAAP%20CareConnect%20demo%20request"
                variant="secondary"
                size="lg"
              >
                Request a product demo
              </Button>
            </div>
            <a
              href="/portal/login"
              className="inline-flex items-center gap-space-1 text-[14px] font-semibold text-brand-600 transition-colors hover:text-brand-700 hover:underline"
            >
              Hospital login →
            </a>
          </div>

          <div className="flex items-center justify-center">
            <PhoneMockup />
          </div>
        </div>
      </div>
    </main>
  );
}
