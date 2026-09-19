"use client";

import { useState } from "react";
import { FileText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { PriorityBadge, StatusBadge } from "./report-columns";
import type { MockReport } from "./mock-reports";

type Tab = "details" | "patient" | "file";

const TABS: { key: Tab; label: string }[] = [
  { key: "details", label: "Report Details" },
  { key: "patient", label: "Patient Info" },
  { key: "file", label: "Report File" },
];

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-space-3 py-space-2 text-[13px]">
      <span className="text-ink-400">{label}</span>
      <span className="truncate text-right font-semibold text-ink-900">{value}</span>
    </div>
  );
}

type Props = {
  report: MockReport | null;
  onApprove: (report: MockReport) => void;
  onReturn: (report: MockReport) => void;
};

/** Right-rail "Report Preview" panel for /portal/report-review -- mock only,
 * mirrors the reference layout's tabs (Report Details/Patient Info/Report
 * File). Patient Info and Report File are illustrative mock content (no
 * real patients/files backing this page yet) rather than left blank, per
 * the "build the full UI from the mockup" convention -- View Report just
 * switches to the File tab since there's no real file to open. */
export function ReportPreviewPanel({ report, onApprove, onReturn }: Props) {
  const [tab, setTab] = useState<Tab>("details");

  if (!report) {
    return (
      <Card className="p-space-4">
        <p className="py-space-4 text-center text-[13px] text-ink-400">No report selected.</p>
      </Card>
    );
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 flex items-start justify-between gap-space-2">
        <h3 className="text-label font-bold text-ink-900">Report Preview</h3>
        <StatusBadge status={report.status} />
      </div>

      <div className="mb-space-3 flex items-start gap-space-3 border-b border-line pb-space-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-600">
          <FileText size={20} />
        </span>
        <div className="min-w-0">
          <p className="truncate text-[14px] font-bold text-ink-900">{report.reportType}</p>
          <p className="truncate text-[12px] text-ink-400">Report ID: {report.reportId}</p>
          <p className="truncate text-[12px] text-ink-400">Uploaded on {report.uploadDate}</p>
        </div>
      </div>

      <div className="mb-space-3 flex gap-space-4 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "-mb-px border-b-2 pb-space-2 text-[12.5px] font-semibold",
              tab === t.key ? "border-brand-600 text-brand-700" : "border-transparent text-ink-400 hover:text-ink-700",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "details" && (
        <div className="divide-y divide-line">
          <Row label="Patient Name" value={report.patientName} />
          <Row label="Age / Gender" value={`${report.age} yrs, ${report.gender}`} />
          <Row label="Report Type" value={report.reportType} />
          <Row label="Uploaded By" value={`${report.uploadedBy} (${report.uploadedByRole})`} />
          <Row label="Reviewing Doctor" value={`${report.reviewingDoctor} (${report.reviewingDoctorSpecialty})`} />
          <Row label="Priority" value={<PriorityBadge priority={report.priority} />} />
          <Row label="Status" value={<StatusBadge status={report.status} />} />
          <Row label="Remarks" value={report.remarks || "—"} />
        </div>
      )}

      {tab === "patient" && (
        <div className="divide-y divide-line">
          <Row label="Patient Name" value={report.patientName} />
          <Row label="Age / Gender" value={`${report.age} yrs, ${report.gender}`} />
          <Row label="Reviewing Doctor" value={report.reviewingDoctor} />
          <p className="pt-space-3 text-[12px] text-ink-400">
            Full patient profile isn&apos;t linked in this mock view.
          </p>
        </div>
      )}

      {tab === "file" && (
        <div className="flex flex-col items-center gap-space-2 py-space-6 text-center">
          <FileText size={28} className="text-ink-300" />
          <p className="text-[13px] text-ink-400">No file preview available — this is mock data.</p>
        </div>
      )}

      <div className="mt-space-4 flex flex-wrap items-center gap-space-2">
        <Button size="md" variant="secondary" onClick={() => setTab("file")}>
          View Report
        </Button>
        <Button size="md" onClick={() => onApprove(report)} disabled={report.status === "Approved"}>
          Approve
        </Button>
        <Button size="md" variant="secondary" onClick={() => onReturn(report)} disabled={report.status === "Rejected"}>
          Return
        </Button>
      </div>
    </Card>
  );
}
