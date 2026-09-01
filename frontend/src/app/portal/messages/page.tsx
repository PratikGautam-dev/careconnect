"use client";

import { AlertTriangle, Check, MessageCircle, Send, Trash2, UserRound } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatShortDateTime } from "@/lib/formatDate";
import { FILTERS, useMessages } from "@/hooks/useMessages";

export default function PortalMessagesPage() {
  const { hospital, ready } = usePortalGuard();
  const {
    filter, setFilter, handoffs, error, dateFilter, setDateFilter,
    selectedId, setSelectedId, selected,
    replyText, setReplyText, sending, handleSend,
    thread, threadError,
    resolvingId, handleResolve,
    deletingId, handleDelete,
  } = useMessages(ready);

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
                          <span className="text-[11px] text-ink-400">{formatShortDateTime(h.created_at)}</span>
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
                        <span className="text-[12px] text-ink-400">{formatShortDateTime(selected.created_at)}</span>
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
                        <Badge tone="success">Resolved {selected.resolved_at ? formatShortDateTime(selected.resolved_at) : ""}</Badge>
                      )}
                      <PermissionGate page="messages" action="delete">
                        <button
                          type="button"
                          onClick={() => handleDelete(selected.id)}
                          disabled={deletingId === selected.id}
                          className="inline-flex items-center gap-space-1 rounded-md px-space-2 py-space-2 text-[12.5px] font-semibold text-ink-400 hover:text-error disabled:opacity-50"
                        >
                          <Trash2 size={14} /> {deletingId === selected.id ? "Deleting…" : "Delete"}
                        </button>
                      </PermissionGate>
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
                              {formatShortDateTime(m.created_at)}
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
