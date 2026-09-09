import { z } from "zod";

// Mirrors the backend's own length check (portal/routes/staff_auth.py's
// staff_change_password) -- just catches the obvious case client-side, the
// backend still re-validates before ever touching the database.
export const changePasswordSchema = z
  .object({
    current_password: z.string().trim().min(1, "Enter your current password."),
    new_password: z.string().min(8, "New password must be at least 8 characters."),
    confirm_password: z.string().min(1, "Confirm your new password."),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    message: "New password and confirmation don't match.",
    path: ["confirm_password"],
  });

export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>;
