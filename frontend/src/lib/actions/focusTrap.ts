const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Stack of previously-focused elements so nested traps (e.g. a modal opened
// from another modal or panel) restore focus to their own invoker in LIFO
// order instead of clobbering a module-level singleton (#1268).
const restoreStack: (Element | null)[] = [];

export function focusTrap(node: HTMLElement) {
  const entry = document.activeElement;
  restoreStack.push(entry);

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
      const idx = restoreStack.lastIndexOf(entry);
      if (idx !== -1) restoreStack.splice(idx, 1);
      // Restore focus only when this is the topmost trap — a deeper trap still
      // open restores its own invoker. The invoker must also still be on the
      // page (it may be gone after a route change or conditional unmount).
      if (idx === restoreStack.length && entry instanceof HTMLElement && entry.isConnected) {
        entry.focus();
      }
    },
  };
}
