"use client";

import { usePermission } from "@/lib/staffAuth";

type Props = {
  page: string;
  action: "view" | "write" | "delete";
  children: React.ReactNode;
};

/** Hides destructive/edit controls the caller's role/permission lacks.
 * Fails open (renders children) when there's no staff session at all, same
 * posture as usePermission -- the backend's 403 is the real enforcement. */
export function PermissionGate({ page, action, children }: Props) {
  const allowed = usePermission(page, action);
  if (!allowed) return null;
  return <>{children}</>;
}
