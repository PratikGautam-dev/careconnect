"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { CAPABILITY_META } from "@/lib/hospitalCapabilities";
import { cn } from "@/lib/cn";
import type { Plan, PlanWritePayload } from "@/hooks/useAdminPlans";

type FormState = {
  name: string;
  description: string;
  price_monthly: string;
  annual_discount_pct: string;
  max_users: string; // "" = unlimited
  max_bookings: string; // "" = unlimited, per subscription period
  capabilities: string[];
  is_active: boolean;
  is_popular: boolean;
  sort_order: string;
};

function formFromPlan(plan: Plan | null, nextSortOrder: number): FormState {
  return {
    name: plan?.name ?? "",
    description: plan?.description ?? "",
    price_monthly: plan ? String(plan.price_monthly) : "",
    annual_discount_pct: plan ? String(plan.annual_discount_pct) : "17",
    max_users: plan?.max_users != null ? String(plan.max_users) : "",
    max_bookings: plan?.max_bookings != null ? String(plan.max_bookings) : "",
    capabilities: plan?.capabilities ?? [],
    is_active: plan?.is_active ?? true,
    is_popular: plan?.is_popular ?? false,
    sort_order: String(plan?.sort_order ?? nextSortOrder),
  };
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: Plan | null; // null = create mode
  nextSortOrder: number;
  allCapabilities: string[];
  onSubmit: (payload: PlanWritePayload) => Promise<boolean>;
  saving: boolean;
};

/** Create/edit form for a single plan -- feature checkboxes are the real
 * admin_capabilities set (src/lib/hospitalCapabilities.ts, same catalog
 * Access Control uses), not free-text bullets: whatever's checked here is
 * exactly what a hospital on this plan would have in its own Access
 * Control page once plan assignment ships. */
export function PlanFormDialog({
  open,
  onOpenChange,
  plan,
  nextSortOrder,
  allCapabilities,
  onSubmit,
  saving,
}: Props) {
  // The parent only renders this component while `open` is true (see
  // plans-billing/page.tsx: `{formOpen && <PlanFormDialog .../>}`), so a
  // fresh mount already happens every time the dialog opens -- no effect
  // needed to re-sync `form`/`errors` on `open`/`plan` changes, the
  // useState initializer runs exactly once per open, which is what's wanted.
  const [form, setForm] = useState<FormState>(() => formFromPlan(plan, nextSortOrder));
  const [errors, setErrors] = useState<string[]>([]);

  function toggleCapability(key: string, checked: boolean) {
    setForm((f) => ({
      ...f,
      capabilities: checked ? [...f.capabilities, key] : f.capabilities.filter((k) => k !== key),
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const nextErrors: string[] = [];
    const price = Number(form.price_monthly);
    const discount = Number(form.annual_discount_pct);
    const maxUsers = form.max_users.trim() === "" ? null : Number(form.max_users);
    const maxBookings = form.max_bookings.trim() === "" ? null : Number(form.max_bookings);
    const sortOrder = Number(form.sort_order) || 0;

    if (!form.name.trim()) nextErrors.push("Name is required.");
    if (!Number.isFinite(price) || price < 0) nextErrors.push("Price must be zero or greater.");
    if (!Number.isFinite(discount) || discount < 0 || discount > 100) {
      nextErrors.push("Discount percentage must be between 0 and 100.");
    }
    if (maxUsers !== null && (!Number.isFinite(maxUsers) || maxUsers < 1)) {
      nextErrors.push("Total users must be at least 1, or left blank for unlimited.");
    }
    if (maxBookings !== null && (!Number.isFinite(maxBookings) || maxBookings < 1)) {
      nextErrors.push("Total bookings must be at least 1, or left blank for unlimited.");
    }
    if (nextErrors.length) {
      setErrors(nextErrors);
      return;
    }

    const ok = await onSubmit({
      name: form.name.trim(),
      description: form.description.trim() || null,
      price_monthly: price,
      annual_discount_pct: discount,
      capabilities: form.capabilities,
      max_users: maxUsers,
      max_bookings: maxBookings,
      is_active: form.is_active,
      is_popular: form.is_popular,
      sort_order: sortOrder,
    });
    if (ok) onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogTitle>{plan ? `Edit ${plan.name}` : "New Plan"}</DialogTitle>
        <form onSubmit={handleSubmit} className="space-y-space-4">
          {errors.length > 0 && <p className="text-error text-[12.5px]">{errors[0]}</p>}

          <div className="gap-space-3 grid grid-cols-2">
            <label className="text-[12.5px]">
              <span className="text-hint mb-space-1 block">Name</span>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
              />
            </label>
            <label className="text-[12.5px]">
              <span className="text-hint mb-space-1 block">Display order</span>
              <input
                type="number"
                value={form.sort_order}
                onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
                className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
              />
            </label>
          </div>

          <label className="block text-[12.5px]">
            <span className="text-hint mb-space-1 block">Description</span>
            <input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Short marketing line shown under the plan name"
              className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
            />
          </label>

          <div className="gap-space-3 grid grid-cols-2">
            <label className="text-[12.5px]">
              <span className="text-hint mb-space-1 block">Price / month (₹)</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={form.price_monthly}
                onChange={(e) => setForm({ ...form, price_monthly: e.target.value })}
                className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
              />
            </label>
            <label className="text-[12.5px]">
              <span className="text-hint mb-space-1 block">Annual discount (%)</span>
              <input
                type="number"
                min={0}
                max={100}
                value={form.annual_discount_pct}
                onChange={(e) => setForm({ ...form, annual_discount_pct: e.target.value })}
                className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
              />
            </label>
            <label className="text-[12.5px]">
              <span className="text-hint mb-space-1 block">Total users</span>
              <input
                type="number"
                min={1}
                placeholder="Unlimited"
                value={form.max_users}
                onChange={(e) => setForm({ ...form, max_users: e.target.value })}
                className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
              />
            </label>
            <label className="text-[12.5px]">
              <span className="text-hint mb-space-1 block">Total bookings</span>
              <input
                type="number"
                min={1}
                placeholder="Unlimited"
                value={form.max_bookings}
                onChange={(e) => setForm({ ...form, max_bookings: e.target.value })}
                className="border-line bg-card px-space-3 text-ink-900 h-9 w-full rounded-md border text-[13px]"
              />
            </label>
          </div>

          <div>
            <span className="text-hint mb-space-2 block">
              Features (sets what hospitals on this plan can access in their staff portal)
            </span>
            <div className="border-line gap-space-1 grid max-h-48 grid-cols-2 overflow-y-auto rounded-md border p-2">
              {allCapabilities.map((key) => {
                const meta = CAPABILITY_META[key];
                const checked = form.capabilities.includes(key);
                return (
                  <label
                    key={key}
                    className="gap-space-2 px-space-2 hover:bg-paper flex items-center rounded py-1 text-[12.5px]"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => toggleCapability(key, e.target.checked)}
                    />
                    <span className="text-ink-700">{meta?.label ?? key}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="gap-space-4 flex items-center">
            <label className="gap-space-2 flex items-center text-[12.5px]">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Active
            </label>
            <label className="gap-space-2 flex items-center text-[12.5px]">
              <input
                type="checkbox"
                checked={form.is_popular}
                onChange={(e) => setForm({ ...form, is_popular: e.target.checked })}
              />
              Mark as &quot;Most Popular&quot;
            </label>
          </div>

          <div className="gap-space-2 flex justify-end">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="border-line text-ink-700 px-space-4 hover:bg-paper h-9 rounded-md border text-[13px] font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className={cn(
                "bg-brand-600 hover:bg-brand-700 px-space-4 h-9 rounded-md text-[13px] font-semibold text-white transition-colors duration-150",
                saving && "opacity-60",
              )}
            >
              {saving ? "Saving…" : plan ? "Save changes" : "Create plan"}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
