"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, MessageCircle, Send, Trash2, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { portalFetch } from "@/lib/portalAuth";

type Handoff = {
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
type HandoffMessage = {
  id: number;
  direction: "inbound" | "outbound";
  message_text: string;
  created_at: string;
};

const FILTERS = [
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

function formatTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function PortalMessagesPage() {
  const router = useRouter();
  const { hospital, ready } = usePortalGuard();
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

  return (
    <PortalShell hospital={hospital} active="messages">
        <h1 className="text-display mb-space-5">Messages</h1>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <div className="mb-space-4 flex flex-wrap items-center gap-space-2">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={cn(
                "rounded-md px-space-3 py-space-2 text-[12.5px] font-semibold transition-colors duration-150",
                filter === f.key ? "bg-brand-600 text-white" : "bg-card text-ink-600 hover:bg-black/[0.04]",
              )}
            >
              {f.label}
            </button>
          ))}
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="h-10 rounded-md border border-line bg-card px-space-3 text-[12.5px] text-ink-900"
          />
          {dateFilter && (
            <button
              type="button"
              onClick={() => setDateFilter("")}
              className="text-[12px] font-semibold text-ink-400 hover:text-ink-700"
            >
              Clear date
            </button>
          )}
        </div>

        {!handoffs ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : handoffs.length === 0 ? (
          <Card className="p-space-6 text-center">
            <MessageCircle size={28} className="mx-auto mb-space-2 text-ink-300" />
            <p className="text-[13px] text-ink-400">
              {filter === "open" ? "No open requests — patients needing a human are queued here." : "Nothing here."}
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[340px_1fr]">
            <Card className="max-h-[calc(100vh-220px)] overflow-y-auto p-space-2">
              <ul className="space-y-space-1">
                {handoffs.map((h) => {
                  const isSelected = h.id === selectedId;
                  return (
                    <li key={h.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(h.id)}
                        className={cn(
                          "flex w-full flex-col items-start gap-space-1 rounded-md px-space-3 py-space-3 text-left transition-colors duration-150",
                          isSelected ? "bg-brand-50" : "hover:bg-black/[0.03]",
                        )}
                      >
                        <div className="flex w-full items-center justify-between gap-space-2">
                          <span className="flex items-center gap-space-2 text-[13.5px] font-semibold text-ink-900">
                            <UserRound size={14} className="shrink-0 text-ink-400" />
                            {h.phone}
                          </span>
                          {h.reason === "system_error" ? (
                            <AlertTriangle size={14} className="shrink-0 text-clay-600" />
                          ) : null}
                        </div>
                        <p className="line-clamp-2 text-[12px] text-ink-600">
                          {h.message_text || (h.reason === "patient_requested" ? "Asked to talk to reception." : "System error.")}
                        </p>
                        <div className="flex items-center gap-space-2">
                          <Badge tone={h.status === "open" ? "clay" : "success"}>{h.status === "open" ? "Open" : "Resolved"}</Badge>
                          <span className="text-[11px] text-ink-400">{formatTime(h.created_at)}</span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </Card>

            <Card className="flex flex-col p-space-5">
              {!selected ? (
                <p className="m-auto text-[13px] text-ink-400">Select a conversation to view details and reply.</p>
              ) : (
                <div className="flex h-full flex-col">
                  <div className="mb-space-4 flex flex-wrap items-start justify-between gap-space-3 border-b border-line pb-space-4">
                    <div>
                      <p className="text-[15px] font-bold text-ink-900">{selected.phone}</p>
                      <div className="mt-space-1 flex items-center gap-space-2">
                        <Badge tone={selected.reason === "system_error" ? "clay" : "brand"}>
                          {selected.reason === "system_error" ? "System error" : "Patient requested"}
                        </Badge>
                        <span className="text-[12px] text-ink-400">{formatTime(selected.created_at)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-space-2">
                      {selected.status === "open" ? (
                        <Button
                          variant="secondary"
                          size="md"
                          onClick={() => handleResolve(selected.id)}
                          disabled={resolvingId === selected.id}
                        >
                          <Check size={14} /> Mark resolved
                        </Button>
                      ) : (
                        <Badge tone="success">Resolved {selected.resolved_at ? formatTime(selected.resolved_at) : ""}</Badge>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(selected.id)}
                        disabled={deletingId === selected.id}
                        className="inline-flex items-center gap-space-1 rounded-md px-space-2 py-space-2 text-[12.5px] font-semibold text-ink-400 hover:text-error disabled:opacity-50"
                      >
                        <Trash2 size={14} /> {deletingId === selected.id ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                  </div>

                  {threadError && <p className="mb-space-3 text-[12.5px] text-error">{threadError}</p>}

                  <div className="mb-space-4 flex-1 space-y-space-3 overflow-y-auto">
                    {thread === null ? (
                      <p className="py-space-4 text-center text-[13px] text-ink-400">Loading conversation…</p>
                    ) : thread.length === 0 ? (
                      <p className="py-space-4 text-center text-[13px] text-ink-400">No messages yet.</p>
                    ) : (
                      thread.map((m) => (
                        <div key={m.id} className={cn("flex", m.direction === "outbound" ? "justify-end" : "justify-start")}>
                          <div
                            className={cn(
                              "max-w-[75%] rounded-lg px-space-3 py-space-2 text-[13.5px]",
                              m.direction === "outbound" ? "bg-brand-600 text-white" : "bg-paper text-ink-900",
                            )}
                          >
                            <p className="whitespace-pre-wrap">{m.message_text}</p>
                            <p className={cn("mt-space-1 text-[10.5px]", m.direction === "outbound" ? "text-white/70" : "text-ink-400")}>
                              {formatTime(m.created_at)}
                            </p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="mt-auto flex items-end gap-space-2 border-t border-line pt-space-4">
                    <textarea
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      placeholder="Reply on WhatsApp…"
                      rows={2}
                      className="h-20 flex-1 resize-none rounded-md border border-line bg-card px-space-3 py-space-2 text-[13.5px] text-ink-900 outline-none focus:border-brand-400"
                    />
                    <Button onClick={handleSend} disabled={sending || !replyText.trim()}>
                      <Send size={14} /> {sending ? "Sending…" : "Send"}
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          </div>
        )}
    </PortalShell>
  );
}
