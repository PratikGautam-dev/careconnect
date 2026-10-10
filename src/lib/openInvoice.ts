import { toast } from "@/lib/toast";

/** Opens a Razorpay-hosted invoice page in a new tab when the row doesn't
 * have its URL stored yet and the backend has to resolve it first
 * (modules/invoices.py's lazy lookup). The blank tab is opened
 * SYNCHRONOUSLY inside the click, then pointed at the URL once it arrives
 * -- opening it only after the await would be blocked as a popup by most
 * browsers. A row that already has its URL should just render a plain
 * <a target="_blank"> link instead of calling this. */
export async function openResolvedInvoice(resolve: () => Promise<string | null>): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const url = await resolve();
    if (url && tab) {
      tab.opener = null;
      tab.location.href = url;
      return;
    }
    tab?.close();
    toast.error("No invoice available", "Razorpay has no invoice for this payment.");
  } catch (err) {
    tab?.close();
    toast.error(
      "Couldn't open invoice",
      err instanceof Error ? err.message : "Something went wrong.",
    );
  }
}
