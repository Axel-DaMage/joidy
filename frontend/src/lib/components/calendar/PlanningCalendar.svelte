<script module lang="ts">
  /** A single renderable item inside a day cell — the normalized shape every
   * data source (calendar_tasks, Google events, planning assignments, AI
   * suggestions, notes) is flattened into before the grid renders it. */
  export interface CalendarDayChip {
    /** Unique {#each} key. */
    key: string;
    label: string;
    kind: 'task' | 'google' | 'goal' | 'suggestion' | 'note';
    /** HH:mm display time; null/undefined = all-day/untimed. */
    time?: string | null;
    allDay?: boolean;
    /** Accent color (CSS color) for the chip's left edge. */
    color?: string;
    /** CalendarTask priority — drives prio-* color/style cues. */
    priority?: string;
    done?: boolean;
    recurring?: boolean;
    /** Ghost/AI-proposed chip — dashed, click-to-accept. */
    ghost?: boolean;
    /** Read-only (Google events) — renders a lock glyph. */
    locked?: boolean;
    /** Show an inline remove button (list variants only). */
    removable?: boolean;
    draggable?: boolean;
    /** Trailing secondary text (e.g. temporality label). */
    meta?: string;
    title?: string;
    /** Opaque payload handed back through the chip callbacks. */
    payload?: unknown;
  }

  /** Lightweight day-cell badge (streak check-in state, notes count). */
  export interface CalendarDayBadge {
    key: string;
    kind: 'streak' | 'note';
    /** StreakIcon name or emoji (streak badges). */
    icon?: string;
    color?: string;
    /** Streak: checked-in state on that day. */
    checked?: boolean;
    /** Note badge: number of notes that day. */
    count?: number;
    title?: string;
  }
</script>

<script lang="ts">
  import { t } from 'svelte-i18n';
  import { locale } from '$lib/stores/locale';
  import Lock from 'lucide-svelte/icons/lock';
  import Repeat from 'lucide-svelte/icons/repeat';
  import Sparkles from 'lucide-svelte/icons/sparkles';
  import FileText from 'lucide-svelte/icons/file-text';
  import X from 'lucide-svelte/icons/x';
  import StreakIcon from '$lib/components/StreakIcon.svelte';
  import {
    monthCellsFor,
    weekDaysFor,
    agendaDaysFor,
    type PlanningCalendarView,
  } from '$lib/stores/planningCalendar';

  interface Props {
    view?: PlanningCalendarView;
    /** YYYY-MM-DD anchoring the visible period. */
    cursor: string;
    todayIso: string;
    selectedDay?: string | null;
    /** Flattened items for a day; the component owns layout + overflow only. */
    chipsForDay?: (iso: string) => CalendarDayChip[];
    badgesForDay?: (iso: string) => CalendarDayBadge[];
    /** Density control — max chips inside a month cell before "+N more". */
    maxChips?: number;
    agendaLength?: number;
    dropTargetKey?: string | null;
    /** Key of the chip currently mid-drag (dims it). */
    draggingChipKey?: string | null;
    onselectday?: (iso: string) => void;
    onchipclick?: (chip: CalendarDayChip, iso: string) => void;
    onchipremove?: (chip: CalendarDayChip, iso: string) => void;
    oncelldragover?: (event: DragEvent, iso: string) => void;
    oncelldragleave?: (event: DragEvent, iso: string) => void;
    oncelldrop?: (event: DragEvent, iso: string) => void;
    onchipdragstart?: (event: DragEvent, chip: CalendarDayChip) => void;
    onchipdragend?: (event: DragEvent, chip: CalendarDayChip) => void;
  }

  let {
    view = 'month',
    cursor,
    todayIso,
    selectedDay = null,
    chipsForDay = () => [],
    badgesForDay = () => [],
    maxChips = 3,
    agendaLength = 14,
    dropTargetKey = null,
    draggingChipKey = null,
    onselectday,
    onchipclick,
    onchipremove,
    oncelldragover,
    oncelldragleave,
    oncelldrop,
    onchipdragstart,
    onchipdragend,
  }: Props = $props();

  let monthCells = $derived(monthCellsFor(cursor));
  let weekDays = $derived(weekDaysFor(cursor));
  let agendaDays = $derived(agendaDaysFor(cursor, agendaLength));

  function priorityClass(chip: CalendarDayChip): string {
    return chip.priority ? `prio prio-${chip.priority.toLowerCase()}` : '';
  }

  function chipKeydown(event: KeyboardEvent, chip: CalendarDayChip, iso: string): void {
    if (!onchipclick) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      event.stopPropagation();
      onchipclick(chip, iso);
    }
  }
</script>

{#snippet badgeRow(badge: CalendarDayBadge)}
  {#if badge.kind === 'note'}
    <span class="pcal-badge pcal-badge-note" title={badge.title}>
      <FileText size={8} /><span class="pcal-badge-count">{badge.count ?? 0}</span>
    </span>
  {:else}
    <span
      class="pcal-badge pcal-badge-streak"
      class:checked={badge.checked}
      title={badge.title}
    >
      <StreakIcon
        name={badge.icon ?? ''}
        size={10}
        color={badge.checked ? badge.color : 'var(--text-muted)'}
      />
    </span>
  {/if}
{/snippet}

{#snippet chipRow(chip: CalendarDayChip, iso: string, variant: 'compact' | 'row' | 'pill')}
  <span
    class="pcal-chip {priorityClass(chip)}"
    class:pcal-row={variant === 'row'}
    class:pcal-pill={variant === 'pill'}
    class:done={chip.done}
    class:ghost={chip.ghost}
    class:dragging={draggingChipKey === chip.key}
    role="button"
    tabindex="-1"
    title={chip.title}
    style={chip.color ? `--chip-accent: ${chip.color}` : undefined}
    draggable={chip.draggable === true}
    ondragstart={(e) => onchipdragstart?.(e, chip)}
    ondragend={(e) => onchipdragend?.(e, chip)}
    onclick={(e) => {
      if (!onchipclick) return;
      e.stopPropagation();
      onchipclick(chip, iso);
    }}
    onkeydown={(e) => chipKeydown(e, chip, iso)}
  >
    {#if chip.removable && variant === 'row'}
      <button
        class="pcal-chip-remove"
        title={$t('goalsPage.remove')}
        aria-label={$t('goalsPage.remove')}
        onclick={(e) => {
          e.stopPropagation();
          onchipremove?.(chip, iso);
        }}><X size={12} /></button
      >
    {/if}
    {#if chip.locked}<Lock size={8} class="pcal-chip-icon" />{/if}
    {#if chip.ghost}<Sparkles size={8} class="pcal-chip-icon" />{/if}
    {#if chip.time || chip.allDay}
      <span class="pcal-chip-time">{chip.allDay ? $t('calendar.allDay') : chip.time}</span>
    {/if}
    {#if chip.recurring}<Repeat size={8} class="pcal-chip-icon recur-icon" />{/if}
    <span class="pcal-chip-label">{chip.label}</span>
    {#if chip.meta && variant === 'row'}<span class="pcal-chip-meta">{chip.meta}</span>{/if}
  </span>
{/snippet}

<div class="pcal" class:pcal-compact={view === 'month'}>
  {#if view === 'month'}
    <div class="pcal-weekdays">
      {#each [0, 1, 2, 3, 4, 5, 6] as i (i)}
        <span class="pcal-dow caption">{$t(`calendar.weekDays.${i}`)}</span>
      {/each}
    </div>
    <div class="pcal-grid">
      {#each monthCells as cell (cell.iso)}
        {@const chips = chipsForDay(cell.iso)}
        {@const badges = badgesForDay(cell.iso)}
        <button
          class="pcal-cell"
          class:other-month={!cell.inMonth}
          class:today={cell.iso === todayIso}
          class:selected={cell.iso === selectedDay}
          class:drop-target={dropTargetKey === cell.iso}
          onclick={() => onselectday?.(cell.iso)}
          ondragover={(e) => oncelldragover?.(e, cell.iso)}
          ondragleave={(e) => oncelldragleave?.(e, cell.iso)}
          ondrop={(e) => oncelldrop?.(e, cell.iso)}
        >
          <span class="pcal-cell-head">
            <span class="pcal-num">{cell.day}</span>
            {#if badges.length > 0}
              <span class="pcal-badges">
                {#each badges as badge (badge.key)}
                  {@render badgeRow(badge)}
                {/each}
              </span>
            {/if}
          </span>
          <span class="pcal-items">
            {#each chips.slice(0, maxChips) as chip (chip.key)}
              {@render chipRow(chip, cell.iso, 'compact')}
            {/each}
            {#if chips.length > maxChips}
              <span class="pcal-chip pcal-more">+{chips.length - maxChips}</span>
            {/if}
          </span>
        </button>
      {/each}
    </div>
  {:else if view === 'week'}
    <div class="pcal-week">
      {#each weekDays as iso, i (iso)}
        {@const chips = chipsForDay(iso)}
        {@const badges = badgesForDay(iso)}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="pcal-col"
          class:today={iso === todayIso}
          class:selected={iso === selectedDay}
          class:drop-target={dropTargetKey === iso}
          ondragover={(e) => oncelldragover?.(e, iso)}
          ondragleave={(e) => oncelldragleave?.(e, iso)}
          ondrop={(e) => oncelldrop?.(e, iso)}
        >
          <button
            class="pcal-col-head"
            onclick={() => onselectday?.(iso)}
            aria-label={iso}
          >
            <span class="pcal-dow">{$t(`calendar.weekDays.${i}`)}</span>
            <span class="pcal-num">{Number(iso.slice(8))}</span>
            {#if chips.length > 0}<span class="pcal-count">{chips.length}</span>{/if}
            {#if badges.length > 0}
              <span class="pcal-badges">
                {#each badges as badge (badge.key)}
                  {@render badgeRow(badge)}
                {/each}
              </span>
            {/if}
          </button>
          <div class="pcal-col-items">
            {#each chips as chip (chip.key)}
              {@render chipRow(chip, iso, 'row')}
            {:else}
              <span class="pcal-col-empty">—</span>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <div class="pcal-agenda">
      {#each agendaDays as iso (iso)}
        {@const chips = chipsForDay(iso)}
        {@const badges = badgesForDay(iso)}
        {@const date = new Date(`${iso}T12:00:00`)}
        <div
          class="pcal-agenda-row"
          class:today={iso === todayIso}
          class:selected={iso === selectedDay}
          class:drop-target={dropTargetKey === iso}
          role="button"
          tabindex="0"
          onclick={() => onselectday?.(iso)}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onselectday?.(iso);
            }
          }}
          ondragover={(e) => oncelldragover?.(e, iso)}
          ondragleave={(e) => oncelldragleave?.(e, iso)}
          ondrop={(e) => oncelldrop?.(e, iso)}
        >
          <div class="pcal-agenda-badge">
            <span class="pcal-num">{date.getDate()}</span>
            <span class="caption"
              >{date.toLocaleDateString($locale, { weekday: 'short', month: 'short' })}</span
            >
            {#if badges.length > 0}
              <span class="pcal-badges">
                {#each badges as badge (badge.key)}
                  {@render badgeRow(badge)}
                {/each}
              </span>
            {/if}
          </div>
          <div class="pcal-agenda-items">
            {#each chips as chip (chip.key)}
              {@render chipRow(chip, iso, 'pill')}
            {:else}
              <span class="caption pcal-agenda-empty">{$t('calendar.noEventsDay')}</span>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .pcal {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    min-width: 0;
  }

  /* ── Month grid ─────────────────────────────────────────────── */
  .pcal-weekdays {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
    flex-shrink: 0;
    padding-bottom: 2px;
  }

  .pcal-dow {
    text-align: center;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .pcal-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    grid-template-rows: repeat(6, minmax(0, 1fr));
    gap: 4px;
    flex: 1;
    min-height: 0;
  }

  .pcal-cell {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 2px;
    padding: 4px 6px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-primary);
    font-size: 11px;
    cursor: pointer;
    min-height: 0;
    overflow: hidden;
    text-align: left;
    transition:
      border-color var(--t-fast),
      background var(--t-fast);
  }

  .pcal-cell:hover {
    border-color: var(--text-muted);
    background: var(--surface-hover, var(--hover));
  }

  .pcal-cell.other-month {
    opacity: 0.45;
  }

  .pcal-cell.today {
    border-color: color-mix(in srgb, var(--xp) 45%, var(--border));
  }

  .pcal-cell.today .pcal-num {
    color: var(--xp);
  }

  .pcal-cell.selected {
    outline: 2px solid var(--link);
    outline-offset: -1px;
  }

  .pcal-cell.drop-target,
  .pcal-col.drop-target,
  .pcal-agenda-row.drop-target {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 18%, transparent);
  }

  .pcal-cell-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
    min-width: 0;
  }

  .pcal-num {
    font-size: 12px;
    font-weight: 700;
    font-family: var(--font-mono);
  }

  .pcal-badges {
    display: flex;
    align-items: center;
    gap: 3px;
    min-width: 0;
    overflow: hidden;
  }

  .pcal-badge {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    font-size: 9px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .pcal-badge-streak {
    opacity: 0.55;
  }

  .pcal-badge-streak.checked {
    opacity: 1;
  }

  .pcal-badge-count {
    font-family: var(--font-mono);
  }

  .pcal-items {
    display: flex;
    flex-direction: column;
    gap: 1px;
    width: 100%;
    min-width: 0;
    margin-top: auto;
  }

  /* ── Chips ──────────────────────────────────────────────────── */
  .pcal-chip {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 9px;
    line-height: 1.3;
    padding: 0 3px;
    border-radius: 3px;
    white-space: nowrap;
    overflow: hidden;
    max-width: 100%;
    background: color-mix(in srgb, var(--text-muted) 15%, transparent);
    color: var(--text-primary);
    box-shadow: inset 2px 0 0 var(--chip-accent, transparent);
  }

  .pcal-chip-icon {
    flex-shrink: 0;
  }

  .pcal-chip-time {
    font-size: 9px;
    opacity: 0.75;
    flex-shrink: 0;
  }

  .pcal-chip-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
  }

  .pcal-chip-meta {
    font-size: 9px;
    color: var(--chip-accent, var(--text-muted));
    flex-shrink: 0;
  }

  .pcal-chip.done {
    text-decoration: line-through;
    opacity: 0.55;
  }

  .pcal-chip.dragging {
    opacity: 0.35;
  }

  .pcal-chip.ghost {
    border: 1px dashed var(--link);
    background: color-mix(in srgb, var(--link) 8%, transparent);
    color: var(--link);
    cursor: pointer;
  }

  .pcal-chip.ghost:hover {
    background: color-mix(in srgb, var(--link) 18%, transparent);
  }

  .pcal-more {
    color: var(--text-muted);
    background: transparent;
    box-shadow: none;
  }

  /* Priority cues — colors plus non-color styles (WCAG 1.4.1, #1309). */
  .prio-low {
    color: var(--text-muted);
  }
  .prio-medium {
    color: var(--accent);
    font-style: italic;
  }
  .prio-high {
    color: #e08c3a;
    font-weight: 600;
  }
  .prio-urgent {
    color: #d9534f;
    font-weight: 700;
    text-decoration: underline;
  }

  /* Row variant — full-width list chip (week columns). */
  .pcal-row {
    font-size: 12px;
    padding: 7px 9px;
    gap: 6px;
    border: 1px solid var(--border);
    border-left: 3px solid var(--chip-accent, var(--border));
    border-radius: var(--r);
    background: var(--surface);
    box-shadow: none;
    width: 100%;
    box-sizing: border-box;
  }

  .pcal-row .pcal-chip-time {
    font-size: 10px;
  }

  .pcal-chip-remove {
    display: flex;
    padding: 2px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
  }

  .pcal-chip-remove:hover {
    color: var(--error);
  }

  /* ── Week board ─────────────────────────────────────────────── */
  .pcal-week {
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    gap: 6px;
  }

  .pcal-col {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    min-height: 0;
    overflow: hidden;
    transition:
      border-color var(--t-fast),
      background var(--t-fast);
  }

  .pcal-col.today {
    border-color: color-mix(in srgb, var(--xp) 45%, var(--border));
  }

  .pcal-col.selected {
    outline: 2px solid var(--link);
    outline-offset: -1px;
  }

  .pcal-col-head {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    padding: 8px 4px;
    background: transparent;
    border: none;
    border-bottom: 1px solid var(--border-light, var(--border));
    cursor: pointer;
    color: var(--text-primary);
    width: 100%;
  }

  .pcal-col-head:hover {
    background: var(--surface-hover, var(--hover));
  }

  .pcal-col.today .pcal-num {
    color: var(--xp);
  }

  .pcal-col-head .pcal-num {
    font-size: 15px;
  }

  .pcal-count {
    position: absolute;
    top: 6px;
    right: 6px;
    font-size: 9px;
    padding: 0 5px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--link) 15%, transparent);
    color: var(--link);
    font-family: var(--font-mono);
  }

  .pcal-col-head .pcal-badges {
    margin-top: 2px;
  }

  .pcal-col-items {
    flex: 1;
    overflow-y: auto;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-height: 0;
  }

  .pcal-col-empty {
    text-align: center;
    color: var(--text-muted);
    font-size: 10px;
    padding: 6px 0;
  }

  /* ── Agenda ─────────────────────────────────────────────────── */
  .pcal-agenda {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding-right: 4px;
  }

  .pcal-agenda-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    cursor: pointer;
    transition:
      border-color var(--t-fast),
      background var(--t-fast);
  }

  .pcal-agenda-row:hover {
    background: var(--surface-hover, var(--hover));
  }

  .pcal-agenda-row.today {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 10%, transparent);
  }

  .pcal-agenda-row.selected {
    outline: 2px solid var(--link);
    outline-offset: -1px;
  }

  .pcal-agenda-badge {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    min-width: 48px;
    padding: 4px;
    border-radius: var(--r);
    background: var(--surface);
    border: 1px solid var(--border);
    flex-shrink: 0;
  }

  .pcal-agenda-badge .pcal-num {
    font-size: 15px;
    line-height: 1;
  }

  .pcal-agenda-badge .caption {
    font-size: 10px;
    text-transform: capitalize;
  }

  .pcal-agenda-items {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    flex: 1;
    min-height: 28px;
    min-width: 0;
  }

  .pcal-agenda-empty {
    font-style: italic;
    opacity: 0.5;
  }

  /* Pill variant — agenda rows. */
  .pcal-pill {
    display: inline-flex;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--chip-accent, var(--border));
    font-size: 11px;
    max-width: 260px;
    box-shadow: none;
  }

  .pcal-pill.done {
    opacity: 0.55;
    text-decoration: line-through;
  }

  .pcal-pill .pcal-chip-time {
    font-size: 10px;
  }

  @media (max-width: 900px) {
    .pcal-week {
      grid-template-columns: repeat(7, minmax(120px, 1fr));
      overflow-x: auto;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .pcal-cell,
    .pcal-col,
    .pcal-agenda-row {
      transition: none;
    }
  }
</style>
