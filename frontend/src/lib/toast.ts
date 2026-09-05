import { Toast } from "@base-ui/react/toast";

// Module-level singleton (not a hook) so any hook/handler can fire a toast
// -- e.g. right after a staffFetch() call in a data hook -- without needing
// to render inside a React component. <Toaster/> (mounted once in the root
// layout) passes this same manager to Toast.Provider so its state drives
// what's actually rendered.
export const toastManager = Toast.createToastManager();

export const toast = {
  success: (title: string, description?: string) => toastManager.add({ type: "success", title, description }),
  error: (title: string, description?: string) => toastManager.add({ type: "error", title, description }),
};
