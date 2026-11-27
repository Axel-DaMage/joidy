<script lang="ts">
  import { pie, arc, type PieArcDatum } from 'd3';
  import ChartPie from 'lucide-svelte/icons/chart-pie';
  import ChartCard from './ChartCard.svelte';
  import type { AnalyticsOverview } from '$lib/api';
  import { t } from 'svelte-i18n';

  // XP sources donut (#1499): d3.pie + d3.arc over xp_by_type, with a legend
  // listing XP and event count per type. Unknown types fall back to a
  // humanized event-type string.
  type XpType = AnalyticsOverview['xp_by_type'][number];

  let { byType = [] }: { byType?: XpType[] } = $props();

  // Theme-aware palette — derived from the user's accent trio (#1655) and
  // cycles if there are more types than colors.
  const PALETTE = [
    'var(--chart-1)',
    'var(--chart-2)',
    'var(--chart-3)',
    'var(--chart-4)',
    'var(--chart-5)',
    'var(--chart-6)',
    'color-mix(in srgb, var(--chart-1) 55%, var(--chart-4))',
    'color-mix(in srgb, var(--chart-2) 55%, var(--chart-5))',
    'color-mix(in srgb, var(--chart-3) 55%, var(--chart-6))',
    'color-mix(in srgb, var(--chart-1) 40%, var(--chart-2))',
  ];

  const EXACT_KEYS: Record<string, string> = {
    goal_completed: 'goal_completed',
    pomodoro_completed: 'pomodoro_completed',
    note_created: 'note_created',
    note_edited: 'note_edited',
    daily_activity: 'daily_activity',
    topic_connected: 'topic_connected',
    note_imported_obsidian: 'note_imported_obsidian',
    day_fully_planned: 'day_fully_planned',
  };

  function typeLabel(type: string): string {
    if (EXACT_KEYS[type]) return $t(`analyticsPage.xpTypes.${EXACT_KEYS[type]}`);
    if (type.startsWith('streak_milestone'))
      return $t('analyticsPage.xpTypes.streak_milestone');
    if (type.startsWith('calendar_task')) return $t('analyticsPage.xpTypes.calendar_task');
    if (type.startsWith('strava_')) return $t('analyticsPage.xpTypes.strava');
    if (type.startsWith('tag_')) return $t('analyticsPage.xpTypes.tag');
    // Fallback: humanize the raw event-type string.
    return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  interface Slice extends XpType {
    label: string;
    color: string;
  }

  const ROW_H = 26;
  let legendH = $state(0);
  let boxW = $state(0);
  let boxH = $state(0);

  // Tail types are folded into one "Other" slice when the legend cannot fit
  // them all — the tile never scrolls.
  let slices = $derived.by<Slice[]>(() => {
    const all = byType
      .filter((s) => s.xp > 0)
      .map((s, i) => ({ ...s, label: typeLabel(s.type), color: PALETTE[i % PALETTE.length] }));
    const cap = Math.max(3, Math.floor(legendH / ROW_H));
    if (all.length <= cap) return all;
    const head = all.slice(0, cap - 1);
    const tail = all.slice(cap - 1);
    return [
      ...head,
      {
        type: '__other',
        label: $t('analyticsPage.sources.other'),
        color: 'var(--text-muted)',
        xp: tail.reduce((a, s) => a + s.xp, 0),
        count: tail.reduce((a, s) => a + s.count, 0),
      },
    ];
  });

  let arcs = $derived(
    pie<Slice>()
      .value((s) => s.xp)
      .sort(null)
      .padAngle(0.012)(slices)
  );

  // Donut radius follows the container (fits both width share and height).
  let size = $derived(Math.max(120, Math.min(boxH, boxW * 0.4, 320)));
  let arcGen = $derived(
    arc<PieArcDatum<Slice>>()
      .innerRadius(size * 0.33)
      .outerRadius(size * 0.48)
      .cornerRadius(2)
  );
  let totalXp = $derived(slices.reduce((acc, s) => acc + s.xp, 0));

  let hovered = $state<Slice | null>(null);
</script>

<ChartCard title={$t('analyticsPage.slides.sources')}>
  {#snippet icon()}<ChartPie size={13} />{/snippet}
  {#if byType.filter((s) => s.xp > 0).length === 0}
    <div class="chart-empty">
      <ChartPie size={22} style="opacity:0.25" />
      <span>{$t('analyticsPage.sources.empty')}</span>
    </div>
  {:else}
    <div class="xs-layout" bind:clientWidth={boxW} bind:clientHeight={boxH}>
      <div class="xs-donut-wrap" style:width="{size}px">
        <svg
          width={size}
          height={size}
          viewBox="{-size / 2} {-size / 2} {size} {size}"
          role="img"
          aria-label={$t('analyticsPage.slides.sources')}
        >
          {#each arcs as a (a.data.type)}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <path
              d={arcGen(a) ?? ''}
              fill={a.data.color}
              class="xs-arc"
              class:dim={hovered !== null && hovered !== a.data}
              onmouseenter={() => (hovered = a.data)}
              onmouseleave={() => (hovered = null)}
            />
          {/each}
          <text class="xs-center-val" text-anchor="middle" y="2"
            >{(hovered ?? { xp: totalXp }).xp.toLocaleString()}</text
          >
          <text class="xs-center-lab" text-anchor="middle" y="18"
            >{hovered ? hovered.label : 'XP'}</text
          >
        </svg>
      </div>
      <div class="xs-legend" bind:clientHeight={legendH}>
        {#each slices as s (s.type)}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div
            class="xs-leg-row"
            class:dim={hovered !== null && hovered !== s}
            onmouseenter={() => (hovered = s)}
            onmouseleave={() => (hovered = null)}
          >
            <span class="xs-dot" style="background: {s.color}"></span>
            <span class="xs-name">{s.label}</span>
            <div class="xs-bar"><div class="xs-bar-fill" style="width: {(s.xp / totalXp) * 100}%; background: {s.color}"></div></div>
            <span class="xs-count">{s.count.toLocaleString()}×</span>
            <span class="xs-xp">{s.xp.toLocaleString()}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</ChartCard>

<style>
  .xs-layout {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    gap: var(--s5);
  }
  .xs-donut-wrap {
    flex-shrink: 0;
    display: flex;
  }
  svg {
    display: block;
  }
  .xs-arc {
    transition: opacity 0.15s ease;
    cursor: default;
  }
  .xs-arc.dim {
    opacity: 0.3;
  }
  .xs-center-val {
    font-size: 20px;
    font-weight: 700;
    fill: var(--text-primary);
    font-family: var(--font-mono);
  }
  .xs-center-lab {
    font-size: 10px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .xs-legend {
    flex: 1;
    min-width: 0;
    align-self: stretch;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    overflow: hidden;
    container-type: inline-size;
  }
  @container (max-width: 340px) {
    .xs-bar {
      display: none;
    }
  }
  @container (max-width: 260px) {
    .xs-count {
      display: none;
    }
  }
  .xs-leg-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    transition: opacity 0.15s ease;
    cursor: default;
  }
  .xs-leg-row.dim {
    opacity: 0.35;
  }
  .xs-dot {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    flex-shrink: 0;
  }
  .xs-name {
    color: var(--text-secondary);
    flex: 1 1 70px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .xs-bar {
    flex: 0 0 56px;
    min-width: 0;
    height: 4px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--text-primary) 6%, transparent);
    overflow: hidden;
  }
  .xs-bar-fill {
    height: 100%;
    border-radius: 2px;
    opacity: 0.75;
  }
  .xs-count {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 10px;
    flex-shrink: 0;
    min-width: 46px;
    text-align: right;
  }
  .xs-xp {
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
    min-width: 54px;
    text-align: right;
  }
  .chart-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--text-muted);
    font-size: 12px;
    text-align: center;
  }
</style>
