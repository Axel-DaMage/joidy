<script lang="ts">
  import type { Snippet } from 'svelte';

  // Shared card shell for the analytics carousel slides (#1499) — replicates
  // the .dash-card look used elsewhere in the app (surface + border + blur).
  let {
    title,
    icon,
    actions,
    children,
  }: {
    title: string;
    icon?: Snippet;
    actions?: Snippet;
    children?: Snippet;
  } = $props();
</script>

<div class="ac-card">
  <div class="ac-card-header">
    {#if icon}
      {@render icon()}
    {/if}
    <span class="ac-card-title">{title}</span>
    {#if actions}
      <div class="ac-card-actions">{@render actions()}</div>
    {/if}
  </div>
  <div class="ac-card-body">
    {@render children?.()}
  </div>
</div>

<style>
  .ac-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    backdrop-filter: blur(10px);
    min-height: 0;
    overflow: hidden;
    height: 100%;
    box-sizing: border-box;
  }
  .ac-card-header {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
    flex-shrink: 0;
  }
  .ac-card-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ac-card-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: var(--s2);
  }
  .ac-card-body {
    flex: 1;
    min-height: 0;
    position: relative;
    display: flex;
    flex-direction: column;
  }
</style>
