<script lang="ts">
  // Create/edit form for a Google contact (#43). Mounted fresh per opening
  // (parent wraps it in {#key editingContact}) so the draft always derives
  // from the current contact — including the etag echoed back on PUT.
  import { untrack } from 'svelte';
  import { api, type Contact, type ContactGroup } from '$lib/api';
  import ModalDialog from './ModalDialog.svelte';
  import { t } from 'svelte-i18n';
  import { logger } from '$lib/utils/logger';
  import {
    contactToDraft,
    contactGroupLabel,
    draftToWriteInput,
    draftHasContent,
    httpStatusOf,
    type ContactDraft,
    type ContactEmailDraft,
    type ContactPhoneDraft,
    type ContactOrgDraft,
  } from '$lib/utils/contacts';
  import Plus from 'lucide-svelte/icons/plus';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import TriangleAlert from 'lucide-svelte/icons/triangle-alert';

  interface Props {
    open: boolean;
    /** null → create mode; a Contact → edit mode (full detail preferred). */
    contact: Contact | null;
    groups: ContactGroup[];
    onSaved?: (contact: Contact) => void;
    /** Refetch the contact after a 409 etag conflict (parent remounts us). */
    onReload?: () => void | Promise<void>;
    onClose?: () => void;
  }

  let { open = false, contact = null, groups = [], onSaved, onReload, onClose }: Props = $props();

  const isEdit = $derived(!!contact?.resource_name);
  const uid = $props.id();

  let draft = $state<ContactDraft>(untrack(() => contactToDraft(contact)));
  let saving = $state(false);
  let saveError = $state('');
  let conflict = $state(false);
  let forbidden = $state(false);
  let validationError = $state('');

  const typeSuggestions = ['home', 'work', 'other', 'mobile', 'main', 'custom'];

  function newEmail(): ContactEmailDraft {
    return { value: '', type: '', display_name: '', primary: draft.emails.length === 0 };
  }
  function newPhone(): ContactPhoneDraft {
    return { value: '', type: '', primary: draft.phones.length === 0 };
  }
  function newOrg(): ContactOrgDraft {
    return {
      name: '',
      title: '',
      department: '',
      type: '',
      current: null,
      job_description: '',
      primary: draft.organizations.length === 0,
    };
  }

  function toggleMembership(resourceName: string): void {
    const idx = draft.memberships.indexOf(resourceName);
    if (idx >= 0) draft.memberships.splice(idx, 1);
    else draft.memberships.push(resourceName);
  }

  function close() {
    if (saving) return;
    onClose?.();
  }

  async function save() {
    validationError = '';
    if (!draftHasContent(draft)) {
      validationError = $t('contacts.editor.needContent');
      return;
    }
    saving = true;
    saveError = '';
    conflict = false;
    forbidden = false;
    try {
      const payload = draftToWriteInput(draft, {
        etag: contact?.etag ?? null,
        original: contact,
      });
      const saved = isEdit
        ? await api.contacts.update(contact!.resource_name!, payload)
        : await api.contacts.create(payload);
      onSaved?.(saved);
    } catch (e) {
      logger.error(e);
      const status = httpStatusOf(e);
      if (status === 409) {
        conflict = true;
        saveError = $t('contacts.editor.conflict');
      } else if (status === 403) {
        forbidden = true;
        saveError = $t('contacts.editor.forbidden');
      } else {
        saveError = $t('contacts.editor.saveError');
      }
    } finally {
      saving = false;
    }
  }
</script>

<ModalDialog
  {open}
  title={isEdit ? $t('contacts.editor.editTitle') : $t('contacts.editor.createTitle')}
  size="lg"
  onClose={close}
>
  <div class="editor-form">
    <div class="field-row">
      <label class="field">
        <span>{$t('contacts.editor.givenName')}</span>
        <input type="text" bind:value={draft.given_name} autocomplete="off" />
      </label>
      <label class="field">
        <span>{$t('contacts.editor.familyName')}</span>
        <input type="text" bind:value={draft.family_name} autocomplete="off" />
      </label>
    </div>

    <div class="field-section">
      <div class="field-section-head">
        <span>{$t('contacts.emails')}</span>
        <button
          type="button"
          class="add-btn"
          onclick={() => (draft.emails = [...draft.emails, newEmail()])}
        >
          <Plus size={12} /> {$t('contacts.editor.add')}
        </button>
      </div>
      {#each draft.emails as email, i (i)}
        <div class="entry-row">
          <input
            type="email"
            class="entry-value"
            placeholder={$t('contacts.editor.emailPlaceholder')}
            aria-label={$t('contacts.editor.emailPlaceholder')}
            bind:value={email.value}
          />
          <input
            type="text"
            class="entry-type"
            list="{uid}-types"
            placeholder={$t('contacts.editor.typePlaceholder')}
            aria-label={$t('contacts.editor.typePlaceholder')}
            bind:value={email.type}
          />
          <label class="entry-primary" title={$t('contacts.primary')}>
            <input type="checkbox" bind:checked={email.primary} />
            <span class="caption">{$t('contacts.primaryShort')}</span>
          </label>
          <button
            type="button"
            class="entry-remove"
            aria-label={$t('common.delete')}
            onclick={() => (draft.emails = draft.emails.filter((_, j) => j !== i))}
          >
            <Trash2 size={13} />
          </button>
        </div>
      {/each}
      {#if draft.emails.length === 0}
        <div class="entry-empty caption">{$t('contacts.editor.noEmails')}</div>
      {/if}
    </div>

    <div class="field-section">
      <div class="field-section-head">
        <span>{$t('contacts.phones')}</span>
        <button
          type="button"
          class="add-btn"
          onclick={() => (draft.phones = [...draft.phones, newPhone()])}
        >
          <Plus size={12} /> {$t('contacts.editor.add')}
        </button>
      </div>
      {#each draft.phones as phone, i (i)}
        <div class="entry-row">
          <input
            type="tel"
            class="entry-value"
            placeholder={$t('contacts.editor.phonePlaceholder')}
            aria-label={$t('contacts.editor.phonePlaceholder')}
            bind:value={phone.value}
          />
          <input
            type="text"
            class="entry-type"
            list="{uid}-types"
            placeholder={$t('contacts.editor.typePlaceholder')}
            aria-label={$t('contacts.editor.typePlaceholder')}
            bind:value={phone.type}
          />
          <label class="entry-primary" title={$t('contacts.primary')}>
            <input type="checkbox" bind:checked={phone.primary} />
            <span class="caption">{$t('contacts.primaryShort')}</span>
          </label>
          <button
            type="button"
            class="entry-remove"
            aria-label={$t('common.delete')}
            onclick={() => (draft.phones = draft.phones.filter((_, j) => j !== i))}
          >
            <Trash2 size={13} />
          </button>
        </div>
      {/each}
      {#if draft.phones.length === 0}
        <div class="entry-empty caption">{$t('contacts.editor.noPhones')}</div>
      {/if}
    </div>

    <div class="field-section">
      <div class="field-section-head">
        <span>{$t('contacts.organizations')}</span>
        <button
          type="button"
          class="add-btn"
          onclick={() => (draft.organizations = [...draft.organizations, newOrg()])}
        >
          <Plus size={12} /> {$t('contacts.editor.add')}
        </button>
      </div>
      {#each draft.organizations as org, i (i)}
        <div class="entry-row org-row">
          <input
            type="text"
            class="entry-value"
            placeholder={$t('contacts.editor.orgNamePlaceholder')}
            aria-label={$t('contacts.editor.orgNamePlaceholder')}
            bind:value={org.name}
          />
          <input
            type="text"
            class="entry-type"
            placeholder={$t('contacts.editor.orgTitlePlaceholder')}
            aria-label={$t('contacts.editor.orgTitlePlaceholder')}
            bind:value={org.title}
          />
          <label class="entry-primary" title={$t('contacts.primary')}>
            <input type="checkbox" bind:checked={org.primary} />
            <span class="caption">{$t('contacts.primaryShort')}</span>
          </label>
          <button
            type="button"
            class="entry-remove"
            aria-label={$t('common.delete')}
            onclick={() => (draft.organizations = draft.organizations.filter((_, j) => j !== i))}
          >
            <Trash2 size={13} />
          </button>
        </div>
      {/each}
      {#if draft.organizations.length === 0}
        <div class="entry-empty caption">{$t('contacts.editor.noOrgs')}</div>
      {/if}
    </div>

    <label class="field">
      <span>{$t('contacts.note')}</span>
      <textarea rows="3" bind:value={draft.note}></textarea>
    </label>

    {#if groups.length > 0}
      <div class="field-section">
        <div class="field-section-head">
          <span>{$t('contacts.groups')}</span>
        </div>
        <div class="group-checks">
          {#each groups as group (group.resource_name)}
            <label class="group-check">
              <input
                type="checkbox"
                checked={draft.memberships.includes(group.resource_name ?? '')}
                onchange={() => group.resource_name && toggleMembership(group.resource_name)}
              />
              <span>{contactGroupLabel(group)}</span>
            </label>
          {/each}
        </div>
      </div>
    {/if}

    {#if validationError}
      <p class="form-error"><TriangleAlert size={13} /> {validationError}</p>
    {/if}
    {#if saveError}
      <p class="form-error">
        <TriangleAlert size={13} /> {saveError}
        {#if conflict && onReload}
          <button type="button" class="reload-btn" onclick={() => void onReload?.()}>
            {$t('contacts.editor.reload')}
          </button>
        {/if}
      </p>
    {/if}
    {#if forbidden}
      <p class="form-hint">{$t('contacts.editor.forbiddenHint')}</p>
    {/if}
  </div>

  {#snippet footer()}
    <button class="btn ghost" type="button" onclick={close} disabled={saving}>
      {$t('common.cancel')}
    </button>
    <button class="btn" type="button" onclick={save} disabled={saving}>
      {saving ? $t('common.saving') : $t('common.save')}
    </button>
  {/snippet}
</ModalDialog>

<datalist id="{uid}-types">
  {#each typeSuggestions as type (type)}
    <option value={type}></option>
  {/each}
</datalist>

<style>
  .editor-form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .field > span {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .field input,
  .field textarea {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 7px 10px;
    font-size: 13px;
    color: var(--text-primary);
    outline: none;
    font-family: inherit;
    resize: vertical;
  }

  .field input:focus-visible,
  .field textarea:focus-visible,
  .entry-row input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 1px;
  }

  .field-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .field-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field-section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .add-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: 1px dashed var(--border);
    border-radius: var(--r);
    color: var(--text-secondary);
    font-size: 11px;
    padding: 3px 8px;
    cursor: pointer;
  }

  .add-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .entry-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .entry-value {
    flex: 1;
    min-width: 0;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 9px;
    font-size: 12px;
    color: var(--text-primary);
    outline: none;
  }

  .entry-type {
    width: 84px;
    flex-shrink: 0;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 8px;
    font-size: 12px;
    color: var(--text-secondary);
    outline: none;
  }

  .org-row .entry-type {
    width: 150px;
  }

  .entry-primary {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    cursor: pointer;
    color: var(--text-muted);
  }

  .entry-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
  }

  .entry-remove:hover {
    color: var(--error, #e5484d);
    border-color: var(--error, #e5484d);
  }

  .entry-empty {
    padding: 4px 0;
  }

  .group-checks {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    max-height: 140px;
    overflow-y: auto;
  }

  .group-check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: 999px;
  }

  .group-check:has(input:checked) {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .form-error {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    font-size: 12px;
    color: var(--error, #e5484d);
  }

  .form-hint {
    margin: 0;
    font-size: 11px;
    color: var(--text-muted);
  }

  .reload-btn {
    margin-left: 8px;
    background: transparent;
    border: 1px solid var(--error, #e5484d);
    border-radius: var(--r);
    color: var(--error, #e5484d);
    font-size: 11px;
    padding: 2px 8px;
    cursor: pointer;
  }

  .btn {
    padding: 8px 14px;
    border-radius: var(--r);
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-secondary);
  }

  .btn.ghost:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .btn:not(.ghost) {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
  }

  .btn:not(.ghost):hover {
    opacity: 0.9;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
