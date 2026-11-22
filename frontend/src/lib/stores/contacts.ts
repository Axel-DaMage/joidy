/**
 * Shared Google Contacts connection status (#43).
 *
 * `GET /integrations/contacts/status` reports `{connected, contacts_read,
 * contacts_write}`. The /contactos page and the Settings panel both consume
 * this store so a connect/reconnect performed in one surface is reflected in
 * the other without a reload.
 */
import { writable } from 'svelte/store';
import { api, type ContactsStatus } from '$lib/api';

export const contactsStatus = writable<ContactsStatus | null>(null);

/** Fetch (or refetch) the contacts status and publish it to the store. */
export async function loadContactsStatus(): Promise<ContactsStatus> {
  const status = await api.contacts.status();
  contactsStatus.set(status);
  return status;
}
