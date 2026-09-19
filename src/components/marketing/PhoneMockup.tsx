import {
  ArrowLeft,
  BadgeCheck,
  Camera,
  Mic,
  MoreVertical,
  Signal,
  Wifi,
  BatteryFull,
} from "lucide-react";

const MENU_ITEMS = [
  "Book an appointment",
  "Reschedule appointment",
  "Cancel appointment",
  "My appointments",
  "Hospital information",
  "Talk to reception",
];

export function PhoneMockup() {
  return (
    <div
      className="p-space-2 mx-auto w-full max-w-70 rounded-[36px] bg-[#0E0E10] shadow-lg transition-transform duration-150 ease-(--ease-standard) hover:-translate-y-1 sm:max-w-78"
      aria-hidden="true"
    >
      <div className="flex aspect-312/600 flex-col overflow-hidden rounded-[26px] bg-[#EDE6DA]">
        {/* Status bar */}
        <div className="px-space-4 pt-space-2 bg-brand-600 flex items-center justify-between pb-1 text-[11px] font-semibold text-white">
          <span>11:41</span>
          <div className="flex items-center gap-1">
            <Signal size={12} strokeWidth={2.5} />
            <Wifi size={12} strokeWidth={2.5} />
            <BatteryFull size={14} strokeWidth={2} />
          </div>
        </div>

        {/* Chat header */}
        <div className="gap-space-2 bg-brand-600 px-space-3 pb-space-2 flex items-center text-white">
          <ArrowLeft size={18} strokeWidth={2} className="shrink-0 text-white/90" />
          <div className="text-brand-600 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-[13px] font-extrabold">
            H
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <span className="flex items-center gap-1">
              <strong className="truncate text-[13.5px]">ABC Hospital</strong>
              <BadgeCheck size={13} className="text-brand-600 shrink-0 fill-white" />
            </span>
            <span className="block text-[10px] tracking-wide text-[#D9E9E1] uppercase">
              Business Account
            </span>
          </div>
          <MoreVertical size={18} strokeWidth={2} className="shrink-0 text-white/90" />
        </div>

        <div className="p-space-3 flex-1 overflow-hidden">
          <div className="p-space-3 text-ink-900 max-w-[92%] rounded-[10px] bg-white text-[12.5px] leading-relaxed font-semibold shadow-[0_1px_1px_rgba(0,0,0,0.06)]">
            Hi! Welcome to ABC Hospital.
            <br />
            How can we help you today?
            <br />
            Please choose an option below.
            <ol className="mt-space-1 pl-space-4 list-decimal space-y-0.5">
              {MENU_ITEMS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <span className="mt-space-1 text-ink-400 block text-right text-[10px] font-normal">
              10:30 AM
            </span>
          </div>
        </div>

        <div className="gap-space-2 border-line px-space-3 py-space-2 flex items-center border-t bg-[#F7F5F0]">
          <div className="px-space-3 flex flex-1 items-center justify-between rounded-full bg-white py-1.5 shadow-[0_1px_1px_rgba(0,0,0,0.05)]">
            <span className="text-ink-400 text-[12.5px]">Type a message</span>
            <Camera size={16} strokeWidth={2} className="text-ink-400 shrink-0" />
          </div>
          <div className="bg-brand-600 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white">
            <Mic size={14} strokeWidth={2} />
          </div>
        </div>
      </div>
    </div>
  );
}
