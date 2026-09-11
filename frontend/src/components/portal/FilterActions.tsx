import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/Button";

type Props = {
  onApply: () => void;
  onReset: () => void;
  /** Whether any filter (staged or already applied) has non-default content
   * -- callers compute this from their own filter fields, since the set of
   * fields (search/status/type/...) differs per page. */
  showReset: boolean;
  applyLabel?: string;
};

/** Shared Filter/Reset pair for every server-side-filtered list page (see
 * useAppointments.ts's staged draft/Apply/Reset pattern) -- Apply is what
 * actually sends the search/status/type/... draft state to the backend;
 * Reset only shows once there's something to clear. */
export function FilterActions({ onApply, onReset, showReset, applyLabel = "Apply Filter" }: Props) {
  return (
    <>
      <Button type="button" size="md" onClick={onApply}>
        <SlidersHorizontal size={14} /> {applyLabel}
      </Button>
      {showReset && (
        <Button type="button" variant="secondary" size="md" onClick={onReset}>
          Reset
        </Button>
      )}
    </>
  );
}
