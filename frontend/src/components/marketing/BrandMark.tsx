import Image from "next/image";

// The full DAAP CareConnect lockup (icon + "DAAP" / "CareConnect" / tagline
// lines) as one designed image -- frontend/public/logo-full.png, a
// whitespace-trimmed, transparent-background crop of the source
// frontend/public/logo-full.jpg the user supplied. Rendered at `width`;
// height follows from the crop's own aspect ratio so the mark is never
// stretched or squashed.
const LOGO_ASPECT_RATIO = 1448 / 410;

export function BrandMark({ width = 168 }: { width?: number }) {
  return (
    <a href="/" aria-label="DAAP CareConnect home" className="inline-flex shrink-0 items-center">
      <Image
        src="/logo-full.png"
        alt="DAAP CareConnect"
        width={width}
        height={Math.round(width / LOGO_ASPECT_RATIO)}
        priority
      />
    </a>
  );
}
