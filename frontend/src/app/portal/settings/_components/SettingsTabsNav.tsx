"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export type SettingsTabKey = "general" | "departments" | "notifications" | "attendance";

export type SettingsTabDef = { key: SettingsTabKey; label: string; icon: LucideIcon };

type Props = {
  tabs: SettingsTabDef[];
  active: SettingsTabKey;
  onChange: (key: SettingsTabKey) => void;
};

/** Segmented tab bar for /portal/settings, matching the reference mockup's
 * pill-style row -- originally General / Departments / Notifications /
 * Integrations / Security, but Hospital Profile, Integrations, and
 * Security were all removed entirely (not left as unbuilt placeholders):
 * Hospital Profile's real fields moved elsewhere (Hospital Name + Contact
 * Information to General, Bed Capacity to a "Manage Beds" dialog on the
 * Daycare Appointments page); Integrations/Security never had any real
 * content of their own (Google Calendar, briefly Integrations' only
 * occupant, now lives in General too). Down to 3 tabs, each `flex-1` so
 * they stretch to fill the bar's full width evenly rather than clustering
 * to the left with empty space on the right. Shared shell so each tab's
 * content can be built out independently, one reference screenshot at a
 * time. */
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
              "flex flex-1 items-center justify-center gap-space-2 rounded-md px-space-3 py-space-2 text-[13px] font-semibold transition-colors duration-150",
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
