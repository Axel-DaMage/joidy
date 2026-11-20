// Shared state for the Goal Editor (#935). The module-level runes store is the
// single source of truth for the editor container and its panes
// (GoalEditorContent / GoalEditorPreview / GoalPropertiesPanel), so nothing is
// prop-drilled deeper than one level.
import type { Goal } from '$lib/api';

export type GoalEditorPane = 'editor' | 'preview' | 'properties';

export interface GoalEditorState {
  /** The goal being edited — synced from the page prop and updated in place
   *  when the properties panel persists field changes. */
  goal: Goal | null;
  title: string;
  content: string;
  saving: boolean;
  saved: boolean;
  hasUnsavedChanges: boolean;
  /** Mid-width layouts (768–1199px): swap the editor pane for the preview. */
  previewMode: boolean;
  zenMode: boolean;
  deleteConfirm: boolean;
  contextSaving: boolean;
  /** Narrow layouts (<768px): which pane the tab bar shows. */
  mobilePane: GoalEditorPane;
}

const initialState = (): GoalEditorState => ({
  goal: null,
  title: '',
  content: '',
  saving: false,
  saved: false,
  hasUnsavedChanges: false,
  previewMode: false,
  zenMode: false,
  deleteConfirm: false,
  contextSaving: false,
  mobilePane: 'editor',
});

export const goalEditor: GoalEditorState = $state(initialState());

/**
 * Reset transient state. Called when the editor mounts and when the goal id
 * changes without a remount (goal → goal client navigation on the same page).
 * `title`/`content` are NOT reset here — they are re-synced from props by the
 * container so in-flight draft recovery still sees them.
 */
export function resetGoalEditor() {
  goalEditor.goal = null;
  goalEditor.saving = false;
  goalEditor.saved = false;
  goalEditor.hasUnsavedChanges = false;
  goalEditor.previewMode = false;
  goalEditor.zenMode = false;
  goalEditor.deleteConfirm = false;
  goalEditor.contextSaving = false;
  goalEditor.mobilePane = 'editor';
}
