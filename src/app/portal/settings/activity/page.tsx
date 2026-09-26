"use client";

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { AuditLogTable } from "@/components/audit/AuditLogTable";
import {
  EMPTY_AUDIT_LOG_FILTERS,
  useAuditLogPage,
  type AuditLogPageResponse,
} from "@/hooks/useAuditLogPage";
import { portalFetch } from "@/lib/portalAuth";

const DEFAULT_PAGE_SIZE = 25;

async function fetchPortalAuditPage(params: URLSearchParams): Promise<AuditLogPageResponse> {
  const result = await portalFetch(`/api/portal/audit-log?${params.toString()}`);
  if (!result.ok) throw new Error(result.unauthorized ? "Not authenticated." : result.error);
  return result.data as AuditLogPageResponse;
}

export default function PortalActivityLogPage() {
  const { hospital, ready } = usePortalGuard();
  const [filters, setFilters] = useState(EMPTY_AUDIT_LOG_FILTERS);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const auditPage = useAuditLogPage(fetchPortalAuditPage, filters, pageSize, ready);

  return (
    <PortalShell hospital={hospital} active="settings">
      <PageHeader
        title="Activity log"
        description="Recent changes made by your staff through this portal — doctor/department edits, feature toggles,
          settings updates. Platform-level changes (made by the operator on your behalf) aren't shown here."
        actions={
          <Button href="/portal/settings" variant="secondary">
            <ArrowLeft size={14} /> Back to settings
          </Button>
        }
      />

      {!ready ? null : auditPage.error ? (
        <p className="text-ink-400 text-[13px]">{auditPage.error}</p>
      ) : (
        <Card className="p-space-4">
          <AuditLogTable
            page={auditPage}
            filters={filters}
            onFiltersChange={setFilters}
            pageSize={pageSize}
            onPageSizeChange={setPageSize}
          />
        </Card>
      )}
    </PortalShell>
  );
}
