/**
 * Spotlight utility — creates a dark overlay with a cutout that highlights
 * a target element without blocking interaction with it.
 *
 * The overlay uses four absolutely-positioned rectangles around the target's
 * bounding box so that pointer events pass through the cutout to the element
 * underneath, while the rest of the screen is dimmed and click-blocked.
 */

import { browser } from '$app/environment';

const SPOTLIGHT_ID = 'joidy-spotlight-overlay';
const SPOTLIGHT_PADDING = 8;

interface SpotlightRect {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

let resizeHandler: (() => void) | null = null;
let currentSelector: string | null = null;
let rafId: number | null = null;

/**
 * Compute the four rectangles that make up the dimmed overlay around the
 * target element's bounding box (with padding).
 */
function computeRects(target: DOMRect): SpotlightRect {
  const pad = SPOTLIGHT_PADDING;
  const top = Math.max(0, target.top - pad);
  const left = Math.max(0, target.left - pad);
  const right = Math.min(window.innerWidth, target.right + pad);
  const bottom = Math.min(window.innerHeight, target.bottom + pad);
  return { top, right, bottom, left };
}

/**
 * Build (or rebuild) the overlay DOM with the four dim rectangles positioned
 * around the current target.
 */
function renderOverlay(selector: string): void {
  if (!browser) return;

  const target = selector === '__none__' ? null : document.querySelector(selector) as HTMLElement | null;
  let overlay = document.getElementById(SPOTLIGHT_ID) as HTMLDivElement | null;

  if (!target) {
    // No target — render a full-screen dim without a cutout (centered step).
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = SPOTLIGHT_ID;
      overlay.setAttribute('aria-hidden', 'true');
      document.body.appendChild(overlay);
    }
    overlay.innerHTML = `<div class="joidy-spotlight-full"></div>`;
    return;
  }

  const rects = computeRects(target.getBoundingClientRect());

  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = SPOTLIGHT_ID;
    overlay.setAttribute('aria-hidden', 'true');
    document.body.appendChild(overlay);
  }

  // Four rectangles leave a transparent hole around the target.
  // pointer-events: none on the container, but each dim block re-enables
  // pointer events so clicks outside the cutout are absorbed.
  overlay.innerHTML = `
    <div class="joidy-spotlight-dim" style="left:0; top:0; right:0; height:${rects.top}px;"></div>
    <div class="joidy-spotlight-dim" style="left:0; top:${rects.top}px; width:${rects.left}px; height:${rects.bottom - rects.top}px;"></div>
    <div class="joidy-spotlight-dim" style="left:${rects.right}px; top:${rects.top}px; right:0; height:${rects.bottom - rects.top}px;"></div>
    <div class="joidy-spotlight-dim" style="left:0; top:${rects.bottom}px; right:0; bottom:0;"></div>
    <div class="joidy-spotlight-ring" style="left:${rects.left}px; top:${rects.top}px; width:${rects.right - rects.left}px; height:${rects.bottom - rects.top}px;"></div>
  `;
}

function scheduleRender(selector: string): void {
  if (rafId !== null) cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(() => {
    rafId = null;
    renderOverlay(selector);
  });
}

/**
 * Highlights the element matching `selector` with a spotlight cutout.
 * Re-positions on window resize/scroll. Safe to call repeatedly.
 */
export function highlightElement(selector: string | null): void {
  if (!browser) return;

  // Clean up previous listeners if selector changed.
  if (currentSelector && currentSelector !== selector) {
    clearHighlight();
  }

  currentSelector = selector;

  if (!selector) {
    // Centered step — full dim, no cutout.
    scheduleRender('__none__');
  } else {
    scheduleRender(selector);
  }

  if (!resizeHandler) {
    resizeHandler = () => {
      if (currentSelector) scheduleRender(currentSelector === '__none__' ? '__none__' : currentSelector);
    };
    window.addEventListener('resize', resizeHandler);
    window.addEventListener('scroll', resizeHandler, true);
  }
}

/**
 * Removes the spotlight overlay and event listeners.
 */
export function clearHighlight(): void {
  if (!browser) return;

  const overlay = document.getElementById(SPOTLIGHT_ID);
  if (overlay) overlay.remove();

  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler);
    window.removeEventListener('scroll', resizeHandler, true);
    resizeHandler = null;
  }

  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }

  currentSelector = null;
}
