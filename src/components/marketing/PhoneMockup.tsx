import { ArrowLeft, BadgeCheck, Camera, Mic, MoreVertical, Signal, Wifi, BatteryFull } from "lucide-react";

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
      className="mx-auto w-full max-w-70 rounded-[36px] bg-[#0E0E10] p-space-2 shadow-lg transition-transform duration-150 ease-(--ease-standard) hover:-translate-y-1 sm:max-w-78"
      aria-hidden="true"
    >
      <div className="flex aspect-312/600 flex-col overflow-hidden rounded-[26px] bg-[#EDE6DA]">
        {/* Status bar */}
        <div className="flex items-center justify-between px-space-4 pt-space-2 pb-1 text-[11px] font-semibold text-white bg-brand-600">
          <span>11:41</span>
          <div className="flex items-center gap-1">
            <Signal size={12} strokeWidth={2.5} />
            <Wifi size={12} strokeWidth={2.5} />
            <BatteryFull size={14} strokeWidth={2} />
          </div>
        </div>

        {/* Chat header */}
        <div className="flex items-center gap-space-2 bg-brand-600 px-space-3 pb-space-2 text-white">
          <ArrowLeft size={18} strokeWidth={2} className="shrink-0 text-white/90" />
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-[13px] font-extrabold text-brand-600">
            H
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <span className="flex items-center gap-1">
              <strong className="truncate text-[13.5px]">ABC Hospital</strong>
              <BadgeCheck size={13} className="shrink-0 fill-white text-brand-600" />
            </span>
            <span className="block text-[10px] tracking-wide text-[#D9E9E1] uppercase">Business Account</span>
          </div>
          <MoreVertical size={18} strokeWidth={2} className="shrink-0 text-white/90" />
        </div>

        <div className="flex-1 overflow-hidden p-space-3">
          <div className="max-w-[92%] rounded-[10px] bg-white p-space-3 text-[12.5px] leading-relaxed font-semibold text-ink-900 shadow-[0_1px_1px_rgba(0,0,0,0.06)]">
            Hi! Welcome to ABC Hospital.
            <br />
            How can we help you today?
            <br />
            Please choose an option below.
            <ol className="mt-space-1 list-decimal space-y-0.5 pl-space-4">
              {MENU_ITEMS.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ol>
            <span className="mt-space-1 block text-right text-[10px] font-normal text-ink-400">10:30 AM</span>
          </div>
        </div>

        <div className="flex items-center gap-space-2 border-t border-line bg-[#F7F5F0] px-space-3 py-space-2">
          <div className="flex flex-1 items-center justify-between rounded-full bg-white px-space-3 py-1.5 shadow-[0_1px_1px_rgba(0,0,0,0.05)]">
            <span className="text-[12.5px] text-ink-400">Type a message</span>
            <Camera size={16} strokeWidth={2} className="shrink-0 text-ink-400" />
          </div>
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white">
            <Mic size={14} strokeWidth={2} />
          </div>
        </div>
      </div>
    </div>
  );
}
