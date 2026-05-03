export function initKeyboardNavigation() {
  const isFocusable = (el: Element): el is HTMLElement => {
    if (!el || !(el instanceof HTMLElement)) return false;
    if (el.hasAttribute('disabled')) return false;
    if (el.getAttribute('tabindex') === '-1') return false;
    return ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName) || el.hasAttribute('tabindex');
  };

  const getFocusables = () => {
    return Array.from(document.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter(el => {
      const rect = el.getBoundingClientRect();
      // Must be visible
      return rect.width > 0 && rect.height > 0 && getComputedStyle(el).visibility !== 'hidden';
    });
  };

  const getCenter = (rect: DOMRect) => ({
    x: rect.left + rect.width / 2,
    y: rect.top + rect.height / 2
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

  window.addEventListener('keydown', (e) => {
    // If user is typing in an input, don't intercept unless it's Escape
    const active = document.activeElement;
    const isTyping = active instanceof HTMLInputElement || 
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
        // Ensure it's in view
        bestMatch.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }

    // Space and Enter should trigger click on focused element
    if ((e.key === 'Enter' || e.key === ' ') && active && isFocusable(active)) {
      // Buttons and links handle Enter/Space natively, but we can ensure consistency
      // Actually browser does this natively for buttons and links, so maybe we just let it be,
      // except if space scrolls the page, we might want to prevent default and click.
      if (e.key === ' ' && active.tagName !== 'INPUT' && active.tagName !== 'TEXTAREA') {
        e.preventDefault();
        (active as HTMLElement).click();
      }
    }
  });
}
