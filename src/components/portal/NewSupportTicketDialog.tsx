"use client";

import { useRef, useState } from "react";
import { Paperclip, Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { useSupportTicketCategories, type TicketPriority } from "@/hooks/useSupportTickets";
import { staffFetch } from "@/lib/staffAuth";
import { toast } from "@/lib/toast";

const QUESTION_MAX = 2000;

const PRIORITY_OPTIONS: { value: TicketPriority; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
];

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: () => void;
};

/** "Raise a Ticket" -- available to every staff role (portal/permissions.py's
 * "raise_ticket" page key, view+write by default for every role, same
 * weight as "holiday_application"). Posted as multipart/form-data so the
 * optional image rides along in the same request, same shape as the Patient
 * Detail page's own document upload (usePatientDetail.ts's handleUpload).
 * There's no tracking view here for the submitter yet (out of scope for
 * this pass) -- a success toast is the only feedback; the ticket itself is
 * reviewed only on the platform super-admin side. */
export function NewSupportTicketDialog({ open, onOpenChange, onCreated }: Props) {
  const { categories } = useSupportTicketCategories(open);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [subject, setSubject] = useState("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [priority, setPriority] = useState<TicketPriority>("medium");
  const [question, setQuestion] = useState("");
  const [problemReference, setProblemReference] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function resetForm() {
    setSubject("");
    setCategoryId("");
    setPriority("medium");
    setQuestion("");
    setProblemReference("");
    setImage(null);
    setFormError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!subject.trim()) {
      setFormError("Subject is required.");
      return;
    }
    if (!question.trim()) {
      setFormError("Please describe your issue.");
      return;
    }

    const formData = new FormData();
    formData.append("subject", subject.trim());
    formData.append("question", question.trim());
    formData.append("priority", priority);
    if (categoryId) formData.append("category_id", categoryId);
    if (problemReference.trim()) formData.append("problem_reference", problemReference.trim());
    if (image) formData.append("image", image);

    setSubmitting(true);
    const result = await staffFetch("/api/portal/support-tickets", {
      method: "POST",
      body: formData,
    });
    setSubmitting(false);
    if (!result.ok) {
      setFormError(result.unauthorized ? "Session expired -- please log in again." : result.error);
      return;
    }
    const ticketNumber = (result.data as { ticket?: { ticket_number?: string } })?.ticket
      ?.ticket_number;
    toast.success(ticketNumber ? `Ticket ${ticketNumber} submitted` : "Ticket submitted");
    resetForm();
    onOpenChange(false);
    onCreated?.();
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) resetForm();
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogTitle>Raise a ticket</DialogTitle>
        <DialogDescription>
          Describe the issue and our support team will get back to you.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="gap-space-3 grid grid-cols-1">
          <Field label="Subject" htmlFor="ticket_subject" required>
            <Input
              id="ticket_subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Short summary of the issue"
            />
          </Field>

          <div className="gap-x-space-4 grid grid-cols-1 sm:grid-cols-2">
            <Field label="Category" htmlFor="ticket_category">
              <select
                id="ticket_category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
              >
                <option value="">Not specified</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priority" htmlFor="ticket_priority" required>
              <select
                id="ticket_priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value as TicketPriority)}
                className="border-line bg-card px-space-3 text-ink-900 h-11 w-full rounded-md border text-[14px]"
              >
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Problem reference" htmlFor="ticket_reference" hint="Optional">
            <Input
              id="ticket_reference"
              value={problemReference}
              onChange={(e) => setProblemReference(e.target.value)}
              placeholder="e.g. an appointment or invoice ID"
            />
          </Field>

          <Field
            label="Question"
            htmlFor="ticket_question"
            required
            hint={`${question.length}/${QUESTION_MAX}`}
          >
            <Textarea
              id="ticket_question"
              rows={4}
              maxLength={QUESTION_MAX}
              placeholder="Describe what's going wrong..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </Field>

          <Field label="Attachment" htmlFor="ticket_image" hint="Optional image">
            <label className="border-line text-ink-600 gap-space-2 flex h-11 w-full cursor-pointer items-center rounded-md border px-3 text-[13px] hover:bg-black/4">
              <Paperclip size={14} className="shrink-0" />
              {image ? image.name : "Choose an image"}
              <input
                ref={fileInputRef}
                id="ticket_image"
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => setImage(e.target.files?.[0] ?? null)}
              />
            </label>
          </Field>

          {formError && <p className="text-error text-[12.5px] font-medium">{formError}</p>}

          <div>
            <Button type="submit" disabled={submitting}>
              <Send size={14} /> {submitting ? "Submitting…" : "Submit ticket"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
