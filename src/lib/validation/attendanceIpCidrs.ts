// "Allowed Hospital IP / CIDR ranges" (Settings -> Attendance) -- the
// backend already does real parsing here (portal/routes/settings.py's
// _parse_ip_cidrs, via Python's ipaddress module) and returns a clear 400
// naming the exact bad entry, so this is a nice-to-have pre-check for
// instant feedback rather than a data-loss risk like reminderOffsets.ts.
// Deliberately loose for IPv6 (backend is authoritative there) -- this
// only needs to catch the common case: an obviously malformed IPv4
// address/CIDR entry, not fully replicate ipaddress.ip_network().
const IPV4_OCTET = "(25[0-5]|2[0-4]\\d|1\\d\\d|[1-9]?\\d|0)";
const IPV4_RE = new RegExp(`^${IPV4_OCTET}(\\.${IPV4_OCTET}){3}$`);
const IPV4_CIDR_RE = new RegExp(`^${IPV4_OCTET}(\\.${IPV4_OCTET}){3}/(3[0-2]|[12]?\\d)$`);
const IPV6_LOOSE_RE = /^[0-9a-fA-F:]+(\/\d{1,3})?$/;

export function validateAttendanceIpCidrs(text: string): string | null {
  const trimmed = (text || "").trim();
  if (!trimmed) return null;
  for (const rawEntry of trimmed.split(",")) {
    const entry = rawEntry.trim();
    if (!entry) return "Remove the extra comma -- each entry must be an IP address or CIDR range.";
    if (IPV4_RE.test(entry) || IPV4_CIDR_RE.test(entry) || IPV6_LOOSE_RE.test(entry)) continue;
    return `"${entry}" isn't a valid IP address or CIDR range.`;
  }
  return null;
}
