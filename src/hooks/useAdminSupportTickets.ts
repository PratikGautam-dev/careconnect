import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";
import { toast } from "@/lib/toast";

export type TicketStatus = "open" | "in_process" | "on_hold" | "completed";
export type TicketPriority = "low" | "medium" | "high" | "urgent";

export type SupportTicketRow = {
  id: number;
  ticket_number: string;
  hospital_id: number;
  hospital_name: string;
  submitted_by_name: string | null;
  submitted_by_email: string;
  category_id: number | null;
  category_name: string | null;
  subject: string;
  question: string;
  problem_reference: string | null;
  priority: TicketPriority;
  status: TicketStatus;
  attachment_url: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

export type SupportTicketSummary = {
  total: number;
  open: number;
  in_process: number;
  on_hold: number;
  completed: number;
};

const TICKETS_QUERY_KEY = ["admin-support-tickets"] as const;

/** Cross-tenant Support Tickets review queue -- backs /admin/support-tickets
 * (and the dashboard's own placeholder card/tile). Any portal identity, in
 * any hospital, can submit one (portal/routes/support_tickets.py); this is
 * the ONLY place a submitted ticket is read or worked, never that
 * hospital's own portal admin. */
export function useAdminSupportTickets() {
  const queryClient = useQueryClient();

  const { data, error, refetch } = useQuery({
    queryKey: TICKETS_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/support-tickets");
      return unwrapAdminResult<{ tickets: SupportTicketRow[]; summary: SupportTicketSummary }>(
        result,
      );
    },
  });

  const statusMutation = useMutation({
    mutationFn: async ({ ticketId, status }: { ticketId: number; status: TicketStatus }) => {
      const result = await adminFetch(`/api/admin/support-tickets/${ticketId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      return unwrapAdminResult<{ ticket: SupportTicketRow }>(result);
    },
  });

  async function setStatus(ticketId: number, status: TicketStatus): Promise<boolean> {
    try {
      const { ticket } = await statusMutation.mutateAsync({ ticketId, status });
      queryClient.setQueryData(
        TICKETS_QUERY_KEY,
        (prev: { tickets: SupportTicketRow[]; summary: SupportTicketSummary } | undefined) =>
          prev
            ? { ...prev, tickets: prev.tickets.map((t) => (t.id === ticketId ? ticket : t)) }
            : prev,
      );
      toast.success("Ticket status updated");
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't update ticket status",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  return {
    tickets: data?.tickets ?? null,
    summary: data?.summary ?? null,
    error: error ? (error as Error).message : null,
    setStatus,
    updatingStatus: statusMutation.isPending,
    load: refetch,
  };
}

export type SupportTicketCategory = { id: number; name: string; is_active: boolean; created_at: string };

const CATEGORIES_QUERY_KEY = ["admin-support-ticket-categories"] as const;

/** Super-admin-owned lookup list backing the category management panel on
 * /admin/support-tickets -- not configurable by a hospital's own portal
 * admin. Portal's own "Raise a Ticket" form reads the active subset of the
 * same table via a separate, portal-scoped endpoint (useSupportTickets.ts). */
export function useAdminSupportTicketCategories() {
  const { data, error, refetch } = useQuery({
    queryKey: CATEGORIES_QUERY_KEY,
    retry: false,
    queryFn: async () => {
      const result = await adminFetch("/api/admin/support-ticket-categories");
      return unwrapAdminResult<{ categories: SupportTicketCategory[] }>(result);
    },
  });

  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      const result = await adminFetch("/api/admin/support-ticket-categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      return unwrapAdminResult<{ category: SupportTicketCategory }>(result);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      categoryId,
      payload,
    }: {
      categoryId: number;
      payload: { name?: string; is_active?: boolean };
    }) => {
      const result = await adminFetch(`/api/admin/support-ticket-categories/${categoryId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return unwrapAdminResult<{ category: SupportTicketCategory }>(result);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (categoryId: number) => {
      const result = await adminFetch(`/api/admin/support-ticket-categories/${categoryId}`, {
        method: "DELETE",
      });
      return unwrapAdminResult<{ status: string }>(result);
    },
  });

  async function create(name: string): Promise<boolean> {
    try {
      await createMutation.mutateAsync(name);
      toast.success("Category added");
      refetch();
      return true;
    } catch (err) {
      toast.error("Couldn't add category", err instanceof Error ? err.message : "Something went wrong.");
      return false;
    }
  }

  async function toggleActive(category: SupportTicketCategory): Promise<boolean> {
    try {
      await updateMutation.mutateAsync({
        categoryId: category.id,
        payload: { is_active: !category.is_active },
      });
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't update category",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  async function remove(category: SupportTicketCategory): Promise<boolean> {
    try {
      await deleteMutation.mutateAsync(category.id);
      toast.success(`"${category.name}" deleted`);
      refetch();
      return true;
    } catch (err) {
      toast.error(
        "Couldn't delete category",
        err instanceof Error ? err.message : "Something went wrong.",
      );
      return false;
    }
  }

  return {
    categories: data?.categories ?? null,
    error: error ? (error as Error).message : null,
    create,
    toggleActive,
    remove,
    creating: createMutation.isPending,
  };
}
