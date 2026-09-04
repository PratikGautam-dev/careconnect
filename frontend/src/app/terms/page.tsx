import type { Metadata } from "next";
import Image from "next/image";
import { Mail } from "lucide-react";
import { Card } from "@/components/ui/Card";

export const metadata: Metadata = {
  title: "Terms of Service — DAAP CareConnect",
  description: "The terms governing use of the DAAP CareConnect WhatsApp appointment platform.",
};

const LAST_UPDATED = "3 September 2026";
const CONTACT_EMAIL = "info@daaprimeprojects.com";

const SECTIONS = [
  { id: "agreement", title: "1. Agreement to these terms" },
  { id: "what-is-careconnect", title: "2. What CareConnect is" },
  { id: "hospital-accounts", title: "3. Hospital accounts" },
  { id: "patients-whatsapp", title: "4. Patients using WhatsApp" },
  { id: "google-calendar", title: "5. Google Calendar integration" },
  { id: "fees", title: "6. Fees" },
  { id: "acceptable-use", title: "7. Acceptable use" },
  { id: "ip", title: "8. Intellectual property" },
  { id: "disclaimers", title: "9. Disclaimers & liability" },
  { id: "termination", title: "10. Termination" },
  { id: "governing-law", title: "11. Governing law" },
  { id: "changes", title: "12. Changes to these terms" },
] as const;

function BrandMark() {
  return (
    <a href="/" aria-label="CareConnect home" className="flex items-center gap-space-3">
      <Image src="/logo-icon.png" alt="" width={32} height={32} className="shrink-0" />
      <span className="font-display text-[19px] leading-tight font-extrabold text-ink-900">
        Care<span className="text-brand-600">Connect</span>
      </span>
    </a>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 border-b border-line py-space-7 first:pt-0 last:border-0">
      <h2 className="mb-space-3 font-display text-[20px] font-bold text-ink-900">{title}</h2>
      <div className="space-y-space-3 text-body">{children}</div>
    </section>
  );
}

export default function TermsOfServicePage() {
  return (
    <>
      <header className="sticky top-0 z-10 flex items-center justify-between gap-space-3 border-b border-line bg-paper/90 px-space-4 py-space-4 backdrop-blur-sm md:px-space-7 lg:px-space-9">
        <BrandMark />
        <a href="/" className="text-[13.5px] font-semibold text-brand-600 hover:underline">
          Back to home
        </a>
      </header>

      <main className="mx-auto max-w-[1080px] px-space-4 py-space-8 md:px-space-7 lg:px-space-9">
        <div className="mb-space-8 max-w-[640px]">
          <p className="text-eyebrow mb-space-2">Legal</p>
          <h1 className="text-display-lg mb-space-2">Terms of Service</h1>
          <p className="text-hint">Last updated: {LAST_UPDATED}</p>
        </div>

        <div className="grid grid-cols-1 gap-space-7 lg:grid-cols-[220px_1fr] lg:gap-space-9">
          <nav aria-label="Sections" className="hidden lg:block">
            <div className="sticky top-28 space-y-space-1">
              <p className="text-eyebrow mb-space-3">On this page</p>
              {SECTIONS.map((s) => (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className="block rounded-md px-space-3 py-space-2 text-[13px] text-ink-600 transition-colors duration-150 hover:bg-black/[0.04] hover:text-brand-600"
                >
                  {s.title}
                </a>
              ))}
            </div>
          </nav>

          <Card className="p-space-6 md:p-space-8">
            <Section id="agreement" title="1. Agreement to these terms">
              <p>
                These Terms of Service (&ldquo;Terms&rdquo;) govern access to and use of DAAP CareConnect
                (&ldquo;CareConnect,&rdquo; &ldquo;the Platform&rdquo;), operated by DaaPrime Tech
                (&ldquo;we,&rdquo; &ldquo;us&rdquo;). By using CareConnect — as a hospital, a member of hospital
                staff, a doctor, or a patient booking through WhatsApp — you agree to these Terms. If you do not
                agree, please do not use the Platform.
              </p>
            </Section>

            <Section id="what-is-careconnect" title="2. What CareConnect is">
              <p>
                CareConnect is a WhatsApp-based appointment booking and reminder platform for hospitals and
                clinics (&ldquo;Hospitals&rdquo;). Patients interact with their Hospital&apos;s own WhatsApp number
                to book, reschedule, and cancel appointments. Hospital staff manage those appointments, patients,
                and doctors through a web dashboard. Doctors may optionally connect a Google account to create
                Google Meet links for tele-consultation appointments.
              </p>
              <p>
                CareConnect is a scheduling and communication tool. It does not provide medical advice, diagnosis,
                or treatment, and is not a substitute for professional medical judgment or emergency services. In
                a medical emergency, contact your local emergency services directly.
              </p>
            </Section>

            <Section id="hospital-accounts" title="3. Hospital accounts">
              <p>
                A Hospital is responsible for the accuracy of the department, doctor, and scheduling information
                it configures on the Platform, for obtaining any consent required from its own patients before
                communicating with them via WhatsApp, and for the conduct of the staff accounts it creates. A
                Hospital must keep its staff login credentials confidential and is responsible for activity under
                its accounts.
              </p>
            </Section>

            <Section id="patients-whatsapp" title="4. Patients using WhatsApp">
              <p>
                Using CareConnect via WhatsApp is free for patients, though your mobile carrier&apos;s standard
                messaging/data rates may apply, and WhatsApp messaging costs charged by Meta may apply to the
                Hospital. Use of WhatsApp itself is also subject to{" "}
                <a href="https://www.whatsapp.com/legal/terms-of-service" target="_blank" rel="noopener noreferrer" className="text-brand-600 hover:underline">
                  WhatsApp&apos;s own Terms of Service
                </a>
                . A patient may withdraw consent to data processing, or request deletion of their data, at any
                time by messaging &ldquo;DELETE&rdquo; to the Hospital&apos;s WhatsApp number.
              </p>
            </Section>

            <Section id="google-calendar" title="5. Google Calendar integration">
              <p>
                Connecting a Google account for the Google Meet tele-consultation feature is entirely optional and
                can be disconnected at any time from a doctor&apos;s own schedule page. CareConnect only requests
                access to create calendar events, and only ever creates one event per tele-consultation booking —
                see our{" "}
                <a href="/privacy#google-calendar" className="text-brand-600 hover:underline">
                  Privacy Policy
                </a>{" "}
                for the full detail of what this access is, and is not, used for.
              </p>
            </Section>

            <Section id="fees" title="6. Fees">
              <p>
                Fees for a Hospital&apos;s use of CareConnect are as agreed separately between the Hospital and
                DaaPrime Tech. WhatsApp messaging costs charged by Meta to the Hospital are separate from, and in
                addition to, any CareConnect platform fee.
              </p>
            </Section>

            <Section id="acceptable-use" title="7. Acceptable use">
              <p>You agree not to use CareConnect to:</p>
              <ul className="list-disc space-y-space-2 pl-space-5">
                <li>Send unsolicited or unlawful messages to patients;</li>
                <li>Attempt to access another Hospital&apos;s data, or another staff member&apos;s or doctor&apos;s account;</li>
                <li>Interfere with or disrupt the Platform&apos;s operation; or</li>
                <li>Use the Platform in a way that violates applicable law, including healthcare data protection law.</li>
              </ul>
            </Section>

            <Section id="ip" title="8. Intellectual property">
              <p>
                CareConnect, its software, and its branding are the property of DaaPrime Tech. These Terms do not
                grant any Hospital, staff member, doctor, or patient ownership of the Platform itself — only the
                right to use it as described here.
              </p>
            </Section>

            <Section id="disclaimers" title="9. Disclaimers & liability">
              <p>
                CareConnect is provided &ldquo;as is.&rdquo; We work to keep the Platform available and accurate,
                but do not guarantee it will be uninterrupted or error-free (including the underlying WhatsApp
                Business Platform and Google Calendar API, which we do not control). To the fullest extent
                permitted by law, DaaPrime Tech is not liable for indirect, incidental, or consequential damages
                arising from use of the Platform, including a missed or double-booked appointment, beyond amounts
                actually paid for the Platform in the preceding three months.
              </p>
            </Section>

            <Section id="termination" title="10. Termination">
              <p>
                We may suspend or terminate access to the Platform for a Hospital, staff account, or doctor
                account that violates these Terms. A Hospital may stop using the Platform at any time by
                discontinuing its subscription.
              </p>
            </Section>

            <Section id="governing-law" title="11. Governing law">
              <p>These Terms are governed by the laws of India.</p>
            </Section>

            <Section id="changes" title="12. Changes to these terms">
              <p>
                We may update these Terms from time to time. We will update the &ldquo;Last updated&rdquo; date
                above when we do. Continued use of CareConnect after a change means you accept the updated Terms.
              </p>
            </Section>
          </Card>
        </div>

        <Card className="mt-space-7 flex flex-col items-start gap-space-4 p-space-6 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-label mb-space-1">Questions about these Terms?</p>
            <p className="text-[13.5px] text-ink-600">We&apos;re happy to help — reach out any time.</p>
          </div>
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="inline-flex shrink-0 items-center gap-space-2 rounded-md bg-brand-600 px-space-4 py-space-3 text-[13.5px] font-semibold text-white transition-colors duration-150 hover:bg-brand-700"
          >
            <Mail size={16} />
            {CONTACT_EMAIL}
          </a>
        </Card>
      </main>
    </>
  );
}
