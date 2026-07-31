import { writable } from 'svelte/store';

/**
 * Describes an achievement that can be rendered as a shareable card.
 * The `icon` is a Lucide icon name (PascalCase) rendered via DynamicIcon.
 */
export interface ShareableAchievement {
  title: string;
  icon: string;
  value: string;
  subtitle?: string;
  color?: string;
}

const currentAchievement = writable<ShareableAchievement | null>(null);

/**
 * Open the global share-achievement modal with the given achievement data.
 */
export function openShare(achievement: ShareableAchievement): void {
  currentAchievement.set(achievement);
}

/**
 * Close the global share-achievement modal.
 */
export function closeShare(): void {
  currentAchievement.set(null);
}

export { currentAchievement };
