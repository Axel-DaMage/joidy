<script lang="ts">
  import TagChip from './TagChip.svelte';
  import { aiSuggestions, findNoteByTitle } from '$lib/stores/notes';
  import { goto } from '$app/navigation';
  import { extractTagsFromContent, escapeRegExp } from '$lib/utils/noteContent';

  interface Props {
    tags: string[];
    content: string;
    previousContentTags: string[];
  }

  let {
    tags = $bindable(),
    content = $bindable(),
    previousContentTags = $bindable(),
  }: Props = $props();

  let tagInput = $state('');

  function addTag(t: string) {
    const clean = t.trim().toLowerCase();
    if (clean && !tags.includes(clean)) {
      tags = [...tags, clean];
      const currentContentTags = extractTagsFromContent(content);
      if (!currentContentTags.includes(clean)) {
        const tagsLineMatch = content.match(/^#\s*Tags?:\s*(.*)$/im);
        if (tagsLineMatch) {
          content = content.replace(/^#\s*Tags?:\s*(.*)$/im, `# Tags: $1 [[${clean}]]`);
        } else {
          const prefix = content.endsWith('\n') ? '' : '\n';
          content += `${prefix}\n# Tags: [[${clean}]]`;
        }
        previousContentTags.push(clean);
      }
    }
    tagInput = '';
  }

  function removeTag(t: string) {
    tags = tags.filter((x) => x !== t);

    // Remove individual #Tag: [[t]]
    const regex1 = new RegExp(
      `\\n?\\s*#Tag:\\s*\\[\\[${escapeRegExp(t)}(?:\\|[^\\]]+)?\\]\\]`,
      'gi'
    );
    content = content.replace(regex1, '');

    // Remove from # Tags: [[...]] line
    const regex2 = new RegExp(`\\[\\[${escapeRegExp(t)}(?:\\|[^\\]]+)?\\]\\]\\s*`, 'gi');
    content = content
      .split('\n')
      .map((line) => {
        if (/^#\s*Tags?:\s*/i.test(line)) {
          let newLine = line.replace(regex2, '').trim();
          // if only "# Tags:" is left, remove the line
          if (/^#\s*Tags?:\s*$/i.test(newLine)) return '';
          return newLine;
        }
        return line;
      })
      .join('\n');

    previousContentTags = previousContentTags.filter((x) => x !== t);
  }

  function onTagKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag(tagInput);
    } else if (e.key === 'Backspace' && tagInput === '' && tags.length > 0)
      tags = tags.slice(0, -1);
  }

  function acceptSuggestion(tag: string) {
    addTag(tag);
    aiSuggestions.update((s) => s.filter((x) => x.tag !== tag));
  }

  function dismissSuggestion(tag: string) {
    aiSuggestions.update((s) => s.filter((x) => x.tag !== tag));
  }
</script>

<!-- Tags bar -->
<div class="tags-bar">
  {#each tags as tag}
    <TagChip
      {tag}
      removable
      onremove={removeTag}
      onclick={(tag) => {
        const linkedNote = findNoteByTitle(tag);
        if (linkedNote) {
          goto(`/notes?id=${linkedNote.id}`);
        }
      }}
    />
  {/each}
  <input
    class="tag-input"
    bind:value={tagInput}
    onkeydown={onTagKeydown}
    placeholder="+ etiqueta..."
  />
  {#if $aiSuggestions.length > 0}
    <span class="ai-label">ia:</span>
    {#each $aiSuggestions as s}
      <button class="suggestion-chip" onclick={() => acceptSuggestion(s.tag)}>
        {s.tag} <span class="conf">{Math.round(s.confidence * 100)}%</span>
      </button>
      <button
        class="dismiss-btn"
        onclick={() => dismissSuggestion(s.tag)}
        aria-label="Descartar sugerencia">×</button
      >
    {/each}
  {/if}
</div>

<style>
  /* ── Tags bar ── */
  .tags-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 5px;
    padding: 10px 24px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    background: var(--surface);
    min-height: 38px;
  }

  .tag-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    min-width: 80px;
  }
  .tag-input::placeholder {
    color: var(--text-muted);
  }

  .ai-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--xp);
    margin-left: 6px;
    opacity: 0.8;
  }

  .suggestion-chip {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 7px;
    border: 1px solid var(--xp);
    border-radius: 2px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--xp);
    background: transparent;
    cursor: pointer;
    opacity: 0.8;
    transition: opacity var(--t-fast);
  }
  .suggestion-chip:hover {
    opacity: 1;
  }
  .conf {
    font-size: 9px;
    opacity: 0.6;
  }

  .dismiss-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    padding: 0;
    margin-left: -4px;
  }
</style>
