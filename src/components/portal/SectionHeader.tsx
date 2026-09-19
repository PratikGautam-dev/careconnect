/** First-time-user orientation: each block in a multi-step dialog form is a
 * distinct step with no visual separation otherwise -- confirmed with the
 * user this was hard to follow without it (first built for DoctorScheduleForm,
 * now shared by every other multi-section portal dialog). */
export function SectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-space-3">
      <p className="text-label text-ink-900 font-bold">{title}</p>
      <p className="text-hint">{description}</p>
    </div>
  );
}
