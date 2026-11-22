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

  // Theme-aware palette — cycles if there are more types than colors.
  const PALETTE = [
    'var(--xp)',
    'var(--success)',
    'var(--link)',
    'var(--today)',
    'var(--xp-2)',
    'var(--error)',
    'var(--xp-3)',
    'color-mix(in srgb, var(--xp) 55%, var(--link))',
    'color-mix(in srgb, var(--success) 55%, var(--link))',
    'color-mix(in srgb, var(--today) 55%, var(--error))',
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
    if (EXACT_KEYS[type]) return $t(`goalsAnalytics.xpTypes.${EXACT_KEYS[type]}`);
    if (type.startsWith('streak_milestone'))
      return $t('goalsAnalytics.xpTypes.streak_milestone');
    if (type.startsWith('calendar_task')) return $t('goalsAnalytics.xpTypes.calendar_task');
    if (type.startsWith('strava_')) return $t('goalsAnalytics.xpTypes.strava');
    if (type.startsWith('tag_')) return $t('goalsAnalytics.xpTypes.tag');
    // Fallback: humanize the raw event-type string.
    return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  interface Slice extends XpType {
    label: string;
    color: string;
  }

  let slices = $derived<Slice[]>(
    byType
      .filter((s) => s.xp > 0)
      .map((s, i) => ({ ...s, label: typeLabel(s.type), color: PALETTE[i % PALETTE.length] }))
  );

  let arcs = $derived(
    pie<Slice>()
      .value((s) => s.xp)
      .sort(null)
      .padAngle(0.015)(slices)
  );

  const arcGen = arc<PieArcDatum<Slice>>().innerRadius(58).outerRadius(92).cornerRadius(3);
  let totalXp = $derived(slices.reduce((acc, s) => acc + s.xp, 0));

  let hovered = $state<Slice | null>(null);
</script>

<ChartCard title={$t('goalsAnalytics.slides.sources')}>
  {#snippet icon()}<ChartPie size={15} />{/snippet}
  {#if slices.length === 0}
    <div class="chart-empty">
      <ChartPie size={22} style="opacity:0.25" />
      <span>{$t('goalsAnalytics.sources.empty')}</span>
    </div>
  {:else}
    <div class="xs-layout">
      <div class="xs-donut-wrap">
        <svg viewBox="0 0 200 200" role="img" aria-label={$t('goalsAnalytics.slides.sources')}>
          <g transform="translate(100,100)">
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
            <text class="xs-center-val" text-anchor="middle" y="-2"
              >{(hovered ?? { xp: totalXp }).xp.toLocaleString()}</text
            >
            <text class="xs-center-lab" text-anchor="middle" y="14"
              >{hovered ? hovered.label : 'XP'}</text
            >
          </g>
        </svg>
      </div>
      <div class="xs-legend">
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
            <span class="xs-count">{s.count}×</span>
            <span class="xs-xp">{s.xp.toLocaleString()} XP</span>
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
    flex: 0 0 200px;
    max-width: 42%;
  }
  svg {
    width: 100%;
    height: auto;
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
    font-size: 8px;
    fill: var(--text-muted);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .xs-legend {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 100%;
    overflow-y: auto;
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
    width: 9px;
    height: 9px;
    border-radius: 2.5px;
    flex-shrink: 0;
  }
  .xs-name {
    color: var(--text-secondary);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .xs-count {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 10px;
    flex-shrink: 0;
  }
  .xs-xp {
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 700;
    flex-shrink: 0;
    min-width: 56px;
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
    min-height: 180px;
  }
  @media (max-width: 700px) {
    .xs-layout {
      flex-direction: column;
      gap: var(--s3);
    }
    .xs-donut-wrap {
      flex: none;
      max-width: 180px;
    }
    .xs-legend {
      width: 100%;
    }
  }
</style>
