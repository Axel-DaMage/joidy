// Svelte action extracted from routes/notes/+page.svelte (#210): auto-scrolls
// overflowing note titles in the "Recientes" dashboard list.

const RECENT_TITLE_SCROLL_MIN_CHARS = 34;

export function autoScrollTitle(node: HTMLSpanElement, title = '') {
  const textEl = node.querySelector<HTMLSpanElement>('.recent-name-text');
  if (!textEl) return;

  let frameId = 0;
  let resizeObserver: ResizeObserver | null = null;

  const update = () => {
    const safeTitle = (title || textEl.textContent || '').trim();
    const overflowPx = Math.ceil(textEl.scrollWidth - node.clientWidth);
    const shouldScroll = safeTitle.length >= RECENT_TITLE_SCROLL_MIN_CHARS && overflowPx > 6;

    textEl.classList.toggle('is-overflowing', shouldScroll);

    if (shouldScroll) {
      textEl.style.setProperty('--scroll-distance', `${overflowPx}px`);
      const durationSec = Math.min(14, Math.max(6, overflowPx / 22 + 4));
      textEl.style.setProperty('--scroll-duration', `${durationSec}s`);
    } else {
      textEl.style.removeProperty('--scroll-distance');
      textEl.style.removeProperty('--scroll-duration');
    }
  };

  const scheduleUpdate = () => {
    cancelAnimationFrame(frameId);
    frameId = requestAnimationFrame(update);
  };

  scheduleUpdate();

  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(scheduleUpdate);
    resizeObserver.observe(node);
    resizeObserver.observe(textEl);
  }
  window.addEventListener('resize', scheduleUpdate);

  return {
    update(newTitle = '') {
      title = newTitle;
      scheduleUpdate();
    },
    destroy() {
      cancelAnimationFrame(frameId);
      resizeObserver?.disconnect();
      window.removeEventListener('resize', scheduleUpdate);
    },
  };
}
