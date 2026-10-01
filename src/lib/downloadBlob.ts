// The one shared Blob -> browser-download sequence for every export route's
// response (see useExport.ts's useCsvExport). Prefers the server's real
// filename (Content-Disposition) over the caller's fallback, same as the
// backend's rows_to_csv_response() always sending one.

function extractFilename(contentDisposition?: string | null): string | null {
  if (!contentDisposition) return null;
  const match = /filename="?([^";]+)"?/i.exec(contentDisposition);
  return match?.[1] ?? null;
}

export function downloadBlob(
  blob: Blob,
  fallbackFilename: string,
  contentDisposition?: string | null,
) {
  const filename = extractFilename(contentDisposition) || fallbackFilename;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
