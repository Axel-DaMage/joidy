<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';

  // Shared frame for every settings section (#1671): identical card chrome,
  // header (title + optional description) and content spacing, so the
  // Settings* children only own their controls.
  interface Props {
    /** Section slug — also used for the element id (`settings-<id>`). */
    id: string;
    title: string;
    description?: string;
    /** DynamicIcon name shown next to the title. */
    icon?: string;
    children?: import('svelte').Snippet;
  }

  let { id, title, description, icon, children }: Props = $props();
</script>

<section class="settings-section" id="settings-{id}" aria-labelledby="settings-{id}-title">
  <header class="settings-section-header">
    <h2 class="settings-section-title" id="settings-{id}-title">
      {#if icon}
        <DynamicIcon name={icon} size={14} />
      {/if}
      {title}
    </h2>
    {#if description}
      <p class="settings-section-description">{description}</p>
    {/if}
  </header>
  <div class="settings-section-body">
    {@render children?.()}
  </div>
</section>

<style>
  /* Panel Border Standard: boxed interior panel, never a flat divider. */
  .settings-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
  }

  .settings-section-header {
    padding: var(--s3) var(--s4);
    border-bottom: 1px solid var(--border-light);
  }

  .settings-section-title {
    display: flex;
    align-items: center;
    gap: 7px;
    margin: 0;
    font-size: 11px;
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--xp, var(--accent));
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .settings-section-description {
    margin: 6px 0 0;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .settings-section-body {
    padding: var(--s3) var(--s4);
  }
</style>
