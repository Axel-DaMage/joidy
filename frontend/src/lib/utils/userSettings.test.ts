import { beforeEach, describe, expect, it } from 'vitest';
import { loadUserSettings, patchUserSettings } from './userSettings';

describe('userSettings goalsUi', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('merges goalsUi subfields without dropping pinnedGoalIds (#1096)', () => {
    patchUserSettings({ goalsUi: { pinnedGoalIds: [1, 2] } });
    patchUserSettings({ goalsUi: { editorFilter: 'PINNED' } });
    patchUserSettings({ goalsUi: { editorSearch: 'darwin' } });

    const goalsUi = loadUserSettings().goalsUi;
    expect(goalsUi).toEqual({
      pinnedGoalIds: [1, 2],
      editorFilter: 'PINNED',
      editorSearch: 'darwin'
    });
  });

  it('persists editorFilter explicitly set to null ("Todos")', () => {
    patchUserSettings({ goalsUi: { editorFilter: 'ACTIVE' } });
    expect(loadUserSettings().goalsUi?.editorFilter).toBe('ACTIVE');

    patchUserSettings({ goalsUi: { editorFilter: null } });
    expect(loadUserSettings().goalsUi?.editorFilter).toBeNull();
  });

  it('does not leak values between namespaces when patching another one', () => {
    patchUserSettings({ notesUi: { search: 'x' } });
    const settings = loadUserSettings();
    expect(settings.notesUi).toEqual({ search: 'x' });
    expect(settings.goalsUi).toEqual({});
  });
});
