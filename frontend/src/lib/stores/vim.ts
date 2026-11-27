// Vim mode state for the note editor (#1666).
//
// `vimModeEnabled` is the persisted user preference — stored inside the shared
// `joidy-user-settings-v1` blob (`editorUi.vimMode`) like `appearance.clockStyle`,
// so it survives reloads and migrates with the rest of the user settings.
// Default: OFF.
//
// `vimEditorMode` is the *live* editing mode of the focused editor instance
// (drives the `-- NORMAL --` / `-- INSERT --` toolbar badge). It is ephemeral
// and always resets to 'normal'.

import { writable, type Subscriber } from 'svelte/store';
import { browser } from '$app/env';
import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
import type { VimMode } from '$lib/utils/vimEngine';

function loadVimMode(): boolean {
  if (!browser) return false;
  return loadUserSettings().editorUi?.vimMode === true;
}

function createVimModeEnabledStore() {
  // Start false for SSR — read the persisted value only client-side (same
  // lazy-init pattern as the other settings stores).
  const { subscribe, set, update } = writable<boolean>(false);
  let _initialized = false;

  function ensureInit() {
    if (_initialized || !browser) return;
    _initialized = true;
    set(loadVimMode());
  }

  return {
    subscribe: (run: Subscriber<boolean>, invalidate?: () => void) => {
      ensureInit();
      return subscribe(run, invalidate);
    },
    set: (val: boolean) => {
      _initialized = true;
      patchUserSettings({ editorUi: { vimMode: val } });
      set(val);
    },
    toggle: () => {
      ensureInit();
      update((v) => {
        const next = !v;
        patchUserSettings({ editorUi: { vimMode: next } });
        return next;
      });
    },
    init: () => {
      _initialized = true;
      set(loadVimMode());
    },
  };
}

export const vimModeEnabled = createVimModeEnabledStore();

export const vimEditorMode = writable<VimMode>('normal');

/**
 * Coarse-pointer (touch-only) devices get no vim mode: modal editing assumes a
 * hardware keyboard and would trap virtual-keyboard users in NORMAL mode.
 * Devices with BOTH a coarse and a fine pointer (touch laptops) keep the
 * setting available — `(pointer: fine)` matches their trackpad/mouse.
 */
export function isTouchDevice(): boolean {
  if (!browser || typeof window.matchMedia !== 'function') return false;
  return (
    window.matchMedia('(pointer: coarse)').matches &&
    !window.matchMedia('(pointer: fine)').matches
  );
}
