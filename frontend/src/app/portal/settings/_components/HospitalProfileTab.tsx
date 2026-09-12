"use client";

import { useState } from "react";
import {
  Bed,
  Building,
  Building2,
  Calendar,
  Check,
  Clock,
  FileText,
  Globe,
  Image as ImageIcon,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Plus,
  ShieldCheck,
  Stethoscope,
  Upload,
  User,
  X,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/cn";
import { toast } from "@/lib/toast";
import {
  ACCREDITATION_BODY_OPTIONS,
  ADDITIONAL_SPECIALTY_OPTIONS,
  EMERGENCY_SERVICE_OPTIONS,
  HOSPITAL_TYPE_OPTIONS,
  LAB_TIMING_OPTIONS,
  OPD_TIMING_OPTIONS,
  PHARMACY_TIMING_OPTIONS,
  initialHospitalProfile,
  type Branch,
  type HospitalProfileState,
} from "./hospital-profile-mock";
import { SectionHeader, Select } from "./settings-ui";

function IconInput({
  icon: Icon, className, ...props
}: { icon: LucideIcon } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="relative">
      <Icon size={14} className="pointer-events-none absolute left-space-3 top-1/2 -translate-y-1/2 text-ink-400" />
      <Input className={cn("pl-space-8", className)} {...props} />
    </div>
  );
}

function ImageDropzone({
  label, hint, dataUrl, onPick, aspectClassName,
}: { label: string; hint: string; dataUrl: string | null; onPick: (dataUrl: string) => void; aspectClassName: string }) {
  const inputId = `hospital-profile-${label.replace(/\s+/g, "-").toLowerCase()}`;

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === "string" && onPick(reader.result);
    reader.readAsDataURL(file);
  }

  return (
    <div className="mb-space-3">
      <label className="text-label mb-space-1 block">{label}</label>
      <div className={cn("mb-space-2 flex items-center justify-center overflow-hidden rounded-md border border-dashed border-line bg-paper text-ink-300", aspectClassName)}>
        {dataUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={dataUrl} alt={label} className="h-full w-full object-cover" />
        ) : (
          <ImageIcon size={22} />
        )}
      </div>
      <div className="flex flex-wrap items-center gap-space-2">
        <label htmlFor={inputId}>
          <Button type="button" variant="secondary" size="md" className="pointer-events-none">
            <Upload size={14} /> Change {label.replace("Hospital ", "")}
          </Button>
        </label>
        <input id={inputId} type="file" accept="image/*" onChange={handleChange} className="hidden" />
        <p className="text-hint">{hint}</p>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: Branch["status"] }) {
  return (
    <span className="inline-flex items-center gap-space-1 text-[12.5px] font-medium text-ink-700">
      <span className={cn("h-1.5 w-1.5 rounded-full", status === "Active" ? "bg-success" : "bg-ink-300")} />
      {status}
    </span>
  );
}

/** Hospital Profile tab of /portal/settings -- frontend-only mock, same
 * convention as GeneralSettingsTab (mirrors its reference screenshot
 * exactly; Save/Reset just reset local state). Hospital Name itself is
 * NOT part of this mock state -- it's read straight from the real,
 * already-loaded `hospitalName` prop (same read-only field the legacy
 * settings page and General tab's Hospital Information card use), so this
 * tab doesn't grow a third, independently-editable copy of it. */
export function HospitalProfileTab({ hospitalName }: { hospitalName: string }) {
  const [profile, setProfile] = useState<HospitalProfileState>(initialHospitalProfile());
  const [newSpecialty, setNewSpecialty] = useState("");

  function patch<K extends keyof HospitalProfileState>(section: K, value: Partial<HospitalProfileState[K] & object>) {
    setProfile((prev) => ({ ...prev, [section]: { ...(prev[section] as object), ...value } }));
  }

  function removeSpecialty(name: string) {
    setProfile((prev) => ({ ...prev, specialties: prev.specialties.filter((s) => s !== name) }));
  }

  function addSpecialty(name: string) {
    if (!name || profile.specialties.includes(name)) return;
    setProfile((prev) => ({ ...prev, specialties: [...prev.specialties, name] }));
  }

  function addBranch() {
    setProfile((prev) => ({
      ...prev,
      branches: [
        ...prev.branches,
        { id: Date.now(), name: "New Branch", location: "Location", type: "Branch", status: "Active" },
      ],
    }));
  }

  function handleReset() {
    setProfile(initialHospitalProfile());
    setNewSpecialty("");
    toast.success("Reset to default", "Hospital profile reverted to its defaults.");
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    toast.success("Saved", "Hospital profile updated (mock -- not yet persisted to the backend).");
  }

  const { overview, registration, accreditation, contact, emergency, operatingHours, bedCapacity, specialties, branches } = profile;
  const availableSpecialties = ADDITIONAL_SPECIALTY_OPTIONS.filter((s) => !specialties.includes(s));

  return (
    <form onSubmit={handleSave} className="flex flex-col gap-space-4">
      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-3">
        <Card className="p-space-4">
          <SectionHeader icon={Building2} tint="brand" title="Hospital Overview" subtitle="Basic information and identity details about your hospital" />
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Hospital Name" required hint="Contact the platform team to change this.">
              <Input value={hospitalName} disabled />
            </Field>
            <Field label="Short Name" required>
              <Input value={overview.shortName} onChange={(e) => patch("overview", { shortName: e.target.value })} />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Hospital Type">
              <Select value={overview.hospitalType} onChange={(v) => patch("overview", { hospitalType: v })} options={HOSPITAL_TYPE_OPTIONS} />
            </Field>
            <Field label="Established Year">
              <IconInput icon={Calendar} value={overview.establishedYear} onChange={(e) => patch("overview", { establishedYear: e.target.value })} />
            </Field>
          </div>
          <Field label="About Hospital" required className="mb-0">
            <Textarea
              rows={4}
              maxLength={500}
              value={overview.about}
              onChange={(e) => patch("overview", { about: e.target.value })}
            />
            <p className="mt-space-1 text-right text-hint">{overview.about.length}/500</p>
          </Field>
        </Card>

        <Card className="p-space-4">
          <SectionHeader icon={ImageIcon} tint="clay" title="Hospital Logo & Cover" subtitle="Manage your hospital logo and cover image" />
          <ImageDropzone
            label="Hospital Logo"
            hint="Recommended size: 300 x 100 px. PNG, JPG or SVG (Max 2 MB)."
            dataUrl={profile.logoDataUrl}
            onPick={(dataUrl) => setProfile((prev) => ({ ...prev, logoDataUrl: dataUrl }))}
            aspectClassName="h-16"
          />
          <ImageDropzone
            label="Hospital Cover Image"
            hint="Recommended size: 1920 x 600 px (Max 5 MB)."
            dataUrl={profile.coverDataUrl}
            onPick={(dataUrl) => setProfile((prev) => ({ ...prev, coverDataUrl: dataUrl }))}
            aspectClassName="h-24"
          />
        </Card>

        <div className="flex flex-col gap-space-4">
          <Card className="p-space-4">
            <SectionHeader icon={FileText} tint="success" title="Registration & License Details" subtitle="Official registration and licensing information" />
            <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
              <Field label="Registration Number" required>
                <Input value={registration.registrationNumber} onChange={(e) => patch("registration", { registrationNumber: e.target.value })} />
              </Field>
              <Field label="License Number" required>
                <Input value={registration.licenseNumber} onChange={(e) => patch("registration", { licenseNumber: e.target.value })} />
              </Field>
            </div>
            <Field label="Issuing Authority">
              <Input value={registration.issuingAuthority} onChange={(e) => patch("registration", { issuingAuthority: e.target.value })} />
            </Field>
            <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
              <Field label="License Valid Till">
                <IconInput icon={Calendar} value={registration.licenseValidTill} onChange={(e) => patch("registration", { licenseValidTill: e.target.value })} />
              </Field>
              <Field label="Registration Date" className="mb-0">
                <IconInput icon={Calendar} value={registration.registrationDate} onChange={(e) => patch("registration", { registrationDate: e.target.value })} />
              </Field>
            </div>
          </Card>

          <Card className="p-space-4">
            <SectionHeader icon={ShieldCheck} tint="brand" title="Accreditation & Certifications" subtitle="Hospital accreditations and quality certifications" />
            <Field label="Accreditation Body">
              <Select value={accreditation.accreditationBody} onChange={(v) => patch("accreditation", { accreditationBody: v })} options={ACCREDITATION_BODY_OPTIONS} />
            </Field>
            <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
              <Field label="Accreditation Number" className="mb-0">
                <Input value={accreditation.accreditationNumber} onChange={(e) => patch("accreditation", { accreditationNumber: e.target.value })} />
              </Field>
              <Field label="Valid Till" className="mb-0">
                <IconInput icon={Calendar} value={accreditation.validTill} onChange={(e) => patch("accreditation", { validTill: e.target.value })} />
              </Field>
            </div>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-4">
        <Card className="p-space-4">
          <SectionHeader icon={Phone} tint="brand" title="Contact Information" subtitle="Primary contact details for your hospital" />
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Phone Number" required>
              <IconInput icon={Phone} value={contact.phone} onChange={(e) => patch("contact", { phone: e.target.value })} />
            </Field>
            <Field label="Alternate Phone">
              <IconInput icon={Phone} value={contact.alternatePhone} onChange={(e) => patch("contact", { alternatePhone: e.target.value })} />
            </Field>
          </div>
          <div className="grid grid-cols-1 gap-x-space-3 sm:grid-cols-2">
            <Field label="Email Address" required>
              <IconInput icon={Mail} type="email" value={contact.email} onChange={(e) => patch("contact", { email: e.target.value })} />
            </Field>
            <Field label="Website">
              <IconInput icon={Globe} value={contact.website} onChange={(e) => patch("contact", { website: e.target.value })} />
            </Field>
          </div>
          <Field label="Address" required className="mb-0">
            <div className="relative">
              <MapPin size={14} className="pointer-events-none absolute left-space-3 top-space-3 text-ink-400" />
              <Textarea rows={2} className="pl-space-8" value={contact.address} onChange={(e) => patch("contact", { address: e.target.value })} />
            </div>
          </Field>
        </Card>

        <Card className="p-space-4">
          <SectionHeader icon={Phone} tint="error" title="Emergency Contact" subtitle="24/7 emergency contact information" />
          <Field label="Emergency Contact Number" required>
            <IconInput icon={Phone} value={emergency.number} onChange={(e) => patch("emergency", { number: e.target.value })} />
          </Field>
          <Field label="Contact Person" required>
            <IconInput icon={User} value={emergency.contactPerson} onChange={(e) => patch("emergency", { contactPerson: e.target.value })} />
          </Field>
          <Field label="Designation" className="mb-0">
            <Input value={emergency.designation} onChange={(e) => patch("emergency", { designation: e.target.value })} />
          </Field>
        </Card>

        <Card className="p-space-4">
          <SectionHeader icon={Clock} tint="clay" title="Operating Hours" subtitle="Hospital working hours" />
          <Field label="OPD Timings">
            <Select value={operatingHours.opdTimings} onChange={(v) => patch("operatingHours", { opdTimings: v })} options={OPD_TIMING_OPTIONS} />
          </Field>
          <Field label="Emergency Services">
            <Select value={operatingHours.emergencyServices} onChange={(v) => patch("operatingHours", { emergencyServices: v })} options={EMERGENCY_SERVICE_OPTIONS} />
          </Field>
          <Field label="Pharmacy Timings">
            <Select value={operatingHours.pharmacyTimings} onChange={(v) => patch("operatingHours", { pharmacyTimings: v })} options={PHARMACY_TIMING_OPTIONS} />
          </Field>
          <Field label="Lab Services Timings" className="mb-0">
            <Select value={operatingHours.labServicesTimings} onChange={(v) => patch("operatingHours", { labServicesTimings: v })} options={LAB_TIMING_OPTIONS} />
          </Field>
        </Card>

        <Card className="p-space-4">
          <SectionHeader icon={Bed} tint="success" title="Bed Capacity" subtitle="Total bed capacity and occupancy details" />
          <div className="grid grid-cols-2 gap-x-space-3">
            <Field label="Total Beds">
              <IconInput icon={Bed} type="number" min={0} value={bedCapacity.totalBeds} onChange={(e) => patch("bedCapacity", { totalBeds: Number(e.target.value) })} />
            </Field>
            <Field label="ICU Beds">
              <IconInput icon={Bed} type="number" min={0} value={bedCapacity.icuBeds} onChange={(e) => patch("bedCapacity", { icuBeds: Number(e.target.value) })} />
            </Field>
            <Field label="General Beds">
              <IconInput icon={Bed} type="number" min={0} value={bedCapacity.generalBeds} onChange={(e) => patch("bedCapacity", { generalBeds: Number(e.target.value) })} />
            </Field>
            <Field label="Semi-Private Beds">
              <IconInput icon={Bed} type="number" min={0} value={bedCapacity.semiPrivateBeds} onChange={(e) => patch("bedCapacity", { semiPrivateBeds: Number(e.target.value) })} />
            </Field>
          </div>
          <Field label="Private Rooms" className="mb-0">
            <IconInput icon={Bed} type="number" min={0} value={bedCapacity.privateRooms} onChange={(e) => patch("bedCapacity", { privateRooms: Number(e.target.value) })} />
          </Field>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-2">
        <Card className="p-space-4">
          <SectionHeader icon={Stethoscope} tint="brand" title="Specialties & Services" subtitle="Select main specialties and services offered at your hospital" />
          <p className="text-label mb-space-2">Primary Specialties</p>
          <div className="flex flex-wrap items-center gap-space-2">
            {specialties.map((s) => (
              <span key={s} className="inline-flex items-center gap-space-1 rounded-full bg-brand-50 px-space-3 py-space-1 text-[12.5px] font-medium text-brand-700">
                {s}
                <button type="button" onClick={() => removeSpecialty(s)} aria-label={`Remove ${s}`} className="text-brand-400 hover:text-brand-700">
                  <X size={12} />
                </button>
              </span>
            ))}
            {availableSpecialties.length > 0 && (
              <div className="relative">
                <select
                  value={newSpecialty}
                  onChange={(e) => {
                    addSpecialty(e.target.value);
                    setNewSpecialty("");
                  }}
                  className="h-8 rounded-full border border-dashed border-line bg-card pl-space-3 pr-space-6 text-[12.5px] text-ink-400"
                >
                  <option value="">+ Add specialty</option>
                  {availableSpecialties.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </Card>

        <Card className="p-space-4">
          <div className="mb-space-4 flex items-start justify-between gap-space-2">
            <SectionHeader icon={Building} tint="clay" title="Branch / Campus Information" subtitle="Manage multiple branches or campuses" />
            <Button type="button" size="md" onClick={addBranch} className="shrink-0">
              <Plus size={14} /> Add Branch
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Branch Name</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {branches.map((b, i) => (
                <TableRow key={b.id}>
                  <TableCell>{i + 1}</TableCell>
                  <TableCell className="font-semibold text-ink-900">{b.name}</TableCell>
                  <TableCell className="text-ink-600">{b.location}</TableCell>
                  <TableCell className="text-ink-600">{b.type}</TableCell>
                  <TableCell><StatusDot status={b.status} /></TableCell>
                  <TableCell>
                    {b.type === "Main Campus" ? (
                      <span title="Primary campus" className="inline-flex text-success"><Check size={15} /></span>
                    ) : (
                      <button
                        type="button"
                        title="Edit branch"
                        onClick={() => toast.success("Mock only", "Editing branches isn't wired to a backend yet.")}
                        className="text-ink-400 hover:text-ink-700"
                      >
                        <Pencil size={14} />
                      </button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>

      <div className="flex items-center justify-end gap-space-2">
        <Button type="button" variant="secondary" onClick={handleReset}>Reset to Default</Button>
        <Button type="submit">Save Changes</Button>
      </div>
    </form>
  );
}
