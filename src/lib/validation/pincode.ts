// Lab Service Areas (Settings -> Appointments) -- mirrors
// db/repositories/lab_service_areas.py's own _validate_range() exactly (6
// digits, from <= to) so a bad entry is caught before the round-trip. The
// single-pincode path has no equivalent backend check today (only the
// range path validates format there) -- validating it the same way here
// client-side is still worth doing for the same "catch it early" reason,
// even though a non-browser API caller could still bypass it.
const PINCODE_RE = /^\d{6}$/;

export function validatePincode(pincode: string): string | null {
  if (!PINCODE_RE.test(pincode)) return "Enter a 6-digit PIN code.";
  return null;
}

export function validatePincodeRange(start: string, end: string): string | null {
  if (!PINCODE_RE.test(start)) return '"From" must be a 6-digit PIN code.';
  if (!PINCODE_RE.test(end)) return '"To" must be a 6-digit PIN code.';
  if (start > end) return '"From" must not be after "To".';
  return null;
}
