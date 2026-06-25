export type OpsMood = "offline" | "standby" | "live" | "alert";

export const MOOD_RGB: Record<OpsMood, [number, number, number]> = {
  offline: [120, 140, 135],
  standby: [94, 207, 184],
  live: [61, 220, 151],
  alert: [232, 160, 69],
};

export function resolveOpsMood(opts: {
  connected: boolean;
  hasData?: boolean;
  alertCount?: number;
}): OpsMood {
  if ((opts.alertCount ?? 0) > 0) return "alert";
  if (opts.connected) return "live";
  if (opts.hasData) return "standby";
  return "offline";
}
