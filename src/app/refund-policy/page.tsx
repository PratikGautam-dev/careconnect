import type { Metadata } from "next";
import Link from "next/link";
import { Mail } from "lucide-react";
import { BrandMark } from "@/components/marketing/BrandMark";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Cancellation & Refund Policy — DAAP CareConnect",
  description:
    "How cancellations and refunds work for paid appointments booked through DAAP CareConnect.",
};

const LAST_UPDATED = "28 September 2026";
const CONTACT_EMAIL = "info@daaprimeprojects.com";

const SECTIONS = [
  { id: "overview", title: "1. Overview" },
  { id: "paid-appointments", title: "2. Which appointments involve payment" },
  { id: "patient-cancellation", title: "3. Cancelling an appointment yourself" },
  { id: "hospital-cancellation", title: "4. When your hospital cancels or can't accommodate you" },
  { id: "non-refundable", title: "5. Charges that are never refunded" },
  { id: "refund-processing", title: "6. How refunds are processed" },
  { id: "how-to-cancel", title: "7. How to cancel a booking" },
  { id: "changes", title: "8. Changes to this policy" },
] as const;

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className="border-line py-space-7 scroll-mt-24 border-b first:pt-0 last:border-0"
    >
      <h2 className="mb-space-3 font-display text-ink-900 text-[20px] font-bold">{title}</h2>
      <div className="space-y-space-3 text-body">{children}</div>
    </section>
  );
}

export default function RefundPolicyPage() {
  return (
    <>
      <header className="gap-space-3 border-line bg-paper/90 px-space-4 py-space-4 md:px-space-7 lg:px-space-9 sticky top-0 z-10 flex items-center justify-between border-b backdrop-blur-sm">
        <BrandMark />
        <Link href="/" className="text-brand-600 text-[13.5px] font-semibold hover:underline">
          Back to home
        </Link>
      </header>

      <main className="px-space-4 py-space-8 md:px-space-7 lg:px-space-9 mx-auto max-w-[1080px]">
        <div className="mb-space-8 max-w-[640px]">
          <p className="text-eyebrow mb-space-2">Legal</p>
          <h1 className="text-display-lg mb-space-2">Cancellation &amp; Refund Policy</h1>
          <p className="text-hint">Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="gap-space-7 lg:gap-space-9 grid grid-cols-1 lg:grid-cols-[220px_1fr]">
          <nav aria-label="Sections" className="hidden lg:block">
            <div className="space-y-space-1 sticky top-28">
              <p className="text-eyebrow mb-space-3">On this page</p>
              {SECTIONS.map((s) => (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className="px-space-3 py-space-2 text-ink-600 hover:text-brand-600 block rounded-md text-[13px] transition-colors duration-150 hover:bg-black/[0.04]"
                >
                  {s.title}
                </a>
              ))}
            </div>
          </nav>

          <Card className="p-space-6 md:p-space-8">
            <Section id="overview" title="1. Overview">
              <p>
                This policy explains how cancellations and refunds work for appointments booked
                through DAAP CareConnect (&ldquo;CareConnect,&rdquo; &ldquo;the Platform&rdquo;),
                operated by DaaPrime Tech. It applies only to bookings your hospital has charged for
                online through the Platform. A booking made on a pay-at-hospital basis, or an
                appointment type your hospital doesn&apos;t charge for, has no online payment and so
                nothing to refund here — see your hospital directly for anything related to
                in-person billing.
              </p>
            </Section>

            <Section id="paid-appointments" title="2. Which appointments involve payment">
              <p>
                Whether a given appointment type is paid for online, and how much it costs, is set
                by your hospital, not by CareConnect. Where a hospital has configured an online fee
                — for example a consultation, tele-consultation, second opinion, diagnostic or lab
                test, or a daycare procedure — you&apos;ll always see the amount and be asked to
                confirm before paying. Payment is collected securely through Razorpay.
              </p>
            </Section>

            <Section id="patient-cancellation" title="3. Cancelling an appointment yourself">
              <p>
                If you cancel a paid appointment yourself, part of the fee may be deducted before
                the remainder is refunded. Each hospital sets its own cancellation schedule, but the
                underlying idea is the same everywhere: the more advance notice you give, the
                smaller the deduction — a cancellation made well ahead of your appointment keeps
                more of your payment refundable, while cancelling very close to (or after) your
                scheduled time keeps less. The exact deduction that applies to your booking is
                always shown to you, in full, before you confirm the cancellation — so you&apos;ll
                never be surprised by it after the fact. We deliberately don&apos;t print specific
                hours or percentages here, since your hospital can change its own schedule at any
                time; what you see at the moment you cancel is always the current, accurate figure.
              </p>
            </Section>

            <Section
              id="hospital-cancellation"
              title="4. When your hospital cancels or can't accommodate you"
            >
              <p>
                If your hospital cancels your appointment, or is otherwise unable to accommodate it,
                you&apos;re entitled to a full refund of the base fee you paid — no deduction
                applies, regardless of how close to the appointment time this happens.
              </p>
            </Section>

            <Section id="non-refundable" title="5. Charges that are never refunded">
              <p>
                Any GST/tax and platform fee included in your payment are never refunded, under
                either cancellation path above. Only the base consultation/service fee is ever
                eligible for a refund, subject to section 3 where you initiated the cancellation.
              </p>
            </Section>

            <Section id="refund-processing" title="6. How refunds are processed">
              <p>
                Refunds are issued through Razorpay, back to whichever method you originally paid
                with. Depending on your hospital&apos;s own settings, a refund is either issued
                immediately once your cancellation is confirmed, or first reviewed by hospital staff
                before being released — either way, you&apos;ll be told which applies to your refund
                at the time you cancel. Once released, how long it takes to actually reflect in your
                account depends on your bank or UPI provider, not on CareConnect, so we don&apos;t
                quote a fixed number of days here — treat it as a normal bank-processed refund
                timeline.
              </p>
            </Section>

            <Section id="how-to-cancel" title="7. How to cancel a booking">
              <p>
                Message your hospital&apos;s WhatsApp number and follow the cancel prompts for your
                upcoming appointment, or ask hospital staff to cancel it for you. Either way, you
                (or the staff member acting on your behalf) will see the refund breakdown — amount
                refunded, amount deducted, and any non-refundable charges — before the cancellation
                is confirmed.
              </p>
            </Section>

            <Section id="changes" title="8. Changes to this policy">
              <p>
                We may update this policy from time to time. We will update the &ldquo;Last
                updated&rdquo; date above when we do. This policy describes how the Platform handles
                refunds generally — the specific cancellation schedule and fee amounts for your
                booking always come from your own hospital and are shown to you directly at the time
                of booking and cancellation.
              </p>
            </Section>
          </Card>
        </div>

        <Card className="mt-space-7 gap-space-4 p-space-6 flex flex-col items-start md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-label mb-space-1">Questions about a cancellation or refund?</p>
            <p className="text-ink-600 text-[13.5px]">
              We&apos;re happy to help — reach out any time.
            </p>
          </div>
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="gap-space-2 bg-brand-600 px-space-4 py-space-3 hover:bg-brand-700 inline-flex shrink-0 items-center rounded-md text-[13.5px] font-semibold text-white transition-colors duration-150"
          >
            <Mail size={16} />
            {CONTACT_EMAIL}
          </a>
        </Card>
      </main>
    </>
  );
}
