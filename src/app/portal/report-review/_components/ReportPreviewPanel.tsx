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
    <div className="gap-space-3 py-space-2 flex items-center justify-between text-[13px]">
      <span className="text-ink-400">{label}</span>
      <span className="text-ink-900 truncate text-right font-semibold">{value}</span>
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
        <p className="py-space-4 text-ink-400 text-center text-[13px]">No report selected.</p>
      </Card>
    );
  }

  return (
    <Card className="p-space-4">
      <div className="mb-space-3 gap-space-2 flex items-start justify-between">
        <h3 className="text-label text-ink-900 font-bold">Report Preview</h3>
        <StatusBadge status={report.status} />
      </div>

      <div className="mb-space-3 gap-space-3 border-line pb-space-3 flex items-start border-b">
        <span className="bg-brand-50 text-brand-600 flex h-11 w-11 shrink-0 items-center justify-center rounded-md">
          <FileText size={20} />
        </span>
        <div className="min-w-0">
          <p className="text-ink-900 truncate text-[14px] font-bold">{report.reportType}</p>
          <p className="text-ink-400 truncate text-[12px]">Report ID: {report.reportId}</p>
          <p className="text-ink-400 truncate text-[12px]">Uploaded on {report.uploadDate}</p>
        </div>
      </div>

      <div className="mb-space-3 gap-space-4 border-line flex border-b">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "pb-space-2 -mb-px border-b-2 text-[12.5px] font-semibold",
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "text-ink-400 hover:text-ink-700 border-transparent",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "details" && (
        <div className="divide-line divide-y">
          <Row label="Patient Name" value={report.patientName} />
          <Row label="Age / Gender" value={`${report.age} yrs, ${report.gender}`} />
          <Row label="Report Type" value={report.reportType} />
          <Row label="Uploaded By" value={`${report.uploadedBy} (${report.uploadedByRole})`} />
          <Row
            label="Reviewing Doctor"
            value={`${report.reviewingDoctor} (${report.reviewingDoctorSpecialty})`}
          />
          <Row label="Priority" value={<PriorityBadge priority={report.priority} />} />
          <Row label="Status" value={<StatusBadge status={report.status} />} />
          <Row label="Remarks" value={report.remarks || "—"} />
        </div>
      )}

      {tab === "patient" && (
        <div className="divide-line divide-y">
          <Row label="Patient Name" value={report.patientName} />
          <Row label="Age / Gender" value={`${report.age} yrs, ${report.gender}`} />
          <Row label="Reviewing Doctor" value={report.reviewingDoctor} />
          <p className="pt-space-3 text-ink-400 text-[12px]">
            Full patient profile isn&apos;t linked in this mock view.
          </p>
        </div>
      )}

      {tab === "file" && (
        <div className="gap-space-2 py-space-6 flex flex-col items-center text-center">
          <FileText size={28} className="text-ink-300" />
          <p className="text-ink-400 text-[13px]">No file preview available — this is mock data.</p>
        </div>
      )}

      <div className="mt-space-4 gap-space-2 flex flex-wrap items-center">
        <Button size="md" variant="secondary" onClick={() => setTab("file")}>
          View Report
        </Button>
        <Button size="md" onClick={() => onApprove(report)} disabled={report.status === "Approved"}>
          Approve
        </Button>
        <Button
          size="md"
          variant="secondary"
          onClick={() => onReturn(report)}
          disabled={report.status === "Rejected"}
        >
          Return
        </Button>
      </div>
    </Card>
  );
}
