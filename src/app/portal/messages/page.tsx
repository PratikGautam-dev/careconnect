"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  Check,
  MessageCircle,
  MoreVertical,
  Paperclip,
  Search,
  Send,
  Settings,
  Smile,
  Trash2,
  UserRound,
  Users,
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
import { NewDaycareBookingDialog } from "@/components/portal/NewDaycareBookingDialog";
import { PermissionGate } from "@/components/portal/PermissionGate";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { cn } from "@/lib/cn";
import { formatHeaderDate, formatShortDateTime, formatTimeOnly } from "@/lib/formatDate";
import { AVATAR_TINTS, initials } from "@/app/portal/patients/_components/patients-columns";
import { FILTERS, useMessages } from "@/hooks/useMessages";
import { MessagePatientPanel } from "./_components/MessagePatientPanel";

// "Patients" is the only tab with a real data source -- handoffs are always
// patient-initiated WhatsApp conversations. Doctors/Staff/System have no
// messaging model in this app (no doctor<->staff chat, no system
// notification inbox), so they show an honest "not built yet" empty state.
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
function groupByDay<T extends { created_at: string }>(
  items: T[],
): { dateKey: string; items: T[] }[] {
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
    filter,
    setFilter,
    handoffs,
    error,
    dateFilter,
    setDateFilter,
    selectedId,
    setSelectedId,
    selected,
    replyText,
    setReplyText,
    sending,
    handleSend,
    thread,
    threadError,
    resolvingId,
    handleResolve,
    deletingId,
    handleDelete,
    selectedIds,
    toggleSelected,
    toggleSelectAll,
    bulkActing,
    bulkError,
    handleBulkResolve,
    handleBulkDelete,
    matchedPatient,
    matchedPatientLoading,
  } = useMessages(ready);

  const [conversationTab, setConversationTab] = useState<ConversationTab>("patients");
  const [searchQuery, setSearchQuery] = useState("");
  const [bookingOpen, setBookingOpen] = useState(false);
  const [testBookingOpen, setTestBookingOpen] = useState(false);
  const [daycareBookingOpen, setDaycareBookingOpen] = useState(false);

  const visibleHandoffs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q || !handoffs) return handoffs;
    return handoffs.filter(
      (h) => h.phone.toLowerCase().includes(q) || (h.message_text || "").toLowerCase().includes(q),
    );
  }, [handoffs, searchQuery]);

  const dayGroups = thread ? groupByDay(thread) : [];

  return (
    <PortalShell hospital={hospital} active="messages">
      <PageHeader title="Messages" description="Secure Communication for Better Care" />
      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      {selectedIds.size > 0 && (
        <div className="mb-space-4 gap-space-3 border-line bg-card px-space-3 py-space-2 flex flex-wrap items-center rounded-md border">
          <span className="text-ink-900 text-[12.5px] font-semibold">
            {selectedIds.size} selected
          </span>
          <button
            type="button"
            onClick={handleBulkResolve}
            disabled={bulkActing}
            className="gap-space-1 px-space-2 py-space-2 text-ink-900 inline-flex items-center rounded-md text-[12.5px] font-semibold hover:bg-black/[0.04] disabled:opacity-50"
          >
            <Check size={14} /> Resolve selected
          </button>
          <PermissionGate page="messages" action="delete">
            <button
              type="button"
              onClick={handleBulkDelete}
              disabled={bulkActing}
              className="gap-space-1 px-space-2 py-space-2 text-ink-400 hover:text-error inline-flex items-center rounded-md text-[12.5px] font-semibold disabled:opacity-50"
            >
              <Trash2 size={14} /> Delete selected
            </button>
          </PermissionGate>
          <button
            type="button"
            onClick={() => toggleSelectAll(false)}
            className="text-ink-400 hover:text-ink-700 ml-auto text-[12px] font-semibold"
          >
            Clear selection
          </button>
        </div>
      )}
      {bulkError && <p className="mb-space-4 text-error text-[13px]">{bulkError}</p>}

      {!handoffs ? (
        <p className="text-ink-400 text-[13px]">Loading…</p>
      ) : (
        <div className="gap-space-4 grid grid-cols-1 lg:grid-cols-[320px_1fr_320px]">
          {/* --- Conversation list --- */}
          <Card className="p-space-3 flex max-h-[calc(100vh-220px)] flex-col overflow-hidden">
            <div className="mb-space-3 bg-paper grid grid-cols-4 gap-1 rounded-md p-1">
              {CONVERSATION_TABS.map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setConversationTab(t.key)}
                  title={
                    t.key !== "patients" ? "Not built yet — no data source for this tab" : undefined
                  }
                  className={cn(
                    "px-space-2 py-space-2 flex items-center justify-center gap-1 rounded-md text-[11px] font-semibold transition-colors duration-150",
                    conversationTab === t.key
                      ? "bg-brand-600 text-white"
                      : "text-ink-600 hover:bg-black/[0.04]",
                  )}
                >
                  <t.icon size={13} /> {t.label}
                </button>
              ))}
            </div>

            {conversationTab !== "patients" ? (
              <div className="py-space-6 flex flex-1 flex-col items-center justify-center text-center">
                <MessageCircle size={26} className="mb-space-2 text-ink-300" />
                <p className="text-ink-400 text-[12.5px]">
                  {CONVERSATION_TABS.find((t) => t.key === conversationTab)?.label} conversations
                  aren&apos;t built yet.
                </p>
              </div>
            ) : (
              <>
                <div className="mb-space-2 relative">
                  <Search
                    size={14}
                    className="left-space-3 text-ink-400 pointer-events-none absolute top-1/2 -translate-y-1/2"
                  />
                  <input
                    type="text"
                    placeholder="Search conversations…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="border-line bg-card pl-space-8 pr-space-3 text-ink-900 focus:border-brand-400 h-9 w-full rounded-md border text-[12.5px] outline-none"
                  />
                </div>

                <div className="mb-space-2 gap-space-1 flex flex-wrap items-center">
                  {FILTERS.map((f) => (
                    <button
                      key={f.key}
                      type="button"
                      onClick={() => setFilter(f.key)}
                      className={cn(
                        "px-space-2 rounded-md py-1 text-[11px] font-semibold transition-colors duration-150",
                        filter === f.key
                          ? "bg-brand-50 text-brand-700"
                          : "text-ink-400 hover:bg-black/[0.04]",
                      )}
                    >
                      {f.label}
                    </button>
                  ))}
                  <input
                    type="date"
                    value={dateFilter}
                    onChange={(e) => setDateFilter(e.target.value)}
                    className="border-line bg-card px-space-2 text-ink-900 h-7 rounded-md border text-[11px]"
                  />
                </div>

                {handoffs.length > 0 && (
                  <div className="gap-space-2 border-line px-space-1 pb-space-2 flex items-center border-b">
                    <input
                      type="checkbox"
                      aria-label="Select all"
                      checked={handoffs.length > 0 && selectedIds.size === handoffs.length}
                      onChange={(e) => toggleSelectAll(e.target.checked)}
                      className="accent-brand-600 h-4 w-4 shrink-0"
                    />
                    <span className="text-ink-400 text-[11px] font-semibold">Select all</span>
                  </div>
                )}

                <ul className="-mx-space-1 space-y-space-1 px-space-1 pt-space-1 flex-1 overflow-y-auto">
                  {handoffs.length === 0 ? (
                    <li className="py-space-6 text-ink-400 text-center text-[12.5px]">
                      {filter === "open"
                        ? "No open requests — patients needing a human are queued here."
                        : "Nothing here."}
                    </li>
                  ) : visibleHandoffs?.length === 0 ? (
                    <li className="py-space-6 text-ink-400 text-center text-[12.5px]">
                      No conversations match your search.
                    </li>
                  ) : (
                    visibleHandoffs?.map((h, i) => {
                      const isSelected = h.id === selectedId;
                      return (
                        <li key={h.id} className="gap-space-2 flex items-start">
                          <input
                            type="checkbox"
                            aria-label={`Select conversation with ${h.phone}`}
                            checked={selectedIds.has(h.id)}
                            onChange={(e) => toggleSelected(h.id, e.target.checked)}
                            className="mt-space-4 accent-brand-600 h-4 w-4 shrink-0"
                          />
                          <button
                            type="button"
                            onClick={() => setSelectedId(h.id)}
                            className={cn(
                              "gap-space-2 px-space-2 py-space-2 flex w-full min-w-0 items-start rounded-md text-left transition-colors duration-150",
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
                              <div className="gap-space-2 flex items-center justify-between">
                                <span className="text-ink-900 truncate text-[13px] font-semibold">
                                  {h.phone}
                                </span>
                                <span className="text-ink-400 shrink-0 text-[10.5px]">
                                  {formatShortDateTime(h.created_at)}
                                </span>
                              </div>
                              <p className="text-ink-600 line-clamp-1 text-[11.5px]">
                                {h.message_text ||
                                  (h.reason === "patient_requested"
                                    ? "Asked to talk to reception."
                                    : "System error.")}
                              </p>
                              <div className="mt-space-1 gap-space-1 flex items-center">
                                <Badge
                                  tone={h.status === "open" ? "clay" : "success"}
                                  className="px-space-2 py-0 text-[9.5px]"
                                >
                                  {h.status === "open" ? "Open" : "Resolved"}
                                </Badge>
                                {h.reason === "system_error" && (
                                  <AlertTriangle size={12} className="text-clay-600 shrink-0" />
                                )}
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
              <p className="text-ink-400 m-auto text-[13px]">
                {conversationTab !== "patients"
                  ? "This tab has no conversations yet."
                  : "Select a conversation to view details and reply."}
              </p>
            ) : (
              <div className="flex h-full flex-col">
                <div className="gap-space-3 border-line px-space-5 py-space-4 flex items-center justify-between border-b">
                  <div className="gap-space-3 flex min-w-0 items-center">
                    <span
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[13px] font-bold",
                        AVATAR_TINTS[
                          handoffs.findIndex((h) => h.id === selected.id) % AVATAR_TINTS.length
                        ],
                      )}
                    >
                      {initials(matchedPatient?.name || selected.phone)}
                    </span>
                    <div className="min-w-0">
                      <p className="text-ink-900 truncate text-[14.5px] font-bold">
                        {matchedPatient?.name || selected.phone}
                      </p>
                      <p className="text-ink-400 truncate text-[11.5px]">
                        Patient
                        {matchedPatient?.patient_display_id
                          ? ` • MRN: ${matchedPatient.patient_display_id}`
                          : ""}
                        {matchedPatient?.age != null ? ` • ${matchedPatient.age} yrs` : ""}
                        {matchedPatient?.gender ? `, ${matchedPatient.gender}` : ""}
                      </p>
                    </div>
                  </div>
                  <div className="gap-space-1 flex shrink-0 items-center">
                    {selected.status === "open" ? (
                      <Badge tone="clay">Open</Badge>
                    ) : (
                      <Badge tone="success">
                        {selected.resolved_by === "auto" ? "Auto-resolved" : "Resolved"}
                      </Badge>
                    )}
                    <DropdownMenu>
                      <DropdownMenuTrigger className="text-ink-600 flex h-9 w-9 items-center justify-center rounded-full hover:bg-black/[0.04]">
                        <MoreVertical size={16} />
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuGroup>
                          <DropdownMenuLabel>Actions</DropdownMenuLabel>
                          {selected.status === "open" && (
                            <DropdownMenuItem
                              disabled={resolvingId === selected.id}
                              onClick={() => handleResolve(selected.id)}
                            >
                              <Check size={14} /> Mark resolved
                            </DropdownMenuItem>
                          )}
                          <PermissionGate page="messages" action="delete">
                            <DropdownMenuItem
                              disabled={deletingId === selected.id}
                              onClick={() => handleDelete(selected.id)}
                            >
                              <Trash2 size={14} /> Delete
                            </DropdownMenuItem>
                          </PermissionGate>
                        </DropdownMenuGroup>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>

                {threadError && (
                  <p className="px-space-5 pt-space-3 text-error text-[12.5px]">{threadError}</p>
                )}

                <div className="space-y-space-4 px-space-5 py-space-4 flex-1 overflow-y-auto">
                  {thread === null ? (
                    <p className="py-space-4 text-ink-400 text-center text-[13px]">
                      Loading conversation…
                    </p>
                  ) : thread.length === 0 ? (
                    <p className="py-space-4 text-ink-400 text-center text-[13px]">
                      No messages yet.
                    </p>
                  ) : (
                    dayGroups.map((group) => (
                      <div key={group.dateKey} className="space-y-space-3">
                        <div className="flex justify-center">
                          <span className="bg-paper px-space-3 text-ink-400 rounded-full py-1 text-[11px] font-semibold">
                            {formatHeaderDate(new Date(`${group.dateKey}T00:00:00`))}
                          </span>
                        </div>
                        {group.items.map((m) => (
                          <div
                            key={m.id}
                            className={cn(
                              "flex",
                              m.direction === "outbound" ? "justify-end" : "justify-start",
                            )}
                          >
                            <div
                              className={cn(
                                "px-space-3 py-space-2 max-w-[75%] rounded-lg text-[13.5px]",
                                m.direction === "outbound"
                                  ? "bg-brand-600 text-white"
                                  : "bg-paper text-ink-900",
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

                <div className="gap-space-2 border-line px-space-5 py-space-4 flex items-center border-t">
                  <button
                    type="button"
                    disabled
                    title="Coming soon — no attachment upload exists yet"
                    className="text-ink-400 flex h-10 w-10 shrink-0 items-center justify-center rounded-full disabled:opacity-50"
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
                    className="border-line bg-card px-space-4 text-ink-900 focus:border-brand-400 h-10 flex-1 rounded-full border text-[13.5px] outline-none"
                  />
                  <button
                    type="button"
                    disabled
                    title="Coming soon — no emoji picker wired up yet"
                    className="text-ink-400 flex h-10 w-10 shrink-0 items-center justify-center rounded-full disabled:opacity-50"
                  >
                    <Smile size={18} />
                  </button>
                  <button
                    type="button"
                    onClick={handleSend}
                    disabled={sending || !replyText.trim()}
                    className="bg-brand-600 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white disabled:opacity-50"
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
              onBookDaycare={() => setDaycareBookingOpen(true)}
            />
          ) : (
            <Card className="p-space-4 hidden lg:block">
              <p className="py-space-4 text-ink-400 text-center text-[13px]">
                Select a conversation to see patient details.
              </p>
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
      <NewDaycareBookingDialog
        open={daycareBookingOpen}
        onOpenChange={setDaycareBookingOpen}
        onBooked={() => setDaycareBookingOpen(false)}
        initialPatientName={matchedPatient?.name || undefined}
        initialPatientPhone={selected?.phone}
      />
    </PortalShell>
  );
}
