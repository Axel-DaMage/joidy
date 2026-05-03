<script lang="ts">
  import StreakIcon from './StreakIcon.svelte';
  import type { StreakDay } from "$lib/api";

  let {
    history = [],
    color = "#c8a96e",
    startDate = null,
    targetDate = null,
    /** ISO date string currently highlighted by the parent */
    selectedDate = null,
    onselect = (_date: string) => {},
    /** allow navigating N months into the future (0 = only up to current month) */
    maxFutureMonths = 0,
    /** If true, hide the view selection tabs */
    hideTabs = false,
  }: {
    history?: StreakDay[];
    color?: string;
    startDate?: string | null;
    targetDate?: string | null;
    selectedDate?: string | null;
    onselect?: (date: string) => void;
    maxFutureMonths?: number;
    hideTabs?: boolean;
  } = $props();

  type ViewMode = "week" | "month" | "year";

  function getInitialView(): ViewMode {
    if (typeof localStorage === 'undefined') return "year";
    const saved = localStorage.getItem('goals.historyView');
    if (saved === 'week' || saved === 'month' || saved === 'year') return saved;
    return "year";
  }

  let view: ViewMode = $state(getInitialView());

  $effect(() => {
    if (typeof localStorage !== 'undefined' && view) {
      localStorage.setItem('goals.historyView', view);
    }
  });

  const today = new Date();

  function localIso(date: Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  const todayIso = localIso(today);

  function parseLocalIso(s: string) {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  }

  function isIcon(s: string | null) {
    if (!s) return false;
    // Heuristic: Lucide icons are longer than 2 chars and usually start with uppercase
    return s.length > 2;
  }

  const targetIso = $derived(targetDate || null);

  const dayDataMap = $derived.by(() => {
    const newMap = new Map<string, any>();
    for (const item of history) {
      if (item.checked || (item as any).failed) newMap.set(item.date, item);
    }

    // If there is no explicit history yet, infer active days from start date.
    if (newMap.size === 0 && startDate) {
      const start = parseLocalIso(startDate);
      const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());
      if (!Number.isNaN(start.getTime()) && start <= end) {
        const cursor = new Date(start);
        while (cursor <= end) {
          newMap.set(localIso(cursor), { checked: true });
          cursor.setDate(cursor.getDate() + 1);
        }
      }
    }
    return newMap;
  });

  const DAY_NAMES = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"];
  const MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
  ];

  const currentMonthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  const minYearMonth = new Date(today.getFullYear(), today.getMonth() - 12, 1);
  let yearCursor = $state(new Date(today.getFullYear(), today.getMonth(), 1));

  function monthKey(date: Date) {
    return date.getFullYear() * 12 + date.getMonth();
  }

  function buildCell(iso: string, data: any, dayNum: number, inMonth: boolean) {
    return {
      iso,
      inMonth,
      checked: data ? data.checked : false,
      failed: data ? data.failed : false,
      emoji: data ? data.failEmoji : null,
      dayNum,
      isToday: iso === todayIso,
      isTarget: iso === targetIso,
      isSelected: iso === selectedDate,
    };
  }

  function getWeekDays(dataMap: Map<string, any>) {
    const days = [];
    const start = new Date(today);
    const diff = today.getDay() === 0 ? 6 : today.getDay() - 1;
    start.setDate(today.getDate() - diff);

    for (let i = 0; i < 7; i++) {
      const date = new Date(start);
      date.setDate(date.getDate() + i);
      const iso = localIso(date);
      const data = dataMap.get(iso);
      days.push(buildCell(iso, data, date.getDate(), true));
    }
    return days;
  }

  function getMonthGrid(dataMap: Map<string, any>, baseDate: Date = today) {
    const year = baseDate.getFullYear();
    const month = baseDate.getMonth();
    const first = new Date(year, month, 1);
    const last = new Date(year, month + 1, 0);
    const startDow = (first.getDay() + 6) % 7;
    const cells = [];

    for (let i = 0; i < startDow; i++) {
      cells.push(buildCell('', null, 0, false));
    }

    for (let day = 1; day <= last.getDate(); day++) {
      const date = new Date(year, month, day);
      const iso = localIso(date);
      const data = dataMap.get(iso);
      cells.push(buildCell(iso, data, day, true));
    }

    while (cells.length % 7 !== 0) {
      cells.push(buildCell('', null, 0, false));
    }

    return cells;
  }

  function shiftYearMonth(offset: number) {
    const nextCursor = new Date(yearCursor.getFullYear(), yearCursor.getMonth() + offset, 1);
    if (monthKey(nextCursor) < monthKey(minYearMonth)) return;
    
    const maxFuture = (maxFutureMonths && !Number.isNaN(maxFutureMonths)) ? maxFutureMonths : 0;
    if (monthKey(nextCursor) > monthKey(currentMonthStart) + maxFuture) return;
    
    yearCursor = nextCursor;
  }

  function handleYearKeyboardNav(event: KeyboardEvent) {
    if (view !== "year") return;
    const target = event.target as HTMLElement | null;
    const tag = target?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable) return;
    if (event.key === "ArrowLeft") { event.preventDefault(); shiftYearMonth(-1); }
    else if (event.key === "ArrowRight") { event.preventDefault(); shiftYearMonth(1); }
  }

  function selectDay(iso: string) {
    if (!iso) return;
    onselect(iso);
  }

  const weekDays = $derived(getWeekDays(dayDataMap));
  const monthGrid = $derived(getMonthGrid(dayDataMap));
  const yearGrid = $derived(getMonthGrid(dayDataMap, yearCursor));
  const canGoPrev = $derived(monthKey(yearCursor) > monthKey(minYearMonth));
  const canGoNext = $derived.by(() => {
    if (maxFutureMonths && !Number.isNaN(maxFutureMonths)) {
      return monthKey(yearCursor) < monthKey(currentMonthStart) + Math.max(0, maxFutureMonths);
    }
    return monthKey(yearCursor) < monthKey(currentMonthStart);
  });

  const MONTH_LABEL = $derived(MONTH_NAMES[today.getMonth()]);
  const YEAR_LABEL = $derived(`${MONTH_NAMES[yearCursor.getMonth()]} ${yearCursor.getFullYear()}`);
</script>

<svelte:window onkeydown={handleYearKeyboardNav} />

<div class="activity" style="--ac: {color};">
  {#if !hideTabs}
    <div class="tabs">
      <button class="tab" class:on={view === "week"} onclick={() => (view = "week")}>Semana</button>
      <button class="tab" class:on={view === "month"} onclick={() => (view = "month")}>Mes</button>
      <button class="tab" class:on={view === "year"} onclick={() => (view = "year")}>Año</button>
    </div>
  {/if}

  <div class="view-title-row">
    {#if view === "week"}
      <span class="title">Semana actual</span>
    {:else if view === "month"}
      <span class="title">{MONTH_LABEL}</span>
    {:else}
      <button
        class="nav-btn"
        class:disabled={!canGoPrev}
        onclick={() => shiftYearMonth(-1)}
        disabled={!canGoPrev}
      >
        ‹
      </button>
      <span class="title">{YEAR_LABEL}</span>
      <button
        class="nav-btn"
        class:disabled={!canGoNext}
        onclick={() => shiftYearMonth(1)}
        disabled={!canGoNext}
      >
        ›
      </button>
    {/if}
  </div>

  <div class="view-area">
    {#if view === "week"}
      <div class="week-wrap">
        <div class="mhdr">
          {#each DAY_NAMES as label}
            <span class="ml">{label}</span>
          {/each}
        </div>
        <div class="week-row">
          {#each weekDays as day}
            <button
              class="week-col"
              class:checked={day.checked}
              class:failed={day.failed}
              class:today={day.isToday}
              class:target={day.isTarget}
              class:selected={day.isSelected}
              onclick={() => selectDay(day.iso)}
              title={day.iso}
            >
              <div class="wd-num-wrap">
                {#if day.failed && day.emoji}
                  <span class="wd-emoji" class:on={day.failed}>
                    {#if isIcon(day.emoji)}
                      <StreakIcon name={day.emoji} size={20} color="var(--bg)" />
                    {:else}
                      {day.emoji}
                    {/if}
                  </span>
                {:else}
                  <span class="wd-num"
                    class:today-num={day.isToday}
                    class:checked-num={day.checked && !day.isToday}
                    class:target-num={day.isTarget}
                    class:selected-num={day.isSelected && !day.isToday && !day.checked}
                  >{day.dayNum}</span>
                {/if}
              </div>
            </button>
          {/each}
        </div>
      </div>
    {:else if view === "month"}
      <div class="month-wrap">
        <div class="mhdr">
          {#each DAY_NAMES as label}
            <span class="ml">{label}</span>
          {/each}
        </div>
        <div class="mgrid-frame">
          <div class="mgrid">
            {#each monthGrid as cell}
              <button
                class="mcell"
                class:empty={!cell.inMonth}
                class:checked={cell.checked}
                class:failed={cell.failed}
                class:today={cell.isToday}
                class:target={cell.isTarget}
                class:selected={cell.isSelected}
                onclick={() => selectDay(cell.iso)}
                title={cell.iso || undefined}
                disabled={!cell.inMonth}
              >
                {#if cell.inMonth}
                  {#if cell.failed && cell.emoji}
                    <span class="mday-emoji" class:on={cell.failed} title="Fallido">
                      {#if isIcon(cell.emoji)}
                        <StreakIcon name={cell.emoji} size={20} color="var(--bg)" />
                      {:else}
                        {cell.emoji}
                      {/if}
                    </span>
                  {:else}
                    <span class="mday" class:on={cell.checked} class:mtoday={cell.isToday} class:mtarget={cell.isTarget} class:mselected={cell.isSelected && !cell.isToday && !cell.checked}>{cell.dayNum}</span>
                  {/if}
                {/if}
              </button>
            {/each}
          </div>
        </div>
      </div>
    {:else}
      <div class="year-wrap">
        <div class="month-wrap">
          <div class="mhdr">
            {#each DAY_NAMES as label}
              <span class="ml">{label}</span>
            {/each}
          </div>
          <div class="mgrid-frame">
            <div class="mgrid">
              {#each yearGrid as cell}
                <button
                  class="mcell"
                  class:empty={!cell.inMonth}
                  class:checked={cell.checked}
                  class:failed={cell.failed}
                  class:today={cell.isToday}
                  class:target={cell.isTarget}
                  class:selected={cell.isSelected}
                  onclick={() => selectDay(cell.iso)}
                  title={cell.iso || undefined}
                  disabled={!cell.inMonth}
                >
                  {#if cell.inMonth}
                    {#if cell.failed && cell.emoji}
                      <span class="mday-emoji" class:on={cell.failed} title="Fallido">
                        {#if isIcon(cell.emoji)}
                          <StreakIcon name={cell.emoji} size={20} color="var(--bg)" />
                        {:else}
                          {cell.emoji}
                        {/if}
                      </span>
                    {:else}
                      <span class="mday" class:on={cell.checked} class:mtoday={cell.isToday} class:mtarget={cell.isTarget} class:mselected={cell.isSelected && !cell.isToday && !cell.checked}>{cell.dayNum}</span>
                    {/if}
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .activity {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    min-height: 100%;
    height: 100%;
    max-height: 100%;
  }

  .tabs {
    display: flex;
    gap: 3px;
    background: var(--elevated);
    border-radius: 6px;
    padding: 3px;
  }

  .tab {
    padding: 4px 16px;
    font-size: 11px;
    font-family: var(--font-mono);
    background: none;
    border: none;
    color: var(--text-disabled);
    cursor: pointer;
    border-radius: 3px;
    transition: all 0.15s;
    letter-spacing: 0.04em;
  }

  .tab:hover { color: var(--text-muted); }

  .tab.on {
    background: var(--surface);
    color: var(--ac);
  }

  .view-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex: 1;
    width: 100%;
    min-height: 0;
    max-width: 620px;
    margin: 0 auto;
  }

  .view-title-row {
    min-height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    width: 100%;
  }

  .title {
    font-size: 13px;
    font-family: var(--font-mono);
    color: var(--ac);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 600;
  }

  .week-wrap,
  .month-wrap {
    width: 100%;
    max-width: 560px;
    margin: 0 auto;
  }

  .mhdr {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    width: 100%;
  }

  .ml {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 32px;
    background: var(--surface);
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-disabled);
    letter-spacing: 0.05em;
  }

  .week-row,
  .mgrid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    width: 100%;
  }

  /* ── Week column ── */
  .week-col {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    margin-left: -1px;
    margin-top: -1px;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    padding: 0;
  }

  .week-col:first-child { margin-left: 0; }
  .week-col:hover { border-color: var(--ac); z-index: 1; background: color-mix(in srgb, var(--ac) 8%, var(--surface)); }
  .week-col.checked { border-color: var(--ac); z-index: 1; }
  .week-col.selected { border-color: var(--ac); box-shadow: 0 0 0 2px var(--ac); z-index: 3; }

  /* ── Day number / emoji ── */
  .wd-num-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .wd-num {
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-secondary);
    border-radius: 50%;
    transition: all 0.2s;
  }

  .wd-emoji, .mday-emoji {
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    border-radius: 50%;
    transition: all 0.2s;
  }

  .wd-emoji.on, .mday-emoji.on {
    background: var(--error);
    color: var(--bg);
  }

  .week-col.failed, .mcell.failed {
    border-color: var(--error);
    z-index: 1;
  }

  .wd-num.today-num,
  .wd-num.checked-num,
  .mday.on,
  .mday.mtoday {
    background: var(--ac);
    color: var(--bg);
  }

  .wd-num.today-num, .mday.mtoday { font-weight: 700; }
  .wd-num.checked-num, .mday.on { font-weight: 600; }

  .wd-num.selected-num,
  .mday.mselected {
    box-shadow: 0 0 0 2px var(--ac);
  }

  .wd-num.target-num, .mday.mtarget {
    background: #10b981 !important;
    color: #000 !important;
    font-weight: 700;
  }

  .week-col.target, .mcell.target { border-color: #10b981 !important; z-index: 2; }

  /* ── Month grid ── */
  .mgrid {
    gap: 1px;
    background: var(--border);
  }

  .mgrid-frame {
    width: 100%;
    aspect-ratio: 7 / 6;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    overflow: hidden;
  }

  .mcell {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--surface);
    transition: box-shadow 0.15s, background 0.15s;
    cursor: pointer;
    border: none;
    padding: 0;
  }

  .mcell:not(.empty):hover {
    background: color-mix(in srgb, var(--ac) 10%, var(--surface));
    box-shadow: inset 0 0 0 1px var(--ac);
    z-index: 1;
  }

  .mcell.checked { box-shadow: inset 0 0 0 1px var(--ac); z-index: 1; }
  .mcell.failed:not(.checked) { box-shadow: inset 0 0 0 1px var(--error); }
  .mcell.selected { box-shadow: inset 0 0 0 2px var(--ac) !important; z-index: 3; }

  .mcell.empty {
    background: #000;
    opacity: 1;
    cursor: default;
    pointer-events: none;
  }

  .mcell:disabled { cursor: default; }

  .mday {
    width: 38px;
    height: 38px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-secondary);
    border-radius: 50%;
    transition: all 0.2s;
  }

  /* ── Year nav ── */
  .year-wrap {
    width: 100%;
    max-width: 560px;
    position: relative;
    margin: 0 auto;
  }

  .year-wrap .month-wrap { max-width: 560px; }

  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--surface-sub);
    color: var(--text-muted);
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
    transition: all 0.2s;
  }

  .nav-btn:hover { color: var(--ac); border-color: var(--ac); background: var(--surface-hover); }

  .nav-btn.disabled,
  .nav-btn:disabled {
    opacity: 0.2;
    cursor: not-allowed;
    color: var(--text-disabled);
    border-color: var(--border);
  }
</style>
