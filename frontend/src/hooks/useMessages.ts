import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetch } from "@/lib/portalAuth";

export type Handoff = {
  id: number;
  phone: string;
  reason: "patient_requested" | "system_error";
  message_text: string | null;
  status: "open" | "resolved";
  created_at: string;
  resolved_at: string | null;
};

// Two-way threading follow-up (Spec.md Section 0): a handoff's full
// conversation, not just its trigger message -- direction distinguishes a
// patient's own message (inbound) from a staff reply (outbound).
export type HandoffMessage = {
  id: number;
  direction: "inbound" | "outbound";
  message_text: string;
  created_at: string;
};

export const FILTERS = [
  { key: "open", label: "Open" },
  { key: "resolved", label: "Resolved" },
  { key: "all", label: "All" },
] as const;

// Item 4 (Spec.md Section 0): new incoming handoff requests don't push to
// this tab -- there's no websocket/SSE infra in this app -- so poll instead
// of requiring a manual refresh, same pattern /portal/dashboard already
// uses. A plain re-fetch + re-render is enough here: `load()` only replaces
// the `handoffs` list, never `replyText` (separate local state), so a poll
// firing mid-type never loses what staff is typing.
const POLL_INTERVAL_MS = 12_000;

/** Loads + owns every mutation on the /portal/messages (handoffs) page:
 * list + status/date filters, thread polling for the selected conversation,
 * reply send, resolve, delete. */
export function useMessages(ready: boolean) {
  const router = useRouter();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("open");
  const [handoffs, setHandoffs] = useState<Handoff[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const [thread, setThread] = useState<HandoffMessage[] | null>(null);
  const [threadError, setThreadError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  // Item 6 (Spec.md Section 0): status filtering already existed (the
  // Open/Resolved/All tabs above) -- this adds a date filter alongside it.
  const [dateFilter, setDateFilter] = useState("");

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ status: filter });
    if (dateFilter) qs.set("date", dateFilter);
    const result = await portalFetch(`/api/portal/handoffs?${qs.toString()}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { handoffs: Handoff[] };
    setHandoffs(data.handoffs);
  }, [router, filter, dateFilter]);

  useEffect(() => {
    if (!ready) return;
    load();
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [ready, load]);

  useEffect(() => {
    if (selectedId !== null && !handoffs?.some((h) => h.id === selectedId)) {
      setSelectedId(null);
    }
  }, [handoffs, selectedId]);

  const selected = handoffs?.find((h) => h.id === selectedId) || null;

  const loadThread = useCallback(async (id: number) => {
    const result = await portalFetch(`/api/portal/handoffs/${id}/messages`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setThreadError(result.error);
      return;
    }
    setThreadError(null);
    setThread((result.data as { messages: HandoffMessage[] }).messages);
  }, [router]);

  // Two-way threading follow-up: while a conversation is open, poll its
  // thread too (same reasoning POLL_INTERVAL_MS already documents for the
  // list itself) -- a patient's follow-up messages must show up without a
  // manual refresh, same as new handoffs appearing in the left list do.
  useEffect(() => {
    if (selectedId === null) {
      setThread(null);
      return;
    }
    setThread(null);
    loadThread(selectedId);
    const interval = setInterval(() => loadThread(selectedId), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [selectedId, loadThread]);

  async function handleSend() {
    if (!selected || !replyText.trim()) return;
    setSending(true);
    const result = await portalFetch(`/api/portal/handoffs/${selected.id}/reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: replyText.trim() }),
    });
    setSending(false);
    if (result.ok) {
      setReplyText("");
      loadThread(selected.id);
    }
  }

  async function handleResolve(id: number) {
    setResolvingId(id);
    const result = await portalFetch(`/api/portal/handoffs/${id}/resolve`, { method: "POST" });
    setResolvingId(null);
    if (result.ok) load();
  }

  // Item 3: soft-delete only (no restriction on status, unlike appointments
  // -- see db.soft_delete_handoff()'s own reasoning).
  async function handleDelete(id: number) {
    if (!window.confirm("Delete this message record? This can't be undone from the portal.")) return;
    setDeletingId(id);
    const result = await portalFetch(`/api/portal/handoffs/${id}/delete`, { method: "POST" });
    setDeletingId(null);
    if (result.ok) {
      setSelectedId(null);
      load();
    }
  }

  return {
    filter, setFilter, handoffs, error, dateFilter, setDateFilter,
    selectedId, setSelectedId, selected,
    replyText, setReplyText, sending, handleSend,
    thread, threadError,
    resolvingId, handleResolve,
    deletingId, handleDelete,
  };
}
