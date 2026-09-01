import Image from "next/image";
import { CircleCheck, ListChecks, Tag } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ClinicSetupButton } from "@/components/marketing/ClinicSetupButton";
import { PhoneMockup } from "@/components/marketing/PhoneMockup";

const FEATURES = [
  { title: "No app for patients", desc: "Works directly on WhatsApp", Icon: CircleCheck },
  { title: "Simple & guided", desc: "Menu-driven booking that just works", Icon: ListChecks },
  { title: "Transparent pricing", desc: "Meta messaging charges may apply", Icon: Tag },
];

function BrandMark({ size = "md" }: { size?: "sm" | "md" }) {
  const mark = size === "sm" ? "h-8 w-8 text-lg" : "h-11 w-11 text-2xl";
  const name = size === "sm" ? "text-[19px]" : "text-[34px]";
  return (
    <div className="flex items-end gap-space-3">
      <div className={`flex ${mark} shrink-0 items-center justify-center rounded-md bg-brand-600 font-display font-extrabold text-white`}>
        H
      </div>
      <div>
        {size === "md" && <span className="block text-eyebrow">DAAP</span>}
        <span className={`font-display ${name} leading-tight font-extrabold text-ink-900`}>
          Care<span className="text-brand-600">Connect</span>
        </span>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <>
    {/* Top nav: brand mark left, hospital login as a real button top-right
        -- previously just a small text link buried under the hero CTAs. */}
    <header className="mx-auto flex max-w-[1440px] items-center justify-between px-space-4 py-space-4 md:px-space-7 lg:px-space-9">
      <a href="/" aria-label="CareConnect home">
        <BrandMark size="sm" />
      </a>
      <div className="flex items-center gap-space-2">
        <Button href="/portal/login" variant="secondary" size="md">
          Hospital login
        </Button>
        <Button href="/portal/login" variant="secondary" size="md">
          Clinic login
        </Button>
        <Button href="/doctor/login" variant="secondary" size="md">
          Doctor login
        </Button>
      </div>
    </header>

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

      <div className="mx-auto max-w-[1440px] px-space-4 pt-space-2 pb-space-8 sm:pt-space-4 md:px-space-7 lg:px-space-9 lg:pt-space-5 lg:pb-space-9">
        <div className="grid grid-cols-1 items-center gap-space-7 lg:grid-cols-[1.15fr_0.85fr] lg:gap-space-9">
          <div>
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

            {/* CTAs -- Hospital login moved to the header button above,
                no longer duplicated here as a text link. */}
            <div className="flex flex-wrap gap-space-3">
              <Button href="/auth" variant="primary" size="lg">
                Set up your hospital
              </Button>
              <ClinicSetupButton />
              <Button
                href="mailto:info@daaprimeprojects.com?subject=Product%20Demo%20Request"
                variant="secondary"
                size="lg"
              >
                Request a product demo
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-center">
            <PhoneMockup />
          </div>
        </div>
      </div>
    </main>

    <footer className="border-t border-line bg-paper">
      <div className="mx-auto max-w-[1440px] px-space-4 py-space-7 md:px-space-7 lg:px-space-9">
        <div className="flex flex-col gap-space-6 sm:flex-row sm:justify-between">
          <div className="max-w-[320px]">
            <BrandMark size="sm" />
            <p className="mt-space-3 text-[13px] text-ink-600">
              WhatsApp appointment booking &amp; reminders for hospitals — no app for patients, managed from one
              dashboard.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-space-6 sm:flex sm:gap-space-9">
            <div>
              <p className="text-eyebrow mb-space-2">Product</p>
              <ul className="space-y-space-2 text-[13.5px] text-ink-600">
                <li>
                  <a href="/auth" className="hover:text-brand-600 hover:underline">
                    Set up your hospital
                  </a>
                </li>
                <li>
                  <a href="/portal/login" className="hover:text-brand-600 hover:underline">
                    Hospital login
                  </a>
                </li>
                <li>
                  <a href="/doctor/login" className="hover:text-brand-600 hover:underline">
                    Doctor login
                  </a>
                </li>
                <li>
                  <a
                    href="mailto:info@daaprimeprojects.com?subject=Product%20Demo%20Request"
                    className="hover:text-brand-600 hover:underline"
                  >
                    Request a demo
                  </a>
                </li>
              </ul>
            </div>

            <div>
              <p className="text-eyebrow mb-space-2">Contact</p>
              <ul className="space-y-space-2 text-[13.5px] text-ink-600">
                <li>
                  <a href="mailto:info@daaprimeprojects.com" className="hover:text-brand-600 hover:underline">
                    info@daaprimeprojects.com
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-space-6 border-t border-line pt-space-4 text-[12.5px] text-ink-400">
          © {new Date().getFullYear()} DAAP CareConnect. All rights reserved.
        </div>
      </div>
    </footer>
    </>
  );
}
