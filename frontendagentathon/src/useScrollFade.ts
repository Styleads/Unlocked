import { useEffect } from "react";
import { animate, scroll } from "motion";

/**
 * Scroll-linked fade from motion.dev's "scroll fade" example: each marked
 * section fades in as it enters, holds while on screen, and fades out as it
 * leaves. Opacity follows scroll position, so it reverses when scrolling up.
 * Also turns on smooth scrolling for in-page anchor clicks while mounted.
 *
 * The offsets differ from the demo's ("end end", "start start") because those
 * only work for sections no taller than the viewport; these hold for any height.
 */
export function useScrollFade(selector = "[data-scroll-fade]") {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const root = document.documentElement;
    root.style.scrollBehavior = "smooth";

    const stops = Array.from(document.querySelectorAll<HTMLElement>(selector)).map((el) =>
      scroll(animate(el, { opacity: [0, 1, 1, 0] }), {
        target: el,
        offset: ["start end", "start 0.6", "end 0.4", "end start"],
      }),
    );

    return () => {
      root.style.scrollBehavior = "";
      stops.forEach((stop) => stop());
    };
  }, [selector]);
}
