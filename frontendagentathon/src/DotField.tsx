import { useEffect, useRef } from "react";

/**
 * Background grid of dots that bounce in a travelling wave, after Jitter's
 * "dancing dots". Decorative only: low opacity, paused off-screen, static for
 * reduced-motion users. Colour is read from the theme so it follows Light/Sage/Dark.
 */
export function DotField({ gap = 34, radius = 2, lift = 7 }: { gap?: number; radius?: number; lift?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, raf = 0, visible = true;

    const size = () => {
      const r = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = r.width; h = r.height;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h);
      const style = getComputedStyle(canvas);
      const base = style.getPropertyValue("--line-4").trim() || "#888";
      const accent = style.getPropertyValue("--primary").trim() || "#8ecfae";
      const cols = Math.ceil(w / gap) + 1;
      const rows = Math.ceil(h / gap) + 1;
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          // A diagonal wave: each dot bounces slightly after its neighbour.
          const phase = (t / 1000) * 1.6 - (x * 0.35 + y * 0.35);
          const s = Math.max(0, Math.sin(phase)); // only the up-swing, so dots rest between bounces
          ctx.globalAlpha = 0.55 + s * 0.45;
          ctx.fillStyle = s > 0.6 ? accent : base;
          ctx.beginPath();
          ctx.arc(x * gap + gap / 2, y * gap + gap / 2 - s * lift, radius + s * 0.9, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
    };

    const loop = (t: number) => {
      if (visible) draw(t);
      raf = requestAnimationFrame(loop);
    };

    size();
    draw(0);
    const ro = new ResizeObserver(() => { size(); draw(0); });
    ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; });
    io.observe(canvas);
    if (!reduced) raf = requestAnimationFrame(loop);

    return () => { cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); };
  }, [gap, radius, lift]);

  return <canvas ref={ref} className="dot-field" aria-hidden />;
}
