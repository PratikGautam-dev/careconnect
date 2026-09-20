// "Reminder offsets (comma-separated hours)" -- three separate places in
// this app (Settings -> Notifications, admin tenant-edit, onboarding
// Step7HospitalDetails) each own a copy of this exact field, none of which
// validated it client-side. The backend's own parser
// (admin/validation.py's _parse_offsets) is deliberately lenient -- it
// silently DROPS any comma-separated entry it can't parse as a number and
// falls back to [24] if nothing parses at all, rather than ever rejecting
// the request. That's the right behavior for a request the backend must
// still accept, but it means a typo (e.g. "24, 1hr, 6") silently loses data
// with no feedback -- this validator catches that BEFORE submit instead,
// so the admin sees the typo rather than a silently different reminder
// schedule than the one they typed.
export function validateReminderOffsetsHours(text: string): string | null {
  const trimmed = (text || "").trim();
  // Blank is valid -- the backend defaults an empty/all-invalid value to
  // [24] (one reminder, 24 hours before), same as this field's own hint text.
  if (!trimmed) return null;
  for (const rawPart of trimmed.split(",")) {
    const part = rawPart.trim();
    if (!part) return "Remove the extra comma -- each entry must be a number.";
    const hours = Number(part);
    if (!Number.isFinite(hours) || hours <= 0) {
      return `"${part}" isn't a valid number of hours -- use positive numbers only, e.g. 24,1.`;
    }
  }
  return null;
}
