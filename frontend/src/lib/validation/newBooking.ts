import { z } from "zod";

// Mirrors the backend's own db.is_valid_phone() (db/repositories/patients.py)
// exactly -- deliberately permissive, just "non-empty after trim and
// contains at least one digit", not a real phone-number format spec.
const phoneSchema = z
  .string()
  .trim()
  .min(1, "Patient phone is required.")
  .refine((v) => /\d/.test(v), "Patient phone must contain at least one digit.");

export const newBookingSchema = z.object({
  patient_name: z.string().trim().optional(),
  patient_phone: phoneSchema,
  department_id: z.string().trim().min(1, "Choose a department."),
  doctor_id: z.string().trim().min(1, "Choose a doctor."),
  slot_id: z.string().trim().min(1, "Choose an available slot."),
});

export type NewBookingFormValues = z.infer<typeof newBookingSchema>;
