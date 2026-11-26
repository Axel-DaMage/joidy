/**
 * marquee — Svelte action that turns a `.pln-mq` container into an infinite
 * horizontal auto-scroll when its text overflows. Expects this structure:
 *
 *   <span class="pln-mq" use:marquee>
 *     <span class="pln-mq-track">
 *       <span class="pln-mq-text">title</span>
 *       <span class="pln-mq-text pln-mq-dup" aria-hidden="true">title</span>
 *     </span>
 *   </span>
 *
 * The animation only activates when the first copy is wider than the
 * container (`marquee-on` class), and its duration scales with the text
 * width so the scroll speed is constant regardless of title length.
 */

const SPEED_PX_PER_S = 32;

export function marquee(node: HTMLElement) {
  function check() {
    const track = node.querySelector<HTMLElement>('.pln-mq-track');
    const first = node.querySelector<HTMLElement>('.pln-mq-text');
    if (!track || !first) return;
    // Copy width includes the trailing padding that creates the loop gap.
    const copyWidth = first.offsetWidth;
    const overflows = copyWidth > node.clientWidth + 2;
    node.classList.toggle('marquee-on', overflows);
    if (overflows) {
      track.style.animationDuration = `${Math.max(copyWidth / SPEED_PX_PER_S, 2)}s`;
    }
  }

  // Children may render in the same tick — measure after the microtask flush.
  queueMicrotask(check);
  const ro = new ResizeObserver(check);
  ro.observe(node);
  const mo = new MutationObserver(check);
  mo.observe(node, { childList: true, subtree: true, characterData: true });

  return {
    destroy() {
      ro.disconnect();
      mo.disconnect();
    },
  };
}
