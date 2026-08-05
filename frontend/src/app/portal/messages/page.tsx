"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, MessageCircle, Send, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PortalSidebar } from "@/components/portal/PortalSidebar";
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

const FILTERS = [
  { key: "open", label: "Open" },
  { key: "resolved", label: "Resolved" },
  { key: "all", label: "All" },
] as const;

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
  const [sentIds, setSentIds] = useState<Set<number>>(new Set());
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const result = await portalFetch(`/api/portal/handoffs?status=${filter}`);
    if (!result.ok) {
      if (result.unauthorized) router.push("/portal/login");
      else setError(result.error);
      return;
    }
    const data = result.data as { handoffs: Handoff[] };
    setHandoffs(data.handoffs);
  }, [router, filter]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  useEffect(() => {
    if (selectedId !== null && !handoffs?.some((h) => h.id === selectedId)) {
      setSelectedId(null);
    }
  }, [handoffs, selectedId]);

  const selected = handoffs?.find((h) => h.id === selectedId) || null;

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
      setSentIds((prev) => new Set(prev).add(selected.id));
    }
  }

  async function handleResolve(id: number) {
    setResolvingId(id);
    const result = await portalFetch(`/api/portal/handoffs/${id}/resolve`, { method: "POST" });
    setResolvingId(null);
    if (result.ok) load();
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <PortalSidebar hospital={hospital} active="messages" />
      <main className="flex-1 overflow-y-auto p-space-6">
        <h1 className="text-display mb-space-5">Messages</h1>
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        <div className="mb-space-4 flex gap-space-2">
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
                  </div>

                  <div className="mb-space-4 rounded-lg bg-paper p-space-4 text-[13.5px] text-ink-900">
                    {selected.message_text ||
                      (selected.reason === "patient_requested"
                        ? "Patient tapped “Talk to Reception” from the main menu."
                        : "The bot hit an unexpected error while handling this patient's message.")}
                  </div>

                  {sentIds.has(selected.id) && (
                    <p className="mb-space-3 text-[12px] font-semibold text-success">Reply sent on WhatsApp.</p>
                  )}

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
      </main>
    </div>
  );
}
