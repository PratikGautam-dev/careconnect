"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, Plus, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input, Textarea } from "@/components/ui/Input";
import { Switch } from "@/components/ui/Switch";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { toast } from "@/lib/toast";
import { useBookingChannels } from "@/hooks/useBookingChannels";
import {
  useSiteEditor,
  type CareerOpening,
  type NewsItem,
  type RecoveryStoryItem,
  type SectionKey,
  type SiteConfig,
  type TestimonialItem,
} from "@/hooks/useSiteEditor";

const SITE_APP_URL = process.env.NEXT_PUBLIC_SITE_APP_URL || "http://localhost:3001";

const SECTION_LABELS: Record<SectionKey, string> = {
  feature_cards: "Feature cards",
  about: "About",
  departments: "Departments",
  services: "Services",
  testimonials: "Testimonials",
  recovery_stories: "Recovery stories",
  news: "News & updates",
  careers: "Careers",
  contact: "Contact",
};
// Real-data-backed sections managed elsewhere in the portal -- this page
// only controls their position/visibility, never their content, same
// distinction DineConnect's own "Name/Logo -- set elsewhere" rows draw.
const MANAGED_ELSEWHERE: Partial<Record<SectionKey, string>> = {
  departments: "Managed on the Doctors page",
  services: "Managed on the Settings page",
  contact: "Managed on the Settings page",
};

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Same scale-to-fit iframe technique the channel overview page's own
 * preview card uses -- DESIGN_WIDTH must match the site's own real desktop
 * layout width (1280, same as the overview page's SitePreview), not a
 * narrow mobile width. The site's header (logo + 4 nav links + a button)
 * is a desktop-style row with no responsive collapse below `md` -- scaling
 * it down from its NATIVE width keeps proportions correct. */
function LivePreview({ src }: { src: string | null }) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const DESIGN_WIDTH = 1280;
  const scale = size.w ? size.w / DESIGN_WIDTH : 0;
  return (
    <div ref={box} className="bg-paper relative h-[560px] overflow-hidden rounded-md">
      {src && scale > 0 && (
        <iframe
          src={src}
          title="Website preview"
          loading="lazy"
          className="absolute left-0 top-0 origin-top-left border-0 bg-white"
          style={{ width: DESIGN_WIDTH, height: size.h / scale, transform: `scale(${scale})` }}
        />
      )}
    </div>
  );
}

/** Theme editor for the public hospital site -- one long scrolling page
 * (DineConnect's own "Customize theme" layout: a profile card, a
 * sections+preview row, then one card per content section below), NOT a
 * left-tab-nav layout -- confirmed with the user after the tabbed version
 * read as cramped/unfinished. */
export default function WebsiteEditorPage() {
  const { hospital, ready } = usePortalGuard();
  const { info } = useBookingChannels(ready);
  const {
    draft, setDraft, error, isLoading, hasUnpublishedChanges,
    saveDraft, saving, publish, publishing, fetchPreviewToken, uploadImage,
  } = useSiteEditor(ready);
  const [previewToken, setPreviewToken] = useState<string | null>(null);
  // Bumped after every successful save -- appended to the iframe's src so
  // its URL actually changes and the browser refetches. The preview reads
  // the SERVER's saved draft (public/site_api.py's /preview endpoint), not
  // this page's own in-memory `draft` state, so without this the iframe
  // would silently keep showing whatever it last loaded even after a save
  // succeeded -- same URL in, same cached response out.
  const [previewNonce, setPreviewNonce] = useState(0);
  const previewUrl =
    info?.display_id && previewToken
      ? `${SITE_APP_URL}/site/${info.display_id}?preview_token=${encodeURIComponent(previewToken)}&v=${previewNonce}`
      : null;

  useEffect(() => {
    if (!info?.display_id) return;
    let cancelled = false;
    fetchPreviewToken().then((token) => {
      if (!cancelled && token) setPreviewToken(token);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch only on display_id change, not every draft edit
  }, [info?.display_id]);

  if (!hospital) return null;

  function updateSections(updater: (sections: SiteConfig["sections"]) => SiteConfig["sections"]) {
    setDraft((prev) => (prev ? { ...prev, sections: updater(prev.sections) } : prev));
  }

  // Shared by the top Save Draft button AND every per-section Save button
  // below -- the draft is always one whole JSON blob server-side (see
  // db/repositories/site_config.py), so there's no such thing as "only
  // save the Testimonials section"; every Save call persists the entire
  // current `draft` and then refreshes the preview so the change is
  // actually visible, not just silently accepted.
  async function saveAndRefreshPreview() {
    await saveDraft();
    setPreviewNonce((n) => n + 1);
  }

  function moveSection(key: SectionKey, direction: -1 | 1) {
    setDraft((prev) => {
      if (!prev) return prev;
      const order = [...prev.section_order];
      const i = order.indexOf(key);
      const j = i + direction;
      if (j < 0 || j >= order.length) return prev;
      [order[i], order[j]] = [order[j], order[i]];
      return { ...prev, section_order: order };
    });
  }

  return (
    <PortalShell hospital={hospital} active="channels-website">
      <PageHeader
        title="Customize Website"
        description="Change the look and content of your website, preview it, then publish."
        actions={
          <Button href="/portal/channels/website" variant="ghost">
            <ChevronLeft size={15} /> Back to Website
          </Button>
        }
      />

      {(error || isLoading) && (
        <p className="mb-space-4 text-[13px]">
          {error ? <span className="text-error">{error}</span> : <span className="text-hint">Loading…</span>}
        </p>
      )}

      {draft && (
        <div className="space-y-space-4">
          {/* Website profile */}
          <Card className="p-space-5">
            <p className="text-ink-900 text-[15px] font-semibold">Website profile</p>
            <p className="text-hint mt-space-1 mb-space-4 text-[12.5px]">
              Changes here save as a draft first — preview them below, then Publish when ready.
              Patients keep seeing today&apos;s live version until you do.
            </p>
            <Field label="Tagline">
              <Input
                value={draft.brand.tagline}
                onChange={(e) => setDraft({ ...draft, brand: { ...draft.brand, tagline: e.target.value } })}
                placeholder="Multi-Specialty Healthcare"
              />
            </Field>
            <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2">
              <Field label="Logo URL" hint="Shown in the header instead of the default letter icon.">
                <ImageUploadField
                  value={draft.brand.logo_url}
                  onChange={(logo_url) => setDraft({ ...draft, brand: { ...draft.brand, logo_url } })}
                  uploadImage={uploadImage}
                  placeholder="https://…/logo.png"
                />
              </Field>
              <Field label="Cover image URL" hint="Shown in the hero section.">
                <ImageUploadField
                  value={draft.brand.cover_image_url}
                  onChange={(cover_image_url) =>
                    setDraft({ ...draft, brand: { ...draft.brand, cover_image_url } })
                  }
                  uploadImage={uploadImage}
                  placeholder="https://…/cover.jpg"
                />
              </Field>
            </div>

            <div className="border-line mt-space-4 pt-space-4 gap-space-3 flex items-center justify-between border-t">
              {hasUnpublishedChanges ? (
                <span className="bg-clay-100 text-clay-700 px-space-3 py-space-1 rounded-full text-[11.5px] font-semibold">
                  Unpublished changes
                </span>
              ) : (
                <span />
              )}
              <div className="gap-space-2 flex items-center">
                <Button variant="secondary" disabled={saving} onClick={saveAndRefreshPreview}>
                  {saving ? "Saving…" : "Save Draft"}
                </Button>
                <Button variant="primary" disabled={publishing} onClick={publish}>
                  {publishing ? "Publishing…" : "Publish"}
                </Button>
              </div>
            </div>
          </Card>

          {/* Sections + live preview, side by side */}
          <div className="gap-space-4 grid grid-cols-1 items-start lg:grid-cols-2">
            <Card className="p-space-5">
              <p className="text-ink-900 text-[15px] font-semibold">Page sections</p>
              <p className="text-hint mt-space-1 mb-space-4 text-[12.5px]">
                Reorder or hide sections on your website.
              </p>
              <div className="space-y-space-2">
                {draft.section_order.map((key, index) => (
                  <div
                    key={key}
                    className="border-line px-space-3 py-space-2 gap-space-3 flex items-center rounded-md border"
                  >
                    <div className="flex flex-col">
                      <button
                        type="button"
                        disabled={index === 0}
                        onClick={() => moveSection(key, -1)}
                        className="text-ink-400 hover:text-ink-900 disabled:opacity-30"
                      >
                        <ArrowUp size={14} />
                      </button>
                      <button
                        type="button"
                        disabled={index === draft.section_order.length - 1}
                        onClick={() => moveSection(key, 1)}
                        className="text-ink-400 hover:text-ink-900 disabled:opacity-30"
                      >
                        <ArrowDown size={14} />
                      </button>
                    </div>
                    <div className="flex-1">
                      <p className="text-ink-900 text-[13.5px] font-medium">{SECTION_LABELS[key]}</p>
                      <p className="text-hint text-[11.5px]">
                        {MANAGED_ELSEWHERE[key] ?? (draft.sections[key].enabled ? "Visible" : "Hidden")}
                      </p>
                    </div>
                    <Switch
                      checked={draft.sections[key].enabled}
                      onChange={() =>
                        updateSections((s) => ({ ...s, [key]: { ...s[key], enabled: !s[key].enabled } }))
                      }
                    />
                  </div>
                ))}
              </div>
              <SectionSaveBar saving={saving} onSave={saveAndRefreshPreview} />
            </Card>

            <Card className="p-space-5">
              <p className="text-ink-900 text-[15px] font-semibold">Live preview</p>
              <p className="text-hint mt-space-1 mb-space-3 text-[12.5px]">
                Your real website, with the saved draft above overlaid — patients keep seeing the
                published version until you Publish.
              </p>
              <LivePreview src={previewUrl} />
            </Card>
          </div>

          {/* About */}
          <Card className="p-space-5">
            <p className="text-ink-900 text-[15px] font-semibold">About</p>
            <SectionToggle
              enabled={draft.sections.about.enabled}
              onChange={(enabled) => updateSections((s) => ({ ...s, about: { ...s.about, enabled } }))}
            />
            <Field label="About text" className="mt-space-3">
              <Textarea
                rows={4}
                value={draft.sections.about.text}
                onChange={(e) => updateSections((s) => ({ ...s, about: { ...s.about, text: e.target.value } }))}
                placeholder="Tell patients about your hospital's history, mission, and facilities."
              />
            </Field>
            <SectionSaveBar saving={saving} onSave={saveAndRefreshPreview} />
          </Card>

          {/* Testimonials */}
          <Card className="p-space-5">
            <p className="text-ink-900 text-[15px] font-semibold">Testimonials</p>
            <TestimonialsEditor
              enabled={draft.sections.testimonials.enabled}
              items={draft.sections.testimonials.items}
              onToggle={(enabled) => updateSections((s) => ({ ...s, testimonials: { ...s.testimonials, enabled } }))}
              onChange={(items) => updateSections((s) => ({ ...s, testimonials: { ...s.testimonials, items } }))}
            />
            <SectionSaveBar saving={saving} onSave={saveAndRefreshPreview} />
          </Card>

          {/* Recovery stories */}
          <Card className="p-space-5">
            <p className="text-ink-900 text-[15px] font-semibold">Recovery Stories</p>
            <RecoveryStoriesEditor
              enabled={draft.sections.recovery_stories.enabled}
              items={draft.sections.recovery_stories.items}
              onToggle={(enabled) =>
                updateSections((s) => ({ ...s, recovery_stories: { ...s.recovery_stories, enabled } }))
              }
              onChange={(items) =>
                updateSections((s) => ({ ...s, recovery_stories: { ...s.recovery_stories, items } }))
              }
              uploadImage={uploadImage}
            />
            <SectionSaveBar saving={saving} onSave={saveAndRefreshPreview} />
          </Card>

          {/* News */}
          <Card className="p-space-5">
            <p className="text-ink-900 text-[15px] font-semibold">News</p>
            <NewsEditor
              enabled={draft.sections.news.enabled}
              items={draft.sections.news.items}
              onToggle={(enabled) => updateSections((s) => ({ ...s, news: { ...s.news, enabled } }))}
              onChange={(items) => updateSections((s) => ({ ...s, news: { ...s.news, items } }))}
              uploadImage={uploadImage}
            />
            <SectionSaveBar saving={saving} onSave={saveAndRefreshPreview} />
          </Card>

          {/* Careers */}
          <Card className="p-space-5">
            <p className="text-ink-900 text-[15px] font-semibold">Careers</p>
            <SectionToggle
              enabled={draft.sections.careers.enabled}
              onChange={(enabled) => updateSections((s) => ({ ...s, careers: { ...s.careers, enabled } }))}
            />
            <Field label="Intro text" className="mt-space-3" hint="Optional -- shown above any openings listed below.">
              <Textarea
                rows={2}
                value={draft.sections.careers.text}
                onChange={(e) => updateSections((s) => ({ ...s, careers: { ...s.careers, text: e.target.value } }))}
              />
            </Field>
            <CareersEditor
              openings={draft.sections.careers.openings}
              onChange={(openings) => updateSections((s) => ({ ...s, careers: { ...s.careers, openings } }))}
            />
            <SectionSaveBar saving={saving} onSave={saveAndRefreshPreview} />
          </Card>
        </div>
      )}
    </PortalShell>
  );
}

/** Every save (whether from here or the top Website Profile card) writes
 * the SAME whole draft blob and then forces the live-preview iframe to
 * refetch -- see saveAndRefreshPreview() above for why that refresh step
 * matters (the iframe was previously showing a stale, server-cached draft
 * even right after a successful save). */
const _MAX_IMAGE_BYTES = 5 * 1024 * 1024;

/** A URL field plus an "Upload" button -- the admin can either paste a URL
 * (unchanged, existing behavior) or upload a file, which replaces the URL
 * with the one careconnect-backend's upload-image endpoint hands back. Kept
 * as one field, not a separate uploader widget, since the underlying data
 * is still just a URL string either way (db/repositories/site_config.py's
 * `image_url`/`logo_url`/`cover_image_url` fields don't distinguish
 * "pasted" from "uploaded"). */
function ImageUploadField({
  value,
  onChange,
  uploadImage,
  placeholder,
  compact = false,
}: {
  value: string;
  onChange: (url: string) => void;
  uploadImage: (file: File) => Promise<string>;
  placeholder?: string;
  compact?: boolean;
}) {
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Couldn't upload image", "Only image files are allowed.");
      return;
    }
    if (file.size > _MAX_IMAGE_BYTES) {
      toast.error("Couldn't upload image", "Images must be 5 MB or smaller.");
      return;
    }
    setUploading(true);
    try {
      const url = await uploadImage(file);
      onChange(url);
    } catch (err) {
      toast.error("Couldn't upload image", err instanceof Error ? err.message : "Try again.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="gap-space-2 flex items-center">
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1"
      />
      {value && (
        // eslint-disable-next-line @next/next/no-img-element -- admin-provided URL, arbitrary origin
        <img
          src={value}
          alt=""
          className={compact ? "border-line h-9 w-9 shrink-0 rounded-md border object-cover" : "border-line h-10 w-10 shrink-0 rounded-md border object-cover"}
        />
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          void handleFile(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="secondary"
        size="md"
        disabled={uploading}
        onClick={() => inputRef.current?.click()}
        className="shrink-0"
      >
        <Upload size={14} /> {uploading ? "Uploading…" : "Upload"}
      </Button>
    </div>
  );
}

function SectionSaveBar({ saving, onSave }: { saving: boolean; onSave: () => void }) {
  return (
    <div className="border-line mt-space-4 pt-space-3 flex justify-end border-t">
      <Button variant="secondary" size="md" disabled={saving} onClick={onSave}>
        {saving ? "Saving…" : "Save"}
      </Button>
    </div>
  );
}

function SectionToggle({ enabled, onChange }: { enabled: boolean; onChange: (enabled: boolean) => void }) {
  return (
    <div className="gap-space-2 mt-space-1 flex items-center">
      <Switch checked={enabled} onChange={() => onChange(!enabled)} />
      <span className="text-ink-900 text-[13px] font-medium">Show this section</span>
    </div>
  );
}

function AddButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <Button variant="secondary" size="md" onClick={onClick} className="mt-space-3">
      <Plus size={14} /> {label}
    </Button>
  );
}

function DeleteButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="text-error shrink-0">
      <Trash2 size={15} />
    </button>
  );
}

function TestimonialsEditor({
  enabled, items, onToggle, onChange,
}: {
  enabled: boolean;
  items: TestimonialItem[];
  onToggle: (enabled: boolean) => void;
  onChange: (items: TestimonialItem[]) => void;
}) {
  return (
    <>
      <SectionToggle enabled={enabled} onChange={onToggle} />
      <div className="mt-space-3 space-y-space-3">
        {items.map((item, i) => (
          <Card key={item.id} className="p-space-3">
            <div className="gap-space-2 flex items-start">
              <div className="flex-1 space-y-space-2">
                <Input
                  value={item.name}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, name: e.target.value };
                    onChange(next);
                  }}
                  placeholder="Patient name"
                />
                <Textarea
                  rows={2}
                  value={item.quote}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, quote: e.target.value };
                    onChange(next);
                  }}
                  placeholder="What they said"
                />
                <select
                  value={item.rating}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, rating: Number(e.target.value) };
                    onChange(next);
                  }}
                  className="border-line bg-card text-ink-900 h-9 rounded-md border px-2 text-[13px]"
                >
                  {[5, 4, 3, 2, 1].map((n) => (
                    <option key={n} value={n}>{n} stars</option>
                  ))}
                </select>
              </div>
              <DeleteButton onClick={() => onChange(items.filter((_, idx) => idx !== i))} />
            </div>
          </Card>
        ))}
      </div>
      <AddButton
        label="Add testimonial"
        onClick={() => onChange([...items, { id: newId(), name: "", quote: "", rating: 5 }])}
      />
    </>
  );
}

function RecoveryStoriesEditor({
  enabled, items, onToggle, onChange, uploadImage,
}: {
  enabled: boolean;
  items: RecoveryStoryItem[];
  onToggle: (enabled: boolean) => void;
  onChange: (items: RecoveryStoryItem[]) => void;
  uploadImage: (file: File) => Promise<string>;
}) {
  return (
    <>
      <SectionToggle enabled={enabled} onChange={onToggle} />
      <div className="mt-space-3 space-y-space-3">
        {items.map((item, i) => (
          <Card key={item.id} className="p-space-3">
            <div className="gap-space-2 flex items-start">
              <div className="flex-1 space-y-space-2">
                <Input
                  value={item.title}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, title: e.target.value };
                    onChange(next);
                  }}
                  placeholder="Title"
                />
                <Textarea
                  rows={2}
                  value={item.description}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, description: e.target.value };
                    onChange(next);
                  }}
                  placeholder="Description"
                />
                <ImageUploadField
                  value={item.image_url}
                  onChange={(image_url) => {
                    const next = [...items];
                    next[i] = { ...item, image_url };
                    onChange(next);
                  }}
                  uploadImage={uploadImage}
                  placeholder="https://…/image.jpg (optional)"
                  compact
                />
              </div>
              <DeleteButton onClick={() => onChange(items.filter((_, idx) => idx !== i))} />
            </div>
          </Card>
        ))}
      </div>
      <AddButton
        label="Add story"
        onClick={() => onChange([...items, { id: newId(), title: "", description: "", image_url: "" }])}
      />
    </>
  );
}

function NewsEditor({
  enabled, items, onToggle, onChange, uploadImage,
}: {
  enabled: boolean;
  items: NewsItem[];
  onToggle: (enabled: boolean) => void;
  onChange: (items: NewsItem[]) => void;
  uploadImage: (file: File) => Promise<string>;
}) {
  return (
    <>
      <SectionToggle enabled={enabled} onChange={onToggle} />
      <div className="mt-space-3 space-y-space-3">
        {items.map((item, i) => (
          <Card key={item.id} className="p-space-3">
            <div className="gap-space-2 flex items-start">
              <div className="flex-1 space-y-space-2">
                <Input
                  value={item.title}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, title: e.target.value };
                    onChange(next);
                  }}
                  placeholder="Title"
                />
                <Textarea
                  rows={2}
                  value={item.summary}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, summary: e.target.value };
                    onChange(next);
                  }}
                  placeholder="Summary"
                />
                <Input
                  value={item.link}
                  onChange={(e) => {
                    const next = [...items];
                    next[i] = { ...item, link: e.target.value };
                    onChange(next);
                  }}
                  placeholder="https://… (optional link)"
                />
                <ImageUploadField
                  value={item.image_url}
                  onChange={(image_url) => {
                    const next = [...items];
                    next[i] = { ...item, image_url };
                    onChange(next);
                  }}
                  uploadImage={uploadImage}
                  placeholder="https://…/image.jpg (optional)"
                  compact
                />
              </div>
              <DeleteButton onClick={() => onChange(items.filter((_, idx) => idx !== i))} />
            </div>
          </Card>
        ))}
      </div>
      <AddButton
        label="Add news item"
        onClick={() => onChange([...items, { id: newId(), title: "", summary: "", link: "", image_url: "" }])}
      />
    </>
  );
}

function CareersEditor({
  openings, onChange,
}: {
  openings: CareerOpening[];
  onChange: (openings: CareerOpening[]) => void;
}) {
  return (
    <div className="mt-space-3">
      <p className="text-label mb-space-2">Openings</p>
      <div className="space-y-space-3">
        {openings.map((item, i) => (
          <Card key={item.id} className="p-space-3">
            <div className="gap-space-2 flex items-start">
              <div className="flex-1 space-y-space-2">
                <Input
                  value={item.title}
                  onChange={(e) => {
                    const next = [...openings];
                    next[i] = { ...item, title: e.target.value };
                    onChange(next);
                  }}
                  placeholder="Job title"
                />
                <Textarea
                  rows={2}
                  value={item.description}
                  onChange={(e) => {
                    const next = [...openings];
                    next[i] = { ...item, description: e.target.value };
                    onChange(next);
                  }}
                  placeholder="Description"
                />
                <Input
                  value={item.link}
                  onChange={(e) => {
                    const next = [...openings];
                    next[i] = { ...item, link: e.target.value };
                    onChange(next);
                  }}
                  placeholder="https://… (optional apply link)"
                />
              </div>
              <DeleteButton onClick={() => onChange(openings.filter((_, idx) => idx !== i))} />
            </div>
          </Card>
        ))}
      </div>
      <AddButton
        label="Add opening"
        onClick={() => onChange([...openings, { id: newId(), title: "", description: "", link: "" }])}
      />
    </div>
  );
}
