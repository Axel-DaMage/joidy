import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';

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
  INBOX: 'Inbox',
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
  return c === 'ROLLOVER' ? 'Traspaso' : c;
}
function onTogglePin() {}
function onClick() {}

// GoalRow reads context values via getGoalContext() instead of props (#351).
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

import GoalRow from './GoalRow.svelte';
import type { Goal } from '$lib/api';

function baseGoal(overrides: Partial<Goal> = {}): Goal {
  return {
    id: 1,
    title: 'My Goal',
    description: '',
    source_path: null,
    state: 'ACTIVE',
    is_completed: false,
    temporality: 'DAILY',
    context: 'ANY',
    measurement_type: 'COUNT',
    current_value: 3,
    target_value: 10,
    progress_pct: 30,
    priority: 0,
    fail_config: 'STATIC',
    fail_emoji: '',
    color: '',
    theme: '',
    tag_id: null,
    note_id: null,
    parent_id: null,
    max_assignment_days: null,
    pending_removal: false,
    completed_at: null,
    created_at: '2024-03-15T10:30:00',
    updated_at: '2024-03-15T10:30:00',
    ...overrides,
  };
}

function renderGoal(goal: Goal, pinned = false) {
  return render(GoalRow, {
    goal,
    pinned,
  });
}

describe('GoalRow — state chip', () => {
  beforeEach(() => cleanup());

  it('hides the state chip for ACTIVE goals', () => {
    const { container } = renderGoal(baseGoal({ state: 'ACTIVE' }));
    expect(container.querySelector('.grow-state')).toBeNull();
    expect(container.querySelector('.grow')?.classList.contains('completed')).toBe(false);
  });

  it('shows the COMPLETED chip and completed class', () => {
    const { container } = renderGoal(baseGoal({ state: 'COMPLETED' }));
    const chip = container.querySelector('.grow-state');
    expect(chip?.textContent?.trim()).toBe('Completado');
    expect(chip?.classList.contains('completed')).toBe(true);
    expect(container.querySelector('.grow')?.classList.contains('completed')).toBe(true);
  });

  it('shows the FAILED chip and failed class', () => {
    const { container } = renderGoal(baseGoal({ state: 'FAILED' }));
    const chip = container.querySelector('.grow-state');
    expect(chip?.textContent?.trim()).toBe('Fallido');
    expect(chip?.classList.contains('failed')).toBe(true);
    expect(container.querySelector('.grow')?.classList.contains('failed')).toBe(true);
  });

  it('shows the PAUSED chip and paused class', () => {
    const { container } = renderGoal(baseGoal({ state: 'PAUSED' }));
    const chip = container.querySelector('.grow-state');
    expect(chip?.textContent?.trim()).toBe('Pausado');
    expect(chip?.classList.contains('paused')).toBe(true);
    expect(container.querySelector('.grow')?.classList.contains('paused')).toBe(true);
  });

  it('shows the CANCELLED chip and archived class', () => {
    const { container } = renderGoal(baseGoal({ state: 'CANCELLED' }));
    const chip = container.querySelector('.grow-state');
    expect(chip?.textContent?.trim()).toBe('Cancelado');
    expect(container.querySelector('.grow')?.classList.contains('archived')).toBe(true);
  });

  it('treats is_completed=true as completed even when state is ACTIVE', () => {
    const { container } = renderGoal(baseGoal({ state: 'ACTIVE', is_completed: true }));
    expect(container.querySelector('.grow')?.classList.contains('completed')).toBe(true);
    expect(container.querySelector('.grow-state')?.textContent?.trim()).toBe('Completado');
  });
});

describe('GoalRow — progress display', () => {
  beforeEach(() => cleanup());

  it('COUNT shows current/target', () => {
    const { container } = renderGoal(baseGoal({ measurement_type: 'COUNT', current_value: 3, target_value: 10 }));
    expect(container.querySelector('.grow-pct')?.textContent?.trim()).toBe('3/10');
  });

  it('PERCENT shows current_value%', () => {
    const { container } = renderGoal(baseGoal({ measurement_type: 'PERCENT', current_value: 42 }));
    expect(container.querySelector('.grow-pct')?.textContent?.trim()).toBe('42%');
  });

  it('BOOLEAN shows current/target like any counter', () => {
    const { container } = renderGoal(baseGoal({ measurement_type: 'BOOLEAN', current_value: 0, target_value: 1 }));
    expect(container.querySelector('.grow-pct')?.textContent?.trim()).toBe('0/1');
  });

  it('completed goals show full target and 100% bar', () => {
    const { container } = renderGoal(baseGoal({ state: 'COMPLETED', current_value: 3, target_value: 10, progress_pct: 30 }));
    expect(container.querySelector('.grow-pct')?.textContent?.trim()).toBe('10/10');
    const fill = container.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('100%');
  });

  it('active goals use progress_pct for the bar', () => {
    const { container } = renderGoal(baseGoal({ state: 'ACTIVE', progress_pct: 30 }));
    const fill = container.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('30%');
  });
});

describe('GoalRow — meta chips', () => {
  beforeEach(() => cleanup());

  it('shows the temporality label', () => {
    const { container } = renderGoal(baseGoal({ temporality: 'WEEKLY' }));
    expect(container.querySelector('.gm-temp')?.textContent?.trim()).toBe('Semanal');
  });

  it('shows priority chip only when priority > 0', () => {
    const { container } = renderGoal(baseGoal({ priority: 3 }));
    expect(container.querySelector('.gm-prio')?.textContent?.trim()).toBe('P3');
    cleanup();
    const { container: c2 } = renderGoal(baseGoal({ priority: 0 }));
    expect(c2.querySelector('.gm-prio')).toBeNull();
  });

  it('shows fail config chip when not STATIC', () => {
    const { container } = renderGoal(baseGoal({ fail_config: 'ROLLOVER' }));
    expect(container.querySelector('.gm-fail')?.textContent?.trim()).toBe('Traspaso');
  });

  it('hides fail config chip when STATIC', () => {
    const { container } = renderGoal(baseGoal({ fail_config: 'STATIC' }));
    expect(container.querySelector('.gm-fail')).toBeNull();
  });

  it('shows context chip for MORNING and hides it for ANY', () => {
    const { container } = renderGoal(baseGoal({ context: 'MORNING' }));
    expect(container.querySelector('.gm-ctx')).not.toBeNull();
    cleanup();
    const { container: c2 } = renderGoal(baseGoal({ context: 'ANY' }));
    expect(c2.querySelector('.gm-ctx')).toBeNull();
  });

  it('shows link chip when tag_id is set and resolves the name', () => {
    _ctx = { ..._ctx, tags: [{ id: 5, name: 'Salud' }] };
    const { container } = renderGoal(baseGoal({ tag_id: 5 }));
    const link = container.querySelector('.gm-link');
    expect(link).not.toBeNull();
    expect(link?.getAttribute('title')).toBe('Salud');
    _ctx = { ..._ctx, tags: [] };
  });
});

describe('GoalRow — actions', () => {
  beforeEach(() => cleanup());

  it('renders the pin mark only when pinned', () => {
    const { container } = renderGoal(baseGoal(), true);
    expect(container.querySelector('.grow-title-row svg')).not.toBeNull();
    cleanup();
    const { container: c2 } = renderGoal(baseGoal(), false);
    expect(c2.querySelector('.grow-title-row svg')).toBeNull();
  });

  it('pin button calls onTogglePin with goal id', () => {
    const toggle = vi.fn();
    _ctx = { ..._ctx, onTogglePin: toggle };
    const { container } = render(GoalRow, { goal: baseGoal({ id: 7 }), pinned: false });
    (container.querySelector('.grow-pin') as HTMLElement).click();
    expect(toggle).toHaveBeenCalledWith(7);
    _ctx = { ..._ctx, onTogglePin };
  });

  it('complete button calls onComplete and is hidden for COMPLETED goals', () => {
    const complete = vi.fn();
    _ctx = { ..._ctx, onComplete: complete };
    const { container } = render(GoalRow, { goal: baseGoal({ id: 3, state: 'ACTIVE' }) });
    (container.querySelector('.grow-complete') as HTMLElement).click();
    expect(complete).toHaveBeenCalledWith(3);
    cleanup();
    const { container: c2 } = render(GoalRow, { goal: baseGoal({ id: 4, state: 'COMPLETED' }) });
    expect(c2.querySelector('.grow-complete')).toBeNull();
    _ctx = { ..._ctx, onComplete: undefined };
  });

  it('fail button calls onFail and toggles failed style', () => {
    const onFail = vi.fn();
    _ctx = { ..._ctx, onFail };
    const { container } = render(GoalRow, { goal: baseGoal({ id: 10, state: 'FAILED' }) });
    const failBtn = container.querySelector('.grow-fail') as HTMLButtonElement;
    expect(failBtn).not.toBeNull();
    expect(failBtn.classList.contains('failed')).toBe(true);
    failBtn.click();
    expect(onFail).toHaveBeenCalledWith(10);
    _ctx = { ..._ctx, onFail: undefined };
  });

  it('archive button calls onArchive with goal id', () => {
    const onArchive = vi.fn();
    _ctx = { ..._ctx, onArchive };
    const { container } = render(GoalRow, { goal: baseGoal({ id: 11, state: 'ACTIVE' }) });
    (container.querySelector('.grow-archive') as HTMLElement).click();
    expect(onArchive).toHaveBeenCalledWith(11);
    _ctx = { ..._ctx, onArchive: undefined };
  });

  it('delete button calls onDelete with the goal object', () => {
    const onDelete = vi.fn();
    _ctx = { ..._ctx, onDelete };
    const goal = baseGoal({ id: 12 });
    const { container } = render(GoalRow, { goal });
    (container.querySelector('.grow-delete') as HTMLElement).click();
    expect(onDelete).toHaveBeenCalledWith(goal);
    _ctx = { ..._ctx, onDelete: undefined };
  });

  it('clicking the main area calls onClick with the goal', () => {
    const onClick = vi.fn();
    _ctx = { ..._ctx, onClick };
    const goal = baseGoal({ id: 9 });
    const { container } = render(GoalRow, { goal });
    (container.querySelector('.grow-main') as HTMLElement).click();
    expect(onClick).toHaveBeenCalledWith(goal);
    _ctx = { ..._ctx, onClick };
  });
});
