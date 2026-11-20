<script lang="ts">
  // Google Contacts page (#43) — list/search/group-filter/detail + CRUD over
  // the People API via /integrations/contacts. URL is the source of truth for
  // ?q= (search), ?group= (contactGroups/{id}) and ?contact= (people/{id}
  // deep link — also the target of [[Contact:Name]] note wikilinks).
  import { onMount, onDestroy } from 'svelte';
  import { page } from '$app/state';
  import { pushState, replaceState } from '$app/navigation';
  import { api, type Contact, type ContactGroup } from '$lib/api';
  import { contactsStatus, loadContactsStatus } from '$lib/stores/contacts';
  import { startGoogleConnect, type GoogleConnectHandle } from '$lib/utils/googleConnect';
  import {
    contactDisplayName,
    contactInitials,
    contactSubtitle,
    contactGroupLabel,
    formatBirthday,
    formatAddress,
    primaryOf,
    httpStatusOf,
  } from '$lib/utils/contacts';
  import ContactEditor from '$lib/components/ContactEditor.svelte';
  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import { showNotification } from '$lib/stores/notifications';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';
  import Search from 'lucide-svelte/icons/search';
  import RefreshCw from 'lucide-svelte/icons/refresh-cw';
  import Plus from 'lucide-svelte/icons/plus';
  import Pencil from 'lucide-svelte/icons/pencil';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import Settings from 'lucide-svelte/icons/settings';
  import Users from 'lucide-svelte/icons/users';
  import Mail from 'lucide-svelte/icons/mail';
  import Phone from 'lucide-svelte/icons/phone';
  import Building2 from 'lucide-svelte/icons/building-2';
  import Cake from 'lucide-svelte/icons/cake';
  import Globe from 'lucide-svelte/icons/globe';
  import MapPin from 'lucide-svelte/icons/map-pin';
  import NotebookPen from 'lucide-svelte/icons/notebook-pen';

  // ── URL-derived state ────────────────────────────────────────────────────
  const urlQ = $derived(page.url.searchParams.get('q') ?? '');
  const urlGroup = $derived(page.url.searchParams.get('group') ?? '');
  const urlContact = $derived(page.url.searchParams.get('contact') ?? '');

  // ── Data state ───────────────────────────────────────────────────────────
  let groups = $state<ContactGroup[]>([]);
  let contacts = $state<Contact[]>([]);
  let nextPageToken = $state<string | null>(null);
  let loading = $state(true);
  let loadingMore = $state(false);
  let loadError = $state(false);
  let detailLoading = $state(false);
  let selected = $state<Contact | null>(null);
  let needsReconsent = $state(false);

  // ── UI state ─────────────────────────────────────────────────────────────
  let searchInput = $state('');
  let editorOpen = $state(false);
  let editingContact = $state<Contact | null>(null);
  let deleteTarget = $state<Contact | null>(null);
  let connecting = $state(false);
  let connectHandle: GoogleConnectHandle | null = null;

  const canRead = $derived(
    !!$contactsStatus?.connected && $contactsStatus.contacts_read !== false
  );
  const canWrite = $derived(
    !!$contactsStatus?.connected && $contactsStatus.contacts_write !== false
  );
  const isConnected = $derived(!!$contactsStatus?.connected);
  const readOnly = $derived(isConnected && $contactsStatus?.contacts_write === false);

  // ── Loaders ──────────────────────────────────────────────────────────────
  let listSeq = 0;
  let detailSeq = 0;

  async function loadList(q: string, group: string, append = false): Promise<void> {
    const seq = ++listSeq;
    if (append) {
      loadingMore = true;
    } else {
      loading = true;
      loadError = false;
    }
    try {
      const res = await api.contacts.list({
        q: q || undefined,
        group: group || undefined,
        pageSize: 100,
        pageToken: append ? (nextPageToken ?? undefined) : undefined,
      });
      if (seq !== listSeq) return; // a newer request superseded this one
      contacts = append ? [...contacts, ...res.contacts] : res.contacts;
      nextPageToken = res.next_page_token;
    } catch (e) {
      if (seq !== listSeq) return;
      logger.error(e);
      if (httpStatusOf(e) === 403) {
        needsReconsent = true;
      } else if (!append || contacts.length === 0) {
        loadError = true;
      } else {
        showNotification($t('contacts.loadMoreError'), 'error');
      }
    } finally {
      if (seq === listSeq) {
        loading = false;
        loadingMore = false;
      }
    }
  }

  async function loadDetail(resourceName: string): Promise<void> {
    const seq = ++detailSeq;
    detailLoading = true;
    try {
      const contact = await api.contacts.get(resourceName);
      if (seq !== detailSeq) return;
      selected = contact;
    } catch (e) {
      if (seq !== detailSeq) return;
      logger.error(e);
      if (httpStatusOf(e) === 403) {
        needsReconsent = true;
      } else {
        showNotification($t('contacts.detailLoadError'), 'error');
        selected = null;
      }
    } finally {
      if (seq === detailSeq) detailLoading = false;
    }
  }

  async function loadGroups(): Promise<void> {
    try {
      const res = await api.contacts.groups({ pageSize: 100 });
      groups = res.groups.filter((g) => !!g.resource_name);
    } catch (e) {
      // Groups only feed the filter chips — degrade silently.
      logger.error(e);
    }
  }

  async function refresh(): Promise<void> {
    try {
      await loadContactsStatus();
    } catch (e) {
      logger.error(e);
    }
    if (isConnected && canRead) {
      void loadGroups();
      void loadList(urlQ, urlGroup);
      if (urlContact) void loadDetail(urlContact);
    }
  }

  // ── URL sync ─────────────────────────────────────────────────────────────
  // External URL changes (wikilink deep links, back/forward) → input value.
  $effect(() => {
    const q = urlQ;
    if (searchInput !== q) searchInput = q;
  });

  // Input → debounced ?q= update (filters are replaceState — no history spam).
  let searchDebounce: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const q = searchInput;
    if (searchDebounce) clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      const params = new URLSearchParams();
      if (urlGroup) params.set('group', urlGroup);
      const trimmed = q.trim();
      if (trimmed) params.set('q', trimmed);
      // A new search invalidates the open detail — results changed.
      const qs = params.toString();
      const target = `/contactos${qs ? `?${qs}` : ''}`;
      if (`${page.url.pathname}${page.url.search}` !== target) {
        replaceState(target, page.state);
      }
    }, 300);
    return () => {
      if (searchDebounce) clearTimeout(searchDebounce);
    };
  });

  // ?q=/?group= changes → reload the list (append=false resets pagination).
  $effect(() => {
    const q = urlQ;
    const g = urlGroup;
    if (!canRead) return;
    void loadList(q, g);
  });

  // ?contact= changes → load the detail (empty param clears the selection).
  $effect(() => {
    const rn = urlContact;
    if (!rn) {
      selected = null;
      return;
    }
    if (!canRead) return;
    void loadDetail(rn);
  });

  // ── Navigation helpers ───────────────────────────────────────────────────
  // eslint-disable-next-line no-unused-vars -- 'params' only names the callback signature
  function urlWithParams(mutate: (params: URLSearchParams) => void): string {
    const params = new URLSearchParams(page.url.search);
    mutate(params);
    const qs = params.toString();
    return `/contactos${qs ? `?${qs}` : ''}`;
  }

  function selectContact(resourceName: string): void {
    pushState(urlWithParams((p) => p.set('contact', resourceName)), page.state);
  }

  function selectGroup(resourceName: string | null): void {
    replaceState(
      urlWithParams((p) => {
        if (resourceName) p.set('group', resourceName);
        else p.delete('group');
        p.delete('contact');
      }),
      page.state
    );
  }

  // ── CRUD ─────────────────────────────────────────────────────────────────
  function openCreate(): void {
    editingContact = null;
    editorOpen = true;
  }

  async function openEdit(contact: Contact): Promise<void> {
    if (!contact.resource_name) return;
    // Always re-read the detail: the list payload lacks memberships/note and
    // may carry a stale etag — the editor needs the freshest one for PUT.
    // Abort on failure instead of falling back to the shallow list row: the
    // editor's PUT fully replaces managed sections, so saving from partial
    // data would silently wipe groups and the note.
    try {
      editingContact = await api.contacts.get(contact.resource_name);
    } catch (e) {
      logger.error(e);
      if (httpStatusOf(e) === 403) {
        needsReconsent = true;
      } else {
        showNotification($t('contacts.detailLoadError'), 'error');
      }
      return;
    }
    editorOpen = true;
  }

  async function reloadEditingContact(): Promise<void> {
    // 409 conflict path — refetch so the editor remounts with a fresh etag.
    if (!editingContact?.resource_name) return;
    try {
      editingContact = await api.contacts.get(editingContact.resource_name);
    } catch (e) {
      logger.error(e);
      showNotification($t('contacts.detailLoadError'), 'error');
    }
  }

  function handleSaved(saved: Contact): void {
    editorOpen = false;
    editingContact = null;
    const idx = contacts.findIndex((c) => c.resource_name === saved.resource_name);
    if (idx >= 0) {
      // Merge over the list row — the detail payload is a superset.
      contacts[idx] = { ...contacts[idx], ...saved };
    } else if (
      !urlQ &&
      (!urlGroup || (saved.memberships ?? []).includes(urlGroup))
    ) {
      // Only surface the new row when it matches the active filters — under
      // an active search the contact may not belong to the result set.
      contacts = [saved, ...contacts];
    }
    if (selected?.resource_name === saved.resource_name) {
      selected = saved;
    }
    showNotification($t('contacts.saved'), 'success');
  }

  function askDelete(contact: Contact): void {
    deleteTarget = contact;
  }

  async function confirmDelete(): Promise<void> {
    const target = deleteTarget;
    if (!target?.resource_name) return;
    try {
      await api.contacts.remove(target.resource_name);
      contacts = contacts.filter((c) => c.resource_name !== target.resource_name);
      if (selected?.resource_name === target.resource_name) {
        replaceState(urlWithParams((p) => p.delete('contact')), page.state);
        selected = null;
      }
      showNotification($t('contacts.deleted'), 'success');
    } catch (e) {
      logger.error(e);
      if (httpStatusOf(e) === 403) {
        needsReconsent = true;
      } else {
        showNotification($t('contacts.deleteError'), 'error');
      }
    } finally {
      deleteTarget = null;
    }
  }

  // ── Google connect ───────────────────────────────────────────────────────
  async function connectGoogle(): Promise<void> {
    if (connecting) return;
    connecting = true;
    connectHandle = startGoogleConnect({
      isReady: async () => {
        const s = await loadContactsStatus();
        return !!(s.connected && s.contacts_read !== false);
      },
    });
    const result = await connectHandle.done;
    connectHandle = null;
    connecting = false;
    if (result === 'connected') {
      needsReconsent = false;
      showNotification($t('contacts.connectedOk'), 'success');
      void loadGroups();
      // The list/detail effects refire automatically via $contactsStatus.
    } else if (result === 'timeout') {
      showNotification($t('contacts.connectTimeout'), 'error');
    } else if (result === 'error') {
      showNotification($t('contacts.connectError'), 'error');
    }
    // 'cancelled' → silent (component destroyed mid-flow)
  }

  // ── Lifecycle ────────────────────────────────────────────────────────────
  onMount(async () => {
    try {
      await loadContactsStatus();
    } catch (e) {
      logger.error(e);
      loadError = true;
      loading = false;
      return;
    }
    if (isConnected && canRead) {
      void loadGroups();
      // List/detail loads are driven by the $effects above once the store
      // publishes — no manual call needed here.
    } else {
      loading = false;
    }
  });

  onDestroy(() => {
    connectHandle?.cancel();
    if (searchDebounce) clearTimeout(searchDebounce);
  });
</script>

<div class="contacts-page">
  <div class="contacts-header">
    <div>
      <h3>{$t('contacts.title')}</h3>
      <span class="caption">{$t('contacts.subtitle')}</span>
    </div>
    <div class="contacts-actions">
      {#if isConnected && canRead}
        <button
          class="filter-chip"
          onclick={refresh}
          aria-label={$t('contacts.refresh')}
          title={$t('contacts.refresh')}
        >
          <RefreshCw size={13} />
        </button>
        {#if canWrite}
          <button class="filter-chip new-chip" onclick={openCreate}>
            <Plus size={13} /> {$t('contacts.new')}
          </button>
        {/if}
      {/if}
    </div>
  </div>

  {#if connecting}
    <div class="connect-banner caption">{$t('contacts.connecting')}</div>
  {/if}

  {#if needsReconsent}
    <div class="reconsent-banner">
      <span>{$t('contacts.reconsentHint')}</span>
      <button class="link-btn" onclick={connectGoogle} disabled={connecting}>
        {$t('contacts.reconnect')}
      </button>
    </div>
  {/if}

  {#if !$contactsStatus}
    <div class="loading-state caption">{$t('contacts.loading')}</div>
  {:else if !isConnected}
    <div class="empty-wrap">
      <EmptyState
        title={$t('contacts.notConnected')}
        message={$t('contacts.notConnectedHint')}
        actionLabel={$t('contacts.connectGoogle')}
        onAction={connectGoogle}
      >
        {#snippet icon()}<Users size={44} />{/snippet}
      </EmptyState>
    </div>
  {:else if !canRead}
    <div class="empty-wrap">
      <EmptyState
        title={$t('contacts.scopeMissing')}
        message={$t('contacts.scopeMissingHint')}
        actionLabel={$t('contacts.reconnect')}
        onAction={connectGoogle}
      >
        {#snippet icon()}<Settings size={44} />{/snippet}
      </EmptyState>
    </div>
  {:else}
    {#if readOnly}
      <div class="readonly-banner caption">
        {$t('contacts.readOnlyHint')}
        <button class="link-btn link-btn-ghost" onclick={connectGoogle} disabled={connecting}>
          {$t('contacts.reconnect')}
        </button>
      </div>
    {/if}

    <div class="contacts-toolbar">
      <div class="search-wrap">
        <Search size={15} />
        <input
          class="search-input"
          type="text"
          placeholder={$t('contacts.searchPlaceholder')}
          aria-label={$t('contacts.searchPlaceholder')}
          bind:value={searchInput}
        />
      </div>
      {#if groups.length > 0}
        <div class="group-chips">
          <button
            class="filter-chip"
            class:active={!urlGroup}
            onclick={() => selectGroup(null)}
          >
            {$t('contacts.allGroups')}
          </button>
          {#each groups as group (group.resource_name)}
            <button
              class="filter-chip"
              class:active={urlGroup === group.resource_name}
              onclick={() => selectGroup(group.resource_name)}
              title={group.member_count != null
                ? $t('contacts.groupCount', { values: { count: group.member_count } })
                : undefined}
            >
              {contactGroupLabel(group)}
            </button>
          {/each}
        </div>
      {/if}
    </div>

    {#if loading}
      <div class="loading-state caption">{$t('contacts.loading')}</div>
    {:else if loadError}
      <div class="empty-wrap">
        <EmptyState
          title={$t('contacts.loadError')}
          actionLabel={$t('common.retry')}
          onAction={() => {
            loading = true;
            void loadList(urlQ, urlGroup);
          }}
        >
          {#snippet icon()}<Users size={44} />{/snippet}
        </EmptyState>
      </div>
    {:else if contacts.length === 0}
      <div class="empty-wrap">
        <EmptyState
          title={urlQ ? $t('contacts.noResults') : $t('contacts.empty')}
          message={urlQ ? '' : $t('contacts.emptyHint')}
        >
          {#snippet icon()}<Users size={44} />{/snippet}
        </EmptyState>
      </div>
    {:else}
      <div class="contacts-layout">
        <div class="contacts-list" role="group" aria-label={$t('contacts.title')}>
          {#each contacts as contact, i (contact.resource_name ?? `contact-${i}`)}
            {@const name = contactDisplayName(contact)}
            {@const active = urlContact === contact.resource_name}
            <button
              class="contact-row"
              class:active
              aria-current={active ? 'true' : undefined}
              onclick={() => contact.resource_name && selectContact(contact.resource_name)}
            >
              {#if contact.photo_url}
                <img class="avatar" src={contact.photo_url} alt="" loading="lazy" />
              {:else}
                <span class="avatar avatar-initials">{contactInitials(name)}</span>
              {/if}
              <span class="contact-row-main">
                <span class="contact-name">{name || $t('contacts.unnamed')}</span>
                {#if contactSubtitle(contact)}
                  <span class="contact-subtitle caption">{contactSubtitle(contact)}</span>
                {/if}
              </span>
            </button>
          {/each}
          {#if nextPageToken}
            <button
              class="load-more"
              onclick={() => void loadList(urlQ, urlGroup, true)}
              disabled={loadingMore}
            >
              {loadingMore ? $t('contacts.loading') : $t('contacts.loadMore')}
            </button>
          {/if}
        </div>

        <div class="contact-detail">
          {#if detailLoading}
            <div class="loading-state caption">{$t('contacts.loading')}</div>
          {:else if selected}
            {@const selName = contactDisplayName(selected)}
            {@const selOrg = primaryOf(selected.organizations)}
            <div class="detail-card">
              <div class="detail-head">
                {#if selected.photo_url}
                  <img class="avatar avatar-lg" src={selected.photo_url} alt="" />
                {:else}
                  <span class="avatar avatar-lg avatar-initials">{contactInitials(selName)}</span>
                {/if}
                <div class="detail-title">
                  <h4>{selName || $t('contacts.unnamed')}</h4>
                  {#if selOrg?.name}
                    <span class="detail-org caption">
                      {[selOrg.name, selOrg.title].filter(Boolean).join(' · ')}
                    </span>
                  {/if}
                </div>
                {#if canWrite}
                  <div class="detail-actions">
                    <button
                      class="icon-btn"
                      title={$t('contacts.edit')}
                      aria-label={$t('contacts.edit')}
                      onclick={() => void openEdit(selected!)}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      class="icon-btn danger"
                      title={$t('contacts.delete')}
                      aria-label={$t('contacts.delete')}
                      onclick={() => askDelete(selected!)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                {/if}
              </div>

              <div class="detail-body">
                {#if selected.emails.length > 0}
                  <div class="detail-section">
                    <div class="detail-label"><Mail size={12} /> {$t('contacts.emails')}</div>
                    {#each selected.emails as email, i (email.value ?? `email-${i}`)}
                      {#if email.value}
                        <a class="detail-line" href="mailto:{email.value}">
                          {email.value}
                          {#if email.type}<span class="detail-tag">{email.type}</span>{/if}
                          {#if email.primary}<span class="detail-tag primary">{$t('contacts.primary')}</span>{/if}
                        </a>
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if selected.phones.length > 0}
                  <div class="detail-section">
                    <div class="detail-label"><Phone size={12} /> {$t('contacts.phones')}</div>
                    {#each selected.phones as phone, i (phone.value ?? `phone-${i}`)}
                      {#if phone.value}
                        <a class="detail-line" href="tel:{phone.value}">
                          {phone.value}
                          {#if phone.type}<span class="detail-tag">{phone.type}</span>{/if}
                          {#if phone.primary}<span class="detail-tag primary">{$t('contacts.primary')}</span>{/if}
                        </a>
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if selected.organizations.length > 0}
                  <div class="detail-section">
                    <div class="detail-label"><Building2 size={12} /> {$t('contacts.organizations')}</div>
                    {#each selected.organizations as org, i (i)}
                      <div class="detail-line">
                        {org.name ?? ''}{#if org.title}{org.name ? ' · ' : ''}{org.title}{/if}
                        {#if org.primary}<span class="detail-tag primary">{$t('contacts.primary')}</span>{/if}
                      </div>
                    {/each}
                  </div>
                {/if}

                {#if selected.addresses.length > 0}
                  <div class="detail-section">
                    <div class="detail-label"><MapPin size={12} /> {$t('contacts.addresses')}</div>
                    {#each selected.addresses as addr, i (i)}
                      <div class="detail-line">{formatAddress(addr)}</div>
                    {/each}
                  </div>
                {/if}

                {#if selected.birthdays.length > 0}
                  <div class="detail-section">
                    <div class="detail-label"><Cake size={12} /> {$t('contacts.birthdays')}</div>
                    {#each selected.birthdays as bday, i (i)}
                      <div class="detail-line">{formatBirthday(bday)}</div>
                    {/each}
                  </div>
                {/if}

                {#if selected.urls.length > 0}
                  <div class="detail-section">
                    <div class="detail-label"><Globe size={12} /> {$t('contacts.urls')}</div>
                    {#each selected.urls as url, i (url.value ?? `url-${i}`)}
                      {#if url.value}
                        <a class="detail-line" href={url.value} target="_blank" rel="noopener noreferrer">
                          {url.value}
                        </a>
                      {/if}
                    {/each}
                  </div>
                {/if}

                {#if selected.note}
                  <div class="detail-section">
                    <div class="detail-label"><NotebookPen size={12} /> {$t('contacts.note')}</div>
                    <p class="detail-note">{selected.note}</p>
                  </div>
                {/if}

                {#if selected.memberships.length > 0}
                  <div class="detail-section">
                    <div class="detail-label">{$t('contacts.groups')}</div>
                    <div class="detail-tags">
                      {#each selected.memberships as m (m)}
                        {@const g = groups.find((gr) => gr.resource_name === m)}
                        <span class="group-badge">{g ? contactGroupLabel(g) : m.replace('contactGroups/', '')}</span>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          {:else}
            <div class="detail-empty caption">{$t('contacts.selectContact')}</div>
          {/if}
        </div>
      </div>
    {/if}
  {/if}
</div>

{#if editorOpen}
  {#key editingContact}
    <ContactEditor
      open={editorOpen}
      contact={editingContact}
      {groups}
      onSaved={handleSaved}
      onReload={reloadEditingContact}
      onClose={() => {
        editorOpen = false;
        editingContact = null;
      }}
    />
  {/key}
{/if}

<ConfirmDialog
  open={deleteTarget !== null}
  title={$t('contacts.deleteTitle')}
  message={$t('contacts.deleteConfirm', {
    values: { name: deleteTarget ? contactDisplayName(deleteTarget) || $t('contacts.unnamed') : '' },
  })}
  confirmLabel={$t('contacts.delete')}
  danger={true}
  onConfirm={confirmDelete}
  onClose={() => {
    deleteTarget = null;
  }}
/>

<style>
  .contacts-page {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 960px;
    margin: 0 auto;
    padding: 16px 8px;
  }

  .contacts-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  h3 {
    margin: 0;
    color: var(--text-primary);
  }

  .contacts-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 5px 10px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: transparent;
    color: var(--text-secondary);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .filter-chip:hover {
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .filter-chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg-primary, #fff);
  }

  .new-chip {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg-primary, #fff);
  }

  .connect-banner,
  .reconsent-banner,
  .readonly-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 12px;
  }

  .reconsent-banner {
    border-color: var(--danger, #e5484d);
  }

  .link-btn {
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 5px 12px;
    border-radius: var(--r);
    font-size: 11px;
    cursor: pointer;
    font-family: var(--font-mono);
    white-space: nowrap;
  }

  .link-btn:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .link-btn-ghost {
    background: transparent;
    color: var(--accent);
    border: 1px solid var(--border);
  }

  .contacts-toolbar {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .search-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-muted);
    background: var(--surface);
  }

  .search-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-size: 13px;
  }
  .search-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
    border-radius: var(--r-sm);
  }

  .group-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .contacts-layout {
    display: grid;
    grid-template-columns: minmax(240px, 320px) 1fr;
    gap: 12px;
    align-items: start;
  }

  @media (max-width: 720px) {
    .contacts-layout {
      grid-template-columns: 1fr;
    }
  }

  .contacts-list {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    background: var(--surface);
    max-height: 70vh;
    overflow-y: auto;
  }

  .contact-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid var(--border);
    background: transparent;
    color: var(--text-primary);
    text-align: left;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .contact-row:last-child {
    border-bottom: none;
  }

  .contact-row:hover {
    background: var(--hover);
  }

  .contact-row.active {
    background: color-mix(in srgb, var(--accent) 10%, transparent);
    box-shadow: inset 2px 0 0 var(--accent);
  }

  .avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }

  .avatar-lg {
    width: 56px;
    height: 56px;
  }

  .avatar-initials {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--elevated);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 600;
  }

  .avatar-lg.avatar-initials {
    font-size: 20px;
  }

  .contact-row-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .contact-name {
    font-size: 13px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .contact-subtitle {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .load-more {
    padding: 8px;
    border: none;
    border-top: 1px solid var(--border);
    background: transparent;
    color: var(--accent);
    font-size: 12px;
    cursor: pointer;
  }

  .load-more:hover {
    background: var(--hover);
  }

  .load-more:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .contact-detail {
    min-width: 0;
  }

  .detail-empty {
    padding: 48px 16px;
    text-align: center;
    color: var(--text-muted);
    border: 1px dashed var(--border);
    border-radius: 12px;
  }

  .detail-card {
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
    overflow: hidden;
  }

  .detail-head {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    border-bottom: 1px solid var(--border);
  }

  .detail-title {
    flex: 1;
    min-width: 0;
  }

  .detail-title h4 {
    margin: 0;
    font-size: 15px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .detail-org {
    color: var(--text-muted);
  }

  .detail-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: transparent;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .icon-btn:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }

  .icon-btn.danger:hover {
    color: var(--error, #e5484d);
    border-color: var(--error, #e5484d);
  }

  .detail-body {
    padding: 8px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .detail-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .detail-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .detail-line {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 13px;
    color: var(--text-primary);
    text-decoration: none;
  }

  a.detail-line {
    color: var(--accent);
  }

  a.detail-line:hover {
    text-decoration: underline;
  }

  .detail-tag {
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    text-transform: lowercase;
  }

  .detail-tag.primary {
    color: var(--accent);
    border-color: color-mix(in srgb, var(--accent) 40%, transparent);
  }

  .detail-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .group-badge {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 999px;
    background: var(--elevated);
    border: 1px solid var(--border);
    color: var(--text-secondary);
  }

  .detail-note {
    margin: 0;
    font-size: 13px;
    color: var(--text-secondary);
    white-space: pre-wrap;
    line-height: 1.6;
  }

  .loading-state {
    text-align: center;
    padding: 24px 0;
    color: var(--text-muted);
  }

  .empty-wrap {
    padding: 24px 0;
  }
</style>
