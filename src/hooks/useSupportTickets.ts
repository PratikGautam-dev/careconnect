import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { staffFetch } from "@/lib/staffAuth";
import { unwrapPortalResult } from "@/lib/portalMutation";

export type TicketPriority = "low" | "medium" | "high" | "urgent";
export type TicketStatus = "open" | "in_process" | "on_hold" | "completed";

export type SupportTicketCategoryOption = { id: number; name: string };

export type MySupportTicketRow = {
  id: number;
  ticket_number: string;
  subject: string;
  question: string;
  problem_reference: string | null;
  priority: TicketPriority;
  status: TicketStatus;
  category_id: number | null;
  category_name: string | null;
  has_attachment: boolean;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

/** "Raise a Ticket" page's own table -- this caller's own past tickets at
 * their own hospital, most recent first (portal/routes/support_tickets.py's
 * GET .../mine). Read-only -- there's no status-change action here, review
 * stays the platform super admin's own surface. */
export function useMySupportTickets(enabled: boolean) {
  const router = useRouter();

  const { data, error, refetch } = useQuery({
    queryKey: ["portal-my-support-tickets"],
    enabled,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/support-tickets/mine");
      return unwrapPortalResult<{ tickets: MySupportTicketRow[] }>(router, result);
    },
  });

  return {
    tickets: data?.tickets ?? null,
    error: error ? "Couldn't load your tickets." : null,
    load: refetch,
  };
}

/** "Raise a Ticket" form's category dropdown -- active categories only,
 * managed on the platform super-admin side (admin/support_tickets_api.py),
 * not by this hospital's own portal admin. */
export function useSupportTicketCategories(enabled: boolean) {
  const router = useRouter();

  const { data, error } = useQuery({
    queryKey: ["portal-support-ticket-categories"],
    enabled,
    retry: false,
    queryFn: async () => {
      const result = await staffFetch("/api/portal/support-tickets/categories");
      return unwrapPortalResult<{ categories: SupportTicketCategoryOption[] }>(router, result);
    },
  });

  return {
    categories: data?.categories ?? [],
    error: error ? "Couldn't load ticket categories." : null,
  };
}
