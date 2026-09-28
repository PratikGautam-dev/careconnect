"use client";

import { useState } from "react";
import axios, { isAxiosError } from "axios";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { API_BASE_URL } from "@/lib/staffAuth";

const MESSAGE_MAX = 2000;

/** Landing page's "Request a product demo" button -- public/
 * product_demo_requests_api.py's POST /api/product-demo-requests, no auth
 * header (same "plain axios call, not staffFetch/portalFetch" reasoning as
 * usePublicPlans.ts -- there is no session here at all, this is a visitor
 * who may never have heard of the portal). Reviewed only by the platform
 * super admin (admin/product-demo-requests page), same posture as Raise a
 * Ticket's own submission dialog. */
export function RequestDemoDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [hospitalName, setHospitalName] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submittedNumber, setSubmittedNumber] = useState<string | null>(null);

  function resetForm() {
    setName("");
    setEmail("");
    setPhone("");
    setHospitalName("");
    setMessage("");
    setFormError(null);
    setSubmittedNumber(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!name.trim()) {
      setFormError("Name is required.");
      return;
    }
    if (!email.trim()) {
      setFormError("Email is required.");
      return;
    }
    if (!phone.trim()) {
      setFormError("Phone is required.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await axios.post(`${API_BASE_URL}/api/product-demo-requests`, {
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim(),
        hospital_name: hospitalName.trim() || undefined,
        message: message.trim() || undefined,
      });
      setSubmittedNumber(res.data?.request_number ?? null);
    } catch (err) {
      if (isAxiosError(err) && err.response) {
        setFormError(err.response.data?.error || "Something went wrong. Please try again.");
      } else {
        setFormError("Network error — check your connection.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button variant="secondary" size="lg" onClick={() => setOpen(true)} type="button">
        Request demo
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!next) resetForm();
          setOpen(next);
        }}
      >
        <DialogContent>
        {submittedNumber ? (
          <>
            <DialogTitle>Thanks — request received</DialogTitle>
            <DialogDescription>
              Your reference number is <strong>{submittedNumber}</strong>. Our team will reach out
              shortly to schedule your demo.
            </DialogDescription>
            <Button type="button" onClick={() => setOpen(false)}>
              Close
            </Button>
          </>
        ) : (
          <>
            <DialogTitle>Request a product demo</DialogTitle>
            <DialogDescription>
              Tell us a bit about your hospital and we&apos;ll get in touch to schedule a walkthrough.
            </DialogDescription>
            <form onSubmit={handleSubmit} className="gap-space-3 grid grid-cols-1">
              <Field label="Name" htmlFor="demo_name" required>
                <Input
                  id="demo_name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your full name"
                />
              </Field>

              <div className="gap-x-space-4 grid grid-cols-1 sm:grid-cols-2">
                <Field label="Email" htmlFor="demo_email" required>
                  <Input
                    id="demo_email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@hospital.com"
                  />
                </Field>
                <Field label="Phone" htmlFor="demo_phone" required>
                  <Input
                    id="demo_phone"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+91…"
                  />
                </Field>
              </div>

              <Field label="Hospital / Clinic name" htmlFor="demo_hospital" hint="Optional">
                <Input
                  id="demo_hospital"
                  value={hospitalName}
                  onChange={(e) => setHospitalName(e.target.value)}
                  placeholder="e.g. Rao Clinic"
                />
              </Field>

              <Field
                label="Message"
                htmlFor="demo_message"
                hint={`Optional — ${message.length}/${MESSAGE_MAX}`}
              >
                <Textarea
                  id="demo_message"
                  rows={3}
                  maxLength={MESSAGE_MAX}
                  placeholder="Anything specific you'd like us to cover?"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                />
              </Field>

              {formError && <p className="text-error text-[12.5px] font-medium">{formError}</p>}

              <div>
                <Button type="submit" disabled={submitting}>
                  <Send size={14} /> {submitting ? "Submitting…" : "Request demo"}
                </Button>
              </div>
            </form>
          </>
        )}
        </DialogContent>
      </Dialog>
    </>
  );
}
