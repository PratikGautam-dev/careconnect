// Shared axios plumbing for adminAuth.ts/staffAuth.ts -- both wrappers keep
// their original fetch-style `(path, init?: RequestInit)` signature (every
// existing caller across pages/components passes a RequestInit-shaped
// object), so this just repackages that into the axios request config
// shape rather than forcing every call site to be rewritten too.

export function requestInitToAxiosConfig(init?: RequestInit): {
  method: string;
  headers: Record<string, string>;
  data: unknown;
} {
  return {
    method: (init?.method as string) || "GET",
    headers: (init?.headers as Record<string, string>) || {},
    // init.body is already a JSON string (every caller does
    // JSON.stringify(payload) + sets Content-Type itself) -- passed through
    // unchanged so axios sends the exact same bytes fetch() did, not
    // re-serialized.
    data: init?.body,
  };
}
