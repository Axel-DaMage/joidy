<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { fade, fly } from 'svelte/transition';
  import DynamicIcon from './DynamicIcon.svelte';
  import { notes } from '$lib/stores/notes';

  let open = false;
  let query = '';
  let selectedIndex = 0;
  let searchInput: HTMLInputElement;

  const routes = [
    { type: 'Páginas', title: 'Inicio', icon: 'Home', action: () => goto('/') },
    { type: 'Páginas', title: 'Notas', icon: 'BookOpen', action: () => goto('/notes') },
    { type: 'Páginas', title: 'Grafo', icon: 'Network', action: () => goto('/graph') },
    { type: 'Páginas', title: 'Habilidades', icon: 'Zap', action: () => goto('/skills') },
    { type: 'Páginas', title: 'Objetivos', icon: 'Target', action: () => goto('/goals') },
    { type: 'Páginas', title: 'Rachas', icon: 'Flame', action: () => goto('/streaks') },
  ];

  const quickActions = [
    { type: 'Acciones', title: 'Nueva Nota', icon: 'Plus', action: () => { goto('/notes'); setTimeout(() => window.dispatchEvent(new CustomEvent('joidy:new-note')), 100); } },
    { type: 'Acciones', title: 'Nuevo Objetivo', icon: 'Target', action: () => { goto('/goals'); setTimeout(() => window.dispatchEvent(new CustomEvent('joidy:new-goal')), 100); } },
    { type: 'Acciones', title: 'Abrir Ajustes', icon: 'Settings', action: () => window.dispatchEvent(new CustomEvent('joidy:open-settings')) },
  ];

  $: filteredItems = (() => {
    const q = query.toLowerCase().trim();
    let items = [];

    // Search Routes
    const matchingRoutes = routes.filter(r => r.title.toLowerCase().includes(q));
    if (matchingRoutes.length) items.push(...matchingRoutes);

    // Search Actions
    const matchingActions = quickActions.filter(a => a.title.toLowerCase().includes(q));
    if (matchingActions.length) items.push(...matchingActions);

    // Search Notes
    if ($notes) {
      const matchingNotes = $notes
        .filter(n => n.title.toLowerCase().includes(q) || n.content.toLowerCase().includes(q))
        .slice(0, 10)
        .map(n => ({
          type: 'Notas',
          title: n.title,
          icon: 'FileText',
          action: () => { goto(`/notes?id=${n.id}`); }
        }));
      if (matchingNotes.length) items.push(...matchingNotes);
    }

    return items;
  })();

  $: if (query) {
    selectedIndex = 0;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      open = !open;
      if (open) {
        query = '';
        selectedIndex = 0;
        setTimeout(() => searchInput?.focus(), 10);
      }
    } else if (open) {
      if (e.key === 'Escape') {
        open = false;
        e.preventDefault();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % filteredItems.length;
        scrollToSelected();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + filteredItems.length) % filteredItems.length;
        scrollToSelected();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const item = filteredItems[selectedIndex];
        if (item) {
          open = false;
          item.action();
        }
      }
    }
  }

  function scrollToSelected() {
    setTimeout(() => {
      const el = document.querySelector('.cp-item.selected');
      if (el) el.scrollIntoView({ block: 'nearest' });
    }, 0);
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown);
  });
</script>

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="cp-backdrop" on:click={() => open = false} transition:fade={{duration: 100}}>
    <div class="cp-modal" on:click|stopPropagation transition:fly={{y: -20, duration: 150}}>
      <div class="cp-header">
        <DynamicIcon name="Search" size={16} />
        <input 
          bind:this={searchInput}
          bind:value={query}
          class="cp-input"
          placeholder="Buscar comandos, notas, páginas..."
        />
        <span class="cp-esc mono">ESC</span>
      </div>
      
      <div class="cp-body">
        {#if filteredItems.length === 0}
          <div class="cp-empty">No se encontraron resultados</div>
        {:else}
          {#each filteredItems as item, index}
            {#if index === 0 || filteredItems[index - 1].type !== item.type}
              <div class="cp-group-title mono">{item.type}</div>
            {/if}
            <button 
              class="cp-item" 
              class:selected={index === selectedIndex}
              on:mouseenter={() => selectedIndex = index}
              on:click={() => { open = false; item.action(); }}
            >
              <DynamicIcon name={item.icon} size={14} />
              <span class="cp-item-title">{item.title}</span>
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
    background: rgba(0,0,0,0.5);
    backdrop-filter: blur(2px);
    z-index: 1000;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 15vh;
  }

  .cp-modal {
    width: 100%;
    max-width: 500px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
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
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: 4px;
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

  .cp-item.selected {
    background: var(--elevated);
    color: var(--text-primary);
  }

  .cp-item-title {
    font-size: 13px;
  }
</style>
