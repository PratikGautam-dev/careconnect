import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — DAAP CareConnect",
  description: "How DAAP CareConnect collects, uses, and protects data on the WhatsApp appointment platform.",
};

const LAST_UPDATED = "3 September 2026";

function BrandMark() {
  return (
    <a href="/" aria-label="CareConnect home" className="flex items-end gap-space-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-600 font-display text-lg font-extrabold text-white">
        H
      </div>
      <span className="font-display text-[19px] leading-tight font-extrabold text-ink-900">
        Care<span className="text-brand-600">Connect</span>
      </span>
    </a>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-space-7">
      <h2 className="mb-space-3 font-display text-[19px] font-bold text-ink-900">{title}</h2>
      <div className="space-y-space-3 text-body">{children}</div>
    </section>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <>
      <header className="flex items-center justify-between gap-space-3 px-space-4 py-space-4 md:px-space-7 lg:px-space-9">
        <BrandMark />
        <a href="/" className="text-[13.5px] font-semibold text-brand-600 hover:underline">
          Back to home
        </a>
      </header>

      <main className="mx-auto max-w-[720px] px-space-4 pb-space-9 md:px-space-7 lg:px-space-9">
        <p className="text-eyebrow mb-space-2">Legal</p>
        <h1 className="text-display-lg mb-space-2">Privacy Policy</h1>
        <p className="mb-space-8 text-hint">Last updated: {LAST_UPDATED}</p>

        <Section title="Who we are">
          <p>
            DAAP CareConnect (&ldquo;CareConnect,&rdquo; &ldquo;we,&rdquo; &ldquo;us&rdquo;) is a WhatsApp-based
            appointment booking and reminder platform built and operated by DaaPrime Tech, provided to hospitals
            and clinics (&ldquo;Hospitals&rdquo;) so their patients can book, reschedule, and manage appointments
            directly on WhatsApp, and so hospital staff can manage those appointments from a web dashboard.
          </p>
          <p>
            This policy explains what information we collect, how we use it, and the choices available to
            patients, hospital staff, and doctors who use CareConnect. If you have questions, contact us at{" "}
            <a href="mailto:info@daaprimeprojects.com" className="text-brand-600 hover:underline">
              info@daaprimeprojects.com
            </a>
            .
          </p>
        </Section>

        <Section title="Information we collect">
          <p>
            <strong className="text-ink-900">From patients, via WhatsApp:</strong> your phone number, name, age,
            and the appointment details you provide (department, doctor, date, time, and any reason or notes you
            share). We only collect what a message-driven appointment flow needs to actually book and remind you
            of your visit.
          </p>
          <p>
            <strong className="text-ink-900">From hospital staff:</strong> the name, email address, and (hashed,
            never stored in plain text) password used to sign in to the hospital dashboard, plus a record of the
            actions taken through that dashboard for audit purposes.
          </p>
          <p>
            <strong className="text-ink-900">From doctors who connect Google Calendar:</strong> if a doctor
            chooses to connect their Google account for the optional Google Meet tele-consultation feature, we
            receive an OAuth access token and refresh token from Google, and the email address of the connected
            Google account. These tokens are encrypted before they are stored. See &ldquo;Google Calendar
            integration&rdquo; below for exactly what we do — and don&apos;t do — with this access.
          </p>
          <p>
            <strong className="text-ink-900">Documents:</strong> if a hospital chooses to upload patient reports
            or prescriptions through the dashboard, those files are stored on the hospital&apos;s behalf.
          </p>
        </Section>

        <Section title="How we use this information">
          <ul className="list-disc space-y-space-2 pl-space-5">
            <li>To book, reschedule, cancel, and send reminders for appointments.</li>
            <li>To let hospital staff view and manage their hospital&apos;s own appointments and patients.</li>
            <li>To create a Google Calendar event with a Google Meet link for a tele-consultation appointment, when a doctor has connected their Google account.</li>
            <li>To maintain an audit trail of actions taken in the hospital dashboard, for security and accountability.</li>
            <li>To operate, secure, and improve the platform itself.</li>
          </ul>
          <p>
            We do not sell patient or hospital data, and we do not use it for advertising.
          </p>
        </Section>

        <Section title="Google Calendar integration">
          <p>
            CareConnect&apos;s use and transfer of information received from Google APIs to any other app will
            adhere to the{" "}
            <a
              href="https://developers.google.com/terms/api-services-user-data-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-600 hover:underline"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements.
          </p>
          <p>Specifically, when a doctor connects their Google account:</p>
          <ul className="list-disc space-y-space-2 pl-space-5">
            <li>We request access only to create calendar events (the <code className="rounded bg-black/[0.05] px-1 py-0.5 text-[13px]">calendar.events</code> scope) — we cannot read your Gmail, Drive, or any other Google data.</li>
            <li>We create exactly one calendar event per tele-consultation booking, containing the appointment time and a Google Meet link. We do not read, list, or otherwise access any of your other existing calendar events.</li>
            <li>The connection can be revoked at any time from the doctor&apos;s own schedule page inside CareConnect, or directly from your Google Account&apos;s{" "}
              <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener noreferrer" className="text-brand-600 hover:underline">
                third-party access settings
              </a>.
            </li>
            <li>Disconnecting deletes the stored access/refresh tokens; it does not delete any calendar event already created.</li>
          </ul>
        </Section>

        <Section title="Who we share information with">
          <p>We use the following third-party services to operate CareConnect, each only for the specific purpose below:</p>
          <ul className="list-disc space-y-space-2 pl-space-5">
            <li><strong className="text-ink-900">Meta (WhatsApp Business Platform)</strong> — to send and receive the WhatsApp messages that power the booking flow.</li>
            <li><strong className="text-ink-900">Google (Calendar API)</strong> — only for doctors who opt in, as described above.</li>
            <li><strong className="text-ink-900">Our hosting and database providers</strong> — to run the application and store data securely.</li>
          </ul>
          <p>We do not share patient or appointment data with any other third party, and never for marketing purposes.</p>
        </Section>

        <Section title="Data retention and deletion">
          <p>
            We retain appointment and patient records for as long as needed to provide the service to your
            hospital and to meet applicable healthcare record-keeping requirements. A patient may request deletion
            of their data at any time by messaging <strong className="text-ink-900">&ldquo;DELETE&rdquo;</strong> to
            the hospital&apos;s WhatsApp number, or by contacting the hospital directly.
          </p>
        </Section>

        <Section title="Security">
          <p>
            Passwords are hashed, never stored in plain text. Google Calendar access/refresh tokens are encrypted
            at rest. All traffic to and from CareConnect is encrypted in transit (HTTPS). Access to a hospital&apos;s
            data within the dashboard is scoped to that hospital&apos;s own staff and doctors.
          </p>
        </Section>

        <Section title="Your rights">
          <p>
            Depending on your location, you may have rights to access, correct, or delete your personal
            information, including under India&apos;s Digital Personal Data Protection Act, 2023. To exercise
            these rights, contact the hospital you booked with, or reach us directly at{" "}
            <a href="mailto:info@daaprimeprojects.com" className="text-brand-600 hover:underline">
              info@daaprimeprojects.com
            </a>
            .
          </p>
        </Section>

        <Section title="Changes to this policy">
          <p>
            We may update this policy from time to time. We will update the &ldquo;Last updated&rdquo; date above
            when we do. Continued use of CareConnect after a change means you accept the updated policy.
          </p>
        </Section>

        <Section title="Contact us">
          <p>
            Questions about this policy or your data? Email{" "}
            <a href="mailto:info@daaprimeprojects.com" className="text-brand-600 hover:underline">
              info@daaprimeprojects.com
            </a>
            .
          </p>
        </Section>
      </main>
    </>
  );
}
