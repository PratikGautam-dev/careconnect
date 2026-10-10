import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { adminFetch, getAdminToken, setAdminToken, type SuperAdmin } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { toast } from "@/lib/toast";
import { changePasswordSchema } from "@/lib/validation/changePassword";

const PROFILE_QUERY_KEY = ["admin-profile"] as const;

/** The signed-in super admin's own profile (GET /api/admin/super/me) plus
 * the name/email edit (PATCH /api/admin/super/profile). Changing the email
 * needs the current password (the backend enforces it); a name-only change
 * doesn't. The session copy in sessionStorage is refreshed on save so the
 * sidebar shows the new name right away. */
export function useAdminProfile() {
  const { data, error, refetch } = useQuery({
    queryKey: PROFILE_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/super/me");
      return unwrapAdminResult<{ super_admin: SuperAdmin }>(result).super_admin;
    },
  });

  const saveMutation = useMutation({
    mutationFn: async (values: { name: string; email: string; currentPassword: string }) => {
      const result = await adminFetch("/api/admin/super/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: values.name,
          email: values.email,
          current_password: values.currentPassword,
        }),
      });
      return unwrapAdminResult<{ super_admin: SuperAdmin }>(result).super_admin;
    },
  });

  async function saveProfile(values: {
    name: string;
    email: string;
    currentPassword: string;
  }): Promise<string | null> {
    try {
      const updated = await saveMutation.mutateAsync(values);
      const token = getAdminToken();
      if (token) setAdminToken(token, updated);
      toast.success("Profile updated");
      await refetch();
      return null;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      toast.error("Couldn't update profile", message);
      return message;
    }
  }

  return {
    profile: data ?? null,
    error: error ? (error as Error).message : null,
    saveProfile,
    saving: saveMutation.isPending,
  };
}

/** Same shape as the staff portal's useChangePassword, against
 * POST /api/admin/super/change-password. The backend logs out every OTHER
 * session and returns a fresh token for this one, saved straight over the
 * current session so the admin isn't signed out. */
export function useAdminChangePassword() {
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
    const result = await adminFetch("/api/admin/super/change-password", {
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
        window.location.reload();
      } else {
        setErrors([result.error]);
        toast.error("Couldn't change password", result.error);
      }
      return;
    }

    const data = result.data as { access_token: string; super_admin: SuperAdmin };
    setAdminToken(data.access_token, data.super_admin);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    toast.success("Password changed");
  }

  return {
    currentPassword,
    setCurrentPassword,
    newPassword,
    setNewPassword,
    confirmPassword,
    setConfirmPassword,
    errors,
    submitting,
    handleSubmit,
  };
}
