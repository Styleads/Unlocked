/** Builds a one-day calendar reminder (.ics). The date always comes from the user: we never invent deadlines. */

const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
const stamp = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
const compact = (isoDate: string) => isoDate.replace(/-/g, "");

/** `isoDate` is YYYY-MM-DD. The event is all-day, so no time zone is involved. */
export function buildIcs(opts: { title: string; isoDate: string; description: string; url?: string }): string {
  const { title, isoDate, description, url } = opts;
  const next = new Date(`${isoDate}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Unlocked//Document plan//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${crypto.randomUUID()}@unlocked.local`,
    `DTSTAMP:${stamp(new Date())}`,
    `DTSTART;VALUE=DATE:${compact(isoDate)}`,
    `DTEND;VALUE=DATE:${compact(next.toISOString().slice(0, 10))}`,
    `SUMMARY:${esc(title)}`,
    `DESCRIPTION:${esc(description)}`,
    ...(url ? [`URL:${url}`] : []),
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return lines.join("\r\n") + "\r\n";
}

export function downloadText(filename: string, text: string, type = "text/calendar") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
