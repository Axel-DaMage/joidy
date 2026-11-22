<script lang="ts">
  import type { Snippet } from 'svelte';

  // Shared card shell for the analytics carousel slides (#1499) — same
  // surface/border/header treatment as the .dash-card used across the app.
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
      <span class="ac-card-icon">{@render icon()}</span>
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
    min-height: 0;
    min-width: 0;
    overflow: hidden;
    height: 100%;
    box-sizing: border-box;
    backdrop-filter: blur(10px);
    transition:
      border-color 0.2s,
      background 0.2s;
    animation: ac-in 0.45s cubic-bezier(0.2, 0.7, 0.2, 1) both;
  }
  .ac-card:hover {
    border-color: var(--primary);
    background: var(--surface-hover);
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
    min-width: 0;
  }
  .ac-card-icon {
    display: inline-flex;
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
    flex-shrink: 0;
  }
  .ac-card-body {
    flex: 1;
    min-height: 0;
    min-width: 0;
    position: relative;
    display: flex;
    flex-direction: column;
  }
  @keyframes ac-in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .ac-card {
      animation: none;
    }
  }
</style>
