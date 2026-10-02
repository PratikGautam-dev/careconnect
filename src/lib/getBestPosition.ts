export type PositionReading = { latitude: number; longitude: number; accuracy: number };

export type PositionResult =
  | { ok: true; reading: PositionReading }
  | { ok: false; reason: "denied" | "unavailable" | "timeout" };

/** Asks the device for its location and keeps the MOST ACCURATE reading it
 * gets within a few seconds, instead of trusting the first one. The first
 * fix a phone/laptop returns is often a rough WiFi/cell-tower guess that
 * sharpens as GPS locks on, and a rough guess is the main reason honest
 * staff get turned away. Stops early as soon as a reading is good enough.
 * Never rejects -- the caller decides what to do with a failure. */
export function getBestPosition({
  maxWaitMs = 4_000,
  goodEnoughMeters = 40,
}: { maxWaitMs?: number; goodEnoughMeters?: number } = {}): Promise<PositionResult> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      resolve({ ok: false, reason: "unavailable" });
      return;
    }
    let best: PositionReading | null = null;
    let finished = false;
    let watchId: number | null = null;

    const finish = (result: PositionResult) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      if (watchId !== null) navigator.geolocation.clearWatch(watchId);
      resolve(result);
    };
    const timer = setTimeout(
      () => finish(best ? { ok: true, reading: best } : { ok: false, reason: "timeout" }),
      maxWaitMs,
    );

    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const reading = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        };
        if (!best || reading.accuracy < best.accuracy) best = reading;
        if (best.accuracy <= goodEnoughMeters) finish({ ok: true, reading: best });
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) finish({ ok: false, reason: "denied" });
        else if (err.code === err.POSITION_UNAVAILABLE && !best)
          finish({ ok: false, reason: "unavailable" });
        // A TIMEOUT error with a reading already in hand just waits for the
        // overall timer above.
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: maxWaitMs },
    );
  });
}
