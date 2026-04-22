<script lang="ts">
  import type { StreakDay } from "$lib/api";

  export let history: StreakDay[] = [];
  export let color = "#c8a96e";
  export let startDate: string | null = null;

  type ViewMode = "week" | "month" | "year";
  let view: ViewMode = "week";

  const today = new Date();

  function localIso(date: Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  const todayIso = localIso(today);
  const checkedSet = new Set<string>();

  $: {
    checkedSet.clear();
    for (const item of history) {
      if (item.checked) checkedSet.add(item.date);
    }

    // If there is no explicit history yet, infer active days from start date.
    if (checkedSet.size === 0 && startDate) {
      const start = new Date(startDate);
      const end = new Date(today);
      if (!Number.isNaN(start.getTime()) && start <= end) {
        const cursor = new Date(start);
        while (cursor <= end) {
          checkedSet.add(localIso(cursor));
          cursor.setDate(cursor.getDate() + 1);
        }
      }
    }
  }

  const DAY_NAMES = ["DOM", "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB"];

  function getWeekDays(activeSet: Set<string>) {
    const days = [];
    const start = new Date(today);
    // Alineamos el inicio de la semana al Domingo para que coincida con "DOM", "LUN"...
    start.setDate(start.getDate() - start.getDay());

    for (let i = 0; i < 7; i++) {
      const date = new Date(start);
      date.setDate(date.getDate() + i);
      const iso = localIso(date);
      days.push({
        dayNum: date.getDate(),
        checked: activeSet.has(iso),
        isToday: iso === todayIso,
      });
    }
    return days;
  }

  function getMonthGrid(activeSet: Set<string>) {
    const year = today.getFullYear();
    const month = today.getMonth();
    const first = new Date(year, month, 1);
    const last = new Date(year, month + 1, 0);
    const startDow = first.getDay();
    const cells = [];

    for (let i = 0; i < startDow; i++) {
      cells.push({ inMonth: false, checked: false, dayNum: 0, isToday: false });
    }

    for (let day = 1; day <= last.getDate(); day++) {
      const date = new Date(year, month, day);
      const iso = localIso(date);
      cells.push({
        inMonth: true,
        checked: activeSet.has(iso),
        dayNum: day,
        isToday: iso === todayIso,
      });
    }

    while (cells.length % 7 !== 0) {
      cells.push({ inMonth: false, checked: false, dayNum: 0, isToday: false });
    }

    return cells;
  }

  function getYearMonths(activeSet: Set<string>) {
    const year = today.getFullYear();
    const labels = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
    return Array.from({ length: 12 }, (_, month) => {
      const lastDay = new Date(year, month + 1, 0).getDate();
      const days = [];
      for (let day = 1; day <= lastDay; day++) {
        const date = new Date(year, month, day);
        const iso = localIso(date);
        days.push({
          checked: date <= today && activeSet.has(iso),
          past: date <= today,
        });
      }
      return { label: labels[month], days };
    });
  }

  $: weekDays = getWeekDays(checkedSet);
  $: monthGrid = getMonthGrid(checkedSet);
  $: yearMonths = getYearMonths(checkedSet);

  const MONTH_LABEL = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
  ][today.getMonth()];
</script>

<div class="activity" style="--ac: {color};">
  <div class="tabs">
    <button class="tab" class:on={view === "week"} on:click={() => (view = "week")}>Semana</button>
    <button class="tab" class:on={view === "month"} on:click={() => (view = "month")}>Mes</button>
    <button class="tab" class:on={view === "year"} on:click={() => (view = "year")}>Año</button>
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
            <div class="week-col" class:checked={day.checked} class:today={day.isToday}>
              <div class="wd-num-wrap">
                <span class="wd-num" class:today-num={day.isToday} class:checked-num={day.checked && !day.isToday}>{day.dayNum}</span>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {:else if view === "month"}
      <span class="title">{MONTH_LABEL}</span>
      <div class="month-wrap">
        <div class="mhdr">
          {#each DAY_NAMES as label}
            <span class="ml">{label}</span>
          {/each}
        </div>
        <div class="mgrid">
          {#each monthGrid as cell}
            <div class="mcell" class:empty={!cell.inMonth} class:checked={cell.checked} class:today={cell.isToday}>
              {#if cell.inMonth}
                <span class="mday" class:on={cell.checked} class:mtoday={cell.isToday}>{cell.dayNum}</span>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <span class="title">{today.getFullYear()}</span>
      <div class="ygrid">
        {#each yearMonths as monthItem}
          <div class="ymo">
            <span class="yl">{monthItem.label}</span>
            <div class="ydots">
              {#each monthItem.days as day}
                <div class="yd" class:on={day.checked} class:fut={!day.past}></div>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .activity {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    width: 100%;
    min-height: 100%;
  }

  .tabs {
    display: flex;
    gap: 2px;
    background: var(--elevated);
    border-radius: 4px;
    padding: 2px;
  }

  .tab {
    padding: 3px 14px;
    font-size: 9px;
    font-family: var(--font-mono);
    background: none;
    border: none;
    color: var(--text-disabled);
    cursor: pointer;
    border-radius: 3px;
    transition: all 0.15s;
    letter-spacing: 0.04em;
  }

  .tab:hover {
    color: var(--text-muted);
  }

  .tab.on {
    background: var(--surface);
    color: var(--ac);
  }

  .view-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    flex: 1;
    width: 100%;
    min-height: 0;
  }

  .title {
    font-size: 9px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.06em;
  }

  .week-wrap,
  .month-wrap {
    width: 100%;
    max-width: 460px;
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
    min-height: 26px;
    background: var(--surface);
    font-size: 9px;
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

  .week-col {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    margin-left: -1px;
    margin-top: -1px;
    transition: border-color 0.15s;
  }

  .week-col:first-child {
    margin-left: 0;
  }

  .week-col.checked {
    border-color: var(--ac);
    z-index: 1;
  }

  .wd-num-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .wd-num {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-secondary);
    border-radius: 50%;
    transition: all 0.2s;
  }

  .wd-num.today-num,
  .wd-num.checked-num,
  .mday.on,
  .mday.mtoday {
    background: var(--ac);
    color: var(--bg);
  }

  .wd-num.today-num,
  .mday.mtoday {
    font-weight: 700;
  }

  .wd-num.checked-num,
  .mday.on {
    font-weight: 600;
  }

  .mgrid {
    gap: 1px;
    background: var(--border);
  }

  .mcell {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--surface);
    transition: box-shadow 0.15s;
  }

  .mcell.checked {
    box-shadow: inset 0 0 0 1px var(--ac);
    z-index: 1;
  }

  .mcell.empty {
    background: #000;
    opacity: 1;
  }

  .mday {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-secondary);
    border-radius: 50%;
    transition: all 0.2s;
  }

  .ygrid {
    display: flex;
    gap: 8px;
    justify-content: center;
    flex-wrap: nowrap;
    overflow: hidden;
    width: 100%;
  }

  .ymo {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
  }

  .yl {
    font-size: 8px;
    font-family: var(--font-mono);
    color: var(--text-muted);
  }

  .ydots {
    display: grid;
    grid-template-columns: repeat(7, 5px);
    gap: 1px;
  }

  .yd {
    width: 5px;
    height: 5px;
    border-radius: 1px;
    background: var(--border);
  }

  .yd.on {
    background: var(--ac);
  }

  .yd.fut {
    opacity: 0.12;
  }
</style>
