const MENU_ITEM = '[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]';

export interface MenuNavOptions {
  /** Called on Escape and on Tab (menus close when focus leaves). */
  onClose?: () => void;
  /** Restore focus to the previously focused element on destroy (default true). */
  restoreFocus?: boolean;
}

/**
 * Keyboard navigation for `role="menu"` containers: Arrow keys / Home / End
 * move between menuitems, Escape and Tab close the menu, and focus is moved
 * to the checked item (or the first one) when the menu opens. On destroy,
 * focus returns to the element that opened the menu.
 */
export function menuNav(node: HTMLElement, options: MenuNavOptions = {}) {
  const previousActiveElement = document.activeElement;
  const restoreFocus = options.restoreFocus !== false;

  function getItems(): HTMLElement[] {
    return Array.from(node.querySelectorAll<HTMLElement>(MENU_ITEM)).filter(
      (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-disabled') !== 'true'
    );
  }

  function handleKeydown(e: KeyboardEvent) {
    const items = getItems();
    if (items.length === 0) return;
    const index = items.indexOf(document.activeElement as HTMLElement);

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        e.stopPropagation();
        items[(index + 1) % items.length].focus();
        break;
      case 'ArrowUp':
        e.preventDefault();
        e.stopPropagation();
        items[(index - 1 + items.length) % items.length].focus();
        break;
      case 'Home':
        e.preventDefault();
        e.stopPropagation();
        items[0].focus();
        break;
      case 'End':
        e.preventDefault();
        e.stopPropagation();
        items[items.length - 1].focus();
        break;
      case 'Escape':
        e.preventDefault();
        e.stopPropagation();
        options.onClose?.();
        break;
      case 'Tab':
        // Tabbing out of a menu dismisses it (focus moves on naturally).
        options.onClose?.();
        break;
    }
  }

  node.addEventListener('keydown', handleKeydown);

  // Move focus into the menu: the checked item when there is one
  // (menuitemradio groups), otherwise the first item.
  const items = getItems();
  const initial = items.find((el) => el.getAttribute('aria-checked') === 'true') ?? items[0];
  initial?.focus();

  return {
    destroy() {
      node.removeEventListener('keydown', handleKeydown);
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
