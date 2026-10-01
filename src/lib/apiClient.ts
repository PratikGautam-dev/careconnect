// Shared axios plumbing for adminAuth.ts/staffAuth.ts -- both wrappers keep
// their original fetch-style `(path, init?: RequestInit)` signature (every
// existing caller across pages/components passes a RequestInit-shaped
// object), so this just repackages that into the axios request config
// shape rather than forcing every call site to be rewritten too.

/** A failed request made with `responseType: "blob"` (adminFetchBlob/
 * staffFetchBlob) still comes back as a Blob even when the body is really
 * JSON -- axios doesn't know to parse it differently just because the
 * status was an error. Reads it as text and parses out the backend's real
 * `{error}` message instead of surfacing "[object Blob]" to the user. */
export async function blobErrorToMessage(blob: Blob): Promise<string> {
  try {
    const text = await blob.text();
    const data = JSON.parse(text);
    return data?.error || "Something went wrong.";
  } catch {
    return "Something went wrong.";
  }
}

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
