<script lang="ts">
  export let title: string;
  export let accentColor: string = 'var(--accent)';
  export let showAction: boolean = false;
  export let actionLabel: string = 'ver →';
  export let actionHref: string = '';
</script>

<div class="section-header section-header--fixed">
  <h4 style="color: {accentColor}">{title}</h4>
  {#if showAction && actionHref}
    <a href={actionHref} class="section-action">{actionLabel}</a>
  {/if}
</div>

<style>
  .section-header--fixed {
    display: flex;
    justify-content: space-between;
    align-items: center;
    min-height: 28px;
    padding: 4px 0;
    border-top: 1px solid var(--border-light);
  }

  h4 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }

  .section-action {
    font-size: 11px;
    color: var(--text-muted);
    text-decoration: none;
    padding: 2px 6px;
    border-radius: 4px;
    transition: all var(--t-fast);
  }

  .section-action:hover {
    color: var(--accent);
    background: var(--hover);
  }
</style>