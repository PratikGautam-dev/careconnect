"use client";

import { Toast as ToastPrimitive } from "@base-ui/react/toast";
import { CheckCircle2, X, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { toastManager } from "@/lib/toast";

const TYPE_ICON = { success: CheckCircle2, error: XCircle } as const;
// Solid, on-brand backgrounds (not the neutral card) -- success uses the
// app's own brand color, error uses the same red as every other error
// state (STATUS_STYLES, Badge, etc.), both always white text/icon/close
// regardless of light/dark mode.
const TYPE_BG_CLASS: Record<string, string> = { success: "bg-brand-600", error: "bg-error" };

function ToastItem({ toast }: { toast: ToastPrimitive.Root.ToastObject }) {
  const Icon = TYPE_ICON[toast.type as keyof typeof TYPE_ICON] ?? CheckCircle2;
  return (
    <ToastPrimitive.Root
      toast={toast}
      className={cn(
        "gap-space-2 p-space-3 pointer-events-auto flex w-full max-w-sm items-start rounded-lg text-white shadow-[var(--shadow-lg)]",
        TYPE_BG_CLASS[toast.type ?? ""] ?? "bg-brand-600",
        "transition-all duration-200 ease-out",
        "data-[starting-style]:translate-y-2 data-[starting-style]:opacity-0",
        "data-[ending-style]:translate-y-2 data-[ending-style]:opacity-0",
      )}
    >
      <Icon size={18} className="mt-0.5 shrink-0 text-white" />
      <ToastPrimitive.Content className="min-w-0 flex-1">
        {toast.title && <ToastPrimitive.Title className="text-[13.5px] font-semibold text-white" />}
        {toast.description && (
          <ToastPrimitive.Description className="mt-0.5 text-[12.5px] text-white/85" />
        )}
      </ToastPrimitive.Content>
      <ToastPrimitive.Close
        aria-label="Dismiss"
        className="shrink-0 rounded-md p-0.5 text-white/80 hover:bg-white/15 hover:text-white"
      >
        <X size={14} />
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  );
}

function ToastViewportContent() {
  const { toasts } = ToastPrimitive.useToastManager();
  return (
    <ToastPrimitive.Portal>
      <ToastPrimitive.Viewport className="gap-space-2 p-space-4 pointer-events-none fixed inset-x-0 top-0 z-100 flex flex-col items-center sm:inset-x-auto sm:right-0 sm:items-end">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} />
        ))}
      </ToastPrimitive.Viewport>
    </ToastPrimitive.Portal>
  );
}

export function Toaster() {
  return (
    <ToastPrimitive.Provider toastManager={toastManager}>
      <ToastViewportContent />
    </ToastPrimitive.Provider>
  );
}
