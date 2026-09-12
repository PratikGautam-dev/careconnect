"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export type SettingsTabKey =
  | "general"
  | "hospital-profile"
  | "departments"
  | "notifications"
  | "integrations"
  | "security";

export type SettingsTabDef = { key: SettingsTabKey; label: string; icon: LucideIcon };

type Props = {
  tabs: SettingsTabDef[];
  active: SettingsTabKey;
  onChange: (key: SettingsTabKey) => void;
};

/** Segmented tab bar for /portal/settings, matching the reference mockup's
 * pill-style row (General / Hospital Profile / Departments / Notifications /
 * Integrations / Security). Shared shell so each tab's content can be built
 * out independently, one reference screenshot at a time. */
export function SettingsTabsNav({ tabs, active, onChange }: Props) {
  return (
    <div className="mb-space-5 flex flex-wrap gap-space-1 rounded-lg border border-line bg-card p-space-1">
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={cn(
              "flex items-center gap-space-2 rounded-md px-space-3 py-space-2 text-[13px] font-semibold transition-colors duration-150",
              isActive ? "bg-brand-50 text-brand-700" : "text-ink-400 hover:bg-black/[0.04] hover:text-ink-700",
            )}
          >
            <tab.icon size={15} strokeWidth={2} />
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
