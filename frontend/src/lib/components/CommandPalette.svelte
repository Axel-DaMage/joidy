<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { fade, fly } from 'svelte/transition';
  import { Search, CornerDownLeft } from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import { notes } from '$lib/stores/notes';
  import { darkMode, devMode } from '$lib/stores/settings';
  import { isOpen, close } from '$lib/stores/commandPalette';
  import { get } from 'svelte/store';
  import { t } from 'svelte-i18n';

  interface Command {
    type: string;
    title: string;
    icon: string;
    hint?: string;
    action: () => void;
  }

  const navCommands: Command[] = [
    { type: 'Navegación', title: 'Ir a Dashboard', icon: 'Home', action: () => goto('/') },
    { type: 'Navegación', title: 'Ir a Notas', icon: 'BookOpen', action: () => goto('/notes') },
    { type: 'Navegación', title: 'Ir a Goals', icon: 'Target', action: () => goto('/goals') },
    { type: 'Navegación', title: 'Ir a Grafo', icon: 'Network', action: () => goto('/graph') },
    { type: 'Navegación', title: 'Ir a Skills', icon: 'Zap', action: () => goto('/skills') },
    { type: 'Navegación', title: 'Ir a Rachas', icon: 'Flame', action: () => goto('/streaks') },
    { type: 'Navegación', title: 'Ir a IA', icon: 'Brain', action: () => goto('/ai') },
    { type: 'Navegación', title: 'Ir a Offline', icon: 'CloudOff', action: () => goto('/offline') },
    { type: 'Navegación', title: 'Ajustes', icon: 'Settings', action: () => window.dispatchEvent(new CustomEvent('joidy:open-settings')) },
  ];

  const actionCommands: Command[] = [
    {
      type: 'Acciones',
      title: 'Crear nota',
      icon: 'Plus',
      action: () => {
        goto('/notes?new=1');
      },
    },
    {
      type: 'Acciones',
      title: 'Crear goal',
      icon: 'Target',
      action: () => {
        goto('/goals');
        setTimeout(() => window.dispatchEvent(new CustomEvent('joidy:new-goal')), 100);
      },
    },
    {
      type: 'Acciones',
      title: 'Crear racha',
      icon: 'Flame',
      action: () => {
        goto('/streaks');
        setTimeout(() => window.dispatchEvent(new CustomEvent('joidy:new-streak')), 100);
      },
    },
    {
      type: 'Acciones',
      title: 'Iniciar Pomodoro',
      icon: 'Timer',
      action: () => {
        window.dispatchEvent(new CustomEvent('joidy:start-pomodoro'));
      },
    },
    {
      type: 'Acciones',
      title: 'Toggle tema',
      icon: 'SunMoon',
      action: () => {
        darkMode.toggle();
      },
    },
    {
      type: 'Acciones',
      title: 'Toggle dev mode',
      icon: 'Terminal',
      action: () => {
        devMode.toggle();
      },
    },
    {
      type: 'Acciones',
      title: 'Exportar notas',
      icon: 'Download',
      hint: 'Exportar',
      action: () => {
        goto('/notes?export=1');
        setTimeout(() => window.dispatchEvent(new CustomEvent('joidy:export-notes')), 150);
      },
    },
  ];

  let query = $state('');
  let selectedIndex = $state(0);
  let searchInput = $state<HTMLInputElement | null>(null);
  let listEl = $state<HTMLElement | null>(null);

  function fuzzyMatch(text: string, pattern: string): boolean {
    if (!pattern) return true;
    const t = text.toLowerCase();
    const p = pattern.toLowerCase();
    if (t.includes(p)) return true;
    let pi = 0;
    for (let ti = 0; ti < t.length && pi < p.length; ti++) {
      if (t[ti] === p[pi]) pi++;
    }
    return pi === p.length;
  }

  function fuzzyScore(text: string, pattern: string): number {
    if (!pattern) return 0;
    const t = text.toLowerCase();
    const p = pattern.toLowerCase();
    if (t === p) return 1000;
    const idx = t.indexOf(p);
    if (idx === 0) return 500;
    if (idx > 0) return 300 - idx;
    let pi = 0;
    for (let ti = 0; ti < t.length && pi < p.length; ti++) {
      if (t[ti] === p[pi]) pi++;
    }
    return pi === p.length ? 100 : 0;
  }

  const allTags = $derived.by(() => {
    const ns = get(notes);
    const set = new Set<string>();
    for (const n of ns) {
      for (const tag of n.tags) {
        if (tag) set.add(tag);
      }
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  });

  const filteredItems = $derived.by<Command[]>(() => {
    const q = query.trim();

    if (q.startsWith('#')) {
      const tagQuery = q.slice(1).toLowerCase();
      return allTags
        .filter((tag) => !tagQuery || fuzzyMatch(tag, tagQuery))
        .slice(0, 20)
        .map((tag) => ({
          type: 'Etiquetas',
          title: `#${tag}`,
          icon: 'Hash',
          hint: tag,
          action: () => goto(`/notes?tag=${encodeURIComponent(tag)}`),
        }));
    }

    const items: Command[] = [];

    const allCommands = [...navCommands, ...actionCommands];
    const matchingCommands = allCommands
      .filter((c) => fuzzyMatch(c.title, q))
      .map((c) => ({ ...c, _score: fuzzyScore(c.title, q) }))
      .sort((a, b) => (b as any)._score - (a as any)._score)
      .map((c) => {
        const rest = c as any;
        delete rest._score;
        return rest as Command;
      });
    items.push(...matchingCommands);

    const ns = get(notes);
    if (ns && ns.length > 0) {
      const matchingNotes = ns
        .filter((n) => fuzzyMatch(n.title, q) || fuzzyMatch(n.content, q))
        .slice(0, 10)
        .map((n) => ({
          type: 'Notas',
          title: n.title || 'Sin título',
          icon: 'FileText',
          hint: n.tags.length ? `#${n.tags[0]}` : undefined,
          action: () => goto(`/notes?id=${n.id}`),
        }));
      items.push(...matchingNotes);
    }

    return items;
  });

  $effect(() => {
    query;
    selectedIndex = 0;
  });

  $effect(() => {
    if ($isOpen) {
      query = '';
      selectedIndex = 0;
      setTimeout(() => searchInput?.focus(), 20);
    }
  });

  function scrollToSelected() {
    setTimeout(() => {
      const el = listEl?.querySelector<HTMLElement>('.cp-item.is-selected');
      if (el) el.scrollIntoView({ block: 'nearest' });
    }, 0);
  }

  function selectItem(index: number) {
    const item = filteredItems[index];
    if (!item) return;
    close();
    item.action();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (!$isOpen) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (filteredItems.length === 0) return;
      selectedIndex = (selectedIndex + 1) % filteredItems.length;
      scrollToSelected();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (filteredItems.length === 0) return;
      selectedIndex = (selectedIndex - 1 + filteredItems.length) % filteredItems.length;
      scrollToSelected();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      selectItem(selectedIndex);
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      close();
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });
</script>

{#if $isOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="cp-backdrop"
    role="dialog"
    aria-modal="true"
    aria-label={$t('commandPalette.label')}
    tabindex="-1"
    onclick={handleBackdropClick}
    transition:fade={{ duration: 100 }}
  >
    <div
      class="cp-modal"
      transition:fly={{ y: -20, duration: 150 }}
    >
      <div class="cp-header">
        <Search size={16} />
        <input
          bind:this={searchInput}
          bind:value={query}
          class="cp-input"
          placeholder={$t('commandPalette.searchPlaceholder')}
          aria-label={$t('commandPalette.searchLabel')}
          autocomplete="off"
          spellcheck="false"
        />
        <span class="cp-esc mono">ESC</span>
      </div>

      <div class="cp-body" bind:this={listEl}>
        {#if filteredItems.length === 0}
          <div class="cp-empty">{$t('commandPalette.noResults')}</div>
        {:else}
          {#each filteredItems as item, index (item.title + index)}
            {#if index === 0 || filteredItems[index - 1].type !== item.type}
              <div class="cp-group-title mono">{item.type}</div>
            {/if}
            <button
              class="cp-item"
              class:is-selected={index === selectedIndex}
              onmouseenter={() => (selectedIndex = index)}
              onclick={() => selectItem(index)}
            >
              <DynamicIcon name={item.icon} size={14} />
              <span class="cp-item-title">{item.title}</span>
              {#if index === selectedIndex}
                <span class="cp-item-hint">
                  <CornerDownLeft size={12} />
                </span>
              {/if}
            </button>
          {/each}
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .cp-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(2px);
    z-index: var(--z-modal);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
  }

  .cp-modal {
    width: 100%;
    max-width: 560px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    max-height: 60vh;
  }

  .cp-header {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    gap: 12px;
    color: var(--text-muted);
  }

  .cp-input {
    flex: 1;
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 15px;
    outline: none;
  }

  .cp-input::placeholder {
    color: var(--text-disabled);
  }

  .cp-esc {
    font-size: 10px;
    padding: 2px 6px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    color: var(--text-secondary);
  }

  .cp-body {
    padding: 8px 0;
    overflow-y: auto;
  }

  .cp-empty {
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  .cp-group-title {
    padding: 4px 16px;
    font-size: 10px;
    color: var(--text-disabled);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 8px;
  }

  .cp-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    text-align: left;
  }

  .cp-item.is-selected {
    background: var(--hover);
    color: var(--text-primary);
  }

  .cp-item-title {
    font-size: 13px;
    flex: 1;
  }

  .cp-item-hint {
    color: var(--text-muted);
    display: flex;
    align-items: center;
  }

  @media (max-width: 560px) {
    .cp-backdrop {
      padding-top: 8vh;
      padding-left: var(--s2);
      padding-right: var(--s2);
    }
    .cp-modal {
      max-width: 100%;
      max-height: 70vh;
      border-radius: var(--r);
    }
    .cp-item {
      padding: 14px var(--s4);
    }
    .cp-item-title {
      font-size: 14px;
    }
  }
</style>
