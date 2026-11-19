import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { portalFetch } from "@/lib/portalAuth";
import { isPortalMutationError, unwrapPortalResult } from "@/lib/portalMutation";
import { toast } from "@/lib/toast";

/** The slice of GET /api/portal/settings the three Booking Channels pages
 * (src/app/portal/channels/{whatsapp,website,walk-in}/page.tsx) need --
 * read-only hospital identifiers (display_id/whatsapp_phone_number_id) plus
 * enabled_features, which website_booking's on/off state lives in. The
 * public site's own appearance/content (logo/cover/tagline/sections) now
 * lives in useSiteEditor.ts instead -- a separate draft/publish-versioned
 * config, not a flat field on this settings object. */
export type ChannelsInfo = {
  display_id: string | null;
  whatsapp_phone_number_id: string | null;
  enabled_features: string[];
};

export function useBookingChannels(ready: boolean) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: ["portal-settings"],
    enabled: ready,
    retry: false,
    queryFn: async () => {
      const result = await portalFetch("/api/portal/settings");
      return unwrapPortalResult<ChannelsInfo>(router, result);
    },
  });

  const websiteToggleMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      const result = await portalFetch("/api/portal/channels/website-booking", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      return unwrapPortalResult<{ enabled: boolean }>(router, result);
    },
    onSuccess: () => {
      // Same cache key usePortalSettings' own GET uses -- a redeploy of
      // either page sees the other's write immediately, not just after a
      // hard refresh.
      queryClient.invalidateQueries({ queryKey: ["portal-settings"] });
      toast.success("Website booking updated");
    },
    onError: (err) => {
      if (isPortalMutationError(err)) toast.error("Couldn't update website booking", err.message);
    },
  });

  const whatsappToggleMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      const result = await portalFetch("/api/portal/channels/whatsapp-booking", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      return unwrapPortalResult<{ enabled: boolean }>(router, result);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portal-settings"] });
      toast.success("WhatsApp bot updated");
    },
    onError: (err) => {
      if (isPortalMutationError(err)) toast.error("Couldn't update WhatsApp bot", err.message);
    },
  });

  return {
    info: data ?? null,
    error: error ? "Couldn't load channel settings — try again." : null,
    isLoading,
    websiteBookingEnabled: data?.enabled_features.includes("website_booking") ?? false,
    setWebsiteBookingEnabled: (enabled: boolean) => websiteToggleMutation.mutate(enabled),
    togglingWebsite: websiteToggleMutation.isPending,
    // Opposite storage polarity -- see db.models.CHANNEL_FEATURE_WHATSAPP_DISABLED's
    // own docstring on the backend.
    whatsappBookingEnabled: !(data?.enabled_features.includes("whatsapp_booking_disabled") ?? false),
    setWhatsappBookingEnabled: (enabled: boolean) => whatsappToggleMutation.mutate(enabled),
    togglingWhatsapp: whatsappToggleMutation.isPending,
  };
}
