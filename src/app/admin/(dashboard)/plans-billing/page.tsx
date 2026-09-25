"use client";

import { useState } from "react";
import {
  AlertCircle,
  Banknote,
  Building2,
  Check,
  FileDown,
  FilePlus,
  FileText,
  PenLine,
  Plus,
  Receipt,
  RefreshCcw,
  Rows3,
  Search,
  SlidersHorizontal,
  Sprout,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { QuickActionList } from "@/components/portal/QuickActions";
import { StatTile } from "@/components/portal/StatTile";
import { cn } from "@/lib/cn";
import { createBillingColumns, type BillingRecordRow } from "./_components/billing-columns";

// Entirely mock, same reasoning as /admin/subscriptions: no plan/pricing or
// invoice model exists in the backend yet, so every card and row here is a
// placeholder built to match the target design -- swap in a real hook once
// a billing API exists.
type PlanTier = {
  key: string;
  name: string;
  description: string;
  icon: typeof Sprout;
  monthly: number;
  annual: number;
  popular?: boolean;
  features: string[];
};

const PLANS: PlanTier[] = [
  {
    key: "starter",
    name: "Starter",
    description: "For small hospitals getting started",
    icon: Sprout,
    monthly: 299,
    annual: 2990,
    features: [
      "Core Hospital Management",
      "Appointments & Patient Records",
      "Basic Reporting",
      "WhatsApp Support",
      "Up to 2 Hospitals",
      "Up to 50 Staff Users",
    ],
  },
  {
    key: "professional",
    name: "Professional",
    description: "For growing multi-specialty hospitals",
    icon: Building2,
    monthly: 599,
    annual: 2990,
    popular: true,
    features: [
      "All Starter Features",
      "Advanced Analytics & Reports",
      "Role-based Access Control",
      "WhatsApp Integration",
      "API Access (Limited)",
      "Up to 10 Hospitals",
      "Up to 250 Staff Users",
    ],
  },
  {
    key: "enterprise",
    name: "Enterprise",
    description: "For large hospital networks",
    icon: Building2,
    monthly: 1299,
    annual: 12990,
    features: [
      "All Professional Features",
      "Custom Integrations (API)",
      "Multi-tenant Management",
      "Dedicated Account Manager",
      "Priority WhatsApp Support",
      "Unlimited Hospitals",
      "Unlimited Staff Users",
    ],
  },
];

const MOCK_BILLING_RECORDS: BillingRecordRow[] = [
  { id: "1", invoiceNo: "INV-2026-00124", hospital: "ABC Super Speciality Hospital", plan: "Professional", amount: 599, paymentMethod: "Credit Card", issueDate: "01 Oct 2026", dueDate: "31 Oct 2026", status: "Paid" },
  { id: "2", invoiceNo: "INV-2026-00123", hospital: "City Care Hospital", plan: "Starter", amount: 299, paymentMethod: "Bank Transfer", issueDate: "30 Sep 2026", dueDate: "30 Oct 2026", status: "Paid" },
  { id: "3", invoiceNo: "INV-2026-00122", hospital: "LifeLine Medical Centre", plan: "Professional", amount: 599, paymentMethod: "UPI", issueDate: "28 Sep 2026", dueDate: "28 Oct 2026", status: "Failed" },
  { id: "4", invoiceNo: "INV-2026-00121", hospital: "Sunrise Multispecialty Hospital", plan: "Enterprise", amount: 1299, paymentMethod: "Credit Card", issueDate: "25 Sep 2026", dueDate: "25 Oct 2026", status: "Paid" },
  { id: "5", invoiceNo: "INV-2026-00120", hospital: "Metro Care Hospital", plan: "Starter", amount: 299, paymentMethod: "Net Banking", issueDate: "20 Sep 2026", dueDate: "20 Oct 2026", status: "Pending" },
];

function PanelHeader({ title, subtitle, mock }: { title: string; subtitle?: string; mock?: boolean }) {
  return (
    <div className="mb-space-3 gap-space-3 flex items-start justify-between">
      <div>
        <h3 className="text-label text-ink-900 font-bold">{title}</h3>
        {subtitle && <p className="text-hint mt-space-0.5">{subtitle}</p>}
      </div>
      {mock && <Badge tone="clay">Mock</Badge>}
    </div>
  );
}

export default function PlansBillingPage() {
  const [search, setSearch] = useState("");

  const filteredRecords = MOCK_BILLING_RECORDS.filter(
    (r) =>
      !search ||
      r.hospital.toLowerCase().includes(search.toLowerCase()) ||
      r.invoiceNo.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div>
      <div className="mb-space-5 gap-space-3 flex flex-wrap items-start justify-between">
        <div>
          <h1 className="text-display">Plans &amp; Billing</h1>
          <p className="text-ink-600 text-[13px]">
            Manage pricing plans, billing operations and monitor revenue across all hospitals.
          </p>
        </div>
        <Badge tone="clay">Mock — no billing model yet</Badge>
      </div>

      <div className="mb-space-4 gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Total Revenue" value={48250} prefix="$" deltaPct={12} hint="This month" icon={Banknote} mock />
        <StatTile label="Invoices Issued" value={126} deltaPct={8} hint="This month" icon={FileText} mock />
        <StatTile label="Failed Payments" value={8} deltaPct={-33} upIsGood={false} hint="This month" icon={AlertCircle} tint="error" mock />
        <StatTile label="Collections" value={44320} prefix="$" deltaPct={15} hint="Received this month" icon={Receipt} mock />
      </div>

      <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card className="p-space-4">
            <div className="mb-space-4 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">CareConnect Plans</h3>
                <p className="text-hint mt-space-0.5">
                  Flexible plans for hospitals of all sizes. Manage pricing, features and availability.
                </p>
              </div>
              <button
                type="button"
                className="text-brand-600 gap-space-1 flex shrink-0 items-center text-[12.5px] font-semibold hover:underline"
              >
                <Rows3 size={13} /> View Plan Comparison
              </button>
            </div>

            <div className="gap-space-4 grid grid-cols-1 md:grid-cols-3">
              {PLANS.map((plan) => {
                const Icon = plan.icon;
                return (
                  <div
                    key={plan.key}
                    className={cn(
                      "border-line rounded-lg border p-space-4 relative flex flex-col",
                      plan.popular && "border-brand-300 shadow-[var(--shadow-md)]",
                    )}
                  >
                    {plan.popular && (
                      <span className="bg-brand-600 px-space-3 absolute top-0 right-space-3 -translate-y-1/2 rounded-full py-1 text-[10.5px] font-bold tracking-wide text-white uppercase">
                        Most Popular
                      </span>
                    )}
                    <span className="bg-brand-50 text-brand-600 mb-space-3 flex h-10 w-10 items-center justify-center rounded-full">
                      <Icon size={20} />
                    </span>
                    <h4 className="text-ink-900 text-[15px] font-bold">{plan.name}</h4>
                    <p className="text-hint mb-space-3">{plan.description}</p>
                    <div className="mb-space-1">
                      <span className="text-ink-900 text-[26px] font-bold">${plan.monthly}</span>
                      <span className="text-ink-400 text-[12.5px]"> / month</span>
                    </div>
                    <div className="mb-space-4 gap-space-2 flex items-center">
                      <span className="text-ink-400 text-[12px]">or ${plan.annual.toLocaleString()} / year</span>
                      <Badge tone="success">Save 17%</Badge>
                    </div>
                    <ul className="space-y-space-2 mb-space-4 flex-1 text-[12.5px]">
                      {plan.features.map((f) => (
                        <li key={f} className="gap-space-2 flex items-start">
                          <Check size={14} className="text-success mt-0.5 shrink-0" />
                          <span className="text-ink-700">{f}</span>
                        </li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      className={cn(
                        "gap-space-2 py-space-2 flex items-center justify-center rounded-md text-[12.5px] font-semibold transition-colors duration-150",
                        plan.popular
                          ? "bg-brand-600 hover:bg-brand-700 text-white"
                          : "border-line text-ink-700 hover:bg-paper border",
                      )}
                    >
                      <PenLine size={13} /> Edit Plan
                    </button>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="p-space-4 mt-space-4">
            <div className="mb-space-4 gap-space-3 flex flex-wrap items-start justify-between">
              <div>
                <h3 className="text-label text-ink-900 font-bold">Recent Billing Records</h3>
                <p className="text-hint mt-space-0.5">View and manage invoices across all hospitals.</p>
              </div>
              <div className="gap-space-2 flex items-center">
                <div className="relative">
                  <Search size={14} className="text-ink-400 absolute top-1/2 left-3 -translate-y-1/2" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search invoices, hospitals…"
                    className="border-line bg-card pl-9 pr-space-3 text-ink-900 h-9 w-56 rounded-md border text-[12.5px]"
                  />
                </div>
                <button
                  type="button"
                  className="border-line text-ink-700 gap-space-2 px-space-3 hover:bg-paper flex h-9 items-center rounded-md border text-[12.5px] font-semibold"
                >
                  <SlidersHorizontal size={13} /> Filters
                </button>
              </div>
            </div>
            <DataTable<BillingRecordRow>
              columns={createBillingColumns()}
              data={filteredRecords}
              getRowId={(row) => row.id}
              pageSize={10}
            />
          </Card>
        </div>

        <div className="space-y-space-4">
          <Card className="p-space-4">
            <PanelHeader title="Quick Actions" subtitle="Common billing and plan management actions." mock />
            <QuickActionList
              size="sm"
              columns={1}
              actions={[
                { label: "Create Plan", icon: Plus, onClick: () => {} },
                { label: "Edit Pricing", icon: PenLine, onClick: () => {} },
                { label: "Generate Invoice", icon: FilePlus, onClick: () => {} },
                { label: "Refund Payment", icon: RefreshCcw, onClick: () => {} },
                { label: "Export Billing Report", icon: FileDown, onClick: () => {} },
              ]}
            />
          </Card>

          <Card className="p-space-4">
            <div className="mb-space-3 gap-space-3 flex items-start justify-between">
              <h3 className="text-label text-ink-900 font-bold">Billing Summary</h3>
              <select
                defaultValue="month"
                className="border-line bg-card px-space-2 text-ink-700 h-8 rounded-md border text-[11.5px] font-semibold"
              >
                <option value="month">This Month</option>
                <option value="quarter">This Quarter</option>
                <option value="year">This Year</option>
              </select>
            </div>
            <div className="space-y-space-2 text-[12.5px]">
              {[
                ["Total Invoiced", "$48,250", "text-ink-900"],
                ["Payments Received", "$44,320", "text-success"],
                ["Pending Payments", "$3,930", "text-ink-900"],
                ["Failed Payments", "$1,200", "text-error"],
              ].map(([label, value, tone]) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-ink-400">{label}</span>
                  <span className={cn("font-semibold", tone)}>{value}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
