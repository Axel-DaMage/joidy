<script lang="ts">
  import { fade, scale } from 'svelte/transition';
  import { uiModal, closeModal } from '$lib/stores/ui';
  import DynamicIcon from './DynamicIcon.svelte';
  import { focusTrap } from '$lib/actions/focusTrap';

  export let title = '';
  export let size: 'sm' | 'md' | 'lg' = 'md';

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      closeModal();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $uiModal.isOpen}
  <div
    class="modal-overlay"
    role="dialog"
    aria-modal="true"
    aria-label={title || 'Diálogo'}
    transition:fade={{ duration: 150 }}
    on:click|self={closeModal}
  >
    <div
      class="modal modal-{size}"
      transition:scale={{ duration: 200, start: 0.95 }}
      use:focusTrap
    >
      <div class="modal-header">
        <h3 class="modal-title">{title}</h3>
        <button class="modal-close" autofocus on:click={closeModal}>
          <DynamicIcon name="X" size={18} />
        </button>
      </div>
      <div class="modal-body">
        <slot />
      </div>
      {#if $$slots.footer}
        <div class="modal-footer">
          <slot name="footer" />
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(2px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    padding: 20px;
  }

  .modal {
    background: var(--elevated, #1a1a1a);
    border: 1px solid var(--border);
    border-radius: 12px;
    width: 100%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
  }

  .modal-sm { max-width: 400px; }
  .modal-md { max-width: 560px; }
  .modal-lg { max-width: 800px; }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .modal-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .modal-close {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-close:hover {
    background: var(--hover);
    color: var(--text-primary);
  }

  .modal-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
  }

  .modal-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    flex-shrink: 0;
  }
</style>