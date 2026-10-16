<script lang="ts">
  import { t } from 'svelte-i18n';

  interface Props {
    zoomIn: () => void;
    zoomOut: () => void;
    zoomToFit: () => void;
    resetView: () => void;
    clearHighlights: () => void;
  }

  let { zoomIn, zoomOut, zoomToFit, resetView, clearHighlights }: Props = $props();
</script>

<!-- PERSISTENT RIGHT TOOLBAR CONTROLS (FIT, ZOOM, MINIMAP) -->
<div class="graph-quick-actions">
  <button class="quick-btn" title={$t('knowledgeGraphForce.zoomIn')} onclick={zoomIn}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="action-icon"
      ><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line
        x1="8"
        y1="12"
        x2="16"
        y2="12"
      ></line></svg
    >
  </button>
  <button class="quick-btn" title={$t('knowledgeGraphForce.zoomOut')} onclick={zoomOut}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="action-icon"
      ><circle cx="12" cy="12" r="10"></circle><line x1="8" y1="12" x2="16" y2="12"></line></svg
    >
  </button>
  <button class="quick-btn" title={$t('knowledgeGraphForce.fitToScreen')} onclick={zoomToFit}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="action-icon"
      ><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line
        x1="9"
        y1="9"
        x2="15"
        y2="15"
      ></line><line x1="15" y1="9" x2="9" y2="15"></line></svg
    >
  </button>
  <button class="quick-btn" title={$t('knowledgeGraphForce.center')} onclick={resetView}>
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="action-icon"
      ><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="3"></circle></svg
    >
  </button>
  <button
    class="quick-btn"
    title={$t('knowledgeGraphForce.clearSelection')}
    onclick={clearHighlights}
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="action-icon"
      ><path d="M21 4H8l-7 8 7 8h13a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"></path><line
        x1="18"
        y1="9"
        x2="12"
        y2="15"
      ></line><line x1="12" y1="9" x2="18" y2="15"></line></svg
    >
  </button>
</div>

<style>
  /* PERSISTENT FLOATING QUICK ACTIONS (FIT / CENTERING) */
  .graph-quick-actions {
    position: absolute;
    bottom: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    z-index: var(--z-modal);
    padding: 8px;
    border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    backdrop-filter: blur(12px);
  }

  .quick-btn {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .quick-btn:hover {
    background: rgba(255, 255, 255, 0.05);
    color: var(--accent);
  }

  .action-icon {
    width: 15px;
    height: 15px;
  }
</style>
