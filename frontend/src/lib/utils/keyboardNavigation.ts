export function initKeyboardNavigation(): () => void {
  const isFocusable = (el: Element): el is HTMLElement => {
    if (!el || !(el instanceof HTMLElement)) return false;
    if (el.hasAttribute('disabled')) return false;
    if (el.getAttribute('tabindex') === '-1') return false;
    return (
      ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) ||
      el.hasAttribute('tabindex')
    );
  };

  // Elements that natively own arrow-key semantics — the spatial layer must
  // not steal their keys: native <select> dropdowns, listboxes/options,
  // sliders, focusable separators (the notes panel splitter), dialogs that
  // manage their own focus, etc. (#1268)
  const NATIVE_ARROW_OWNERS =
    'select, [role="listbox"], [role="option"], [role="menu"], [role="menubar"], ' +
    '[role="tree"], [role="grid"], [role="slider"], [role="spinbutton"], ' +
    '[role="scrollbar"], [role="tablist"], [role="tab"], [role="radiogroup"], ' +
    '[role="combobox"], [role="dialog"], [role="separator"], [data-arrow-nav="native"]';

  const isInNativeArrowOwner = (el: Element | null): boolean =>
    el instanceof HTMLElement && el.closest(NATIVE_ARROW_OWNERS) !== null;

  // Nearest ancestor (or self) that can actually scroll in the pressed
  // direction — used to restore native arrow-key scrolling when focus sits on
  // a non-interactive element inside a scrollable region.
  const scrollableInDirection = (el: Element | null, dir: string): Element | null => {
    const vertical = dir === 'ArrowUp' || dir === 'ArrowDown';
    let cur: Element | null = el;
    while (cur && cur instanceof HTMLElement) {
      if (cur === document.body || cur === document.documentElement) break;
      const style = getComputedStyle(cur);
      if (
        vertical &&
        /(auto|scroll)/.test(style.overflowY) &&
        cur.scrollHeight > cur.clientHeight
      ) {
        const atTop = cur.scrollTop <= 0;
        const atBottom = cur.scrollTop + cur.clientHeight >= cur.scrollHeight - 1;
        if ((dir === 'ArrowUp' && !atTop) || (dir === 'ArrowDown' && !atBottom)) return cur;
      } else if (
        !vertical &&
        /(auto|scroll)/.test(style.overflowX) &&
        cur.scrollWidth > cur.clientWidth
      ) {
        const atStart = cur.scrollLeft <= 0;
        const atEnd = cur.scrollLeft + cur.clientWidth >= cur.scrollWidth - 1;
        if ((dir === 'ArrowLeft' && !atStart) || (dir === 'ArrowRight' && !atEnd)) return cur;
      }
      cur = cur.parentElement;
    }
    return null;
  };

  const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const getFocusables = () => {
    return Array.from(
      document.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((el) => {
      const rect = el.getBoundingClientRect();
      // Must be visible
      return rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden';
    });
  };

  const getCenter = (rect: DOMRect) => ({
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2,
  });

  const getDistance = (rect1: DOMRect, rect2: DOMRect, dir: string) => {
    const c1 = getCenter(rect1);
    const c2 = getCenter(rect2);

    // Check if rect2 is in the correct direction from rect1
    if (dir === 'ArrowUp' && c2.y >= c1.y) return Infinity;
    if (dir === 'ArrowDown' && c2.y <= c1.y) return Infinity;
    if (dir === 'ArrowLeft' && c2.x >= c1.x) return Infinity;
    if (dir === 'ArrowRight' && c2.x <= c1.x) return Infinity;

    // Euclidean distance
    const dx = c1.x - c2.x;
    const dy = c1.y - c2.y;
    // Add weight to the primary axis
    if (dir === 'ArrowUp' || dir === 'ArrowDown') {
      return Math.sqrt(dx * dx * 4 + dy * dy);
    } else {
      return Math.sqrt(dx * dx + dy * dy * 4);
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    // If user is typing in an input, don't intercept unless it's Escape
    const active = document.activeElement;
    const isTyping =
      active instanceof HTMLInputElement ||
      active instanceof HTMLTextAreaElement ||
      (active instanceof HTMLElement && active.isContentEditable);

    if (e.key === 'Escape') {
      if (isTyping) {
        (active as HTMLElement).blur();
        e.preventDefault();
        return;
      }
      // Broadcast escape for modals/panels to close
      window.dispatchEvent(new CustomEvent('joidy:escape'));
      return;
    }

    if (isTyping) return; // Let default input behavior work

    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
      // Widgets that own arrow keys handle them natively (select options,
      // listbox navigation, slider/separator adjustment, dialog contents).
      if (isInNativeArrowOwner(active)) return;

      // When focus is on a non-interactive element (or nowhere), arrows are
      // the native scroll keys — keep them working inside scrollable regions.
      if (!active || !isFocusable(active)) {
        if (scrollableInDirection(active ?? document.body, e.key)) return;
      }

      e.preventDefault(); // Prevent scrolling

      const focusables = getFocusables();
      if (focusables.length === 0) return;

      if (!active || !isFocusable(active) || !focusables.includes(active as HTMLElement)) {
        // Focus first element if nothing is focused
        focusables[0].focus();
        return;
      }

      const activeRect = active.getBoundingClientRect();
      let bestMatch: HTMLElement | null = null;
      let minDistance = Infinity;

      for (const el of focusables) {
        if (el === active) continue;
        const rect = el.getBoundingClientRect();
        const distance = getDistance(activeRect, rect, e.key);
        if (distance < minDistance) {
          minDistance = distance;
          bestMatch = el;
        }
      }

      if (bestMatch) {
        bestMatch.focus();
        // Ensure it's in view (no smooth scroll under prefers-reduced-motion).
        bestMatch.scrollIntoView({
          behavior: reduceMotion() ? 'auto' : 'smooth',
          block: 'nearest',
        });
      }
    }

    // Space and Enter should trigger click on focused element
    if ((e.key === 'Enter' || e.key === ' ') && active && isFocusable(active)) {
      // Buttons and links handle Enter/Space natively, but we can ensure consistency
      // Actually browser does this natively for buttons and links, so maybe we just let it be,
      // except if space scrolls the page, we might want to prevent default and click.
      if (e.key === ' ' && active.tagName !== 'INPUT' && active.tagName !== 'TEXTAREA') {
        // Native widgets keep their own Space behavior (e.g. <select> opens
        // its picker; programmatic .click() does not reliably do so).
        if (isInNativeArrowOwner(active)) return;
        e.preventDefault();
        (active as HTMLElement).click();
      }
    }
  };

  window.addEventListener('keydown', handleKeyDown);
  // Return a cleanup function so the layout can remove the listener on
  // teardown, preventing duplicate handlers accumulating across remounts (#362).
  return () => window.removeEventListener('keydown', handleKeyDown);
}
