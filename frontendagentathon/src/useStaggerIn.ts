import { useEffect } from "react";
import { animate, inView, stagger } from "motion";

/**
 * motion.dev's "stagger from edges": the items of a group fade up one after
 * another, starting at both ends and meeting in the middle. Plays once, when the
 * group scrolls into view. Skipped for reduced-motion users (items stay visible).
 */
export function useStaggerIn(containerSelector: string, itemSelector: string) {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const container = document.querySelector<HTMLElement>(containerSelector);
    const items = Array.from(container?.querySelectorAll<HTMLElement>(itemSelector) ?? []);
    if (!container || items.length === 0) return;

    // Hidden from script rather than CSS, so a failed script can never leave them invisible.
    items.forEach((el) => { el.style.opacity = "0"; });

    const stop = inView(container, () => {
      animate(items, { opacity: 1, y: [40, 0] }, { delay: stagger(0.12, { from: "edges" }), duration: 0.6, ease: [0.2, 0.7, 0.2, 1] })
        // an inline transform would otherwise beat the CSS hover lift
        .then(() => items.forEach((el) => { el.style.transform = ""; }));
    }, { amount: 0.3 });

    return () => { stop(); items.forEach((el) => { el.style.opacity = ""; el.style.transform = ""; }); };
  }, [containerSelector, itemSelector]);
}
