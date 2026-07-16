<script lang="ts">
  import { browser } from '$app/environment';
  import DynamicIcon from './DynamicIcon.svelte';

  let hasError = false;
  let errorMessage = '';
  let errorStack = '';
  let showDetails = false;

  export function handleError(e: unknown) {
    hasError = true;
    if (e instanceof Error) {
      errorMessage = e.message;
      errorStack = e.stack || '';
    } else {
      errorMessage = String(e);
    }
    console.error('[ErrorBoundary]', e);
  }

  function retry() {
    hasError = false;
    errorMessage = '';
    errorStack = '';
  }
</script>

{#if hasError}
  <div class="error-boundary">
    <DynamicIcon name="AlertTriangle" size={32} />
    <h3>Algo sali&oacute; mal</h3>
    <p class="error-msg">{errorMessage || 'Error inesperado en este componente.'}</p>
    <div class="actions">
      <button class="btn" on:click={retry}>
        <DynamicIcon name="RefreshCw" size={12} /> Reintentar
      </button>
      <button class="btn btn-ghost" on:click={() => showDetails = !showDetails}>
        Detalles
      </button>
    </div>
    {#if showDetails && errorStack}
      <pre class="error-stack">{errorStack}</pre>
    {/if}
  </div>
{:else}
  <slot />
{/if}

<style>
  .error-boundary {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
    text-align: center;
    color: var(--text-secondary);
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    margin: 16px;
  }
  .error-boundary :global(svg) { color: var(--error, #ef4444); margin-bottom: 12px; }
  .error-boundary h3 { margin: 0 0 8px 0; font-size: 16px; color: var(--text-primary); }
  .error-msg { font-size: 13px; color: var(--text-muted); margin: 0 0 16px 0; max-width: 400px; }
  .actions { display: flex; gap: 8px; }
  .btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 14px; border-radius: var(--r);
    font-size: 12px; cursor: pointer; border: 1px solid var(--border);
    background: var(--surface); color: var(--text-primary);
  }
  .btn-ghost { background: transparent; color: var(--text-muted); }
  .error-stack {
    margin-top: 12px; padding: 8px; font-size: 10px;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--r); max-width: 100%; overflow-x: auto;
    text-align: left; white-space: pre-wrap; color: var(--text-muted);
    max-height: 200px;
  }
</style>
