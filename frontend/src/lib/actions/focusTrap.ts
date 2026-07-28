const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

let previousActiveElement: Element | null = null;

export function focusTrap(node: HTMLElement) {
  previousActiveElement = document.activeElement;

  function getFocusable(): HTMLElement[] {
    return Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
  }

  function trapFocus(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    const focusable = getFocusable();
    if (focusable.length === 0) {
      e.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function focusFirst() {
    const focusable = getFocusable();
    if (focusable.length > 0) {
      focusable[0].focus();
    } else {
      node.focus();
    }
  }

  focusFirst();
  node.addEventListener('keydown', trapFocus);

  return {
    destroy() {
      node.removeEventListener('keydown', trapFocus);
      if (previousActiveElement instanceof HTMLElement) {
        previousActiveElement.focus();
      }
    }
  };
}
