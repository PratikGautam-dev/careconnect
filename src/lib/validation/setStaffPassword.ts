import { z } from "zod";

// Admin-initiated reset (portal/routes/staff.py's POST
// /api/portal/staff/{id}/password) -- no current_password field since the
// caller is resetting someone ELSE's password, unlike changePassword.ts.
export const setStaffPasswordSchema = z
  .object({
    new_password: z.string().min(8, "New password must be at least 8 characters."),
    confirm_password: z.string().min(1, "Confirm the new password."),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: "New password and confirmation don't match.",
    path: ["confirm_password"],
  });

export type SetStaffPasswordFormValues = z.infer<typeof setStaffPasswordSchema>;
