"use client";

import {
  Bell, Boxes, ChevronRight, Coins, Globe, Pill, Printer, Settings as SettingsIcon, Store, Tag, Users,
} from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { PortalShell } from "@/components/portal/PortalShell";
import { StatTile } from "@/components/portal/StatTile";
import { StatTileGrid } from "@/components/portal/StatTileGrid";
import { usePortalGuard } from "@/components/portal/usePortalGuard";
import { usePermission } from "@/lib/staffAuth";
import { useMedicines } from "@/hooks/usePharmacyMedicines";
import { usePharmacyCategories, usePharmacyUnits } from "@/hooks/usePharmacySettings";

type Tile = { href: string; icon: typeof Store; title: string; description: string };

const TILES: Tile[] = [
  { href: "/portal/settings/roles", icon: Users, title: "Users & Roles", description: "Create users, assign roles, and manage access permissions across pharmacy operations." },
  { href: "/portal/pharmacy/inventory", icon: Pill, title: "Medicine Master", description: "Add, update, and manage medicines, brands, compositions, and related details." },
  { href: "/portal/pharmacy/settings/profile", icon: Store, title: "Pharmacy Profile", description: "Manage pharmacy details, branch info, contact, and operational timings." },
  { href: "/portal/pharmacy/settings/categories", icon: Tag, title: "Categories", description: "Create and manage medicine categories (e.g., Tablets, Capsules, Injections, etc.)." },
  { href: "/portal/pharmacy/settings/units", icon: Boxes, title: "Units & Dosage", description: "Configure units, dosage forms, strengths, and pack sizes (e.g., mg, ml, strip, vial)." },
  { href: "/portal/pharmacy/settings/pricing", icon: Coins, title: "Pricing & Taxes", description: "Manage sale price, discounts, and tax rates (GST) applied to pharmacy sales." },
  { href: "/portal/pharmacy/settings/alerts", icon: Bell, title: "Alerts & Thresholds", description: "Set low-stock alerts, expiry thresholds, and other critical notifications." },
  { href: "/portal/pharmacy/settings/integrations", icon: Globe, title: "Integrations", description: "Configure integrations with EMR, Billing, Finance, and other hospital systems." },
  { href: "/portal/pharmacy/settings/print", icon: Printer, title: "Print Settings", description: "Customize and manage print templates for bills, labels, and prescriptions." },
];

export default function PharmacySettingsPage() {
  const { hospital, ready } = usePortalGuard();
  const canView = usePermission("pharmacy", "view");
  const { medicines } = useMedicines(ready);
  const { categories } = usePharmacyCategories(ready);
  const { units } = usePharmacyUnits(ready);

  if (!hospital) return null;
  if (!canView) {
    return (
      <PortalShell hospital={hospital} active="pharmacy-settings">
        <p className="text-hint text-[13px]">You don&apos;t have access to this page.</p>
      </PortalShell>
    );
  }

  return (
    <PortalShell hospital={hospital} active="pharmacy-settings">
      <PageHeader title="Settings" description="Configure pharmacy operations, masters, billing, alerts, and system preferences." />

      <StatTileGrid cols={3} className="mb-space-5">
        <StatTile label="Medicines Configured" value={medicines.length} icon={Pill} tint="brand" />
        <StatTile label="Categories" value={categories.length} icon={Tag} tint="clay" />
        <StatTile label="Units & Dosage Forms" value={units.length} icon={Boxes} tint="success" />
      </StatTileGrid>

      <div className="gap-space-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {TILES.map((tile) => (
          <Link key={tile.href} href={tile.href}>
            <Card className="p-space-4 hover:border-brand-300 h-full transition-colors duration-150">
              <div className="mb-space-3 flex items-start justify-between">
                <span className="bg-brand-50 text-brand-600 flex h-10 w-10 items-center justify-center rounded-lg">
                  <tile.icon size={20} />
                </span>
                <ChevronRight size={16} className="text-ink-400 mt-space-2" />
              </div>
              <p className="text-ink-900 mb-space-1 text-[14px] font-bold">{tile.title}</p>
              <p className="text-hint text-[12px]">{tile.description}</p>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="p-space-4 mt-space-4">
        <div className="gap-space-3 flex items-start">
          <span className="bg-brand-50 text-brand-600 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg">
            <SettingsIcon size={20} />
          </span>
          <div className="flex-1">
            <Link href="/portal/pharmacy/settings/system" className="text-ink-900 text-[14px] font-bold hover:underline">
              System Preferences
            </Link>
            <p className="text-hint mt-space-1 text-[12px]">Set general pharmacy preferences, numbering formats, and other system-level settings.</p>
          </div>
          <Link href="/portal/pharmacy/settings/system">
            <ChevronRight size={16} className="text-ink-400 mt-space-2" />
          </Link>
        </div>
      </Card>
    </PortalShell>
  );
}
