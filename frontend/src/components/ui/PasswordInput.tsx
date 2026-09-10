"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { cn } from "@/lib/cn";

type PasswordInputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & { invalid?: boolean };

/** Password field with a show/hide toggle -- same eye/eye-off pattern
 * /portal/login's own password field established, pulled out here so a form
 * with more than one password field (change-password) doesn't repeat the
 * relative/absolute-positioned button markup per field. */
export function PasswordInput({ className, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="relative">
      <Input type={visible ? "text" : "password"} className={cn("pr-space-9", className)} {...props} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        tabIndex={-1}
        className="absolute right-space-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-700"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}
