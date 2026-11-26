import { writable } from 'svelte/store';
import type { Component, ComponentType, SvelteComponent } from 'svelte';

type AnyComponent = Component | ComponentType<SvelteComponent>;

export interface HeaderTab {
  id: string;
  label: string;
  icon: AnyComponent;
  badge?: number;
  /** When set, the entry renders as a navigation link instead of a tab. */
  href?: string;
}

/** Segmented button group rendered at the right of the app header (e.g. a range selector). */
export interface HeaderSegmented {
  type: 'segmented';
  /** aria-label for the group. */
  label: string;
  options: { id: string; label: string; title?: string }[];
  activeId: string;
  onselect: (id: string) => void;
}

/** Single icon-button action rendered at the right of the app header (e.g. refresh). */
export interface HeaderAction {
  type: 'action';
  icon: AnyComponent;
  title: string;
  onclick: () => void;
  disabled?: boolean;
  spinning?: boolean;
}

export type HeaderControl = HeaderSegmented | HeaderAction;

export interface AppHeaderTabs {
  /** aria-label for the tablist. */
  label: string;
  tabs: HeaderTab[];
  activeId: string;
  onselect: (id: string) => void;
  /** Optional page-owned controls rendered at the right side of the header. */
  trailing?: HeaderControl[];
}

/**
 * Page-owned navigation rendered inside the global app header.
 * A page writes its tab configuration on mount (reactively, via $effect)
 * and clears it on destroy. Null means the header shows no page tabs.
 */
export const appHeaderTabs = writable<AppHeaderTabs | null>(null);
