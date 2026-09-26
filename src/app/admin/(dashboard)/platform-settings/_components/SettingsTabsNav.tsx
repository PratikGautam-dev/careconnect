"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export type PlatformSettingsTabKey = "general" | "menu_labels" | "notifications" | "audit_logs";

export type PlatformSettingsTabDef = { key: PlatformSettingsTabKey; label: string; icon: LucideIcon };

type Props = {
  tabs: PlatformSettingsTabDef[];
  active: PlatformSettingsTabKey;
  onChange: (key: PlatformSettingsTabKey) => void;
};

/** Segmented pill-style tab bar for /admin/platform-settings -- same visual
 * pattern as /portal/settings' own SettingsTabsNav (each tab `flex-1` so
 * they stretch to fill the bar's full width evenly), kept as its own local
 * copy rather than a shared import since the two pages' tab vocabularies
 * are unrelated. */
export function SettingsTabsNav({ tabs, active, onChange }: Props) {
  return (
    <div className="mb-space-5 gap-space-1 border-line bg-card p-space-1 flex flex-wrap rounded-lg border">
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={cn(
              "gap-space-2 px-space-3 py-space-2 flex flex-1 items-center justify-center rounded-md text-[13px] font-semibold transition-colors duration-150",
              isActive
                ? "bg-brand-50 text-brand-700"
                : "text-ink-400 hover:text-ink-700 hover:bg-black/[0.04]",
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
