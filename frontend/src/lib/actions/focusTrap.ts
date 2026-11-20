const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Stack of live trap roots (innermost = last). Lets stacked dialogs know
// which one is on top so only it reacts to Escape and restores focus.
const trapStack: HTMLElement[] = [];

export function isTopmostTrap(node: HTMLElement): boolean {
  return trapStack.length > 0 && trapStack[trapStack.length - 1] === node;
}

export interface FocusTrapOptions {
  /**
   * CSS selector (resolved inside the trap root) for the element that should
   * receive initial focus. Falls back to the first focusable element, then
   * to the trap root itself.
   */
  initialFocus?: string;
  /**
   * Called on Escape, but only while this trap is the topmost one — stacked
   * dialogs therefore close one at a time instead of all at once.
   */
  onEscape?: () => void;
  /** Restore focus to the previously focused element on destroy (default true). */
  restoreFocus?: boolean;
}

export function focusTrap(node: HTMLElement, options: FocusTrapOptions = {}) {
  // Per-instance restore target. The previous module-level singleton made a
  // second (stacked) dialog overwrite the first one's restore element, so
  // closing both never returned focus to the original trigger (#1307).
  const previousActiveElement = document.activeElement;
  const restoreFocus = options.restoreFocus !== false;

  trapStack.push(node);

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
    const active = document.activeElement;

    if (e.shiftKey) {
      if (active === first || !node.contains(active)) {
        e.preventDefault();
        last.focus();
      }
    } else if (active === last || !node.contains(active)) {
      e.preventDefault();
      first.focus();
    }
  }

  function onWindowKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && options.onEscape && isTopmostTrap(node)) {
      e.preventDefault();
      options.onEscape();
    }
  }

  function focusInitial() {
    const preferred = options.initialFocus
      ? node.querySelector<HTMLElement>(options.initialFocus)
      : null;
    const target = preferred ?? getFocusable()[0];
    if (target) {
      target.focus();
    } else {
      node.focus();
    }
  }

  focusInitial();
  node.addEventListener('keydown', trapFocus);
  if (options.onEscape) {
    window.addEventListener('keydown', onWindowKeydown);
  }

  return {
    destroy() {
      node.removeEventListener('keydown', trapFocus);
      if (options.onEscape) {
        window.removeEventListener('keydown', onWindowKeydown);
      }
      const index = trapStack.indexOf(node);
      if (index !== -1) trapStack.splice(index, 1);
      if (
        restoreFocus &&
        previousActiveElement instanceof HTMLElement &&
        previousActiveElement.isConnected
      ) {
        previousActiveElement.focus();
      }
    },
  };
}
