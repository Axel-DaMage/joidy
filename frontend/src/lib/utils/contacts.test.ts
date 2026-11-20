import { describe, it, expect } from 'vitest';
import type { Contact, ContactGroup } from '$lib/api';
import {
  contactDisplayName,
  contactInitials,
  contactSubtitle,
  contactGroupLabel,
  primaryOf,
  formatBirthday,
  formatAddress,
  httpStatusOf,
  emptyContactDraft,
  contactToDraft,
  draftToWriteInput,
  draftHasContent,
} from './contacts';

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

describe('contactDisplayName', () => {
  it('prefers display_name', () => {
    expect(contactDisplayName(makeContact())).toBe('Ada Lovelace');
  });

  it('falls back to structured name parts when display_name is empty', () => {
    const c = makeContact({ display_name: null, given_name: 'Grace', family_name: 'Hopper' });
    expect(contactDisplayName(c)).toBe('Grace Hopper');
  });

  it('includes middle name in the fallback', () => {
    const c = makeContact({ display_name: null, given_name: 'A', middle_name: 'B', family_name: 'C' });
    expect(contactDisplayName(c)).toBe('A B C');
  });

  it('returns empty string for null contact', () => {
    expect(contactDisplayName(null)).toBe('');
    expect(contactDisplayName(undefined)).toBe('');
  });
});

describe('contactInitials', () => {
  it('takes first and last word initials', () => {
    expect(contactInitials('Ada Lovelace')).toBe('AL');
  });

  it('handles single-word names', () => {
    expect(contactInitials('Cher')).toBe('CH');
  });

  it('returns ? for empty input', () => {
    expect(contactInitials('   ')).toBe('?');
  });
});

describe('primaryOf', () => {
  it('returns the primary entry', () => {
    const items = [
      { value: 'a@x.com', primary: false },
      { value: 'b@x.com', primary: true },
    ];
    expect(primaryOf(items)?.value).toBe('b@x.com');
  });

  it('falls back to the first entry when none is primary', () => {
    const items = [
      { value: 'a@x.com', primary: false },
      { value: 'b@x.com', primary: false },
    ];
    expect(primaryOf(items)?.value).toBe('a@x.com');
  });

  it('returns undefined for empty input', () => {
    expect(primaryOf([])).toBeUndefined();
    expect(primaryOf(undefined)).toBeUndefined();
  });
});

describe('contactSubtitle', () => {
  it('prefers organization name · title', () => {
    const c = makeContact({
      organizations: [
        { name: 'Analytical Engines', title: 'Engineer', department: null, type: null, current: true, job_description: null, primary: true },
      ],
      emails: [{ value: 'ada@example.com', type: null, primary: true }],
    });
    expect(contactSubtitle(c)).toBe('Analytical Engines · Engineer');
  });

  it('falls back to primary email then phone', () => {
    const c = makeContact({ organizations: [] });
    expect(contactSubtitle(c)).toBe('ada@example.com');
    const c2 = makeContact({
      organizations: [],
      emails: [],
      phones: [{ value: '+1 555', type: null, primary: true }],
    });
    expect(contactSubtitle(c2)).toBe('+1 555');
  });
});

describe('contactGroupLabel', () => {
  it('prefers formatted_name then name then resource_name', () => {
    const base: ContactGroup = {
      resource_name: 'contactGroups/g1',
      name: 'work',
      formatted_name: 'Work',
      group_type: 'USER_CONTACT_GROUP',
      member_count: 3,
    };
    expect(contactGroupLabel(base)).toBe('Work');
    expect(contactGroupLabel({ ...base, formatted_name: null })).toBe('work');
    expect(contactGroupLabel({ ...base, formatted_name: null, name: null })).toBe('contactGroups/g1');
  });
});

describe('formatBirthday', () => {
  it('prefers free text', () => {
    expect(formatBirthday({ year: 1815, month: 12, day: 10, text: 'Dec 10' })).toBe('Dec 10');
  });
  it('joins date parts day/month/year', () => {
    expect(formatBirthday({ year: 1815, month: 12, day: 10, text: null })).toBe('10/12/1815');
  });
  it('handles partial dates', () => {
    expect(formatBirthday({ year: null, month: 12, day: null, text: null })).toBe('12');
  });
});

describe('formatAddress', () => {
  it('prefers formatted_value', () => {
    expect(
      formatAddress({
        formatted_value: '1 Main St',
        street_address: 'ignored',
        extended_address: null,
        city: null,
        region: null,
        postal_code: null,
        country: null,
      })
    ).toBe('1 Main St');
  });
  it('joins address parts', () => {
    expect(
      formatAddress({
        formatted_value: null,
        street_address: '1 Main St',
        extended_address: null,
        city: 'Springfield',
        region: 'IL',
        postal_code: '62701',
        country: 'US',
      })
    ).toBe('1 Main St, Springfield, IL, 62701, US');
  });
});

describe('httpStatusOf', () => {
  it('parses the status embedded in req() error messages', () => {
    expect(httpStatusOf(new Error('API PUT /integrations/contacts/people/x → 409: {"detail":"conflict"}'))).toBe(409);
    expect(httpStatusOf(new Error('API GET /x → 403: nope'))).toBe(403);
    expect(httpStatusOf(new Error('API GET /x → 401 Unauthorized'))).toBe(401);
  });
  it('returns null for non-API errors', () => {
    expect(httpStatusOf(new Error('network down'))).toBeNull();
    expect(httpStatusOf('weird')).toBeNull();
    expect(httpStatusOf(null)).toBeNull();
  });
});

describe('contactToDraft / draftToWriteInput', () => {
  it('round-trips a full contact into a write payload with etag', () => {
    const contact = makeContact({
      note: 'Met at conference',
      memberships: ['contactGroups/work'],
      phones: [{ value: '+1 555', type: 'mobile', primary: false }],
      organizations: [
        {
          name: 'ACME',
          title: 'CTO',
          department: 'Eng',
          type: 'work',
          current: true,
          job_description: null,
          primary: true,
        },
      ],
    });
    const draft = contactToDraft(contact);
    const payload = draftToWriteInput(draft, { original: contact });

    // Names unchanged vs original → section omitted (protects unstructuredName).
    expect(payload.given_name).toBeUndefined();
    expect(payload.family_name).toBeUndefined();
    expect(payload.etag).toBe('"etag-1"');
    expect(payload.note).toBe('Met at conference');
    expect(payload.memberships).toEqual(['contactGroups/work']);
    expect(payload.emails).toEqual([
      { value: 'ada@example.com', type: 'home', display_name: undefined, primary: true },
    ]);
    expect(payload.phones).toEqual([{ value: '+1 555', type: 'mobile', primary: false }]);
    expect(payload.organizations?.[0]).toMatchObject({
      name: 'ACME',
      title: 'CTO',
      department: 'Eng',
      type: 'work',
      current: true,
      primary: true,
    });
    // Unmanaged sections are never sent → preserved server-side.
    expect(payload.addresses).toBeUndefined();
    expect(payload.birthdays).toBeUndefined();
    expect(payload.urls).toBeUndefined();
  });

  it('sends the names section when a name field changed', () => {
    const contact = makeContact();
    const draft = contactToDraft(contact);
    draft.family_name = 'Byron';
    const payload = draftToWriteInput(draft, { original: contact });
    expect(payload.given_name).toBe('Ada');
    expect(payload.family_name).toBe('Byron');
    expect(payload.middle_name).toBeNull();
  });

  it('sends names on create (no original) even when partially filled', () => {
    const draft = emptyContactDraft();
    draft.given_name = 'New';
    draft.emails = [{ value: 'n@x.com', type: '', display_name: '', primary: true }];
    const payload = draftToWriteInput(draft);
    expect(payload.given_name).toBe('New');
    expect(payload.family_name).toBeNull();
    expect(payload.emails).toEqual([{ value: 'n@x.com', primary: true }]);
  });

  it('filters out empty email/phone rows and empty orgs', () => {
    const draft = emptyContactDraft();
    draft.emails = [
      { value: '', type: 'home', display_name: '', primary: true },
      { value: 'real@x.com', type: ' work ', display_name: '', primary: false },
    ];
    draft.phones = [{ value: '   ', type: '', primary: true }];
    draft.organizations = [
      { name: '', title: '', department: '', type: '', current: null, job_description: '', primary: true },
      { name: 'ACME', title: '', department: '', type: '', current: null, job_description: '', primary: true },
    ];
    const payload = draftToWriteInput(draft);
    expect(payload.emails).toEqual([{ value: 'real@x.com', type: 'work', primary: false }]);
    expect(payload.phones).toEqual([]);
    expect(payload.organizations).toHaveLength(1);
    expect(payload.organizations?.[0]?.name).toBe('ACME');
  });

  it('clears note when emptied', () => {
    const contact = makeContact({ note: 'old note' });
    const draft = contactToDraft(contact);
    draft.note = '   ';
    const payload = draftToWriteInput(draft, { original: contact });
    expect(payload.note).toBeNull();
  });

  it('drops blank memberships', () => {
    const draft = emptyContactDraft();
    draft.memberships = ['contactGroups/a', '  ', 'contactGroups/b'];
    expect(draftToWriteInput(draft).memberships).toEqual(['contactGroups/a', 'contactGroups/b']);
  });
});

describe('draftHasContent', () => {
  it('is false for an empty draft', () => {
    expect(draftHasContent(emptyContactDraft())).toBe(false);
  });
  it('is true with only a note? — no: note alone does not count', () => {
    const draft = emptyContactDraft();
    draft.note = 'just a note';
    expect(draftHasContent(draft)).toBe(false);
  });
  it('is true with an email', () => {
    const draft = emptyContactDraft();
    draft.emails = [{ value: 'a@b.c', type: '', display_name: '', primary: true }];
    expect(draftHasContent(draft)).toBe(true);
  });
});
