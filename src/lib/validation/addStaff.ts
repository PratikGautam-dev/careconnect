import { z } from "zod";

// "Add staff member" dialog (AddStaffDialog.tsx/useAddStaff.ts) -- mirrors
// portal/routes/staff.py's CreateStaffPayload required checks (name, email,
// password >= 8 chars) so a bad value is caught before the round-trip,
// same "client mirrors the backend's own rule" reasoning setStaffPassword.ts
// already uses for password length. Role isn't included here -- it's a
// numeric select (roleId), not free text, and AddStaffDialog already
// disables submit / shows "Choose a role." separately when it's unset.
export const addStaffSchema = z.object({
  name: z.string().trim().min(1, "Name is required."),
  email: z.string().trim().min(1, "Email is required.").email("Enter a valid email address."),
  password: z.string().min(8, "Password must be at least 8 characters."),
});

export type AddStaffFormValues = z.infer<typeof addStaffSchema>;
