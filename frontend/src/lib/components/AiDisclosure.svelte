<script lang="ts">
  import { Sparkles } from 'lucide-svelte';
  import { t } from 'svelte-i18n';

  interface Props {
    /** Optional provider name appended to the notice (e.g. "gemini"). */
    provider?: string;
    /** Compact variant for dense surfaces (smaller text/padding). */
    compact?: boolean;
    /** Hide the "learn more" link (e.g. inside tight containers). */
    showLink?: boolean;
  }

  let { provider = '', compact = false, showLink = true }: Props = $props();

  // Public docs page describing which data goes to which AI provider (#1395).
  const DOCS_URL =
    'https://github.com/Axel-DaMage/joidy/blob/development/docs/ai-transparency.md';
</script>

<p class="ai-disclosure" class:compact role="note">
  <span class="ai-disclosure-icon"
    ><Sparkles size={compact ? 11 : 13} aria-hidden="true" /></span
  >
  <span class="ai-disclosure-text"
    >{$t('aiDisclosure.notice')}{#if provider}
      <span class="ai-disclosure-provider"
        >{$t('aiDisclosure.provider', { values: { provider } })}</span
      >{/if}</span
  >
  {#if showLink}
    <a
      class="ai-disclosure-link"
      href={DOCS_URL}
      target="_blank"
      rel="noopener noreferrer">{$t('aiDisclosure.learnMore')}</a
    >
  {/if}
</p>

<style>
  .ai-disclosure {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 4px 8px;
    margin: 0 0 6px;
    padding: 4px 10px;
    font-size: 0.72rem;
    line-height: 1.4;
    color: var(--text-muted);
    border: 1px dashed var(--border);
    border-radius: var(--r-md, 5px);
    background: var(--surface);
  }
  .ai-disclosure.compact {
    margin: 0;
    padding: 2px 8px;
    font-size: 0.68rem;
    border-radius: var(--r-full, 999px);
  }
  .ai-disclosure-icon {
    display: inline-flex;
    flex-shrink: 0;
    align-self: center;
    color: var(--xp, var(--accent));
  }
  .ai-disclosure-text {
    min-width: 0;
  }
  .ai-disclosure-provider {
    font-family: var(--font-mono, monospace);
  }
  .ai-disclosure-link {
    color: var(--xp, var(--accent));
    text-decoration: underline;
    text-underline-offset: 2px;
    white-space: nowrap;
  }
  .ai-disclosure-link:hover {
    text-decoration: none;
  }
  .ai-disclosure-link:focus-visible {
    outline: 2px solid var(--xp, var(--accent));
    outline-offset: 2px;
    border-radius: 2px;
  }
</style>