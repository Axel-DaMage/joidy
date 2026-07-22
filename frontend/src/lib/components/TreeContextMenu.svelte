<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import type { FlatNode } from '$lib/utils/fileTree';
  import DynamicIcon from './DynamicIcon.svelte';

  export let x: number;
  export let y: number;
  export let node: FlatNode;

  const dispatch = createEventDispatcher<{
    close: void;
    rename: { node: FlatNode };
    move: { node: FlatNode };
    deleteNote: { node: FlatNode };
    newNoteInFolder: { node: FlatNode };
    deleteFolder: { node: FlatNode };
  }>();

  function handleItem(action: string) {
    return () => {
      switch (action) {
        case 'rename': dispatch('rename', { node }); break;
        case 'move': dispatch('move', { node }); break;
        case 'deleteNote': dispatch('deleteNote', { node }); break;
        case 'newNoteInFolder': dispatch('newNoteInFolder', { node }); break;
        case 'deleteFolder': dispatch('deleteFolder', { node }); break;
      }
      dispatch('close');
    };
  }

  function adjustPos() {
    const w = menuEl?.offsetWidth ?? 160;
    const h = menuEl?.offsetHeight ?? 120;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let cx = x;
    let cy = y;
    if (cx + w > vw - 8) cx = vw - w - 8;
    if (cy + h > vh - 8) cy = vh - h - 8;
    if (cx < 8) cx = 8;
    if (cy < 8) cy = 8;
    style = `left:${cx}px;top:${cy}px;`;
  }

  let style = '';
  let menuEl: HTMLDivElement;

  onMount(() => {
    adjustPos();
    const close = () => dispatch('close');
    window.addEventListener('click', close, { once: true });
    window.addEventListener('contextmenu', close, { once: true });
    return () => {
      window.removeEventListener('click', close);
      window.removeEventListener('contextmenu', close);
    };
  });
</script>

<div class="ctx-menu" bind:this={menuEl} style={style} on:click|stopPropagation on:contextmenu|stopPropagation>
  {#if node.type === 'file'}
    <button class="ctx-item" on:click={handleItem('rename')}>
      <DynamicIcon name="Edit" size={12} /> Renombrar
    </button>
    <button class="ctx-item" on:click={handleItem('move')}>
      <DynamicIcon name="MoveRight" size={12} /> Mover a...
    </button>
    <div class="ctx-divider"></div>
    <button class="ctx-item ctx-danger" on:click={handleItem('deleteNote')}>
      <DynamicIcon name="Trash2" size={12} /> Eliminar
    </button>
  {:else}
    <button class="ctx-item" on:click={handleItem('newNoteInFolder')}>
      <DynamicIcon name="FilePlus" size={12} /> Nueva nota aquí
    </button>
    <button class="ctx-item" on:click={handleItem('rename')}>
      <DynamicIcon name="Edit" size={12} /> Renombrar
    </button>
    <button class="ctx-item ctx-danger" on:click={handleItem('deleteFolder')}>
      <DynamicIcon name="FolderX" size={12} /> Eliminar carpeta
    </button>
  {/if}
</div>

<style>
  .ctx-menu {
    position: fixed;
    z-index: 1000;
    min-width: 160px;
    background: var(--surface, #fff);
    border: 1px solid var(--border, #ddd);
    border-radius: 6px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.18);
    padding: 4px 0;
    display: flex;
    flex-direction: column;
  }
  .ctx-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 14px;
    font-size: 0.8rem;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-primary, #222);
    text-align: left;
    width: 100%;
  }
  .ctx-item:hover {
    background: var(--hover, #f0f0f0);
  }
  .ctx-danger {
    color: var(--color-error, #e53e3e);
  }
  .ctx-divider {
    height: 1px;
    background: var(--border-light, #eee);
    margin: 4px 0;
  }
</style>
