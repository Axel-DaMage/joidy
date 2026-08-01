import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import { writable } from 'svelte/store';

// Use vi.hoisted so the mock stores are initialised before the hoisted
// vi.mock factory runs.
const { mockGlobalLevel, mockPlantStageName, mockAccentColors } = vi.hoisted(() => {
  const { writable } = require('svelte/store') as typeof import('svelte/store');
  return {
    mockGlobalLevel: writable(1),
    mockPlantStageName: writable('semilla'),
    mockAccentColors: writable(['#c8a96e']),
  };
});

vi.mock('$lib/stores/gamification', () => ({
  globalLevel: mockGlobalLevel,
  plantStageName: mockPlantStageName,
}));

vi.mock('$lib/stores/settings', () => ({
  accentColors: mockAccentColors,
}));

import Plant from './Plant.svelte';

describe('Plant — stage transitions', () => {
  beforeEach(() => {
    cleanup();
    mockGlobalLevel.set(1);
    mockPlantStageName.set('semilla');
    mockAccentColors.set(['#c8a96e']);
  });

  it('renders stage 0 (seed) at level 1', () => {
    mockGlobalLevel.set(1);
    const { container } = render(Plant, {});
    // Stage 0 renders an ellipse (seed) — no stem path
    const ellipse = container.querySelector('ellipse');
    expect(ellipse).not.toBeNull();
  });

  it('renders stage 1 (sprout) at level ~16', () => {
    // (16 - 1) / (100/7) ≈ 1.05 → floor = 1
    mockGlobalLevel.set(16);
    const { container } = render(Plant, {});
    const paths = container.querySelectorAll('path');
    expect(paths.length).toBeGreaterThanOrEqual(2);
  });

  it('renders stage 2 (seedling) at level ~30', () => {
    // (30 - 1) / 14.28 ≈ 2.03 → floor = 2
    mockGlobalLevel.set(30);
    const { container } = render(Plant, {});
    const paths = container.querySelectorAll('path');
    // Stage 2 has stem + 4 leaves = 5 paths
    expect(paths.length).toBeGreaterThanOrEqual(5);
  });

  it('renders stage 3 (young) at level ~44', () => {
    // (44 - 1) / 14.28 ≈ 3.01 → floor = 3
    mockGlobalLevel.set(44);
    const { container } = render(Plant, {});
    const paths = container.querySelectorAll('path');
    expect(paths.length).toBeGreaterThanOrEqual(6);
  });

  it('renders stage 4 (mature) at level ~59', () => {
    // (59 - 1) / 14.28 ≈ 4.06 → floor = 4
    mockGlobalLevel.set(59);
    const { container } = render(Plant, {});
    const paths = container.querySelectorAll('path');
    expect(paths.length).toBeGreaterThanOrEqual(8);
  });

  it('renders stage 5 (flowering) at level ~73', () => {
    // (73 - 1) / 14.28 ≈ 5.04 → floor = 5
    mockGlobalLevel.set(73);
    const { container } = render(Plant, {});
    // Stage 5 has flowers (circles)
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBeGreaterThanOrEqual(6);
  });

  it('renders stage 6 (tree) at level ~87', () => {
    // (87 - 1) / 14.28 ≈ 6.02 → floor = 6
    mockGlobalLevel.set(87);
    const { container } = render(Plant, {});
    // Stage 6 has a thick trunk (stroke-width="3")
    const trunk = container.querySelector('path[stroke-width="3"]');
    expect(trunk).not.toBeNull();
  });

  it('caps at stage 6 even at very high levels', () => {
    mockGlobalLevel.set(200);
    const { container } = render(Plant, {});
    const trunk = container.querySelector('path[stroke-width="3"]');
    expect(trunk).not.toBeNull();
  });
});

describe('Plant — wilted state', () => {
  beforeEach(() => {
    cleanup();
    mockGlobalLevel.set(1);
    mockPlantStageName.set('semilla');
  });

  it('adds wilted class when wilted=true', () => {
    const { container } = render(Plant, { wilted: true });
    const plantContainer = container.querySelector('.plant-container');
    expect(plantContainer?.classList.contains('wilted')).toBe(true);
  });

  it('does not add wilted class when wilted=false', () => {
    const { container } = render(Plant, { wilted: false });
    const plantContainer = container.querySelector('.plant-container');
    expect(plantContainer?.classList.contains('wilted')).toBe(false);
  });
});

describe('Plant — title and size', () => {
  beforeEach(() => {
    cleanup();
    mockGlobalLevel.set(1);
    mockPlantStageName.set('semilla');
  });

  it('shows stage name and level in title', () => {
    mockPlantStageName.set('brote');
    mockGlobalLevel.set(16);
    const { container } = render(Plant, {});
    const plantContainer = container.querySelector('.plant-container') as HTMLElement;
    expect(plantContainer?.getAttribute('title')).toContain('brote');
    expect(plantContainer?.getAttribute('title')).toContain('16');
  });

  it('applies custom size', () => {
    const { container } = render(Plant, { size: 300 });
    const plantContainer = container.querySelector('.plant-container') as HTMLElement;
    expect(plantContainer?.style.width).toContain('300');
    expect(plantContainer?.style.height).toContain('300');
  });
});
