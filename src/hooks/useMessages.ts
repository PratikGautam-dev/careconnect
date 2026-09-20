import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import type { Patient } from "@/hooks/usePatients";

export type Handoff = {
  id: number;
  phone: string;
  reason: "patient_requested" | "system_error";
  message_text: string | null;
  status: "open" | "resolved";
  created_at: string;
  resolved_at: string | null;
  // "auto" for the scheduler (/internal/auto-resolve-handoffs), a staff
  // session's hashed token for a manual resolve, or null (never resolved).
  resolved_by: string | null;
};

// A handoff's full conversation, not just its trigger message --
// direction distinguishes a patient's own message (inbound) from a staff
// reply (outbound).
export type HandoffMessage = {
  id: number;
  direction: "inbound" | "outbound";
  message_text: string;
  created_at: string;
};

// "Errored" is a peer tab, not a status -- it shows every
// system_error-triggered conversation regardless of resolved state
// (status="all"), since a bot error worth following up on doesn't stop
// being worth seeing just because it auto-resolved or got marked resolved.
export const FILTERS = [
  { key: "open", label: "Open", status: "open", reason: null },
  { key: "resolved", label: "Resolved", status: "resolved", reason: null },
  { key: "errored", label: "Errored", status: "all", reason: "system_error" },
  { key: "all", label: "All", status: "all", reason: null },
] as const;

// New incoming handoff requests don't push to this tab -- there's no
// websocket/SSE infra in this app -- so poll instead of requiring a
// manual refresh. Polling only ever replaces the `handoffs` list, never
// `replyText` (separate local state), so a poll firing mid-type never
// loses what staff is typing.
const POLL_INTERVAL_MS = 12_000;

/** Loads + owns every mutation on the /portal/messages (handoffs) page:
 * list + status/date filters, multi-select + bulk resolve/delete, thread
 * polling for the selected conversation, reply send, single resolve/delete. */
export function useMessages(ready: boolean) {
  const router = useRouter();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("open");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [replyText, setReplyText] = useState("");
  const [dateFilter, setDateFilter] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkError, setBulkError] = useState<string | null>(null);

  const {
    data: handoffs,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: ["portal-handoffs", filter, dateFilter],
    enabled: ready,
    retry: false,
    refetchInterval: ready ? POLL_INTERVAL_MS : false,
    queryFn: async () => {
      const active = FILTERS.find((f) => f.key === filter) ?? FILTERS[0];
      const qs = new URLSearchParams({ status: active.status });
      if (active.reason) qs.set("reason", active.reason);
      if (dateFilter) qs.set("date", dateFilter);
      const result = await portalFetch(`/api/portal/handoffs?${qs.toString()}`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return (result.data as { handoffs: Handoff[] }).handoffs;
    },
  });
  const error = queryError ? (queryError as Error).message : null;

  // Drops a selected/opened row the moment it's no longer in the current
  // list (a poll refresh after someone else resolves/deletes it, or after
  // this tab's own bulk action) -- computed during render (not an effect),
  // React's own "adjusting state when a prop changes" pattern.
  if (selectedId !== null && handoffs && !handoffs.some((h) => h.id === selectedId)) {
    setSelectedId(null);
  }
  const [lastHandoffsForPrune, setLastHandoffsForPrune] = useState<Handoff[] | undefined>(
    undefined,
  );
  if (handoffs && handoffs !== lastHandoffsForPrune) {
    setLastHandoffsForPrune(handoffs);
    setSelectedIds((prev) => {
      const visible = new Set(handoffs.map((h) => h.id));
      const next = new Set([...prev].filter((id) => visible.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }

  // Switching tabs/date shows a different list entirely -- a selection made
  // on "Open" shouldn't silently carry over and get bulk-acted-on from
  // "All". Computed during render, keyed on the [filter, dateFilter] pair
  // actually changing.
  const [lastFilterKey, setLastFilterKey] = useState(`${filter}:${dateFilter}`);
  const filterKey = `${filter}:${dateFilter}`;
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    setSelectedIds(new Set());
  }

  function toggleSelected(id: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleSelectAll(checked: boolean) {
    setSelectedIds(checked ? new Set((handoffs ?? []).map((h) => h.id)) : new Set());
  }

  const bulkResolveMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      const result = await portalFetch("/api/portal/handoffs/bulk-resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handoff_ids: ids }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function handleBulkResolve() {
    if (selectedIds.size === 0) return;
    setBulkError(null);
    try {
      await bulkResolveMutation.mutateAsync(Array.from(selectedIds));
      setSelectedIds(new Set());
      refetch();
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  const bulkDeleteMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      const result = await portalFetch("/api/portal/handoffs/bulk-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ handoff_ids: ids }),
      });
      if (!result.ok) {
        throw new Error(
          result.unauthorized ? "Session expired — please log in again." : result.error,
        );
      }
    },
  });

  async function handleBulkDelete() {
    if (selectedIds.size === 0) return;
    if (
      !window.confirm(
        `Delete ${selectedIds.size} message record(s)? This can't be undone from the portal.`,
      )
    )
      return;
    setBulkError(null);
    try {
      await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSelectedId(null);
      setSelectedIds(new Set());
      refetch();
    } catch (err) {
      setBulkError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  const selected = handoffs?.find((h) => h.id === selectedId) || null;

  // Messages page redesign: a handoff only ever carries a phone number, not
  // a patient_id -- the right-rail "Patient Details" panel resolves the
  // real patient record (if any) by searching the existing patients list
  // for this exact phone. Prefers an exact phone match over the (already
  // narrow) ILIKE search's first result, since a partial digit-substring
  // match could otherwise surface the wrong patient.
  const { data: matchedPatient, isFetching: matchedPatientLoading } = useQuery({
    queryKey: ["portal-message-matched-patient", selected?.phone],
    enabled: !!selected?.phone,
    retry: false,
    queryFn: async () => {
      const phone = selected!.phone;
      const result = await portalFetch(`/api/portal/patients?search=${encodeURIComponent(phone)}`);
      if (!result.ok) return null;
      const patients = (result.data as { patients: Patient[] }).patients;
      return patients.find((p) => p.phone === phone) || patients[0] || null;
    },
  });

  const { data: thread, error: threadQueryError } = useQuery({
    queryKey: ["portal-handoff-thread", selectedId],
    enabled: selectedId !== null,
    retry: false,
    refetchInterval: selectedId !== null ? POLL_INTERVAL_MS : false,
    queryFn: async () => {
      const result = await portalFetch(`/api/portal/handoffs/${selectedId}/messages`);
      if (!result.ok) {
        if (result.unauthorized) router.push("/portal/login");
        throw new Error(result.unauthorized ? "Not authenticated." : result.error);
      }
      return (result.data as { messages: HandoffMessage[] }).messages;
    },
  });
  const threadError = threadQueryError ? (threadQueryError as Error).message : null;

  const sendMutation = useMutation({
    mutationFn: async ({ handoffId, text }: { handoffId: number; text: string }) => {
      const result = await portalFetch(`/api/portal/handoffs/${handoffId}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!result.ok) throw new Error("Couldn't send reply.");
    },
  });

  async function handleSend() {
    if (!selected || !replyText.trim()) return;
    try {
      await sendMutation.mutateAsync({ handoffId: selected.id, text: replyText.trim() });
      setReplyText("");
    } catch {
      // Nothing to surface beyond the button no longer showing "Sending…" --
      // matches the original silent-fail-on-send behavior.
    }
  }

  const resolveMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/handoffs/${id}/resolve`, { method: "POST" });
      if (!result.ok) throw new Error("Couldn't resolve.");
    },
  });

  const [resolvingId, setResolvingId] = useState<number | null>(null);
  async function handleResolve(id: number) {
    setResolvingId(id);
    try {
      await resolveMutation.mutateAsync(id);
      refetch();
    } catch {
      // Silent-fail, matches original.
    } finally {
      setResolvingId(null);
    }
  }

  // Item 3: soft-delete only (no restriction on status, unlike appointments
  // -- see db.soft_delete_handoff()'s own reasoning).
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const result = await portalFetch(`/api/portal/handoffs/${id}/delete`, { method: "POST" });
      if (!result.ok) throw new Error("Couldn't delete.");
    },
  });

  const [deletingId, setDeletingId] = useState<number | null>(null);
  async function handleDelete(id: number) {
    if (!window.confirm("Delete this message record? This can't be undone from the portal."))
      return;
    setDeletingId(id);
    try {
      await deleteMutation.mutateAsync(id);
      setSelectedId(null);
      refetch();
    } catch {
      // Silent-fail, matches original.
    } finally {
      setDeletingId(null);
    }
  }

  return {
    filter,
    setFilter,
    handoffs: handoffs ?? null,
    error,
    dateFilter,
    setDateFilter,
    selectedId,
    setSelectedId,
    selected,
    replyText,
    setReplyText,
    sending: sendMutation.isPending,
    handleSend,
    thread: thread ?? null,
    threadError,
    resolvingId,
    handleResolve,
    deletingId,
    handleDelete,
    selectedIds,
    toggleSelected,
    toggleSelectAll,
    bulkActing: bulkResolveMutation.isPending || bulkDeleteMutation.isPending,
    bulkError,
    handleBulkResolve,
    handleBulkDelete,
    matchedPatient: matchedPatient ?? null,
    matchedPatientLoading,
  };
}
