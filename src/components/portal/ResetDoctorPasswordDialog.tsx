"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { portalFetch } from "@/lib/portalAuth";
import { toast } from "@/lib/toast";
import { setStaffPasswordSchema } from "@/lib/validation/setStaffPassword";
import type { Doctor } from "@/hooks/useDoctors";

type Props = {
  doctor: Doctor | null;
  onOpenChange: (open: boolean) => void;
};

/** Doctors page's admin-side "Reset login access" quick action -- a
 * doctor's login IS a staff_details row under the unified-login system, so
 * this mirrors the Staff page's own "Reset password" dialog exactly (same
 * validation schema, same POST .../password shape), just addressed by
 * doctor_id (backend/portal/routes/doctors.py resolves login_staff_id and
 * gates on manage_doctors instead of the staff RBAC permission). Only
 * shown once a doctor already has a login -- "Create login" covers the
 * case where they don't yet. */
export function ResetDoctorPasswordDialog({ doctor, onOpenChange }: Props) {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [resetting, setResetting] = useState(false);

  function handleOpenChange(open: boolean) {
    if (!open) {
      setNewPassword("");
      setConfirmPassword("");
      setErrors([]);
    }
    onOpenChange(open);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!doctor) return;

    const parsed = setStaffPasswordSchema.safeParse({
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    if (!parsed.success) {
      setErrors(parsed.error.issues.map((issue) => issue.message));
      return;
    }

    setResetting(true);
    setErrors([]);
    const result = await portalFetch(`/api/portal/doctors/${doctor.id}/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: parsed.data.new_password }),
    });
    setResetting(false);

    if (!result.ok) {
      if (!result.unauthorized) {
        setErrors([result.error]);
        toast.error("Couldn't reset password", result.error);
      }
      return;
    }
    toast.success(`Password reset for Dr. ${doctor.name}`);
    handleOpenChange(false);
  }

  return (
    <Dialog open={doctor !== null} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogTitle>
          {doctor ? `Reset password for Dr. ${doctor.name}` : "Reset password"}
        </DialogTitle>
        <form onSubmit={handleSubmit} className="gap-space-3 flex flex-col">
          <Field
            label="New password"
            htmlFor="doctor_reset_new_password"
            required
            hint="At least 8 characters."
          >
            <PasswordInput
              id="doctor_reset_new_password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </Field>
          <Field label="Confirm new password" htmlFor="doctor_reset_confirm_password" required>
            <PasswordInput
              id="doctor_reset_confirm_password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </Field>
          {errors.length > 0 && (
            <ul className="pl-space-4 text-error list-disc text-[12.5px] font-medium">
              {errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          )}
          <div className="gap-space-2 flex">
            <Button type="submit" disabled={resetting} size="md">
              {resetting ? "Resetting…" : "Reset password"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => handleOpenChange(false)}
              disabled={resetting}
            >
              Cancel
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
