<script lang="ts">
  // Per-layer visibility toggles + chip-density control for the unified
  // calendar (#1660). Backed by lib/stores/planningCalendar — state persists
  // under `calendarUi` in the shared user-settings blob.
  import { t } from 'svelte-i18n';
  import ListFilter from 'lucide-svelte/icons/list-filter';
  import {
    CALENDAR_LAYERS,
    CHIP_DENSITY_ORDER,
    calendarLayers,
    chipDensity,
    toggleCalendarLayer,
    setChipDensity,
    type CalendarLayer,
  } from '$lib/stores/planningCalendar';

  interface Props {
    /** Restrict which layers are offered (e.g. no 'google' on surfaces that
     * don't fetch events). Defaults to all layers. */
    layers?: CalendarLayer[];
    /** Show the chip-density control (month cells only). */
    showDensity?: boolean;
  }

  let { layers = CALENDAR_LAYERS, showDensity = true }: Props = $props();
</script>

<div class="layer-toggles" role="group" aria-label={$t('calendar.layers')}>
  {#each layers as layer (layer)}
    <button
      class="layer-toggle"
      class:active={$calendarLayers[layer]}
      aria-pressed={$calendarLayers[layer]}
      title={$t(`calendar.layerHint.${layer}`)}
      onclick={() => toggleCalendarLayer(layer)}
    >
      {$t(`calendar.layer.${layer}`)}
    </button>
  {/each}
  {#if showDensity}
    <span class="layer-sep" aria-hidden="true"></span>
    <div
      class="density-toggle"
      role="group"
      aria-label={$t('calendar.density')}
      title={$t('calendar.densityHint')}
    >
      <ListFilter size={11} />
      {#each CHIP_DENSITY_ORDER as level (level)}
        <button
          class="density-btn"
          class:active={$chipDensity === level}
          aria-pressed={$chipDensity === level}
          title={$t(`calendar.densityLevels.${level}`)}
          onclick={() => setChipDensity(level)}
        >
          {$t(`calendar.densityLevels.${level}`)}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .layer-toggles {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 2px;
  }

  .layer-toggle,
  .density-btn {
    font-size: 10px;
    padding: 3px 7px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
    transition:
      color var(--t-fast),
      background var(--t-fast),
      border-color var(--t-fast);
  }

  .layer-toggle:hover,
  .density-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }

  .layer-toggle.active,
  .density-btn.active {
    background: color-mix(in srgb, var(--link) 14%, transparent);
    border-color: color-mix(in srgb, var(--link) 45%, var(--border));
    color: var(--link);
  }

  .layer-sep {
    width: 1px;
    height: 14px;
    background: var(--border);
    margin: 0 4px;
    flex-shrink: 0;
  }

  .density-toggle {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    color: var(--text-muted);
  }

  @media (prefers-reduced-motion: reduce) {
    .layer-toggle,
    .density-btn {
      transition: none;
    }
  }
</style>
