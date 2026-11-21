/**
 * Pure helpers for the Google Contacts UI (#43): display fallbacks, draft
 * form state and write-payload building. Kept framework-free so the logic is
 * unit-testable without rendering components.
 */
import type {
  Contact,
  ContactGroup,
  ContactWriteInput,
  ContactEmailInput,
  ContactPhoneInput,
  ContactOrganizationInput,
} from '$lib/api';

// ── Display helpers ──────────────────────────────────────────────────────────

/** Best available display name: explicit display_name, else structured parts. */
export function contactDisplayName(contact: Contact | null | undefined): string {
  if (!contact) return '';
  if (contact.display_name?.trim()) return contact.display_name.trim();
  return [contact.given_name, contact.middle_name, contact.family_name]
    .filter((p): p is string => !!p?.trim())
    .join(' ')
    .trim();
}

/** First `primary` entry, falling back to the first entry (Google marks one). */
export function primaryOf<T extends { primary: boolean }>(items: T[] | undefined): T | undefined {
  if (!items || items.length === 0) return undefined;
  return items.find((i) => i.primary) ?? items[0];
}

export function contactInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Secondary line for list rows: org (name · title) → email → phone. */
export function contactSubtitle(contact: Contact | null | undefined): string {
  if (!contact) return '';
  const org = primaryOf(contact.organizations);
  if (org?.name?.trim()) {
    const title = org.title?.trim();
    return title ? `${org.name.trim()} · ${title}` : org.name.trim();
  }
  const email = primaryOf(contact.emails)?.value?.trim();
  if (email) return email;
  return primaryOf(contact.phones)?.value?.trim() ?? '';
}

export function contactGroupLabel(group: ContactGroup): string {
  return group.formatted_name?.trim() || group.name?.trim() || group.resource_name || '';
}

/** Human-readable birthday: full date, partial date, or Google's free text. */
export function formatBirthday(b: {
  year: number | null;
  month: number | null;
  day: number | null;
  text: string | null;
}): string {
  if (b.text?.trim()) return b.text.trim();
  const parts: string[] = [];
  if (b.day) parts.push(String(b.day));
  if (b.month) parts.push(String(b.month));
  if (b.year) parts.push(String(b.year));
  return parts.join('/');
}

/** Single-line address for the detail pane. */
export function formatAddress(a: {
  formatted_value: string | null;
  street_address: string | null;
  extended_address: string | null;
  city: string | null;
  region: string | null;
  postal_code: string | null;
  country: string | null;
}): string {
  if (a.formatted_value?.trim()) return a.formatted_value.trim();
  return [
    a.street_address,
    a.extended_address,
    a.city,
    a.region,
    a.postal_code,
    a.country,
  ]
    .filter((p): p is string => !!p?.trim())
    .join(', ');
}

// ── Error helpers ────────────────────────────────────────────────────────────

/**
 * `req()` in api.ts throws `Error("API METHOD path → STATUS: body")` — there
 * is no typed error. Extract the HTTP status from the message, or null.
 */
export function httpStatusOf(error: unknown): number | null {
  const msg = error instanceof Error ? error.message : String(error ?? '');
  const m = msg.match(/→\s*(\d{3})\b/);
  return m ? Number(m[1]) : null;
}

// ── Editor draft ─────────────────────────────────────────────────────────────

export interface ContactEmailDraft {
  value: string;
  type: string;
  /** Passthrough — Google email displayName is preserved but not edited. */
  display_name: string;
  primary: boolean;
}

export interface ContactPhoneDraft {
  value: string;
  type: string;
  primary: boolean;
}

export interface ContactOrgDraft {
  name: string;
  title: string;
  /** Passthrough fields — preserved on save, not shown as inputs. */
  department: string;
  type: string;
  current: boolean | null;
  job_description: string;
  primary: boolean;
}

export interface ContactDraft {
  given_name: string;
  family_name: string;
  /** Passthrough name parts (not rendered, round-tripped on save). */
  middle_name: string;
  honorific_prefix: string;
  honorific_suffix: string;
  /** Not returned by the read API — kept so create-mode payloads stay uniform. */
  unstructured_name: string;
  emails: ContactEmailDraft[];
  phones: ContactPhoneDraft[];
  organizations: ContactOrgDraft[];
  note: string;
  memberships: string[];
}

export function emptyContactDraft(): ContactDraft {
  return {
    given_name: '',
    family_name: '',
    middle_name: '',
    honorific_prefix: '',
    honorific_suffix: '',
    unstructured_name: '',
    emails: [],
    phones: [],
    organizations: [],
    note: '',
    memberships: [],
  };
}

export function contactToDraft(contact: Contact | null | undefined): ContactDraft {
  const draft = emptyContactDraft();
  if (!contact) return draft;
  draft.given_name = contact.given_name ?? '';
  draft.family_name = contact.family_name ?? '';
  draft.middle_name = contact.middle_name ?? '';
  draft.honorific_prefix = contact.honorific_prefix ?? '';
  draft.honorific_suffix = contact.honorific_suffix ?? '';
  draft.emails = (contact.emails ?? []).map((e) => ({
    value: e.value ?? '',
    type: e.type ?? '',
    display_name: e.display_name ?? '',
    primary: e.primary,
  }));
  draft.phones = (contact.phones ?? []).map((p) => ({
    value: p.value ?? '',
    type: p.type ?? '',
    primary: p.primary,
  }));
  draft.organizations = (contact.organizations ?? []).map((o) => ({
    name: o.name ?? '',
    title: o.title ?? '',
    department: o.department ?? '',
    type: o.type ?? '',
    current: o.current ?? null,
    job_description: o.job_description ?? '',
    primary: o.primary,
  }));
  draft.note = contact.note ?? '';
  draft.memberships = [...(contact.memberships ?? [])];
  return draft;
}

const NAME_KEYS = [
  'given_name',
  'family_name',
  'middle_name',
  'honorific_prefix',
  'honorific_suffix',
  'unstructured_name',
] as const;

function draftNameUnchanged(draft: ContactDraft, original: Contact): boolean {
  const orig: Record<string, string> = {
    given_name: original.given_name ?? '',
    family_name: original.family_name ?? '',
    middle_name: original.middle_name ?? '',
    honorific_prefix: original.honorific_prefix ?? '',
    honorific_suffix: original.honorific_suffix ?? '',
    // unstructured_name is not part of the read model — treat as '' so an
    // untouched draft never triggers a names-section replace.
    unstructured_name: '',
  };
  return NAME_KEYS.every((k) => (draft[k] ?? '') === orig[k]);
}

function cleanStr(v: string | undefined | null): string | undefined {
  const t = (v ?? '').trim();
  return t === '' ? undefined : t;
}

function buildEmails(rows: ContactEmailDraft[]): ContactEmailInput[] {
  return rows
    .filter((r) => cleanStr(r.value))
    .map((r) => {
      const out: ContactEmailInput = { value: r.value.trim(), primary: r.primary };
      const type = cleanStr(r.type);
      if (type) out.type = type;
      const dn = cleanStr(r.display_name);
      if (dn) out.display_name = dn;
      return out;
    });
}

function buildPhones(rows: ContactPhoneDraft[]): ContactPhoneInput[] {
  return rows
    .filter((r) => cleanStr(r.value))
    .map((r) => {
      const out: ContactPhoneInput = { value: r.value.trim(), primary: r.primary };
      const type = cleanStr(r.type);
      if (type) out.type = type;
      return out;
    });
}

function buildOrganizations(rows: ContactOrgDraft[]): ContactOrganizationInput[] {
  return rows
    .filter((r) => cleanStr(r.name) || cleanStr(r.title))
    .map((r) => {
      const out: ContactOrganizationInput = { primary: r.primary };
      for (const [src, dst] of [
        ['name', 'name'],
        ['title', 'title'],
        ['department', 'department'],
        ['type', 'type'],
        ['job_description', 'job_description'],
      ] as const) {
        const v = cleanStr(r[src]);
        if (v) out[dst] = v;
      }
      if (r.current !== null && r.current !== undefined) out.current = r.current;
      return out;
    });
}

/**
 * Build the ContactWriteInput payload for create/update.
 *
 * PUT semantics: every section the form manages is sent (it fully replaces
 * the stored section — the draft was loaded from the full detail read, so
 * sending it back is a faithful round-trip). Sections the form does NOT
 * manage (addresses, birthdays, urls) are omitted entirely so Google keeps
 * them untouched.
 *
 * The `names` section is the exception: the read model does not return
 * `unstructuredName`, so when the name fields are unchanged vs `original`
 * the whole section is omitted — otherwise an edit to e.g. only the email
 * would silently wipe an unstructured name. When names DID change, all six
 * fields are sent (empty → null) so clearing works too.
 */
export function draftToWriteInput(
  draft: ContactDraft,
  opts: { etag?: string | null; original?: Contact | null } = {}
): ContactWriteInput {
  const out: ContactWriteInput = {};

  const namesChanged = !opts.original || !draftNameUnchanged(draft, opts.original);
  if (namesChanged) {
    for (const k of NAME_KEYS) {
      (out as Record<string, string | null>)[k] = draft[k].trim() || null;
    }
  }

  out.emails = buildEmails(draft.emails);
  out.phones = buildPhones(draft.phones);
  out.organizations = buildOrganizations(draft.organizations);
  out.note = draft.note.trim() || null;
  out.memberships = draft.memberships.filter((m) => typeof m === 'string' && m.trim() !== '');

  const etag = opts.etag ?? opts.original?.etag ?? null;
  if (etag) out.etag = etag;
  return out;
}

/** Light client-side guard: a contact needs at least one identifying field. */
export function draftHasContent(draft: ContactDraft): boolean {
  return (
    NAME_KEYS.some((k) => draft[k].trim() !== '') ||
    draft.emails.some((e) => e.value.trim() !== '') ||
    draft.phones.some((p) => p.value.trim() !== '') ||
    draft.organizations.some((o) => o.name.trim() !== '' || o.title.trim() !== '')
  );
}
