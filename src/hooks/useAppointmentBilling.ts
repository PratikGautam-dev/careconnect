import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "@/lib/adminAuth";
import { unwrapAdminResult } from "@/lib/adminMutation";

/** Super-admin Appointment Billing page (admin/appointment_billing_api.py)
 * -- reconciling patient-facing Razorpay collections
 * (payment_for='appointment') across every hospital, as opposed to
 * useAdminSubscriptions/useAdminBillingRecords' hospital->CareConnect SaaS
 * billing (payment_for='subscription'), a completely separate concept.
 * Read-only: there is no mutation here, refund approve/reject stays in the
 * hospital's own portal.
 *
 * Five INDEPENDENT hooks below, each its own query/loading state -- so a
 * slow refund-queue fetch, say, never blocks the stat tiles or the
 * hospital table from rendering the moment their own data arrives. */

export type AppointmentBillingFilters = {
  dateFrom: string; // bare ISO date, e.g. "2026-09-28"
  dateTo: string;
  hospitalId?: number;
};

export type AppointmentBillingStats = {
  gross_collected: number;
  online_collected: number;
  cash_collected: number;
  total_refunded: number;
  net_actual: number;
  platform_revenue: number;
  failed_count: number;
  failed_amount: number;
};

export type AppointmentBillingHospitalRow = {
  hospital_id: number;
  hospital_name: string;
  online_collected: number;
  cash_collected: number;
  total_collected: number;
  platform_gateway_collected: number;
  hospital_gateway_collected: number;
  platform_share: number;
  payable_to_hospital: number;
  payable_to_platform: number;
  refund_pending_count: number;
  refund_pending_amount: number;
};

export type AppointmentBillingPaymentRow = {
  id: number;
  hospital_id: number;
  hospital_name: string;
  appointment_id: number | null;
  patient_name: string | null;
  reference_id: string | null;
  amount: number;
  base_amount: number | null;
  gst_amount: number | null;
  platform_fee_amount: number | null;
  currency: string;
  method: "online" | "pay_at_hospital";
  status: "pending" | "paid" | "failed" | "expired" | "pay_at_hospital";
  gateway_account: "platform" | "hospital_own";
  razorpay_payment_id: string | null;
  refund_amount: number | null;
  created_at: string;
  paid_at: string | null;
};

export type AppointmentBillingTrendPoint = {
  date: string;
  gross_collected: number;
  refunded: number;
  net_actual: number;
  platform_revenue: number;
};

export type AppointmentBillingRefundRow = {
  id: number;
  hospital_id: number;
  hospital_name: string;
  appointment_id: number;
  payment_id: number;
  cancelled_by: "patient" | "hospital";
  reason: string | null;
  base_amount: number;
  deduction_amount: number;
  refund_amount: number;
  status: "pending_approval" | "approved" | "processing" | "completed" | "failed" | "rejected";
  razorpay_refund_id: string | null;
  failure_reason: string | null;
  created_at: string;
  processed_at: string | null;
  patient_name: string | null;
  patient_phone: string | null;
  reference_id: string | null;
  appointment_scheduled_at: string | null;
};

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export function useAppointmentBillingStats(filters: AppointmentBillingFilters) {
  const { dateFrom, dateTo, hospitalId } = filters;
  const { data, error } = useQuery({
    queryKey: ["admin-appointment-billing-stats", dateFrom, dateTo, hospitalId],
    retry: false,
    queryFn: async () => {
      const qs = buildQuery({ date_from: dateFrom, date_to: dateTo, hospital_id: hospitalId });
      const result = await adminFetch(`/api/admin/appointment-billing/stats${qs}`);
      return unwrapAdminResult<AppointmentBillingStats>(result);
    },
  });
  return { stats: data ?? null, error: error ? (error as Error).message : null };
}

export function useAppointmentBillingByHospital(
  filters: Pick<AppointmentBillingFilters, "dateFrom" | "dateTo"> & { method?: string },
  page: number,
  limit = 25,
) {
  const { dateFrom, dateTo, method } = filters;
  const { data, error } = useQuery({
    queryKey: ["admin-appointment-billing-hospitals", dateFrom, dateTo, method, page, limit],
    retry: false,
    queryFn: async () => {
      const qs = buildQuery({ date_from: dateFrom, date_to: dateTo, method, page, limit });
      const result = await adminFetch(`/api/admin/appointment-billing/hospitals${qs}`);
      return unwrapAdminResult<{ total: number; rows: AppointmentBillingHospitalRow[] }>(result);
    },
  });
  return {
    rows: data?.rows ?? null,
    total: data?.total ?? 0,
    error: error ? (error as Error).message : null,
  };
}

export function useAppointmentBillingPayments(
  filters: AppointmentBillingFilters & { method?: string; status?: string },
  page: number,
  limit = 25,
) {
  const { dateFrom, dateTo, hospitalId, method, status } = filters;
  const { data, error } = useQuery({
    queryKey: [
      "admin-appointment-billing-payments",
      dateFrom,
      dateTo,
      hospitalId,
      method,
      status,
      page,
      limit,
    ],
    retry: false,
    queryFn: async () => {
      const qs = buildQuery({
        date_from: dateFrom,
        date_to: dateTo,
        hospital_id: hospitalId,
        method,
        status,
        page,
        limit,
      });
      const result = await adminFetch(`/api/admin/appointment-billing/payments${qs}`);
      return unwrapAdminResult<{ total: number; rows: AppointmentBillingPaymentRow[] }>(result);
    },
  });
  return {
    rows: data?.rows ?? null,
    total: data?.total ?? 0,
    error: error ? (error as Error).message : null,
  };
}

export function useAppointmentBillingTrend(filters: AppointmentBillingFilters) {
  const { dateFrom, dateTo, hospitalId } = filters;
  const { data, error } = useQuery({
    queryKey: ["admin-appointment-billing-trend", dateFrom, dateTo, hospitalId],
    retry: false,
    queryFn: async () => {
      const qs = buildQuery({ date_from: dateFrom, date_to: dateTo, hospital_id: hospitalId });
      const result = await adminFetch(`/api/admin/appointment-billing/trend${qs}`);
      return unwrapAdminResult<{ trend: AppointmentBillingTrendPoint[] }>(result);
    },
  });
  return { trend: data?.trend ?? null, error: error ? (error as Error).message : null };
}

export function useAppointmentBillingRefundQueue(
  filters: AppointmentBillingFilters & { status?: string },
  page: number,
  limit = 25,
) {
  const { dateFrom, dateTo, hospitalId, status } = filters;
  const { data, error } = useQuery({
    queryKey: [
      "admin-appointment-billing-refund-queue",
      dateFrom,
      dateTo,
      hospitalId,
      status,
      page,
      limit,
    ],
    retry: false,
    queryFn: async () => {
      const qs = buildQuery({
        date_from: dateFrom,
        date_to: dateTo,
        hospital_id: hospitalId,
        status,
        page,
        limit,
      });
      const result = await adminFetch(`/api/admin/appointment-billing/refund-queue${qs}`);
      return unwrapAdminResult<{ total: number; rows: AppointmentBillingRefundRow[] }>(result);
    },
  });
  return {
    rows: data?.rows ?? null,
    total: data?.total ?? 0,
    error: error ? (error as Error).message : null,
  };
}
