"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { toast } from "@/lib/toast";

export type BedCapacity = {
  totalBeds: number;
  icuBeds: number;
  generalBeds: number;
  semiPrivateBeds: number;
  privateRooms: number;
};

/** Seed values -- frontend-only mock, same as the rest of /portal/settings'
 * Hospital Profile tab this was moved out of (no `bed_capacity`-shaped
 * table/endpoint exists yet). */
function initialBedCapacity(): BedCapacity {
  return {
    totalBeds: 250,
    icuBeds: 40,
    generalBeds: 180,
    semiPrivateBeds: 20,
    privateRooms: 10,
  };
}

type ManageBedsDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** "Manage Beds" dialog opened from the Daycare Appointments page header --
 * moved here from /portal/settings' Hospital Profile tab (bed capacity is
 * an operational/occupancy concern for the Daycare team, not a hospital-
 * identity field). Frontend-only mock, same convention as the settings tabs
 * it came from -- Save just resets local state, nothing is persisted to a
 * backend yet. */
export function ManageBedsDialog({ open, onOpenChange }: ManageBedsDialogProps) {
  const [beds, setBeds] = useState<BedCapacity>(initialBedCapacity());

  function patch(value: Partial<BedCapacity>) {
    setBeds((prev) => ({ ...prev, ...value }));
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    toast.success("Saved", "Bed capacity updated (mock -- not yet persisted to the backend).");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogTitle>Manage Beds</DialogTitle>
        <p className="mb-space-4 text-[12.5px] text-ink-400">Total bed capacity and occupancy details</p>
        <form onSubmit={handleSave}>
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Total Beds">
              <Input type="number" min={0} value={beds.totalBeds} onChange={(e) => patch({ totalBeds: Number(e.target.value) })} />
            </Field>
            <Field label="ICU Beds">
              <Input type="number" min={0} value={beds.icuBeds} onChange={(e) => patch({ icuBeds: Number(e.target.value) })} />
            </Field>
            <Field label="General Beds">
              <Input type="number" min={0} value={beds.generalBeds} onChange={(e) => patch({ generalBeds: Number(e.target.value) })} />
            </Field>
            <Field label="Semi-Private Beds">
              <Input type="number" min={0} value={beds.semiPrivateBeds} onChange={(e) => patch({ semiPrivateBeds: Number(e.target.value) })} />
            </Field>
          </div>
          <Field label="Private Rooms" className="mb-0">
            <Input type="number" min={0} value={beds.privateRooms} onChange={(e) => patch({ privateRooms: Number(e.target.value) })} />
          </Field>
          <Button type="submit" className="mt-space-4">Save Changes</Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
