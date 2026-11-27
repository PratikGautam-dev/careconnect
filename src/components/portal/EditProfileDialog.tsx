"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentName: string;
};

/** Profile page's only self-service edit today -- name. Role/department/
 * phone/etc. stay admin-managed via the Staff page's own edit dialog;
 * PUT /api/portal/staff/me is scoped to name alone (see staff_auth.py). */
export function EditProfileDialog({ open, onOpenChange, currentName }: Props) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(currentName);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleOpenChange(next: boolean) {
    // Closing (X/Escape/backdrop/Cancel) discards any typed-but-unsaved
    // name; a successful save already left `name` equal to the saved
    // value, so there's nothing to resync there.
    if (!next) {
      setName(currentName);
      setError(null);
    }
    onOpenChange(next);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Name cannot be empty.");
      return;
    }
    setSubmitting(true);
    setError(null);
    const result = await staffFetch("/api/portal/staff/me", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: trimmed }),
    });
    setSubmitting(false);
    if (!result.ok) {
      setError(result.unauthorized ? "Session expired -- please log in again." : result.error);
      return;
    }
    await queryClient.invalidateQueries({ queryKey: ["portal-staff-profile"] });
    toast.success("Profile updated");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogTitle>Edit Profile</DialogTitle>
        <form onSubmit={handleSubmit} className="gap-space-3 mt-space-3 grid grid-cols-1">
          <Field label="Name" htmlFor="profile_name" required>
            <Input id="profile_name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          {error && <p className="text-error text-[12.5px] font-medium">{error}</p>}
          <div className="gap-space-2 flex justify-end">
            <Button type="button" variant="secondary" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
