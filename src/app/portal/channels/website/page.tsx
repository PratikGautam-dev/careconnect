"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink, Globe } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Switch } from "@/components/ui/Switch";
import { PortalShell } from "@/components/portal/PortalShell";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { formatShortDateTime } from "@/lib/formatDate";
import { hasPermission, useStaffSession } from "@/lib/staffAuth";
import { useBookingChannels } from "@/hooks/useBookingChannels";
import { useSiteEditor } from "@/hooks/useSiteEditor";

/** Scales an iframe down to fit its wrapper -- same technique the editor
 * page's own preview pane uses, just a wider design width (this is a
 * real site hero preview, not a narrow mobile-widget card). */
function SitePreview({ src }: { src: string }) {
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
    <div ref={box} className="relative h-[560px] overflow-hidden">
      {scale > 0 && (
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

/** Config page for the Website booking channel -- same "big live preview
 * hero card, overlaid site info + edit button" shape ShopConnect's own
 * Website channel page uses, rather than a small side-by-side status card.
 * The on/off toggle (PATCH /api/portal/channels/website-booking) moved up
 * into the page header; appearance/section editing lives in the separate
 * draft/publish-versioned editor (/portal/channels/website/editor). */
export default function WebsiteChannelPage() {
  const { hospital, ready } = usePortalGuard();
  const session = useStaffSession();
  const { info, error, websiteBookingEnabled, setWebsiteBookingEnabled, togglingWebsite } =
    useBookingChannels(ready);
  const { hasUnpublishedChanges, isPublished, publishedAt } = useSiteEditor(ready);
  const canManage = hasPermission(session, "settings", "write");

  if (!hospital) return null;

  // The separate careconnect-site project's own origin -- its marketing
  // homepage (/site/[id]) is the real public "front door" patients land
  // on; the bare booking widget in THIS app (/book/[id]) is one click away
  // from there, not the link shown here anymore.
  const siteAppUrl = process.env.NEXT_PUBLIC_SITE_APP_URL || "http://localhost:3001";
  const publicUrl = info?.display_id ? `${siteAppUrl}/site/${info.display_id}` : null;
  const canPreview = websiteBookingEnabled && isPublished && publicUrl;

  return (
    <PortalShell hospital={hospital} active="channels-website">
      <PageHeader
        title="Website"
        description="Customize and publish your hospital's public website."
        actions={
          <>
            {canManage && (
              <div className="gap-space-2 flex items-center">
                <span className="text-ink-600 text-[11.5px] font-bold uppercase">
                  {websiteBookingEnabled ? "On" : "Off"}
                </span>
                <Switch
                  checked={websiteBookingEnabled}
                  onChange={() => setWebsiteBookingEnabled(!websiteBookingEnabled)}
                  disabled={togglingWebsite}
                />
              </div>
            )}
            {publicUrl && (
              <Button href={publicUrl} target="_blank" rel="noopener noreferrer" variant="secondary">
                <ExternalLink size={14} /> View Website
              </Button>
            )}
          </>
        }
      />

      {error && <p className="mb-space-4 text-error text-[13px]">{error}</p>}

      <Card className="relative overflow-hidden bg-ink-900 p-0">
        {canPreview ? (
          <SitePreview src={publicUrl} />
        ) : (
          <div className="flex h-[560px] flex-col items-center justify-center text-center">
            <Globe size={32} className="text-white/30" />
            <p className="mt-space-3 text-[14px] font-semibold text-white">
              {!websiteBookingEnabled ? "Website booking is off" : "Nothing published yet"}
            </p>
            <p className="text-hint mt-space-1 max-w-xs text-[12.5px] text-white/50">
              {!websiteBookingEnabled
                ? "Turn it on above to preview and publish your public website."
                : "Customize your website and publish it to make it live."}
            </p>
          </div>
        )}

        {/* Bottom info/action bar, overlaid on the preview */}
        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-black/70 to-transparent p-space-4">
          <div>
            <p className="text-[14px] font-bold text-white">{hospital.name}</p>
            <p className="text-[12px] text-white/70">
              {isPublished && publishedAt
                ? `Published: ${formatShortDateTime(publishedAt)}`
                : "Not published yet"}
              {hasUnpublishedChanges && canManage && " · Unpublished changes"}
            </p>
          </div>
          {canManage && (
            <Button href="/portal/channels/website/editor" variant="primary">
              Customize Website
            </Button>
          )}
        </div>
      </Card>
    </PortalShell>
  );
}
