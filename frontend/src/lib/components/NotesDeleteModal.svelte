<script lang="ts">
  import ModalDialog from './ModalDialog.svelte';
  import { selectedNoteIds } from '$lib/stores/notes';
  import { confirmDelete } from '$lib/utils/notesPage';
  import { deleteModalOpen, deleteMode } from '$lib/stores/notesUi';
  import { t } from 'svelte-i18n';
</script>

{#if $deleteModalOpen}
  <ModalDialog
    open={true}
    title={$deleteMode === 'bulk'
      ? `¿Eliminar ${$selectedNoteIds.size} nota${$selectedNoteIds.size !== 1 ? 's' : ''}?`
      : $t('notesPage.delete')}
    size="sm"
    onClose={() => ($deleteModalOpen = false)}
  >
    <p class="delete-modal-desc">{$t('notesPage.deleteHint')}</p>
    <div class="delete-modal-actions">
      <button class="btn btn-ghost" onclick={() => ($deleteModalOpen = false)}
        >{$t('notesPage.cancel')}</button
      >
      <button class="btn btn-danger" onclick={confirmDelete}>{$t('notesPage.delete')}</button>
    </div>
  </ModalDialog>
{/if}
