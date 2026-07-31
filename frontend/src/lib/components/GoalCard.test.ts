import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import { get } from 'svelte/store';

// Mock StreakIcon so we don't pull in dynamic icon resolution.
vi.mock('./StreakIcon.svelte', () => ({
  default: () => null,
}));

const STATE_LABELS: Record<string, string> = {
  ACTIVE: 'Activo',
  COMPLETED: 'Completado',
  FAILED: 'Fallido',
  PAUSED: 'Pausado',
  CANCELLED: 'Cancelado',
};

const TEMPORALITY_LABELS: Record<string, string> = {
  DAILY: 'Diario',
  WEEKLY: 'Semanal',
  MONTHLY: 'Mensual',
};

function getGoalColor() {
  return '#c8a96e';
}
function formatFailConfig(c: string) {
  return c === 'STREAK' ? 'Racha' : c;
}
function onTogglePin() {}
function onClick() {}

// GoalCard reads context values via getGoalContext() instead of props (#351).
// Mock the module so the test can supply the context values.
let _ctx: any = {
  tags: [],
  notes: [],
  getGoalColor,
  TEMPORALITY_LABELS,
  STATE_LABELS,
  formatFailConfig,
  onTogglePin,
  onClick,
};
vi.mock('$lib/stores/goalContext', () => ({
  getGoalContext: () => _ctx,
  setGoalContext: () => {},
}));

import GoalCard from './GoalCard.svelte';

function baseGoal(overrides: Record<string, any> = {}) {
  return {
    id: 1,
    title: 'My Goal',
    description: '',
    state: 'ACTIVE',
    is_completed: false,
    temporality: 'DAILY',
    measurement_type: 'NUMERIC',
    current_value: 3,
    target_value: 10,
    progress_pct: 30,
    fail_config: 'STATIC',
    created_at: '2024-03-15T10:30:00',
    tag_id: null,
    note_id: null,
    fail_emoji: null,
    ...overrides,
  };
}

function renderGoal(goal: Record<string, any>, pinned = false) {
  return render(GoalCard, {
    goal,
    pinned,
  });
}

describe('GoalCard — state display', () => {
  beforeEach(() => cleanup());

  it('shows the ACTIVE state label', () => {
    const { container } = renderGoal(baseGoal({ state: 'ACTIVE' }));
    const indicator = container.querySelector('.goal-state-indicator');
    expect(indicator?.textContent?.trim()).toBe('Activo');
    expect(indicator?.classList.contains('active')).toBe(true);
  });

  it('shows the COMPLETED state label and completed class', () => {
    const { container } = renderGoal(baseGoal({ state: 'COMPLETED' }));
    const indicator = container.querySelector('.goal-state-indicator');
    expect(indicator?.textContent?.trim()).toBe('Completado');
    expect(indicator?.classList.contains('completed')).toBe(true);
    const card = container.querySelector('.goal-editor-card');
    expect(card?.classList.contains('completed')).toBe(true);
  });

  it('shows the FAILED state label and failed class', () => {
    const { container } = renderGoal(baseGoal({ state: 'FAILED' }));
    const indicator = container.querySelector('.goal-state-indicator');
    expect(indicator?.textContent?.trim()).toBe('Fallido');
    expect(indicator?.classList.contains('failed')).toBe(true);
    expect(container.querySelector('.goal-editor-card')?.classList.contains('failed')).toBe(true);
  });

  it('shows the PAUSED state label and paused class', () => {
    const { container } = renderGoal(baseGoal({ state: 'PAUSED' }));
    const indicator = container.querySelector('.goal-state-indicator');
    expect(indicator?.textContent?.trim()).toBe('Pausado');
    expect(indicator?.classList.contains('paused')).toBe(true);
    expect(container.querySelector('.goal-editor-card')?.classList.contains('paused')).toBe(true);
  });

  it('shows the CANCELLED state label', () => {
    const { container } = renderGoal(baseGoal({ state: 'CANCELLED' }));
    const indicator = container.querySelector('.goal-state-indicator');
    expect(indicator?.textContent?.trim()).toBe('Cancelado');
  });

  it('falls back to raw state when label missing', () => {
    const { container } = renderGoal(baseGoal({ state: 'UNKNOWN' }));
    const indicator = container.querySelector('.goal-state-indicator');
    expect(indicator?.textContent?.trim()).toBe('UNKNOWN');
  });

  it('treats is_completed=true as completed', () => {
    const { container } = renderGoal(baseGoal({ state: 'ACTIVE', is_completed: true }));
    expect(container.querySelector('.goal-editor-card')?.classList.contains('completed')).toBe(true);
  });
});

describe('GoalCard — progress calculation', () => {
  beforeEach(() => cleanup());

  it('NUMERIC shows current / target', () => {
    const { container } = renderGoal(baseGoal({ measurement_type: 'NUMERIC', current_value: 3, target_value: 10 }));
    const text = container.querySelector('.progress-text')?.textContent?.trim();
    expect(text).toBe('3 / 10');
  });

  it('BOOLEAN shows Completado when current_value >= 1', () => {
    const { container } = renderGoal(baseGoal({ measurement_type: 'BOOLEAN', current_value: 1 }));
    expect(container.querySelector('.progress-text')?.textContent?.trim()).toBe('Completado');
  });

  it('BOOLEAN shows Pendiente when current_value < 1', () => {
    const { container } = renderGoal(baseGoal({ measurement_type: 'BOOLEAN', current_value: 0 }));
    expect(container.querySelector('.progress-text')?.textContent?.trim()).toBe('Pendiente');
  });

  it('PERCENT shows current_value%', () => {
    const { container } = renderGoal(baseGoal({ measurement_type: 'PERCENT', current_value: 42 }));
    expect(container.querySelector('.progress-text')?.textContent?.trim()).toBe('42%');
  });

  it('progress pct uses progress_pct for active goals', () => {
    const { container } = renderGoal(baseGoal({ state: 'ACTIVE', progress_pct: 30 }));
    expect(container.querySelector('.progress-pct')?.textContent?.trim()).toBe('30%');
    const fill = container.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('30%');
  });

  it('progress pct is 100 when completed', () => {
    const { container } = renderGoal(baseGoal({ state: 'COMPLETED', progress_pct: 30 }));
    expect(container.querySelector('.progress-pct')?.textContent?.trim()).toBe('100%');
    const fill = container.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('100%');
  });

  it('progress pct is 100 when is_completed true', () => {
    const { container } = renderGoal(baseGoal({ state: 'ACTIVE', is_completed: true, progress_pct: 30 }));
    expect(container.querySelector('.progress-pct')?.textContent?.trim()).toBe('100%');
  });
});

describe('GoalCard — date formatting', () => {
  beforeEach(() => cleanup());

  it('formats created_at as the date part before T', () => {
    const { container } = renderGoal(baseGoal({ created_at: '2024-03-15T10:30:00' }));
    const date = container.querySelector('.goal-date')?.textContent?.trim();
    expect(date).toBe('Creado: 2024-03-15');
  });

  it('hides the date when created_at is missing', () => {
    const { container } = renderGoal(baseGoal({ created_at: undefined }));
    expect(container.querySelector('.goal-date')).toBeNull();
  });
});

describe('GoalCard — meta and description', () => {
  beforeEach(() => cleanup());

  it('shows the temporality label', () => {
    const { container } = renderGoal(baseGoal({ temporality: 'WEEKLY' }));
    const meta = container.querySelectorAll('.meta-item');
    expect(meta[0]?.textContent?.trim()).toBe('Semanal');
  });

  it('truncates long descriptions to 80 chars with ellipsis', () => {
    const long = 'x'.repeat(100);
    const { container } = renderGoal(baseGoal({ description: long }));
    const desc = container.querySelector('.card-description')?.textContent ?? '';
    expect(desc.endsWith('...')).toBe(true);
    expect(desc.length).toBeLessThan(long.length);
  });

  it('shows full short description without ellipsis', () => {
    const { container } = renderGoal(baseGoal({ description: 'short' }));
    const desc = container.querySelector('.card-description')?.textContent ?? '';
    expect(desc).toBe('short');
  });

  it('shows fail config meta when not STATIC', () => {
    const { container } = renderGoal(baseGoal({ fail_config: 'STREAK' }));
    const configMeta = container.querySelector('.meta-item.config');
    expect(configMeta).not.toBeNull();
    expect(configMeta?.textContent?.trim()).toBe('Racha');
  });

  it('hides fail config meta when STATIC', () => {
    const { container } = renderGoal(baseGoal({ fail_config: 'STATIC' }));
    expect(container.querySelector('.meta-item.config')).toBeNull();
  });
});

describe('GoalCard — pin button', () => {
  beforeEach(() => cleanup());

  it('shows pinned class when pinned', () => {
    const { container } = renderGoal(baseGoal(), true);
    const pinBtn = container.querySelector('.pin-btn');
    expect(pinBtn?.classList.contains('pinned')).toBe(true);
  });

  it('pin button calls onTogglePin with goal id', async () => {
    const toggle = vi.fn();
    _ctx = { ..._ctx, onTogglePin: toggle };
    const { container } = render(GoalCard, {
      goal: baseGoal({ id: 7 }),
      pinned: false,
    });
    const pinBtn = container.querySelector('.pin-btn') as HTMLElement;
    pinBtn.click();
    expect(toggle).toHaveBeenCalledWith(7);
  });
});
