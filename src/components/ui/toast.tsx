"use client";

import { Toast as ToastPrimitive } from "@base-ui/react/toast";
import { CheckCircle2, X, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { toastManager } from "@/lib/toast";

const TYPE_ICON = { success: CheckCircle2, error: XCircle } as const;
const TYPE_ICON_CLASS: Record<string, string> = { success: "text-success", error: "text-error" };

function ToastItem({ toast }: { toast: ToastPrimitive.Root.ToastObject }) {
  const Icon = TYPE_ICON[toast.type as keyof typeof TYPE_ICON] ?? CheckCircle2;
  return (
    <ToastPrimitive.Root
      toast={toast}
      className={cn(
        "gap-space-2 border-line bg-card p-space-3 pointer-events-auto flex w-full max-w-sm items-start rounded-lg border shadow-[var(--shadow-lg)]",
        "transition-all duration-200 ease-out",
        "data-[starting-style]:translate-y-2 data-[starting-style]:opacity-0",
        "data-[ending-style]:translate-y-2 data-[ending-style]:opacity-0",
      )}
    >
      <Icon
        size={18}
        className={cn("mt-0.5 shrink-0", TYPE_ICON_CLASS[toast.type ?? ""] ?? "text-ink-600")}
      />
      <ToastPrimitive.Content className="min-w-0 flex-1">
        {toast.title && (
          <ToastPrimitive.Title className="text-ink-900 text-[13.5px] font-semibold" />
        )}
        {toast.description && (
          <ToastPrimitive.Description className="text-ink-600 mt-0.5 text-[12.5px]" />
        )}
      </ToastPrimitive.Content>
      <ToastPrimitive.Close
        aria-label="Dismiss"
        className="text-ink-400 hover:text-ink-700 shrink-0 rounded-md p-0.5 hover:bg-black/[0.04]"
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
      <ToastPrimitive.Viewport className="gap-space-2 p-space-4 pointer-events-none fixed inset-x-0 bottom-0 z-100 flex flex-col items-center sm:inset-x-auto sm:right-0 sm:items-end">
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
