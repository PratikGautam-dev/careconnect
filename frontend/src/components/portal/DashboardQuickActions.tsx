import { FlaskConical, Megaphone, Plus, UserPlus, FileDown } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { QuickActionButton } from "./QuickActionButton";

type Action = {
  label: string;
  icon: typeof Plus;
} & ({ href: string } | { disabled: true });

// Add doctor/Add staff/Create test navigate to the existing management
// pages, which already own their add-forms. Broadcast/Export have no
// backend anywhere in this app -- disabled, same "Coming soon" convention
// PortalSidebar uses for its own unbuilt nav items.
const ACTIONS: Action[] = [
  { label: "Add doctor", icon: UserPlus, href: "/portal/doctors" },
  { label: "Add staff", icon: Plus, href: "/portal/settings/staff" },
  { label: "Broadcast message", icon: Megaphone, disabled: true },
  { label: "Create test", icon: FlaskConical, href: "/portal/settings" },
  { label: "Export report", icon: FileDown, disabled: true },
];

export function DashboardQuickActions() {
  return (
    <Card className="p-space-4">
      <h3 className="text-label mb-space-3 font-bold text-ink-900">Quick actions</h3>
      <div className="space-y-space-2">
        {ACTIONS.map((action) =>
          "disabled" in action ? (
            <QuickActionButton key={action.label} label={action.label} icon={action.icon} disabled />
          ) : (
            <QuickActionButton key={action.label} label={action.label} icon={action.icon} href={action.href} />
          ),
        )}
      </div>
    </Card>
  );
}
