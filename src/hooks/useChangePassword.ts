import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveStaffTokens, staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";
import { changePasswordSchema } from "@/lib/validation/changePassword";

type ChangePasswordResponse = { access_token: string; refresh_token: string };

/** Profile settings page's self-service password change -- POST
 * /api/portal/staff/change-password re-issues fresh access/refresh tokens
 * in its response (the password change itself invalidates every OTHER
 * outstanding session via token_version), so a successful change here saves
 * those straight over the current session instead of forcing a re-login. */
export function useChangePassword() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors([]);

    const parsed = changePasswordSchema.safeParse({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
    if (!parsed.success) {
      setErrors(parsed.error.issues.map((issue) => issue.message));
      return;
    }

    setSubmitting(true);
    const result = await staffFetch("/api/portal/staff/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: parsed.data.current_password,
        new_password: parsed.data.new_password,
      }),
    });
    setSubmitting(false);

    if (!result.ok) {
      if (result.unauthorized) {
        router.push("/portal/login");
      } else {
        setErrors([result.error]);
        toast.error("Couldn't change password", result.error);
      }
      return;
    }

    const data = result.data as ChangePasswordResponse;
    saveStaffTokens(data.access_token, data.refresh_token);

    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    toast.success("Password changed");
  }

  return {
    currentPassword, setCurrentPassword,
    newPassword, setNewPassword,
    confirmPassword, setConfirmPassword,
    errors, submitting,
    handleSubmit,
  };
}
