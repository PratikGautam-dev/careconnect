"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  Check,
  MessageCircle,
  MoreVertical,
  Paperclip,
  Phone,
  Search,
  Send,
  Settings,
  Smile,
  Trash2,
  UserRound,
  Users,
  Video,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PageHeader } from "@/components/ui/PageHeader";
import { NewBookingDialog } from "@/components/portal/NewBookingDialog";
import { NewTestBookingDialog } from "@/components/portal/NewTestBookingDialog";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatHeaderDate, formatShortDateTime, formatTimeOnly } from "@/lib/formatDate";
import { AVATAR_TINTS, initials } from "@/app/portal/patients/_components/patients-columns";
import { FILTERS, useMessages } from "@/hooks/useMessages";
import { MessagePatientPanel } from "./_components/MessagePatientPanel";

// Reference-layout tabs (Spec.md-style follow-up): "Patients" is the only
// one with a real data source -- handoffs are always patient-initiated
// WhatsApp conversations. Doctors/Staff/System have no messaging model in
// this app at all yet (no doctor<->staff chat, no system-notification
// inbox), so they stay visible per the mockup but show an honest "not built
// yet" empty state instead of fabricating conversations.
const CONVERSATION_TABS = [
  { key: "patients", label: "Patients", icon: UserRound },
  { key: "doctors", label: "Doctors", icon: Building2 },
  { key: "staff", label: "Staff", icon: Users },
  { key: "system", label: "System", icon: Settings },
] as const;
type ConversationTab = (typeof CONVERSATION_TABS)[number]["key"];

/** Groups a thread's messages into per-day sections so a date divider (the
 * reference layout's "Monday, 8 September 2026" pill) only ever appears once
 * per calendar day, in order. */
function groupByDay<T extends { created_at: string }>(items: T[]): { dateKey: string; items: T[] }[] {
  const groups: { dateKey: string; items: T[] }[] = [];
  for (const item of items) {
    const dateKey = item.created_at.slice(0, 10);
    const last = groups[groups.length - 1];
    if (last && last.dateKey === dateKey) last.items.push(item);
    else groups.push({ dateKey, items: [item] });
  }
  return groups;
}

export default function PortalMessagesPage() {
  const { hospital, ready } = usePortalGuard();
  const {
    filter, setFilter, handoffs, error, dateFilter, setDateFilter,
    selectedId, setSelectedId, selected,
    replyText, setReplyText, sending, handleSend,
    thread, threadError,
    resolvingId, handleResolve,
    deletingId, handleDelete,
    selectedIds, toggleSelected, toggleSelectAll,
    bulkActing, bulkError, handleBulkResolve, handleBulkDelete,
    matchedPatient, matchedPatientLoading,
  } = useMessages(ready);

  const [conversationTab, setConversationTab] = useState<ConversationTab>("patients");
  const [searchQuery, setSearchQuery] = useState("");
  const [bookingOpen, setBookingOpen] = useState(false);
  const [testBookingOpen, setTestBookingOpen] = useState(false);

  const visibleHandoffs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q || !handoffs) return handoffs;
    return handoffs.filter((h) => h.phone.toLowerCase().includes(q) || (h.message_text || "").toLowerCase().includes(q));
  }, [handoffs, searchQuery]);

  const dayGroups = thread ? groupByDay(thread) : [];

  return (
    <PortalShell hospital={hospital} active="messages">
        <PageHeader title="Messages" description="Secure Communication for Better Care" />
        {error && <p className="mb-space-4 text-[13px] text-error">{error}</p>}

        {selectedIds.size > 0 && (
          <div className="mb-space-4 flex flex-wrap items-center gap-space-3 rounded-md border border-line bg-card px-space-3 py-space-2">
            <span className="text-[12.5px] font-semibold text-ink-900">{selectedIds.size} selected</span>
            <button
              type="button"
              onClick={handleBulkResolve}
              disabled={bulkActing}
              className="inline-flex items-center gap-space-1 rounded-md px-space-2 py-space-2 text-[12.5px] font-semibold text-ink-900 hover:bg-black/[0.04] disabled:opacity-50"
            >
              <Check size={14} /> Resolve selected
            </button>
            <PermissionGate page="messages" action="delete">
              <button
                type="button"
                onClick={handleBulkDelete}
                disabled={bulkActing}
                className="inline-flex items-center gap-space-1 rounded-md px-space-2 py-space-2 text-[12.5px] font-semibold text-ink-400 hover:text-error disabled:opacity-50"
              >
                <Trash2 size={14} /> Delete selected
              </button>
            </PermissionGate>
            <button
              type="button"
              onClick={() => toggleSelectAll(false)}
              className="ml-auto text-[12px] font-semibold text-ink-400 hover:text-ink-700"
            >
              Clear selection
            </button>
          </div>
        )}
        {bulkError && <p className="mb-space-4 text-[13px] text-error">{bulkError}</p>}

        {!handoffs ? (
          <p className="text-[13px] text-ink-400">Loading…</p>
        ) : (
          <div className="grid grid-cols-1 gap-space-4 lg:grid-cols-[320px_1fr_320px]">
            {/* --- Conversation list --- */}
            <Card className="flex max-h-[calc(100vh-220px)] flex-col overflow-hidden p-space-3">
              <div className="mb-space-3 grid grid-cols-4 gap-1 rounded-md bg-paper p-1">
                {CONVERSATION_TABS.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setConversationTab(t.key)}
                    title={t.key !== "patients" ? "Not built yet — no data source for this tab" : undefined}
                    className={cn(
                      "flex items-center justify-center gap-1 rounded-md px-space-2 py-space-2 text-[11px] font-semibold transition-colors duration-150",
                      conversationTab === t.key ? "bg-brand-600 text-white" : "text-ink-600 hover:bg-black/[0.04]",
                    )}
                  >
                    <t.icon size={13} /> {t.label}
                  </button>
                ))}
              </div>

              {conversationTab !== "patients" ? (
                <div className="flex flex-1 flex-col items-center justify-center py-space-6 text-center">
                  <MessageCircle size={26} className="mb-space-2 text-ink-300" />
                  <p className="text-[12.5px] text-ink-400">
                    {CONVERSATION_TABS.find((t) => t.key === conversationTab)?.label} conversations aren&apos;t built yet.
                  </p>
                </div>
              ) : (
                <>
                  <div className="relative mb-space-2">
                    <Search size={14} className="pointer-events-none absolute left-space-3 top-1/2 -translate-y-1/2 text-ink-400" />
                    <input
                      type="text"
                      placeholder="Search conversations…"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="h-9 w-full rounded-md border border-line bg-card pl-space-8 pr-space-3 text-[12.5px] text-ink-900 outline-none focus:border-brand-400"
                    />
                  </div>

                  <div className="mb-space-2 flex flex-wrap items-center gap-space-1">
                    {FILTERS.map((f) => (
                      <button
                        key={f.key}
                        type="button"
                        onClick={() => setFilter(f.key)}
                        className={cn(
                          "rounded-md px-space-2 py-1 text-[11px] font-semibold transition-colors duration-150",
                          filter === f.key ? "bg-brand-50 text-brand-700" : "text-ink-400 hover:bg-black/[0.04]",
                        )}
                      >
                        {f.label}
                      </button>
                    ))}
                    <input
                      type="date"
                      value={dateFilter}
                      onChange={(e) => setDateFilter(e.target.value)}
                      className="h-7 rounded-md border border-line bg-card px-space-2 text-[11px] text-ink-900"
                    />
                  </div>

                  {handoffs.length > 0 && (
                    <div className="flex items-center gap-space-2 border-b border-line px-space-1 pb-space-2">
                      <input
                        type="checkbox"
                        aria-label="Select all"
                        checked={handoffs.length > 0 && selectedIds.size === handoffs.length}
                        onChange={(e) => toggleSelectAll(e.target.checked)}
                        className="h-4 w-4 shrink-0 accent-brand-600"
                      />
                      <span className="text-[11px] font-semibold text-ink-400">Select all</span>
                    </div>
                  )}

                  <ul className="-mx-space-1 flex-1 space-y-space-1 overflow-y-auto px-space-1 pt-space-1">
                    {handoffs.length === 0 ? (
                      <li className="py-space-6 text-center text-[12.5px] text-ink-400">
                        {filter === "open" ? "No open requests — patients needing a human are queued here." : "Nothing here."}
                      </li>
                    ) : visibleHandoffs?.length === 0 ? (
                      <li className="py-space-6 text-center text-[12.5px] text-ink-400">No conversations match your search.</li>
                    ) : (
                      visibleHandoffs?.map((h, i) => {
                        const isSelected = h.id === selectedId;
                        return (
                          <li key={h.id} className="flex items-start gap-space-2">
                            <input
                              type="checkbox"
                              aria-label={`Select conversation with ${h.phone}`}
                              checked={selectedIds.has(h.id)}
                              onChange={(e) => toggleSelected(h.id, e.target.checked)}
                              className="mt-space-4 h-4 w-4 shrink-0 accent-brand-600"
                            />
                            <button
                              type="button"
                              onClick={() => setSelectedId(h.id)}
                              className={cn(
                                "flex w-full min-w-0 items-start gap-space-2 rounded-md px-space-2 py-space-2 text-left transition-colors duration-150",
                                isSelected ? "bg-brand-50" : "hover:bg-black/[0.03]",
                              )}
                            >
                              <span
                                className={cn(
                                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[12px] font-bold",
                                  AVATAR_TINTS[i % AVATAR_TINTS.length],
                                )}
                              >
                                {initials(h.phone)}
                              </span>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center justify-between gap-space-2">
                                  <span className="truncate text-[13px] font-semibold text-ink-900">{h.phone}</span>
                                  <span className="shrink-0 text-[10.5px] text-ink-400">{formatShortDateTime(h.created_at)}</span>
                                </div>
                                <p className="line-clamp-1 text-[11.5px] text-ink-600">
                                  {h.message_text || (h.reason === "patient_requested" ? "Asked to talk to reception." : "System error.")}
                                </p>
                                <div className="mt-space-1 flex items-center gap-space-1">
                                  <Badge tone={h.status === "open" ? "clay" : "success"} className="px-space-2 py-0 text-[9.5px]">
                                    {h.status === "open" ? "Open" : "Resolved"}
                                  </Badge>
                                  {h.reason === "system_error" && <AlertTriangle size={12} className="shrink-0 text-clay-600" />}
                                </div>
                              </div>
                            </button>
                          </li>
                        );
                      })
                    )}
                  </ul>
                </>
              )}
            </Card>

            {/* --- Conversation thread --- */}
            <Card className="flex flex-col p-0">
              {conversationTab !== "patients" || !selected ? (
                <p className="m-auto text-[13px] text-ink-400">
                  {conversationTab !== "patients" ? "This tab has no conversations yet." : "Select a conversation to view details and reply."}
                </p>
              ) : (
                <div className="flex h-full flex-col">
                  <div className="flex items-center justify-between gap-space-3 border-b border-line px-space-5 py-space-4">
                    <div className="flex min-w-0 items-center gap-space-3">
                      <span
                        className={cn(
                          "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[13px] font-bold",
                          AVATAR_TINTS[handoffs.findIndex((h) => h.id === selected.id) % AVATAR_TINTS.length],
                        )}
                      >
                        {initials(matchedPatient?.name || selected.phone)}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-[14.5px] font-bold text-ink-900">{matchedPatient?.name || selected.phone}</p>
                        <p className="truncate text-[11.5px] text-ink-400">
                          Patient
                          {matchedPatient?.patient_display_id ? ` • MRN: ${matchedPatient.patient_display_id}` : ""}
                          {matchedPatient?.age != null ? ` • ${matchedPatient.age} yrs` : ""}
                          {matchedPatient?.gender ? `, ${matchedPatient.gender}` : ""}
                        </p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-space-1">
                      {selected.status === "open" ? (
                        <Badge tone="clay">Open</Badge>
                      ) : (
                        <Badge tone="success">{selected.resolved_by === "auto" ? "Auto-resolved" : "Resolved"}</Badge>
                      )}
                      <button
                        type="button"
                        disabled
                        title="Coming soon — no calling integration exists yet"
                        className="flex h-9 w-9 items-center justify-center rounded-full text-ink-400 disabled:opacity-50"
                      >
                        <Phone size={16} />
                      </button>
                      <button
                        type="button"
                        disabled
                        title="Coming soon — no calling integration exists yet"
                        className="flex h-9 w-9 items-center justify-center rounded-full text-ink-400 disabled:opacity-50"
                      >
                        <Video size={16} />
                      </button>
                      <DropdownMenu>
                        <DropdownMenuTrigger className="flex h-9 w-9 items-center justify-center rounded-full text-ink-600 hover:bg-black/[0.04]">
                          <MoreVertical size={16} />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent>
                          <DropdownMenuGroup>
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            {selected.status === "open" && (
                              <DropdownMenuItem disabled={resolvingId === selected.id} onClick={() => handleResolve(selected.id)}>
                                <Check size={14} /> Mark resolved
                              </DropdownMenuItem>
                            )}
                            <PermissionGate page="messages" action="delete">
                              <DropdownMenuItem disabled={deletingId === selected.id} onClick={() => handleDelete(selected.id)}>
                                <Trash2 size={14} /> Delete
                              </DropdownMenuItem>
                            </PermissionGate>
                          </DropdownMenuGroup>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>

                  {threadError && <p className="px-space-5 pt-space-3 text-[12.5px] text-error">{threadError}</p>}

                  <div className="flex-1 space-y-space-4 overflow-y-auto px-space-5 py-space-4">
                    {thread === null ? (
                      <p className="py-space-4 text-center text-[13px] text-ink-400">Loading conversation…</p>
                    ) : thread.length === 0 ? (
                      <p className="py-space-4 text-center text-[13px] text-ink-400">No messages yet.</p>
                    ) : (
                      dayGroups.map((group) => (
                        <div key={group.dateKey} className="space-y-space-3">
                          <div className="flex justify-center">
                            <span className="rounded-full bg-paper px-space-3 py-1 text-[11px] font-semibold text-ink-400">
                              {formatHeaderDate(new Date(`${group.dateKey}T00:00:00`))}
                            </span>
                          </div>
                          {group.items.map((m) => (
                            <div key={m.id} className={cn("flex", m.direction === "outbound" ? "justify-end" : "justify-start")}>
                              <div
                                className={cn(
                                  "max-w-[75%] rounded-lg px-space-3 py-space-2 text-[13.5px]",
                                  m.direction === "outbound" ? "bg-brand-600 text-white" : "bg-paper text-ink-900",
                                )}
                              >
                                <p className="whitespace-pre-wrap">{m.message_text}</p>
                                <div
                                  className={cn(
                                    "mt-space-1 flex items-center justify-end gap-1 text-[10.5px]",
                                    m.direction === "outbound" ? "text-white/70" : "text-ink-400",
                                  )}
                                >
                                  {formatTimeOnly(m.created_at)}
                                  {m.direction === "outbound" && <Check size={11} />}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ))
                    )}
                  </div>

                  <div className="flex items-center gap-space-2 border-t border-line px-space-5 py-space-4">
                    <button
                      type="button"
                      disabled
                      title="Coming soon — no attachment upload exists yet"
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-ink-400 disabled:opacity-50"
                    >
                      <Paperclip size={17} />
                    </button>
                    <input
                      value={replyText}
                      onChange={(e) => setReplyText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          handleSend();
                        }
                      }}
                      placeholder="Type a message…"
                      className="h-10 flex-1 rounded-full border border-line bg-card px-space-4 text-[13.5px] text-ink-900 outline-none focus:border-brand-400"
                    />
                    <button
                      type="button"
                      disabled
                      title="Coming soon — no emoji picker wired up yet"
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-ink-400 disabled:opacity-50"
                    >
                      <Smile size={18} />
                    </button>
                    <button
                      type="button"
                      onClick={handleSend}
                      disabled={sending || !replyText.trim()}
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white disabled:opacity-50"
                    >
                      <Send size={16} />
                    </button>
                  </div>
                </div>
              )}
            </Card>

            {/* --- Patient details --- */}
            {conversationTab === "patients" && selected ? (
              <MessagePatientPanel
                patient={matchedPatient}
                loading={matchedPatientLoading}
                onBookAppointment={() => setBookingOpen(true)}
                onOrderTest={() => setTestBookingOpen(true)}
              />
            ) : (
              <Card className="hidden p-space-4 lg:block">
                <p className="py-space-4 text-center text-[13px] text-ink-400">Select a conversation to see patient details.</p>
              </Card>
            )}
          </div>
        )}

        <NewBookingDialog
          open={bookingOpen}
          onOpenChange={setBookingOpen}
          onBooked={() => setBookingOpen(false)}
          initialPatientName={matchedPatient?.name || undefined}
          initialPatientPhone={selected?.phone}
        />
        <NewTestBookingDialog
          open={testBookingOpen}
          onOpenChange={setTestBookingOpen}
          onBooked={() => setTestBookingOpen(false)}
          initialPatientName={matchedPatient?.name || undefined}
          initialPatientPhone={selected?.phone}
        />
    </PortalShell>
  );
}
