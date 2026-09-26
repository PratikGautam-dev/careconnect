"use client";

import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { AuditLogTable } from "@/components/audit/AuditLogTable";
import {
  EMPTY_AUDIT_LOG_FILTERS,
  useAuditLogPage,
  type AuditLogPageResponse,
} from "@/hooks/useAuditLogPage";
import { useTenants } from "@/hooks/useTenants";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

const RETENTION_OPTIONS = [30, 60, 90, 180, 365, 730];
const DEFAULT_PAGE_SIZE = 25;

type Props = {
  auditLogRetentionDays: string;
  setAuditLogRetentionDays: (value: string) => void;
};

/** Audit Logs tab -- was its own standalone /admin/audit-log sidebar page;
 * folded in here (sidebar entry removed) so retention policy and the log
 * itself live in one place. */
export function AuditLogsTab({ auditLogRetentionDays, setAuditLogRetentionDays }: Props) {
  const [filters, setFilters] = useState(EMPTY_AUDIT_LOG_FILTERS);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const { tenants } = useTenants();

  const auditPage = useAuditLogPage(
    async (params) => {
      const result = await adminFetch(`/api/admin/audit-log?${params.toString()}`);
      return unwrapAdminResult<AuditLogPageResponse>(result);
    },
    filters,
    pageSize,
  );

  return (
    <div className="gap-space-5 flex flex-col">
      <Card className="p-space-5">
        <h2 className="mb-space-1 text-ink-900 text-[15px] font-bold">Audit Log Controls</h2>
        <p className="mb-space-3 text-ink-400 text-[12.5px]">
          How long audit log entries are kept before being permanently deleted. A daily job purges
          anything older than this window (POST /internal/purge-audit-logs).
        </p>
        <Field label="Retention period" htmlFor="audit_log_retention_days">
          <select
            id="audit_log_retention_days"
            value={auditLogRetentionDays}
            onChange={(e) => setAuditLogRetentionDays(e.target.value)}
            className="border-line bg-card px-space-3 text-ink-900 h-10 w-full max-w-60 rounded-md border text-[13px]"
          >
            {RETENTION_OPTIONS.map((days) => (
              <option key={days} value={days}>
                {days} days
              </option>
            ))}
          </select>
        </Field>
      </Card>

      <Card className="p-space-4">
        <h2 className="mb-space-3 text-ink-900 text-[15px] font-bold">Activity Log</h2>
        <AuditLogTable
          page={auditPage}
          filters={filters}
          onFiltersChange={setFilters}
          pageSize={pageSize}
          onPageSizeChange={setPageSize}
          showHospitalColumn
          hospitalOptions={tenants?.map((t) => ({ id: t.id, name: t.name })) ?? null}
          showActorLevelFilter
        />
      </Card>
    </div>
  );
}
