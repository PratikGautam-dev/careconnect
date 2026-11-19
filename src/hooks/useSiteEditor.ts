import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

export type TestimonialItem = { id: string; name: string; quote: string; rating: number };
export type RecoveryStoryItem = { id: string; title: string; description: string; image_url: string };
export type NewsItem = { id: string; title: string; summary: string; link: string; image_url: string };
export type CareerOpening = { id: string; title: string; description: string; link: string };

export type SectionKey =
  | "feature_cards" | "about" | "departments" | "services"
  | "testimonials" | "recovery_stories" | "news" | "careers" | "contact";

/** Must stay in sync by hand with careconnect-backend's
 * db/repositories/site_config.py::default_site_config() -- the one
 * backend source of truth for this shape, two separate codebases. */
export type SiteConfig = {
  brand: { logo_url: string; cover_image_url: string; tagline: string };
  sections: {
    feature_cards: { enabled: boolean };
    about: { enabled: boolean; text: string };
    departments: { enabled: boolean };
    services: { enabled: boolean };
    testimonials: { enabled: boolean; items: TestimonialItem[] };
    recovery_stories: { enabled: boolean; items: RecoveryStoryItem[] };
    news: { enabled: boolean; items: NewsItem[] };
    careers: { enabled: boolean; text: string; openings: CareerOpening[] };
    contact: { enabled: boolean };
  };
  section_order: SectionKey[];
};

type SiteConfigState = {
  draft_config: SiteConfig;
  draft_version: number;
  published_config: SiteConfig | null;
  published_version: number | null;
  published_at: string | null;
};

const QUERY_KEY = ["portal-site-config"];

/** Draft/publish/preview for the Website channel's theme editor
 * (src/app/portal/channels/website/editor/page.tsx) -- mirrors
 * careconnect-backend's portal/routes/site_editor.py exactly: load once,
 * edit a local draft copy, Save Draft (optimistic-concurrency versioned),
 * Publish, and a one-off preview-token fetch for the live preview pane. */
export function useSiteEditor(ready: boolean) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/channels/website/site-config");
      return unwrapPortalResult<SiteConfigState>(router, result);
    },
  });

  const [seeded, setSeeded] = useState(false);
  const [draft, setDraft] = useState<SiteConfig | null>(null);
  const [draftVersion, setDraftVersion] = useState(0);
  if (data && !seeded) {
    setSeeded(true);
    setDraft(data.draft_config);
    setDraftVersion(data.draft_version);
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error("Nothing to save.");
      const result = await portalFetch("/api/portal/channels/website/site-config/draft", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config: draft, version: draftVersion }),
      });
      return unwrapPortalResult<SiteConfigState>(router, result);
    },
    onSuccess: (result) => {
      setDraftVersion(result.draft_version);
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success("Draft saved");
    },
    onError: (err) => {
      if (!isPortalMutationError(err)) return;
      // A 409 conflict (someone else saved first) -- reload the server's
      // latest draft rather than silently overwriting it; the admin's own
      // in-progress edits are lost here, which is the right tradeoff for
      // "don't clobber someone else's save" over "never lose an edit."
      toast.error("Couldn't save draft", err.message);
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      setSeeded(false);
    },
  });

  const publishMutation = useMutation({
    mutationFn: async () => {
      const result = await portalFetch("/api/portal/channels/website/site-config/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ version: draftVersion }),
      });
      return unwrapPortalResult<SiteConfigState>(router, result);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success("Website published");
    },
    onError: (err) => {
      if (isPortalMutationError(err)) toast.error("Couldn't publish", err.message);
    },
  });

  async function fetchPreviewToken(): Promise<string | null> {
    const result = await portalFetch("/api/portal/channels/website/site-config/preview-token", {
      method: "POST",
    });
    if (!result.ok) return null;
    return (result.data as { token: string }).token;
  }

  /** Used by every image field on the editor (logo, cover, recovery-story/
   * news thumbnails) -- uploads straight to careconnect-backend's public
   * asset storage (core/storage.py's upload_public()) and returns a
   * permanent URL to drop into the corresponding field, same as if the
   * admin had pasted one in by hand. No Content-Type header set here on
   * purpose: axios auto-detects a FormData body and sets its own
   * multipart boundary -- forcing one would break the upload. */
  async function uploadImage(file: File): Promise<string> {
    const body = new FormData();
    body.append("file", file);
    const result = await portalFetch("/api/portal/channels/website/site-config/upload-image", {
      method: "POST",
      body,
    });
    if (!result.ok) {
      throw new Error(!result.unauthorized ? result.error : "Not authenticated.");
    }
    return (result.data as { url: string }).url;
  }

  const hasUnpublishedChanges = data ? data.draft_version !== data.published_version : false;

  return {
    draft,
    setDraft,
    draftVersion,
    error: error ? "Couldn't load website settings — try again." : null,
    isLoading,
    hasUnpublishedChanges,
    isPublished: Boolean(data?.published_version),
    publishedAt: data?.published_at ?? null,
    // mutateAsync (not mutate) -- the editor page awaits this to know
    // exactly when the server's draft actually changed, so it can force
    // the live-preview iframe to refetch right after, not on some
    // unrelated timer.
    saveDraft: () => saveMutation.mutateAsync(),
    saving: saveMutation.isPending,
    publish: () => publishMutation.mutate(),
    publishing: publishMutation.isPending,
    fetchPreviewToken,
    uploadImage,
  };
}
