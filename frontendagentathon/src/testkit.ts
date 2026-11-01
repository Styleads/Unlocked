/** Shared setup for the jsdom tests: the browser APIs the app needs but jsdom lacks. */
export function installBrowserShims() {
  window.matchMedia = ((q: string) => ({ matches: q.includes("reduce"), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false })) as typeof window.matchMedia;
  class Obs { observe() {} unobserve() {} disconnect() {} }
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = Obs;
  (globalThis as unknown as Record<string, unknown>).IntersectionObserver = Obs;
  window.scrollTo = (() => {}) as typeof window.scrollTo;
  // Node 25 ships its own half-working localStorage that shadows jsdom's; use a plain in-memory Storage.
  for (const key of ["localStorage", "sessionStorage"] as const) {
    const m = new Map<string, string>();
    const store = {
      getItem: (k: string) => m.get(k) ?? null,
      setItem: (k: string, v: string) => void m.set(k, String(v)),
      removeItem: (k: string) => void m.delete(k),
      clear: () => m.clear(),
      key: (i: number) => [...m.keys()][i] ?? null,
      get length() { return m.size; },
    };
    Object.defineProperty(window, key, { value: store, configurable: true });
    Object.defineProperty(globalThis, key, { value: store, configurable: true });
  }
}
