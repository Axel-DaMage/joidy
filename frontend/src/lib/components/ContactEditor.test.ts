import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import type { Contact } from '$lib/api';

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    contacts: {
      create: vi.fn(),
      update: vi.fn(),
      get: vi.fn(),
    },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

import ContactEditor from './ContactEditor.svelte';

function makeContact(overrides: Partial<Contact> = {}): Contact {
  return {
    resource_name: 'people/abc123',
    etag: '"etag-1"',
    display_name: 'Ada Lovelace',
    given_name: 'Ada',
    family_name: 'Lovelace',
    middle_name: null,
    honorific_prefix: null,
    honorific_suffix: null,
    emails: [{ value: 'ada@example.com', type: 'home', primary: true, display_name: null }],
    phones: [],
    organizations: [],
    addresses: [],
    birthdays: [],
    urls: [],
    photo_url: null,
    note: null,
    memberships: [],
    ...overrides,
  };
}

const GROUPS = [
  {
    resource_name: 'contactGroups/work',
    name: 'work',
    formatted_name: 'Work',
    group_type: 'USER_CONTACT_GROUP',
    member_count: 2,
  },
];

describe('ContactEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it('creates a contact: name + email reach api.contacts.create', async () => {
    const saved = makeContact({ resource_name: 'people/new1' });
    apiMock.contacts.create.mockResolvedValue(saved);
    const onSaved = vi.fn();
    const { getByLabelText, getByRole, getByText, getAllByText } = render(ContactEditor, {
      props: { open: true, contact: null, groups: [], onSaved, onClose: () => {} },
    });

    expect(getByText('Nuevo contacto')).toBeTruthy();

    // Add an email row (first "Añadir" button belongs to the emails section),
    // then fill name + email.
    await fireEvent.click(getAllByText('Añadir')[0]);
    await tick();
    const emailInput = getByLabelText('email@ejemplo.com');
    await fireEvent.input(emailInput, { target: { value: 'new@example.com' } });
    await fireEvent.input(getByLabelText('Nombre'), { target: { value: 'New' } });
    await fireEvent.input(getByLabelText('Apellidos'), { target: { value: 'Person' } });

    await fireEvent.click(getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(apiMock.contacts.create).toHaveBeenCalledTimes(1));
    const payload = apiMock.contacts.create.mock.calls[0][0];
    expect(payload.given_name).toBe('New');
    expect(payload.family_name).toBe('Person');
    expect(payload.emails).toEqual([{ value: 'new@example.com', primary: true }]);
    expect(payload.etag).toBeUndefined();

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved));
  });

  it('edits a contact: PUT echoes the etag and prefills fields', async () => {
    const contact = makeContact();
    apiMock.contacts.update.mockResolvedValue({ ...contact, family_name: 'Byron' });
    const onSaved = vi.fn();
    const { getByLabelText, getByRole, getByText } = render(ContactEditor, {
      props: { open: true, contact, groups: GROUPS, onSaved, onClose: () => {} },
    });

    expect(getByText('Editar contacto')).toBeTruthy();
    expect((getByLabelText('Nombre') as HTMLInputElement).value).toBe('Ada');
    expect((getByLabelText('Apellidos') as HTMLInputElement).value).toBe('Lovelace');
    // Existing email row is prefilled.
    expect((getByLabelText('email@ejemplo.com') as HTMLInputElement).value).toBe('ada@example.com');

    await fireEvent.input(getByLabelText('Apellidos'), { target: { value: 'Byron' } });
    await fireEvent.click(getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(apiMock.contacts.update).toHaveBeenCalledTimes(1));
    const [resourceName, payload] = apiMock.contacts.update.mock.calls[0];
    expect(resourceName).toBe('people/abc123');
    expect(payload.etag).toBe('"etag-1"');
    expect(payload.family_name).toBe('Byron');
    expect(payload.given_name).toBe('Ada');
    // Names changed → section sent; untouched sections still round-trip.
    expect(payload.emails).toEqual([
      { value: 'ada@example.com', type: 'home', primary: true },
    ]);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it('blocks save with a validation error when the draft is empty', async () => {
    const { getByRole, getByText } = render(ContactEditor, {
      props: { open: true, contact: null, groups: [], onClose: () => {} },
    });
    await fireEvent.click(getByRole('button', { name: 'Guardar' }));
    await waitFor(() =>
      expect(getByText('Añade al menos un nombre, email o teléfono')).toBeTruthy()
    );
    expect(apiMock.contacts.create).not.toHaveBeenCalled();
  });

  it('shows the conflict state on a 409 etag mismatch', async () => {
    const contact = makeContact();
    apiMock.contacts.update.mockRejectedValue(
      new Error('API PUT /integrations/contacts/people/abc123 → 409: {"detail":"conflict"}')
    );
    const onReload = vi.fn();
    const { getByRole, getByText } = render(ContactEditor, {
      props: { open: true, contact, groups: [], onReload, onClose: () => {} },
    });

    await fireEvent.click(getByRole('button', { name: 'Guardar' }));

    await waitFor(() =>
      expect(getByText('El contacto cambió desde que lo cargaste')).toBeTruthy()
    );
    await fireEvent.click(getByText('Recargar'));
    expect(onReload).toHaveBeenCalled();
  });

  it('toggles group memberships into the payload', async () => {
    apiMock.contacts.create.mockResolvedValue(makeContact({ resource_name: 'people/n2' }));
    const { getByLabelText, getByRole } = render(ContactEditor, {
      props: { open: true, contact: null, groups: GROUPS, onClose: () => {} },
    });

    await fireEvent.input(getByLabelText('Nombre'), { target: { value: 'Grouped' } });
    // The group checkbox is label-wrapped → accessible name is the group label.
    await fireEvent.click(getByLabelText('Work'));
    await fireEvent.click(getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(apiMock.contacts.create).toHaveBeenCalledTimes(1));
    expect(apiMock.contacts.create.mock.calls[0][0].memberships).toEqual(['contactGroups/work']);
  });
});
