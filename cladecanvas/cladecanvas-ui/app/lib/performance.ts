export type PerfSample = {
  event: string;
  name: string;
  durationMs: number;
  tags?: Record<string, string>;
};

declare global {
  interface Window {
    __CLADECANVAS_PERF__?: PerfSample[];
  }
}

const canMeasure = () =>
  typeof window !== "undefined" && typeof window.performance !== "undefined";

function record(sample: PerfSample) {
  if (!canMeasure()) return;

  window.__CLADECANVAS_PERF__ = window.__CLADECANVAS_PERF__ ?? [];
  window.__CLADECANVAS_PERF__.push(sample);

  console.info("cladecanvas_perf", sample);
}

export function recordDuration(
  event: string,
  name: string,
  durationMs: number,
  tags?: Record<string, string>
) {
  record({
    event,
    name,
    durationMs: Math.round(durationMs * 1000) / 1000,
    tags,
  });
}

export function markStart(event: string, name: string) {
  if (!canMeasure()) return null;
  const markName = `${event}:${name}:start:${crypto.randomUUID()}`;
  performance.mark(markName);
  return markName;
}

export function markEnd(
  startMark: string | null,
  event: string,
  name: string,
  tags?: Record<string, string>
) {
  if (!startMark || !canMeasure()) return;

  const endMark = startMark.replace(":start:", ":end:");
  const measureName = startMark.replace(":start:", ":measure:");
  performance.mark(endMark);
  performance.measure(measureName, startMark, endMark);
  const entries = performance.getEntriesByName(measureName, "measure");
  const duration = entries[entries.length - 1]?.duration ?? 0;

  recordDuration(event, name, duration, tags);
  performance.clearMarks(startMark);
  performance.clearMarks(endMark);
  performance.clearMeasures(measureName);
}
