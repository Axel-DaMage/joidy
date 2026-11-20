<script lang="ts">
  // Live markdown preview pane for the Goal Editor (#935). Renders the shared
  // `goalEditor.content` through the common marked + DOMPurify + highlight.js
  // pipeline, debounced well under the 150ms budget required by the redesign.
  import { untrack } from 'svelte';
  import { t } from 'svelte-i18n';
  import { renderMarkdown as renderMarkdownShared } from '$lib/utils/markdown';
  import { goalEditor } from '$lib/stores/goalEditor.svelte';

  interface Props {
    /** Double-click on the preview asks the container to show the editor
     *  again (relevant on layouts where the preview replaces the editor). */
    onrequestedit?: () => void;
  }

  let { onrequestedit }: Props = $props();

  // Preview renders lag typing by at most this much (#935 requires <150ms).
  const PREVIEW_DEBOUNCE_MS = 120;

  // Seed with the current value so the first render is instant; the debounce
  // effect keeps it updated afterwards.
  let debouncedContent = $state(untrack(() => goalEditor.content));

  // The effect cleanup clears the pending debounce on every re-run AND on
  // component teardown (#1003).
  $effect(() => {
    const current = goalEditor.content;
    const debounceTimer = setTimeout(() => {
      debouncedContent = current;
    }, PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(debounceTimer);
  });

  let renderedHtml = $derived(renderMarkdown(debouncedContent));

  function renderMarkdown(md: string): string {
    if (!md.trim())
      return `<p style="color:var(--text-muted);font-style:italic;">${$t('goalEditor.previewPlaceholder')}</p>`;
    return renderMarkdownShared(md);
  }
</script>

<div
  class="preview"
  ondblclick={() => onrequestedit?.()}
  role="button"
  tabindex="-1"
  aria-label={$t('goalEditor.previewPaneLabel')}
>
  {@html renderedHtml}
</div>

<style>
  .preview {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 24px;
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.8;
    color: var(--text-primary);
  }
</style>
