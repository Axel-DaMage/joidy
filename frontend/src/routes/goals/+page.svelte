<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { appHeaderTabs } from '$lib/stores/appHeader';
  import { page } from '$app/state';
  import { goto, replaceState } from '$app/navigation';
  import { resolve } from '$app/paths';
  import Plus from 'lucide-svelte/icons/plus';
  import Check from 'lucide-svelte/icons/check';
  import ChevronDown from 'lucide-svelte/icons/chevron-down';
  import Calendar from 'lucide-svelte/icons/calendar';
  import CalendarDays from 'lucide-svelte/icons/calendar-days';
  import Clock from 'lucide-svelte/icons/clock';
  import Pencil from 'lucide-svelte/icons/pencil';
  import X from 'lucide-svelte/icons/x';
  import ChevronRight from 'lucide-svelte/icons/chevron-right';
  import ChevronLeft from 'lucide-svelte/icons/chevron-left';
  import Settings from 'lucide-svelte/icons/settings';
  import Palette from 'lucide-svelte/icons/palette';
  import Hexagon from 'lucide-svelte/icons/hexagon';
  import Inbox from 'lucide-svelte/icons/inbox';
  import TriangleAlert from 'lucide-svelte/icons/triangle-alert';
  import FilePen from 'lucide-svelte/icons/file-pen';
  import Tag from 'lucide-svelte/icons/tag';
  import FileText from 'lucide-svelte/icons/file-text';
  import Pin from 'lucide-svelte/icons/pin';
  import PinOff from 'lucide-svelte/icons/pin-off';
  import Zap from 'lucide-svelte/icons/zap';
  import List from 'lucide-svelte/icons/list';
  import Lock from 'lucide-svelte/icons/lock';
  import Target from 'lucide-svelte/icons/target';
  import {
    api,
    type CalendarEvent,
    type CalendarTask,
    type Goal,
    type GoalContext,
    type Tag as TagType,
    type Note,
    type PersonalStreak,
  } from '$lib/api';
  import PlanningCalendar, {
    type CalendarDayBadge,
    type CalendarDayChip,
  } from '$lib/components/calendar/PlanningCalendar.svelte';
  import CalendarLayerToggles from '$lib/components/calendar/CalendarLayerToggles.svelte';
  import {
    CHIP_DENSITY_LIMITS,
    PLAN_TEMPS,
    agendaDaysFor,
    assignGoal,
    assignedIdsForDate,
    calendarLayers,
    chipDensity,
    getNormalizedDate,
    jumpToPlanningDay,
    loadAssignmentsForDate,
    loadAssignmentsForRange,
    monthCellsFor,
    planningAssignments,
    planningCursor,
    planningEventSources,
    planningSelectedDay,
    planningView,
    refreshAssignmentsForDate,
    selectPlanningDay,
    goPlanningToday,
    setPlanningView,
    shiftPlanningPeriod,
    unassignGoal,
    weekDaysFor,
  } from '$lib/stores/planningCalendar';
  import GoalFilters from '$lib/components/GoalFilters.svelte';
  import GoalInbox from '$lib/components/GoalInbox.svelte';
  import GoalList from '$lib/components/GoalList.svelte';
  import GoalStatsRail from '$lib/components/GoalStatsRail.svelte';
  import GoalUpcoming from '$lib/components/GoalUpcoming.svelte';
  import { inboxCount } from '$lib/utils/goalTriage';
  import { localDayKey } from '$lib/utils/date';
  import { applyGamificationResult, showXPGain } from '$lib/stores/gamification';
  import {
    getCachedData,
    setCachedData,
    loadUserSettings,
    patchUserSettings,
  } from '$lib/utils/userSettings';
  import { loadPref, savePref, removePref } from '$lib/utils/persistedState';
  import { logger } from '$lib/utils/logger';
  import {
    GOALS_SPECIFIC_COLOR_PRESETS,
    DEFAULT_GOAL_COLOR,
    TEMPORALITY_COLORS,
  } from '$lib/utils/goalColors';
  import {
    suggestEmoji,
    suggestIcon,
    suggestIconKey,
  } from '$lib/utils/iconSuggest';
  import StreakIcon from '$lib/components/StreakIcon.svelte';
  import LazyIconPicker from '$lib/components/LazyIconPicker.svelte';
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import GoalFromEventModal, { type GoalEventSeed } from '$lib/components/GoalFromEventModal.svelte';
  import NoteLinkPicker from '$lib/components/NoteLinkPicker.svelte';
  import { focusTrap } from '$lib/actions/focusTrap';
  import { marquee } from '$lib/actions/marquee';
  import { t } from 'svelte-i18n';
  import { locale } from '$lib/stores/locale';

  // Lazy-load the heavy StreakHeatmap (561 lines) so it is split into a
  // separate chunk and only downloaded when the history tab is active — the
  // only tab that renders it (#347). A failed chunk surfaces an
  // error + retry instead of leaving the slot empty forever (#1459).
  let StreakHeatmap = $state<typeof import('$lib/components/StreakHeatmap.svelte').default | null>(
    null
  );
  let heatmapChunkError = $state(false);
  let heatmapChunkLoading = $state(false);
  function loadStreakHeatmap() {
    if (StreakHeatmap || heatmapChunkLoading) return;
    heatmapChunkLoading = true;
    heatmapChunkError = false;
    import('$lib/components/StreakHeatmap.svelte')
      .then((m) => (StreakHeatmap = m.default))
      .catch((err) => {
        logger.error('[goals] StreakHeatmap chunk failed:', err);
        heatmapChunkError = true;
      })
      .finally(() => (heatmapChunkLoading = false));
  }
  $effect(() => {
    if (currentTab === 'history' && !StreakHeatmap && !heatmapChunkError) {
      loadStreakHeatmap();
    }
  });

  let goals = $state<Goal[]>([]);
  let tags = $state<TagType[]>([]);
  let notes = $state<Note[]>([]);
  const VALID_TABS = ['editor', 'inbox', 'planning', 'history'] as const;
  let currentTab = $state<(typeof VALID_TABS)[number]>('editor');

  // Page tabs live in the global app header (shared store, cleared on unmount).
  $effect(() => {
    appHeaderTabs.set({
      label: 'Goals sections',
      activeId: currentTab,
      onselect: (id) => {
        if (id === 'editor' || id === 'inbox' || id === 'planning' || id === 'history') {
          currentTab = id;
        }
      },
      tabs: [
        { id: 'exec', label: $t('executionPage.tabLabel'), icon: Zap, href: '/goals/ejecucion' },
        { id: 'editor', label: 'Editor', icon: Pencil },
        {
          id: 'inbox',
          label: $t('goalsPage.inboxTab'),
          icon: Inbox,
          badge: inboxBadgeCount,
        },
        { id: 'planning', label: 'Planificación', icon: Clock },
        { id: 'history', label: 'Historial', icon: Calendar },
      ],
    });
  });
  onDestroy(() => appHeaderTabs.set(null));
  let currentPlanningTab = $state<'WEEKLY' | 'MONTHLY' | 'ANNUAL'>('ANNUAL');
  let showAddForm = $state(false);
  let goalSearchQuery = $state('');
  let goalFilterState = $state<string | null>(null);
  // Energy-context filter for the editor list (#1200); persisted in goalsUi.
  let goalContextFilter = $state<GoalContext | null>(null);
  // Matches the states rendered by GoalFilters.svelte (null = "Todos")
  const VALID_EDITOR_FILTERS = ['PINNED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'FAILED', 'INBOX'] as const;
  const VALID_POOL_FILTERS = ['recent', 'active', 'completed', 'failed'] as const;
  const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
  let inboxBadgeCount = $derived(inboxCount(goals));
  let pinnedGoals = $state<Set<number>>(new Set());
  // Last goal opened in the goal editor (/goals/[id]) — persisted so the
  // editor list can highlight it across sessions (#1673).
  let lastEditedGoalId = $state<number | null>(null);
  let deleteConfirm = $state<number | null>(null);

  function togglePinned(goalId: number) {
    const newPinned = new Set(pinnedGoals);
    if (newPinned.has(goalId)) {
      newPinned.delete(goalId);
    } else {
      newPinned.add(goalId);
    }
    pinnedGoals = newPinned;
    patchUserSettings({ goalsUi: { pinnedGoalIds: [...newPinned] } });
  }

  const EMOJIS = Array.from(
    new Set([
      '🔴',
      '❌',
      '⚠️',
      '📉',
      '⛔',
      '🌧️',
      '🔥',
      '💪',
      '🏃',
      '🚴',
      '🏊',
      '🏋️',
      '🤸',
      '🧘',
      '❤️',
      '💚',
      '💙',
      '💛',
      '🧠',
      '👁️',
      '👂',
      '👃',
      '💊',
      '💉',
      '🩹',
      '🩺',
      '📚',
      '📖',
      '📝',
      '✍️',
      '📓',
      '📔',
      '📕',
      '📗',
      '📘',
      '🖊️',
      '🖍️',
      '📜',
      '📋',
      '🗂️',
      '🎨',
      '🎭',
      '🎬',
      '🎤',
      '🎧',
      '🎵',
      '🎶',
      '🎸',
      '🎹',
      '🎺',
      '🎷',
      '📸',
      '🖼️',
      '🌿',
      '🍀',
      '🌱',
      '🌲',
      '🌳',
      '🌴',
      '🌵',
      '🌾',
      '🌻',
      '🌺',
      '🌸',
      '🌼',
      '🌷',
      '🌹',
      '🌎',
      '🍎',
      '🍊',
      '🍋',
      '🍌',
      '🍇',
      '🍓',
      '🥗',
      '🥙',
      '🍕',
      '🍔',
      '🍟',
      '🌮',
      '☕',
      '🍵',
      '💻',
      '📱',
      '⌚',
      '🎮',
      '🧩',
      '🪀',
      '🪁',
      '🎯',
      '🔐',
      '🔒',
      '🔓',
      '🔑',
      '⚙️',
      '🔧',
      '🔨',
      '⚒️',
      '✈️',
      '🚂',
      '🚗',
      '🚙',
      '🚕',
      '🚌',
      '🚎',
      '🏎️',
      '🚓',
      '🚑',
      '🚒',
      '🚐',
      '🛻',
      '🚚',
      '🚛',
      '🚜',
      '☀️',
      '🌤️',
      '⛅',
      '🌥️',
      '☁️',
      '🌦️',
      '🌧️',
      '⛈️',
      '🌩️',
      '🌨️',
      '❄️',
      '☃️',
      '⛄',
      '🌊',
      '💧',
      '💦',
      '😀',
      '😃',
      '😄',
      '😁',
      '😆',
      '😊',
      '☺️',
      '😉',
      '😌',
      '😚',
      '😍',
      '🤩',
      '😘',
      '🥰',
      '😏',
      '😐',
      '🥇',
      '🥈',
      '🥉',
      '🏆',
      '🎖️',
      '🏅',
      '⭐',
      '🌟',
      '✨',
      '💫',
      '🎊',
      '🎉',
      '🎁',
    ])
  );

  const TEMPORALITIES: Goal['temporality'][] = ['ONEOFF', 'DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'];
  const TEMPORALITY_LABELS: Record<string, string> = {
    ONEOFF: 'Indefinido',
    DAILY: 'Diario',
    WEEKLY: 'Semanal',
    MONTHLY: 'Mensual',
    ANNUAL: 'Anual',
  };
  const STATE_LABELS: Record<string, string> = {
    INBOX: 'Inbox',
    ACTIVE: 'Activo',
    PAUSED: 'Pausado',
    COMPLETED: 'Completado',
    FAILED: 'Fallido',
    CANCELLED: 'Cancelado',
  };
  const COLOR_PRESETS = GOALS_SPECIFIC_COLOR_PRESETS;

  // Deletion confirmation modal state
  let goalToDelete = $state<Goal | null>(null);

  // New goal form
  let newTitle = $state('');
  let newDescription = $state('');
  let newTargetValue = $state(1);
  let newTemporality = $state<Goal['temporality']>('ONEOFF');
  let newMeasurement = $state<Goal['measurement_type']>('COUNT');
  let newFailConfig = $state<Goal['fail_config']>('STATIC');
  let newFailEmoji = $state('🔴');
  let newFailIcon = $state('Activity');
  let newGoalColor = $state(DEFAULT_GOAL_COLOR);
  let newMaxAssignmentDays = $state<number | null>(null);
  let newPriority = $state(0);
  let useFailIcon = $state(false);
  // #1092 — la elección manual del usuario no se sobreescribe
  let newFailEmojiManual = $state(false);
  let newFailIconManual = $state(false);
  let newTagId = $state<number | null>(null);
  let newNoteId = $state<number | null>(null);
  let saving = $state(false);

  // #1092 — sugerencia automática de icono/emoji al escribir el título
  let suggestedFailEmoji = $derived(suggestEmoji(newTitle));
  let suggestedFailIcon = $derived(suggestIcon(newTitle));
  let hasFailSuggestion = $derived(suggestIconKey(newTitle) !== null);

  $effect(() => {
    if (!newFailEmojiManual) newFailEmoji = suggestedFailEmoji;
  });
  $effect(() => {
    if (!newFailIconManual) newFailIcon = suggestedFailIcon;
  });

  function useFailSuggestion() {
    if (useFailIcon) {
      newFailIcon = suggestedFailIcon;
      newFailIconManual = false;
    } else {
      newFailEmoji = suggestedFailEmoji;
      newFailEmojiManual = false;
    }
  }

  // Untriaged inbox captures (#1200) live in their own tab — they must not
  // leak into dashboards, planning lists or statistics.
  const isListGoal = (g: Goal) => g.state !== 'INBOX' && g.state !== 'CANCELLED';
  let planningGoals = $derived(goals.filter(isListGoal));
  let pendingGoals = $derived(goals.filter((g) => g.pending_removal));

  let historyData = $state<any[]>([]);
  $effect(() => {
    const dataMap = new Map();
    // Procesar fallidos
    for (const g of goals) {
      if (g.state === 'FAILED' && g.updated_at) {
        const date = g.updated_at.split('T')[0];
        if (!dataMap.has(date)) {
          dataMap.set(date, { date, checked: false, failed: true, failEmoji: g.fail_emoji });
        } else {
          dataMap.get(date).failed = true;
          dataMap.get(date).failEmoji = g.fail_emoji;
        }
      }
    }
    // Procesar completados (los completados se superponen y tienen prioridad sobre fallidos)
    for (const g of goals) {
      if ((g.state === 'COMPLETED' || g.is_completed) && g.completed_at) {
        const date = g.completed_at.split('T')[0];
        if (!dataMap.has(date)) {
          dataMap.set(date, { date, checked: true, failed: false, failEmoji: null });
        } else {
          dataMap.get(date).checked = true;
        }
      }
    }
    historyData = Array.from(dataMap.values());
  });

  // ── History tab state ──
  let selectedHistoryDate = $state<string | null>(localDayKey(new Date()));

  let goalsForDate = $derived.by(() => {
    if (!selectedHistoryDate) return { completed: [], failed: [] };
    const completed = goals.filter(
      (g) =>
        (g.state === 'COMPLETED' || g.is_completed) &&
        g.completed_at?.startsWith(selectedHistoryDate!)
    );
    const failed = goals.filter(
      (g) => g.state === 'FAILED' && g.updated_at?.startsWith(selectedHistoryDate!)
    );
    return { completed, failed };
  });

  function formatHistoryDate(iso: string | null): string {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    const DAYS = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
    const MONTHS = [
      'enero',
      'febrero',
      'marzo',
      'abril',
      'mayo',
      'junio',
      'julio',
      'agosto',
      'septiembre',
      'octubre',
      'noviembre',
      'diciembre',
    ];
    return `${DAYS[date.getDay()]}, ${d} de ${MONTHS[m - 1]} de ${y}`;
  }

  let loadError = $state('');

  function deduplicateGoals(arr: Goal[]): Goal[] {
    const seen = new Set<number>();
    return arr.filter((g) => {
      if (seen.has(g.id)) return false;
      seen.add(g.id);
      return true;
    });
  }

  onMount(() => {
    // Re-derive "today" on a poll + tab focus so highlights, daily lists and
    // planning buckets roll over at midnight without a reload (#1306).
    const todayTimer = setInterval(syncToday, 30_000);
    const onVisible = () => {
      if (document.visibilityState === 'visible') syncToday();
    };
    document.addEventListener('visibilitychange', onVisible);

    void (async () => {
    // Restore UI state immediately to prevent flash. All view prefs live
    // under the `joidy.goals.*` namespace (device-level, survives logout);
    // the legacy `goals.*` keys are migrated on first read (#1673).
    try {
      const savedTab = loadPref<string | null>('goals', 'tab', null, {
        legacyKey: 'goals.currentTab',
      });
      // Analytics moved to its own page (#1499) — migrate the legacy tab.
      if (savedTab === 'analytics') {
        removePref('goals', 'tab');
        void goto('/analytics', { replaceState: true });
      } else if (savedTab && (VALID_TABS as readonly string[]).includes(savedTab)) {
        currentTab = savedTab as typeof currentTab;
      }
      // Planning selection, view and cursor restore through the shared
      // planning-calendar store (#1660) — it hydrates `joidy.calendar.*`
      // with `joidy.goals.*`/legacy-key migration (#1673).
      const savedHistoryDate = loadPref<string | null>('goals', 'historyDate', null, {
        legacyKey: 'goals.selectedHistoryDate',
        isValid: (v) => typeof v === 'string' && ISO_DAY.test(v),
      });
      if (savedHistoryDate) selectedHistoryDate = savedHistoryDate;
      poolFilter = loadPref<(typeof VALID_POOL_FILTERS)[number]>('goals', 'poolFilter', poolFilter, {
        isValid: (v) => (VALID_POOL_FILTERS as readonly string[]).includes(v as string),
      });
      poolOpen = loadPref<boolean>('goals', 'poolOpen', poolOpen, {
        isValid: (v) => typeof v === 'boolean',
      });
      lastEditedGoalId = loadPref<number | null>('goals', 'editorGoalId', null, {
        isValid: (v) => v === null || typeof v === 'number',
      });
      // if we are on planning, pre-load assignments for the selected date
      if (currentTab === 'planning') {
        loadAssignmentsForDate(selDay).catch(logger.error);
      }
    } catch (e) {
      // ignore storage errors
    }

    const cachedGoals = getCachedData<Goal[]>('goals');
    const cachedTags = getCachedData<TagType[]>('tags');
    if (cachedGoals) goals = deduplicateGoals(cachedGoals);
    if (cachedTags) tags = cachedTags;

    // Restore persisted UI state (pins, editor filter and search) from localStorage
    try {
      const saved = loadUserSettings().goalsUi;
      if (saved?.pinnedGoalIds && Array.isArray(saved.pinnedGoalIds)) {
        pinnedGoals = new Set(saved.pinnedGoalIds);
      }
      // Editor filters are device-level view prefs (#1673) — the legacy
      // goalsUi blob value is the fallback while the pref is unmigrated.
      const legacyFilter =
        saved &&
        (saved.editorFilter === null ||
          (typeof saved.editorFilter === 'string' &&
            (VALID_EDITOR_FILTERS as readonly string[]).includes(saved.editorFilter)))
          ? saved.editorFilter
          : undefined;
      goalFilterState = loadPref<string | null>(
        'goals',
        'editorFilter',
        legacyFilter ?? goalFilterState,
        {
          isValid: (v) =>
            v === null ||
            (typeof v === 'string' && (VALID_EDITOR_FILTERS as readonly string[]).includes(v)),
        }
      );
      if (typeof saved?.editorSearch === 'string') {
        goalSearchQuery = saved.editorSearch;
      }
      const legacyContext =
        saved &&
        (saved.editorContextFilter === null ||
          saved.editorContextFilter === 'ANY' ||
          saved.editorContextFilter === 'MORNING' ||
          saved.editorContextFilter === 'NIGHT')
          ? saved.editorContextFilter
          : undefined;
      goalContextFilter = loadPref<GoalContext | null>(
        'goals',
        'editorContextFilter',
        legacyContext ?? goalContextFilter,
        {
          isValid: (v) => v === null || v === 'ANY' || v === 'MORNING' || v === 'NIGHT',
        }
      );
    } catch {
      // ignore storage errors
    }

    try {
      // Load essential data immediately (goals + tags + notes). Notes are
      // needed by the linked-note chip, NoteLinkPicker and the auto-track
      // select on every tab — previously they only loaded under the
      // analytics tab, leaving those controls silently empty (#1305).
      const [fetchedGoals, fetchedTags, fetchedNotes] = await Promise.all([
        api.goals.list(),
        api.tags.list(),
        api.notes.list(),
      ]);
      goals = deduplicateGoals(fetchedGoals);
      tags = fetchedTags;
      notes = fetchedNotes;
      setCachedData('goals', goals);
      setCachedData('tags', tags);
    } catch (e) {
      if (goals.length === 0) {
        loadError = 'No se pudo cargar los objetivos.';
        logger.error('[goals] onMount failed:', e);
      }
    }

    })();

    return () => {
      clearInterval(todayTimer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  });

  let addError = $state('');

  async function addGoal() {
    if (!newTitle.trim()) return;
    saving = true;
    addError = '';
    try {
      const g = await api.goals.create({
        title: newTitle.trim(),
        description: '',
        target_value: newTargetValue,
        temporality: newTemporality,
        measurement_type: newMeasurement,
        fail_config: newFailConfig,
        fail_emoji: useFailIcon ? newFailIcon : newFailEmoji,
        color: newGoalColor,
        tag_id: newTagId,
        note_id: newNoteId,
        max_assignment_days: newMaxAssignmentDays,
        priority: newPriority,
      });
      goals = [g, ...goals];
      showAddForm = false;
      newTitle = '';
      // #1092 — reactivar la sugerencia para el próximo objetivo
      newFailEmojiManual = false;
      newFailIconManual = false;
      newTargetValue = 1;
      newTagId = null;
      newNoteId = null;
      newMaxAssignmentDays = null;
      newPriority = 0;
      // #1142 — permanecer en la vista general; el objetivo ya aparece en la lista
    } catch (e) {
      addError = 'Error al crear el objetivo.';
    } finally {
      saving = false;
    }
  }

  // #1141 — crear una nota nueva desde el picker y enlazarla al objetivo.
  async function createNoteAndLink(title: string) {
    try {
      const n = await api.notes.create({
        title,
        content: `# ${title}\n`,
        tags: [],
      });
      notes = [n, ...notes];
      newNoteId = n.id;
    } catch (e) {
      logger.error('[goals] createNoteAndLink failed:', e);
      addError = 'Error al crear la nota.';
    }
  }

  async function completeGoal(id: number) {
    const result = await api.goals.complete(id);
    goals = goals.map((g) => (g.id === id ? result.goal : g));
    applyGamificationResult(result.gamification);
    showXPGain(result.gamification.xp_awarded);
  }

  async function failGoal(id: number) {
    const target = goals.find((g) => g.id === id);
    if (target && target.state === 'FAILED') {
      return updateGoalState(id, 'ACTIVE');
    }
    try {
      const result = await api.goals.fail(id);
      goals = goals.map((g) => (g.id === id ? result : g));
    } catch (e) {
      logger.error('Error al marcar como fallido:', e);
    }
  }

  async function updateGoalState(id: number, state: 'ACTIVE' | 'PAUSED' | 'CANCELLED') {
    try {
      const result = await api.goals.update(id, { state });
      goals = goals.map((g) => (g.id === id ? result : g));
    } catch (e) {
      logger.error('Error al actualizar estado:', e);
    }
  }

  function confirmDeleteGoal(goal: Goal) {
    goalToDelete = goal;
  }

  async function handleConfirmDeleteGoal() {
    if (!goalToDelete) return;
    try {
      await api.goals.delete(goalToDelete.id);
      goals = goals.filter((g) => g.id !== goalToDelete!.id);
      goalToDelete = null;
    } catch (e) {
      logger.error('Error al eliminar objetivo:', e);
    }
  }

  async function deleteGoal(id: number) {
    if (deleteConfirm !== id) {
      deleteConfirm = id;
      return;
    }
    await api.goals.delete(id);
    goals = goals.filter((g) => g.id !== id);
    deleteConfirm = null;
  }

  function formatFailConfig(config: string) {
    if (config === 'STATIC') return 'Estático';
    if (config === 'ROLLOVER') return 'Traspaso';
    if (config === 'SNOWBALL') return 'Acumulativo';
    return config;
  }

  async function updateGoalTemporality(id: number, temporality: Goal['temporality']) {
    try {
      const result = await api.goals.update(id, { temporality });
      goals = goals.map((g) => (g.id === id ? result : g));
    } catch (e) {
      logger.error('Error al actualizar temporalidad:', e);
    }
  }

  // ── Hierarchical planning helpers ──
  function getParentGoals(goalList: Goal[]) {
    return goalList.filter((g) => !g.parent_id || !goalList.some((p) => p.id === g.parent_id));
  }
  function getChildGoals(parentId: number, goalList: Goal[]) {
    return goalList.filter((g) => g.parent_id === parentId);
  }

  // Planning assignment state (frontend-only mapping date -> goal ids).
  // `todayIso` is $state — `syncToday()` bumps it across midnight so every
  // derived "today" highlight/list refreshes without a reload (#1306).
  let todayIso = $state(localDayKey(new Date()));

  function syncToday(): void {
    const next = localDayKey(new Date());
    if (next === todayIso) return;
    const prev = todayIso;
    todayIso = next;
    // Selections pinned to "today" follow the rollover; explicit picks stay.
    if (selectedHistoryDate === prev) selectedHistoryDate = next;
    if ($planningSelectedDay === prev) selectPlanningDay(next);
  }

  // Planning selection + assignments live in the shared planning-calendar
  // store (#1660). `selDay` resolves a concrete day for this surface (the
  // shared selection is nullable — /calendar unselects on re-click).
  let selDay = $derived($planningSelectedDay ?? todayIso);
  // Read aliases for the agenda rail / day detail; writes go through the
  // store actions (assignGoal/unassignGoal/refreshAssignmentsForDate), which
  // also repost goal_event_ids so event-source links survive (#1645).
  let assignments = $derived($planningAssignments);
  let assignmentEventSources = $derived($planningEventSources);

  let poolFilter = $state<'recent' | 'active' | 'completed' | 'failed'>('recent');

  let filteredUnassignedGoals = $derived.by(() => {
    let unassigned = goals.filter((g) => isListGoal(g) && !isAssigned(g.id, selDay));
    if (poolFilter === 'active') {
      unassigned = unassigned.filter((g) => g.state === 'ACTIVE');
    } else if (poolFilter === 'completed') {
      unassigned = unassigned.filter((g) => g.state === 'COMPLETED' || g.is_completed);
    } else if (poolFilter === 'failed') {
      unassigned = unassigned.filter((g) => g.state === 'FAILED');
    }
    unassigned.sort((a, b) => b.id - a.id);
    return unassigned;
  });

  function getGoalStatusOnDate(goal: Goal, dateStr: string): 'COMPLETED' | 'FAILED' | 'PENDING' {
    const normDate = getNormalizedDate(dateStr, goal.temporality);

    if (goal.completed_at) {
      const compDate = getNormalizedDate(goal.completed_at.split('T')[0], goal.temporality);
      if (compDate === normDate) return 'COMPLETED';
    }

    if (goal.state === 'FAILED' && goal.updated_at) {
      const failDate = getNormalizedDate(goal.updated_at.split('T')[0], goal.temporality);
      if (failDate === normDate) return 'FAILED';
    }

    return 'PENDING';
  }

  function isAssigned(goalId: number, date: string) {
    const goal = goals.find((g) => g.id === goalId);
    if (!goal) return false;
    const normDate = getNormalizedDate(date, goal.temporality);
    return (
      $planningAssignments[normDate] && $planningAssignments[normDate].includes(goalId)
    );
  }

  // persist current tab and selected planning date in localStorage
  $effect(() => {
    savePref('goals', 'tab', currentTab);
  });

  $effect(() => {
    // The store already persists the selection to `joidy.calendar.selectedDay`
    // (#1660/#1673) — this page just keeps the assignment buckets warm.
    if ($planningSelectedDay) {
      loadAssignmentsForDate($planningSelectedDay);
    }
    // Preload upcoming assignments for dashboard
    const today = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      loadAssignmentsForDate(localDayKey(d));
    }
  });

  $effect(() => {
    if (selectedHistoryDate) {
      savePref('goals', 'historyDate', selectedHistoryDate);
    }
  });

  // Editor filters are device-level view prefs (#1673); the search text is
  // user-scoped and stays in userSettings (debounced below — a localStorage
  // write per keystroke otherwise).
  $effect(() => {
    savePref('goals', 'editorFilter', goalFilterState);
    savePref('goals', 'editorContextFilter', goalContextFilter);
  });

  // Planning pool + cursor prefs (#1673).
  $effect(() => {
    savePref('goals', 'poolFilter', poolFilter);
  });
  $effect(() => {
    savePref('goals', 'poolOpen', poolOpen);
  });
  // planningCursor/view/selectedDay persist through the shared store
  // (`joidy.calendar.*`, #1660/#1673); assignments always mirror to the
  // calendar so there is no mirrorToCalendar pref anymore.

  // Deep-link support: /goals?tab=inbox (used by Quick Capture toasts, #1200)
  // and /goals?tab=planning&date=YYYY-MM-DD (used by the /calendar quick-nav,
  // #1668). The params are consumed once so manual navigation isn't overridden.
  $effect(() => {
    const tabParam = page.url.searchParams.get('tab');
    const dateParam = page.url.searchParams.get('date');
    if (tabParam === 'analytics') {
      void goto(resolve('/analytics'), { replaceState: true });
      return;
    }
    let handled = false;
    if (tabParam && (VALID_TABS as readonly string[]).includes(tabParam)) {
      currentTab = tabParam as typeof currentTab;
      handled = true;
    }
    if (dateParam && /^\d{4}-\d{2}-\d{2}$/.test(dateParam)) {
      selectPlanningDay(dateParam);
      handled = true;
    }
    if (handled) {
      const clean = new URL(page.url.href);
      clean.searchParams.delete('tab');
      clean.searchParams.delete('date');
      // eslint-disable-next-line svelte/no-navigation-without-resolve -- page.url.pathname already includes the base path; resolve() would prepend it twice
      replaceState(`${clean.pathname}${clean.search}${clean.hash}`, page.state);
    }
  });

  $effect(() => {
    const query = goalSearchQuery;
    const timer = setTimeout(() => {
      patchUserSettings({ goalsUi: { editorSearch: query } });
    }, 300);
    return () => clearTimeout(timer);
  });

  async function assignGoalToDate(goalId: number, date: string) {
    if (!date) return;
    const goal = goals.find((g) => g.id === goalId);
    if (!goal) return;
    // The store mirrors into calendar_tasks by default and reposts sibling
    // goal_event_ids (#goal-planning-calendar/#1645); refresh the agenda
    // rail so the mirrored task shows up.
    await assignGoal(goal, date);
    void loadRangeAgenda();
  }

  async function unassignGoalFromDate(goalId: number, date: string) {
    if (!date) return;
    const goal = goals.find((g) => g.id === goalId);
    if (!goal) return;
    await unassignGoal(goal, date);
    void loadRangeAgenda();
  }

  // ── Planning v2 — shared calendar component + store (#1660) ──
  // The grid lives in lib/components/calendar/PlanningCalendar.svelte; the
  // goals surface keeps its own toolbar, goal pool and day-detail aside.
  let poolOpen = $state(true);
  let dragGoalId = $state<number | null>(null);

  // 'agenda' is a /calendar-only view — coerce back to the month grid here.
  let plnView = $derived<'month' | 'week'>($planningView === 'agenda' ? 'month' : $planningView);

  let planningPeriodLabel = $derived.by(() => {
    if (plnView === 'month') {
      const d = new Date($planningCursor + 'T12:00:00');
      const label = d.toLocaleDateString($locale, { month: 'long', year: 'numeric' });
      return label.charAt(0).toUpperCase() + label.slice(1);
    }
    const days = weekDaysFor($planningCursor);
    const first = new Date(days[0] + 'T12:00:00');
    const last = new Date(days[6] + 'T12:00:00');
    return `${first.toLocaleDateString($locale, { day: 'numeric', month: 'short' })} – ${last.toLocaleDateString($locale, { day: 'numeric', month: 'short', year: 'numeric' })}`;
  });

  // Union of every day iso currently visible across the three grid modes —
  // bounds the assignment prefetch and the tasks-layer fetch.
  let planningVisibleDays = $derived.by(() => {
    const days = new Set<string>();
    for (const c of monthCellsFor($planningCursor)) days.add(c.iso);
    for (const d of weekDaysFor($planningCursor)) days.add(d);
    for (const d of agendaDaysFor($planningCursor)) days.add(d);
    // Preload the upcoming week so the editor rail agenda never waits.
    const today = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      days.add(localDayKey(d));
    }
    return [...days].sort();
  });

  $effect(() => {
    if (currentTab !== 'planning') return;
    loadAssignmentsForRange(planningVisibleDays).catch(logger.error);
  });

  // ── Real-calendar agenda for the visible planning range (read-only) ──
  // Events + tasks are fetched once for the whole visible range and bucketed
  // per day, so every day cell can show real titles and colors (#1645/#1668).
  // Nothing here mutates — clicks open a detail modal; editing stays in
  // /calendar.
  let rangeTasks = $state<CalendarTask[]>([]);
  let rangeEvents = $state<CalendarEvent[]>([]);
  let agendaLoading = $state(false);
  let agendaDetail = $state<
    { kind: 'event'; event: CalendarEvent } | { kind: 'task'; task: CalendarTask } | null
  >(null);
  // Google event → quick goal creation (#goal-from-event)
  let goalFromEventSeed = $state<GoalEventSeed | null>(null);

  type PlanningAgendaEntry =
    | { kind: 'event'; sort: string; event: CalendarEvent }
    | { kind: 'task'; sort: string; task: CalendarTask };

  const AGENDA_PRIORITY_COLORS: Record<string, string> = {
    LOW: 'var(--text-muted)',
    MEDIUM: 'var(--link)',
    HIGH: 'var(--warning, #d9a13b)',
    URGENT: 'var(--error)',
  };
  const RECURRENCE_LABEL_KEYS: Record<string, string> = {
    NONE: 'calendar.recurrenceNone',
    DAILY: 'calendar.recurrenceDaily',
    WEEKLY: 'calendar.recurrenceWeekly',
    MONTHLY: 'calendar.recurrenceMonthly',
  };
  const REMINDER_LABEL_KEYS: Record<number, string> = {
    5: 'calendar.reminderMin5',
    15: 'calendar.reminderMin15',
    30: 'calendar.reminderMin30',
    60: 'calendar.reminderMin60',
  };

  function eventDayKey(ev: CalendarEvent): string {
    // All-day events are cached as UTC midnight — bucket by the raw date
    // prefix so they don't shift to the previous local day (same rule as
    // the /calendar page).
    if (ev.all_day) return ev.start_at.slice(0, 10);
    return localDayKey(new Date(ev.start_at));
  }

  function eventTimeLabel(ev: CalendarEvent): string {
    if (ev.all_day) return $t('calendar.allDay');
    const start = new Date(ev.start_at);
    if (!ev.end_at) return start.toLocaleTimeString($locale, { hour: '2-digit', minute: '2-digit' });
    const end = new Date(ev.end_at);
    return `${start.toLocaleTimeString($locale, { hour: '2-digit', minute: '2-digit' })} – ${end.toLocaleTimeString($locale, { hour: '2-digit', minute: '2-digit' })}`;
  }

  function taskTimeLabel(task: CalendarTask): string {
    if (!task.start_time) return '·';
    const start = task.start_time.slice(0, 5);
    return task.end_time ? `${start} – ${task.end_time.slice(0, 5)}` : start;
  }

  function reminderLabel(minutes: number | null): string {
    if (minutes === null) return '—';
    const key = REMINDER_LABEL_KEYS[minutes];
    return key ? $t(key) : `${minutes} min`;
  }

  async function loadRangeAgenda(): Promise<void> {
    const dates = planningVisibleDays;
    if (dates.length === 0) return;
    agendaLoading = true;
    const first = dates[0];
    const last = dates[dates.length - 1];
    // Pad both bounds a day: all-day events are cached at UTC midnight,
    // which lands on the adjacent local day in offset zones — the exact
    // day is filtered client-side by eventDayKey (same rule as /calendar).
    const start = new Date(`${first}T00:00:00`);
    start.setDate(start.getDate() - 1);
    const end = new Date(`${last}T23:59:59.999`);
    end.setDate(end.getDate() + 1);
    try {
      const [evts, taskRows] = await Promise.all([
        api.google.calendarEvents({
          start: start.toISOString(),
          end: end.toISOString(),
        }),
        api.calendarTasks.list({ start: first, end: last }),
      ]);
      rangeEvents = evts;
      rangeTasks = taskRows;
    } catch (e) {
      logger.error('Error loading planning agenda:', e);
    } finally {
      agendaLoading = false;
    }
  }

  // True when `task` is the auto-created calendar mirror of a goal assigned
  // on its own anchor date — the goal chip already represents it, so the
  // agenda must not render the same item twice. A mirror the user moved to
  // a non-anchor date keeps showing as a regular task.
  function isMirrorOfAssignedGoal(task: CalendarTask): boolean {
    if (task.goal_id === null || !task.date) return false;
    return PLAN_TEMPS.some((temp) => {
      const anchor = getNormalizedDate(task.date as string, temp);
      return anchor === task.date && (assignments[anchor] || []).includes(task.goal_id as number);
    });
  }

  // Merged, time-sorted read-only agenda bucketed by day. Tasks that mirror
  // a Google event (google_event_id) suppress the cached Google copy so each
  // item appears once — same dedup rule as /calendar. Events that seeded a
  // goal-from-event assignment are likewise represented by the goal chip.
  let agendaByDay = $derived.by(() => {
    const byDay = new Map<string, PlanningAgendaEntry[]>();
    const mirroredGoogleIds = new Set(
      rangeTasks.map((t) => t.google_event_id).filter((id): id is string => id !== null)
    );
    const sourcedEventIds = new Set(
      Object.values(assignmentEventSources).flatMap((m) => Object.values(m))
    );
    const push = (key: string, item: PlanningAgendaEntry) => {
      const list = byDay.get(key) ?? [];
      list.push(item);
      byDay.set(key, list);
    };
    for (const ev of rangeEvents) {
      if (mirroredGoogleIds.has(ev.google_id)) continue;
      if (sourcedEventIds.has(ev.google_id)) continue;
      push(eventDayKey(ev), {
        kind: 'event',
        sort: ev.all_day ? '00:00' : ev.start_at.slice(11, 16),
        event: ev,
      });
    }
    for (const task of rangeTasks) {
      if (!task.date) continue;
      if (isMirrorOfAssignedGoal(task)) continue;
      push(task.date, { kind: 'task', sort: task.start_time?.slice(0, 5) ?? '99:99', task });
    }
    for (const list of byDay.values()) {
      list.sort((a, b) => {
        if (a.sort !== b.sort) return a.sort.localeCompare(b.sort);
        const al = a.kind === 'event' ? (a.event.summary ?? '') : a.task.title;
        const bl = b.kind === 'event' ? (b.event.summary ?? '') : b.task.title;
        return al.localeCompare(bl);
      });
    }
    return byDay;
  });

  // Selected-day agenda for the detail rail.
  let dayAgendaItems = $derived.by(() => agendaByDay.get(selDay) ?? []);

  function agendaEntryColor(item: PlanningAgendaEntry): string {
    if (item.kind === 'event') return item.event.color ?? 'var(--text-muted)';
    return item.task.color ?? AGENDA_PRIORITY_COLORS[item.task.priority] ?? 'var(--text-muted)';
  }

  function agendaEntryTitle(item: PlanningAgendaEntry): string {
    return item.kind === 'event' ? item.event.summary || '—' : item.task.title;
  }

  function agendaEntryTime(item: PlanningAgendaEntry): string {
    return item.kind === 'event' ? eventTimeLabel(item.event) : taskTimeLabel(item.task);
  }

  function openAgendaDetail(item: PlanningAgendaEntry): void {
    agendaDetail =
      item.kind === 'event' ? { kind: 'event', event: item.event } : { kind: 'task', task: item.task };
  }

  $effect(() => {
    if (currentTab !== 'planning') return;
    // Anchor read keeps this effect subscribed to the visible range
    // (view switch, month/week navigation) so the agenda refetches.
    const anchor = planningVisibleDays[0];
    if (!anchor) return;
    loadRangeAgenda().catch(logger.error);
  });

  // Quick-nav to /calendar on the selected planning day (#1668). The date is
  // carried in the query param; the calendar consumes it on mount.
  function openPlanningInCalendar() {
    void goto(resolve(`/calendar?date=${selDay}`));
  }

  // Streaks layer: lazy — personal streaks only load when the layer is on.
  let planningStreaks = $state<PersonalStreak[]>([]);
  let streaksFetched = $state(false);
  $effect(() => {
    if (currentTab !== 'planning' || !$calendarLayers.streaks || streaksFetched) return;
    streaksFetched = true;
    api.personalStreaks
      .list()
      .then((list) => (planningStreaks = list))
      .catch((e) => {
        streaksFetched = false;
        logger.error('[goals] streaks fetch failed:', e);
      });
  });

  // Notes layer: badge counting notes created on each day — the notes list is
  // already loaded for the linked-note controls, no extra fetch needed.
  let notesCountByDay = $derived.by(() => {
    const byDay = new Map<string, number>();
    for (const note of notes) {
      const key = note.created_at.slice(0, 10);
      byDay.set(key, (byDay.get(key) ?? 0) + 1);
    }
    return byDay;
  });

  // Unified day chips: planning-assignment goal chips + real-agenda chips
  // (Google events, calendar tasks). agendaByDay already dedupes: a task
  // mirrored from an assignment and an event that seeded a goal render as
  // the goal chip only (#1234, #1645, #1660). Layer toggles gate events
  // (google) and tasks independently.
  function planningChipsForDay(iso: string): CalendarDayChip[] {
    const layers = $calendarLayers;
    const assigned = layers.planning ? assignedIdsForDate($planningAssignments, iso) : [];
    const chips: CalendarDayChip[] = [];

    for (const item of agendaByDay.get(iso) ?? []) {
      if (item.kind === 'event') {
        if (!layers.google) continue;
        chips.push({
          key: `ev-${item.event.google_id}`,
          kind: 'google',
          label: item.event.summary || '—',
          time: item.event.all_day ? null : item.event.start_at.slice(11, 16),
          allDay: item.event.all_day,
          locked: true,
          color: item.event.color ?? undefined,
          title: item.event.location
            ? `${item.event.summary} · ${item.event.location}`
            : item.event.summary || '—',
          payload: item,
        });
      } else {
        if (!layers.tasks) continue;
        chips.push({
          key: `ct-${item.task.id}`,
          kind: 'task',
          label: item.task.title,
          time: item.task.start_time ? item.task.start_time.slice(0, 5) : null,
          priority: item.task.priority,
          done: item.task.done,
          recurring: item.task.recurrence !== 'NONE',
          color: item.task.color ?? undefined,
          title: item.task.goal_title
            ? `${item.task.title} · ${item.task.goal_title}`
            : item.task.title,
          payload: item,
        });
      }
    }

    for (const id of assigned) {
      const g = goals.find((x) => x.id === id);
      if (!g) continue;
      const status = getGoalStatusOnDate(g, iso);
      chips.push({
        key: `g-${id}-${iso}`,
        kind: 'goal',
        label: g.title,
        color:
          status === 'FAILED'
            ? 'var(--error)'
            : status === 'COMPLETED'
              ? 'var(--success)'
              : getGoalColor(g),
        done: status === 'COMPLETED',
        removable: true,
        meta: TEMPORALITY_LABELS[g.temporality] || g.temporality,
        title: g.title,
        payload: g,
      });
    }

    chips.sort((a, b) => (a.time ?? '99:99').localeCompare(b.time ?? '99:99'));
    return chips;
  }

  function planningBadgesForDay(iso: string): CalendarDayBadge[] {
    const layers = $calendarLayers;
    const badges: CalendarDayBadge[] = [];
    if (layers.streaks) {
      for (const streak of planningStreaks) {
        if (streak.is_archived) continue;
        const entry = streak.history?.find((h) => h.date === iso);
        badges.push({
          key: `s-${streak.id}`,
          kind: 'streak',
          icon: streak.icon || streak.emoji,
          color: streak.color || 'var(--xp)',
          checked: entry?.checked ?? false,
          title: streak.name,
        });
      }
    }
    if (layers.notes) {
      const count = notesCountByDay.get(iso) ?? 0;
      if (count > 0) {
        badges.push({
          key: 'notes',
          kind: 'note',
          count,
          title: $t('calendar.layer.notes'),
        });
      }
    }
    return badges;
  }

  function onPoolDragStart(e: DragEvent, goalId: number) {
    dragGoalId = goalId;
    e.dataTransfer?.setData('text/plain', String(goalId));
    if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy';
  }

  function onCellDrop(e: DragEvent, iso: string) {
    e.preventDefault();
    const id = Number(e.dataTransfer?.getData('text/plain')) || dragGoalId;
    if (id) assignGoalToDate(id, iso);
    dragGoalId = null;
  }

  function onPlanningChipClick(chip: CalendarDayChip) {
    if (chip.kind === 'goal' && chip.payload) {
      openGoalEditor(chip.payload as Goal);
    } else if ((chip.kind === 'google' || chip.kind === 'task') && chip.payload) {
      // Real-calendar entries open the read-only agenda detail (#1645).
      openAgendaDetail(chip.payload as PlanningAgendaEntry);
    }
  }

  function onPlanningChipRemove(chip: CalendarDayChip, iso: string) {
    if (chip.kind === 'goal' && chip.payload) {
      unassignGoalFromDate((chip.payload as Goal).id, iso);
    }
  }

  // ── Modal de Consistencia (pending removal resolver) ──
  async function resolveRemoval(goalId: number, action: 'delete' | 'manual' | 'cancel') {
    try {
      const result = await api.goals.resolveRemoval(goalId, action);
      if (action === 'delete' || ('status' in result && result.status === 'deleted')) {
        goals = goals.filter((g) => g.id !== goalId);
      } else {
        goals = goals.map((g) => (g.id === goalId ? (result as Goal) : g));
      }
    } catch (e) {
      logger.error('Error al resolver objetivo huérfano:', e);
    }
  }

  function openGoalEditor(goal: Goal) {
    // Track the selection so the editor list can re-highlight it after a
    // reload (#1673). The [id] page also records it for direct URL loads.
    lastEditedGoalId = goal.id;
    savePref('goals', 'editorGoalId', goal.id);
    goto(`/goals/${goal.id}`);
  }

  // Shared toggle for every "Nuevo Objetivo" entry point (editor toolbar,
  // today header, empty state). Re-enables the fail icon/emoji suggestion
  // each time the form opens (#1092).
  function toggleNewGoalForm() {
    if (!showAddForm) {
      newFailEmojiManual = false;
      newFailIconManual = false;
    }
    showAddForm = !showAddForm;
  }

  // KPI rail stats for the editor tab — derived from the already-loaded goals
  // list; "today" reuses the planning assignments map (today + next 6 days
  // are prefetched on mount).
  let editorRailStats = $derived.by(() => {
    const managed = goals.filter(isListGoal);
    const todayAssigned = managed.filter((g) => isAssigned(g.id, todayIso));
    return {
      active: managed.filter((g) => g.state === 'ACTIVE').length,
      completed: managed.filter((g) => g.state === 'COMPLETED' || g.is_completed).length,
      paused: managed.filter((g) => g.state === 'PAUSED').length,
      todayTotal: todayAssigned.length,
      todayDone: todayAssigned.filter(
        (g) => getGoalStatusOnDate(g, todayIso) === 'COMPLETED'
      ).length,
      total: managed.length,
    };
  });

  // 7-day agenda for the editor rail column — reuses the same normalized
  // assignment keys the planning calendar prefetches.
  let upcomingWeek = $derived.by(() => {
    const managed = goals.filter(isListGoal);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(todayIso + 'T12:00:00');
      d.setDate(d.getDate() + i);
      const iso = localDayKey(d);
      const entries = assignedIdsForDate($planningAssignments, iso)
        .map((id) => managed.find((g) => g.id === id))
        .filter((g): g is Goal => Boolean(g))
        .map((goal) => ({ goal, status: getGoalStatusOnDate(goal, iso) }));
      return { iso, entries };
    });
  });

  function jumpToPlanning(iso: string) {
    jumpToPlanningDay(iso);
    currentTab = 'planning';
  }

  function getGoalColor(goal: Goal): string {
    // Semantic states win over custom colors so terminal readouts never mix
    // palettes: completed = green, failed/abandoned = red (#1506).
    if (goal.state === 'COMPLETED' || goal.is_completed) {
      return 'var(--target)';
    }
    if (goal.state === 'FAILED' || goal.state === 'CANCELLED') {
      return 'var(--error)';
    }
    if (goal.color) {
      return goal.color;
    }
    const colorMap: Record<string, string> = {
      DAILY: 'var(--today)',
      WEEKLY: TEMPORALITY_COLORS['WEEKLY'],
      MONTHLY: 'var(--link)',
      ANNUAL: TEMPORALITY_COLORS['ANNUAL'],
      ONEOFF: TEMPORALITY_COLORS['ONEOFF'],
      ACTIVE: 'var(--today)',
      PAUSED: 'var(--error)',
    };

    if (goal.state === 'ACTIVE' || goal.state === 'PAUSED') {
      return colorMap[goal.state] || 'var(--border)';
    }
    if (goal.temporality) {
      return colorMap[goal.temporality];
    }
    return 'var(--border)';
  }
</script>

<!-- Escape for showAddForm is handled by the focusTrap on its panel so a
     stacked dialog above it closes first. -->
<svelte:window
  onkeydown={(e) => {
    if (e.key === 'Escape' && deleteConfirm !== null) {
      deleteConfirm = null;
    }
  }}
/>

<div class="goals-page">
  {#if loadError}
    <div class="error-banner">{loadError}</div>
  {/if}


  <div
    class="goals-body framed"
    class:full-width={currentTab === 'history' ||
      currentTab === 'planning' ||
      currentTab === 'inbox' ||
      currentTab === 'editor'}
  >
    {#if currentTab === 'inbox'}
      <div class="tab-content fade-in">
        <GoalInbox bind:goals onOpen={openGoalEditor} {getGoalColor} />
      </div>
    {/if}
    {#if currentTab === 'planning'}
      <div class="tab-content fade-in pln">
        <div class="pln-toolbar">
          <button
            class="pln-pool-toggle"
            class:active={poolOpen}
            onclick={() => (poolOpen = !poolOpen)}
            title={$t('goalsPage.togglePool')}
            aria-label={$t('goalsPage.togglePool')}
            aria-pressed={poolOpen}
          >
            <List size={14} />
            {$t('goalsPage.poolTitle')}
            <span class="pln-pool-count">{filteredUnassignedGoals.length}</span>
          </button>

          <div class="pln-center">
            <div class="pln-nav">
              <button
                class="pln-nav-btn"
                onclick={() => shiftPlanningPeriod(-1)}
                title={$t('goalsPage.prevPeriod')}
                aria-label={$t('goalsPage.prevPeriod')}><ChevronLeft size={15} /></button
              >
              <span class="pln-period">{planningPeriodLabel}</span>
              <button
                class="pln-nav-btn"
                onclick={() => shiftPlanningPeriod(1)}
                title={$t('goalsPage.nextPeriod')}
                aria-label={$t('goalsPage.nextPeriod')}><ChevronRight size={15} /></button
              >
              <button class="pln-today-btn" onclick={goPlanningToday}
                >{$t('goalsPage.todayBtn')}</button
              >
            </div>
          </div>

          <div class="pln-right">
            <CalendarLayerToggles layers={['planning', 'google', 'tasks', 'streaks', 'notes']} />

            <div class="pln-view-toggle" role="group" aria-label={$t('goalsPage.calendar')}>
              <button
                class:active={plnView === 'month'}
                aria-pressed={plnView === 'month'}
                onclick={() => setPlanningView('month')}>{$t('goalsPage.viewMonth')}</button
              >
              <button
                class:active={plnView === 'week'}
                aria-pressed={plnView === 'week'}
                onclick={() => setPlanningView('week')}>{$t('goalsPage.viewWeek')}</button
              >
            </div>

            <button
              class="pln-nav-btn"
              onclick={openPlanningInCalendar}
              title={$t('goalsPage.openInCalendar')}
              aria-label={$t('goalsPage.openInCalendar')}
            >
              <CalendarDays size={15} />
            </button>
          </div>
        </div>

        <div class="pln-main">
          {#if poolOpen}
            <aside class="pln-pool">
              <div class="pln-pool-head">
                <div class="pln-pool-filter" role="group" aria-label={$t('goalsPage.sortBy')}>
                  <button
                    class:active={poolFilter === 'recent'}
                    aria-pressed={poolFilter === 'recent'}
                    onclick={() => (poolFilter = 'recent')}>{$t('goalsPage.poolRecent')}</button
                  >
                  <button
                    class:active={poolFilter === 'active'}
                    aria-pressed={poolFilter === 'active'}
                    onclick={() => (poolFilter = 'active')}>{$t('goalsPage.poolActive')}</button
                  >
                  <button
                    class:active={poolFilter === 'completed'}
                    aria-pressed={poolFilter === 'completed'}
                    onclick={() => (poolFilter = 'completed')}>{$t('goalsPage.poolCompleted')}</button
                  >
                  <button
                    class:active={poolFilter === 'failed'}
                    aria-pressed={poolFilter === 'failed'}
                    onclick={() => (poolFilter = 'failed')}>{$t('goalsPage.poolFailed')}</button
                  >
                </div>
              </div>
              <div class="pln-pool-list">
                {#each filteredUnassignedGoals as goal (goal.id)}
                  <button
                    class="pln-pool-item"
                    style="border-left: 3px solid {getGoalColor(goal)}"
                    draggable="true"
                    ondragstart={(e) => onPoolDragStart(e, goal.id)}
                    onclick={() => assignGoalToDate(goal.id, selDay)}
                    title={$t('goalsPage.assignToDay')}
                  >
                    {#if goal.fail_emoji}
                      <span class="pln-item-icon">
                        <StreakIcon name={goal.fail_emoji} size={14} color={getGoalColor(goal)} />
                      </span>
                    {/if}
                    <span class="pln-item-title pln-mq" use:marquee>
                      <span class="pln-mq-track">
                        <span class="pln-mq-text">{goal.title}</span>
                        <span class="pln-mq-text pln-mq-dup" aria-hidden="true">{goal.title}</span>
                      </span>
                    </span>
                    {#if goal.temporality !== 'ONEOFF'}
                      <span class="pln-item-temp" style="color: {getGoalColor(goal)}"
                        >{TEMPORALITY_LABELS[goal.temporality] || goal.temporality}</span
                      >
                    {/if}
                  </button>
                {:else}
                  <div class="pln-pool-empty caption">{$t('goalsPage.unassignedEmpty')}</div>
                {/each}
              </div>
            </aside>
          {/if}

          <div class="pln-cal-wrap">
            <PlanningCalendar
              view={plnView}
              cursor={$planningCursor}
              {todayIso}
              selectedDay={$planningSelectedDay}
              chipsForDay={planningChipsForDay}
              badgesForDay={planningBadgesForDay}
              maxChips={CHIP_DENSITY_LIMITS[$chipDensity]}
              onselectday={(iso) => jumpToPlanningDay(iso)}
              onchipclick={onPlanningChipClick}
              onchipremove={onPlanningChipRemove}
              oncelldragover={(e) => e.preventDefault()}
              oncelldrop={onCellDrop}
            />
          </div>

          <aside class="pln-detail">
            <div class="history-detail-header">
              <div class="history-detail-date" style="text-transform:none;">
                {$t('goalsPage.assignedOn', {
                  values: {
                    date: new Date(selDay + 'T12:00:00').toLocaleDateString(
                      undefined,
                      { day: 'numeric' }
                    ),
                  },
                })}
              </div>
            </div>

            <div class="history-goal-list" style="width:100%">
              {#each PLAN_TEMPS as temp (temp)}
                {@const normDate = getNormalizedDate(selDay, temp)}
                {@const assignedIds = Array.from(new Set(assignments[normDate] || []))}
                {@const filteredGoals = assignedIds
                  .map((id) => goals.find((g) => g.id === id))
                  .filter((g): g is Goal => g !== undefined && Boolean(g) && g.temporality === temp)}

                {#if filteredGoals.length > 0}
                  <div class="planning-section-header">
                    {temp === 'DAILY'
                      ? 'Día'
                      : temp === 'WEEKLY'
                        ? 'Semana'
                        : temp === 'MONTHLY'
                          ? 'Mes'
                          : temp === 'ANNUAL'
                            ? 'Año'
                            : 'Único'}
                  </div>
                  {#each filteredGoals as g (g.id)}
                    {@const status = getGoalStatusOnDate(g, selDay)}
                    {@const rowColor =
                      status === 'FAILED'
                        ? 'var(--error)'
                        : status === 'COMPLETED'
                          ? 'var(--success)'
                          : getGoalColor(g)}
                    <div class="pln-detail-item" style="border-left: 3px solid {rowColor}">
                      <button
                        class="pln-day-unassign"
                        onclick={() => unassignGoalFromDate(g.id, selDay)}
                        title={$t('goalsPage.remove')}
                        aria-label={$t('goalsPage.remove')}><X size={12} /></button
                      >
                      {#if g.fail_emoji}
                        <span class="pln-item-icon">
                          <StreakIcon name={g.fail_emoji} size={13} color={rowColor} />
                        </span>
                      {/if}
                      <button
                        class="pln-day-name"
                        class:line-through={status === 'COMPLETED'}
                        onclick={() => openGoalEditor(g)}
                      >
                        <span class="pln-mq" use:marquee>
                          <span class="pln-mq-track">
                            <span class="pln-mq-text">{g.title}</span>
                            <span class="pln-mq-text pln-mq-dup" aria-hidden="true">{g.title}</span>
                          </span>
                        </span>
                      </button>
                      {#if status === 'COMPLETED'}
                        <span class="status-badge success">{$t('goalsPage.completed')}</span>
                      {:else if status === 'FAILED'}
                        <span class="status-badge error">{$t('goalsPage.failed')}</span>
                      {/if}
                      {#if g.max_assignment_days}
                        <span class="pln-item-temp" style="color: var(--text-muted)"
                          >{$t('goalsPage.limit', {
                            values: { days: g.max_assignment_days },
                          })}</span
                        >
                      {/if}
                    </div>
                  {/each}
                {/if}
              {/each}

              {#if !PLAN_TEMPS.some( (temp) => (assignments[getNormalizedDate(selDay, temp)] || []).some((id) => goals.find((g) => g.id === id)?.temporality === temp) )}
                <div
                  class="history-detail-empty"
                  style="padding: 2rem; border: 1px dashed var(--border); border-radius: var(--r); margin: 1rem;"
                >
                  <span
                    class="history-detail-msg"
                    style="font-size: 12px; text-align: center; display: block;"
                    >{$t('goalsPage.noGoalsForPeriod')}</span
                  >
                </div>
              {/if}

              <!-- Real-calendar agenda: Google events + joidy tasks for the
                   selected day. Read-only — clicks open a detail modal. -->
              <div class="planning-section-header">{$t('goalsPage.realCalendar')}</div>
              {#if agendaLoading}
                <div class="pln-agenda-empty caption">{$t('goalsPage.agendaLoading')}</div>
              {:else if dayAgendaItems.length === 0}
                <div class="pln-agenda-empty caption">{$t('goalsPage.noCalendarItems')}</div>
              {:else}
                {#each dayAgendaItems as item (item.kind === 'event' ? `e-${item.event.google_id}` : `t-${item.task.id}`)}
                  <button
                    class="pln-agenda-item"
                    style="border-left: 3px solid {agendaEntryColor(item)}"
                    onclick={() => openAgendaDetail(item)}
                  >
                    {#if item.kind === 'event'}
                      <span class="pln-agenda-icon"><Lock size={11} /></span>
                    {:else if item.task.done}
                      <span class="pln-agenda-icon pln-agenda-done"><Check size={11} /></span>
                    {:else}
                      <span
                        class="pln-agenda-dot"
                        style="background: {agendaEntryColor(item)}"
                      ></span>
                    {/if}
                    <span class="pln-agenda-time caption">{agendaEntryTime(item)}</span>
                    <span class="pln-agenda-body">
                      <span class="pln-agenda-label">{agendaEntryTitle(item)}</span>
                      {#if item.kind === 'task' && item.task.goal_title}
                        <span class="pln-agenda-goal"><Target size={9} />{item.task.goal_title}</span>
                      {:else if item.kind === 'event' && item.event.location}
                        <span class="pln-agenda-sub caption">{item.event.location}</span>
                      {/if}
                    </span>
                  </button>
                {/each}
              {/if}
            </div>
          </aside>
        </div>
      </div>
    {/if}

    {#if currentTab === 'history'}
      <div class="tab-content fade-in history-layout">
        <!-- Left: Annual Calendar -->
        <div class="history-calendar-col">
          <div class="history-cal-header">
            <span class="section-title" style="margin:0;">{$t('goalsPage.yearMap')}</span>
            <span class="history-hint">{$t('goalsPage.selectDayHint')}</span>
          </div>
          {#if historyData.length === 0}
            <div class="empty-state">{$t('goalsPage.noActivityYet')}</div>
          {:else}
            <div class="history-heatmap-wrap">
              {#if StreakHeatmap}
                <StreakHeatmap
                  history={historyData}
                  color="var(--success)"
                  selectedDate={selectedHistoryDate}
                  onselect={(date) => (selectedHistoryDate = date)}
                />
              {:else if heatmapChunkError}
                <div class="heatmap-chunk-error caption">
                  <span>{$t('common.loadFailed')}</span>
                  <button class="btn btn-ghost" onclick={loadStreakHeatmap}
                    >{$t('common.retry')}</button
                  >
                </div>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Right: Detail Panel -->
        <div class="history-detail-col">
          {#if !selectedHistoryDate}
            <div class="history-detail-empty">
              <div class="history-detail-icon"><Calendar size={40} strokeWidth={1} /></div>
              <span class="history-detail-msg">{$t('goalsPage.selectDayCalendarHint')}</span>
            </div>
          {:else}
            <div class="history-detail-header">
              <div class="history-detail-date" style="text-transform:none;">
                {formatHistoryDate(selectedHistoryDate)}
              </div>
            </div>

            {#if goalsForDate.completed.length === 0 && goalsForDate.failed.length === 0}
              <div class="history-no-activity">
                <span>{$t('goalsPage.noActivityForDay')}</span>
              </div>
            {/if}

            {#if goalsForDate.completed.length > 0}
              <div class="history-section-label success">
                <Check size={12} />
                {$t('goalsPage.completedLabel')} ({goalsForDate.completed.length})
              </div>
              <div class="history-goal-list">
                {#each goalsForDate.completed as g (g.id)}
                  <div
                    class="goal-card completed"
                    style="border-left: 3px solid {getGoalColor(g)}; width: 100%;"
                  >
                    <div class="goal-main">
                      <div class="goal-title">
                        {#if g.fail_emoji}
                          <span
                            class="emoji-badge"
                            style="display:flex; align-items:center; margin-right:8px;"
                          >
                            <StreakIcon name={g.fail_emoji} size={16} color={getGoalColor(g)} />
                          </span>
                        {/if}
                        {g.title}
                      </div>
                      <div class="goal-meta">
                        <span
                          class="tag-chip"
                          style="background: color-mix(in srgb, {getGoalColor(
                            g
                          )} 12%, transparent); border: 1px solid {getGoalColor(
                            g
                          )}; color: {getGoalColor(g)};"
                          >{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span
                        >
                      </div>
                    </div>
                    <div class="goal-progress" style="width: 100px;">
                      <div class="progress-meta">
                        <span class="mono caption"></span>
                        <span class="caption" style="color: {getGoalColor(g)};">100%</span>
                      </div>
                      <div class="progress-track" style="height: 4px;">
                        <div
                          class="progress-fill"
                          style="width: 100%; background: {getGoalColor(g)};"
                        ></div>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}

            {#if goalsForDate.failed.length > 0}
              <div class="history-section-label failed">
                <X size={12} />
                {$t('goalsPage.failedLabel')} ({goalsForDate.failed.length})
              </div>
              <div class="history-goal-list">
                {#each goalsForDate.failed as g (g.id)}
                  <div
                    class="goal-card failed"
                    style="border-left: 3px solid var(--error); width: 100%;"
                  >
                    <div class="goal-main">
                      <div class="goal-title">
                        {#if g.fail_emoji}
                          <span
                            class="emoji-badge"
                            style="display:flex; align-items:center; margin-right:8px;"
                          >
                            <StreakIcon name={g.fail_emoji} size={16} color="var(--error)" />
                          </span>
                        {/if}
                        {g.title}
                      </div>
                      <div class="goal-meta">
                        <span
                          class="tag-chip"
                          style="background: color-mix(in srgb, var(--error) 12%, transparent); border: 1px solid var(--error); color: var(--error);"
                          >{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span
                        >
                      </div>
                    </div>
                    <div class="goal-progress" style="width: 100px;">
                      <div class="progress-meta">
                        <span class="mono caption"></span>
                        <span class="caption" style="color: var(--error);">{g.progress_pct}%</span>
                      </div>
                      <div class="progress-track" style="height: 4px;">
                        <div
                          class="progress-fill"
                          style="width: {g.progress_pct}%; background: var(--error);"
                        ></div>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          {/if}
        </div>
      </div>
    {/if}
    {#if currentTab === 'editor'}
      <div class="tab-content fade-in editor-tab">
        <div class="editor-toolbar">
          <GoalFilters
            bind:query={goalSearchQuery}
            bind:filter={goalFilterState}
            bind:contextFilter={goalContextFilter}
          />
          <button class="btn btn-primary new-goal-cta-inline" onclick={toggleNewGoalForm}>
            <Plus size={16} />
            {$t('goalsPage.newGoal')}
          </button>
        </div>
        <div class="editor-body">
          <div class="editor-rail-col">
            <GoalStatsRail
              active={editorRailStats.active}
              completed={editorRailStats.completed}
              paused={editorRailStats.paused}
              todayTotal={editorRailStats.todayTotal}
              todayDone={editorRailStats.todayDone}
              total={editorRailStats.total}
            />
            <GoalUpcoming
              days={upcomingWeek}
              {todayIso}
              {getGoalColor}
              onSelectDay={jumpToPlanning}
            />
          </div>
          <GoalList
            {goals}
            query={goalSearchQuery}
            filter={goalFilterState}
            contextFilter={goalContextFilter}
            pinned={pinnedGoals}
            selectedId={lastEditedGoalId}
            {tags}
            {notes}
            {getGoalColor}
            {TEMPORALITY_LABELS}
            {STATE_LABELS}
            {formatFailConfig}
            onTogglePin={togglePinned}
            onClick={openGoalEditor}
            onComplete={completeGoal}
            onFail={failGoal}
            onDelete={confirmDeleteGoal}
            onArchive={(id) => {
              const target = goals.find((g) => g.id === id);
              if (target) {
                updateGoalState(id, target.state === 'CANCELLED' ? 'ACTIVE' : 'CANCELLED');
              }
            }}
            onNew={toggleNewGoalForm}
          />
        </div>
      </div>
    {/if}
  </div>

  <!-- ── New Goal Slide-Down Panel ── -->
  {#if showAddForm}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="new-goal-backdrop"
      onclick={(e) => {
        if (e.target === e.currentTarget) showAddForm = false;
      }}
      role="presentation"
    >
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <div
        class="new-goal-panel slide-down"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-goal-heading"
        tabindex="-1"
        use:focusTrap={{ initialFocus: '#new-goal-title', onEscape: () => (showAddForm = false) }}
      >
        <div class="new-goal-header">
          <div class="new-goal-title-row">
            <div class="new-goal-icon-wrap">
              <Plus size={16} />
            </div>
            <div>
              <h3 id="new-goal-heading" class="new-goal-heading">{$t('goalsPage.newGoal')}</h3>
              <span class="new-goal-sub">{$t('goalsPage.newGoalSub')}</span>
            </div>
          </div>
          <button
            class="history-close-btn"
            onclick={() => (showAddForm = false)}
            title={$t('goalsPage.cancel')}
            aria-label={$t('goalsPage.closeForm')}
          >
            <X size={15} />
          </button>
        </div>

        <div class="new-goal-body">
          <div class="ng-columns">
            <!-- Column 1: Basics -->
            <div class="ng-col">
              <span class="ng-col-title">{$t('goalsPage.basics')}</span>
              <div class="form-field">
                <label for="new-goal-title" class="label">{$t('goalsPage.goalTitle')}</label>
                <input
                  id="new-goal-title"
                  class="input w-full"
                  bind:value={newTitle}
                  placeholder={$t('goalsPage.goalTitlePlaceholder')}
                  maxlength="38"
                />
              </div>

              <div class="form-field">
                <span class="label">{$t('goalsPage.repeatFrequency')}</span>
                <div class="ng-freq-grid">
                  {#each TEMPORALITIES as temp}
                    <button
                      class="ng-freq-btn"
                      class:active={newTemporality === temp}
                      aria-pressed={newTemporality === temp}
                      onclick={() => (newTemporality = temp)}
                    >
                      {temp === 'DAILY'
                        ? 'Diario'
                        : temp === 'WEEKLY'
                          ? 'Semanal'
                          : temp === 'MONTHLY'
                            ? 'Mensual'
                            : temp === 'ANNUAL'
                              ? 'Anual'
                              : 'Único'}
                    </button>
                  {/each}
                </div>
              </div>
              <div class="form-field">
                <label for="new-goal-measurement" class="label">{$t('goalsPage.measurementType')}</label>
                <select id="new-goal-measurement" class="input w-full" bind:value={newMeasurement}>
                  <option value="COUNT">{$t('goalsPage.countNumeric')}</option>
                  <option value="BOOLEAN">{$t('goalsPage.booleanDone')}</option>
                  <option value="PERCENT">{$t('goalsPage.percent')}</option>
                </select>
              </div>
              <div class="form-field">
                <label for="new-goal-target" class="label">{$t('goalsPage.targetGoal')}</label>
                <input
                  id="new-goal-target"
                  class="input w-full"
                  type="number"
                  bind:value={newTargetValue}
                  min="1"
                  disabled={newMeasurement === 'BOOLEAN'}
                />
              </div>

              <div class="form-field">
                <span class="label">{$t('goalsPage.priority')}</span>
                <div class="ng-priority-row">
                  {#each [0, 1, 2, 3, 4, 5] as p}
                    <button
                      class="ng-priority-btn"
                      class:active={newPriority === p}
                      aria-pressed={newPriority === p}
                      onclick={() => (newPriority = p)}
                      title={p === 0 ? $t('goalsPage.priorityNone') : $t('goalsPage.priorityLevel', { values: { level: p } })}
                    >
                      {p}
                    </button>
                  {/each}
                </div>
              </div>
            </div>

            <!-- Column 2: Appearance -->
            <div class="ng-col">
              <span class="ng-col-title">{$t('goalsPage.appearance')}</span>
              <div class="form-field">
                <div
                  style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;"
                >
                  <span class="label" style="margin:0;">{$t('goalsPage.failIconEmoji')}</span>
                  <div style="display:flex; align-items:center; gap:8px;">
                    {#if hasFailSuggestion && (useFailIcon ? newFailIcon !== suggestedFailIcon : newFailEmoji !== suggestedFailEmoji)}
                      <button type="button" class="icon-suggest-btn" onclick={useFailSuggestion}>
                        usar sugerencia
                      </button>
                    {/if}
                    <div class="icon-toggle-row">
                      <button
                        class="icon-type-btn"
                        class:selected={!useFailIcon}
                        onclick={() => (useFailIcon = false)}>{$t('goalsPage.emoji')}</button
                      >
                      <button
                        class="icon-type-btn"
                        class:selected={useFailIcon}
                        onclick={() => (useFailIcon = true)}>{$t('goalsPage.icon')}</button
                      >
                    </div>
                  </div>
                </div>
                {#if !useFailIcon}
                  <div class="ng-picker-field">
                    <div class="emoji-grid">
                      {#each EMOJIS as e}
                        <button
                          class="emoji-btn"
                          class:selected={newFailEmoji === e}
                          onclick={() => {
                            newFailEmoji = e;
                            newFailEmojiManual = true;
                          }}>{e}</button
                        >
                      {/each}
                    </div>
                  </div>
                {:else}
                  <div class="ng-picker-field ng-picker-icon">
                    <LazyIconPicker
                      selected={newFailIcon}
                      color={newGoalColor}
                      onSelect={(ic) => {
                        newFailIcon = ic;
                        newFailIconManual = true;
                      }}
                    />
                  </div>
                {/if}
              </div>

              <div class="form-field">
                <span class="label">{$t('goalsPage.identityColor')}</span>
                <div class="ng-color-grid">
                  {#each COLOR_PRESETS as c}
                    <button
                      class="ng-color-btn"
                      class:selected={newGoalColor === c.hex}
                      aria-pressed={newGoalColor === c.hex}
                      style="background: {c.hex};"
                      onclick={() => (newGoalColor = c.hex)}
                      title={c.name}
                      aria-label={c.name}
                    ></button>
                  {/each}
                </div>
                <div class="ng-color-manual-row">
                  <div class="ng-color-swatch-wrapper" style="background: {newGoalColor};">
                    <input
                      type="color"
                      class="ng-color-swatch"
                      value={newGoalColor}
                      oninput={(e) => (newGoalColor = e.currentTarget.value)}
                      aria-label={$t('goalsPage.goalColor')}
                    />
                  </div>
                  <input
                    type="text"
                    class="ng-hex-input mono"
                    maxlength="7"
                    bind:value={newGoalColor}
                    placeholder="#c8a96e"
                    aria-label={$t('goalsPage.goalColorHex')}
                  />
                </div>
              </div>
            </div>

            <!-- Column 3: Advanced -->
            <div class="ng-col">
              <span class="ng-col-title">{$t('goalsPage.advanced')}</span>
              <div class="form-field">
                <label for="new-goal-max-days" class="label"
                  >{$t('goalsPage.limitDays')}
                  <span class="optional">{$t('goalsPage.limitDaysOptional')}</span></label
                >
                <input
                  id="new-goal-max-days"
                  class="input w-full"
                  type="number"
                  bind:value={newMaxAssignmentDays}
                  min="1"
                  placeholder={$t('goalsPage.unlimited')}
                />
              </div>

              <div class="form-field">
                <span class="label">{$t('goalsPage.failPolicy')}</span>
                <div class="ng-fail-options">
                  <button
                    class="ng-fail-btn"
                    class:active={newFailConfig === 'STATIC'}
                    aria-pressed={newFailConfig === 'STATIC'}
                    onclick={() => (newFailConfig = 'STATIC')}
                  >
                    <strong>{$t('goalsPage.static')}</strong>
                    <span>{$t('goalsPage.staticDesc')}</span>
                  </button>
                  <button
                    class="ng-fail-btn"
                    class:active={newFailConfig === 'ROLLOVER'}
                    aria-pressed={newFailConfig === 'ROLLOVER'}
                    onclick={() => (newFailConfig = 'ROLLOVER')}
                  >
                    <strong>{$t('goalsPage.rollover')}</strong>
                    <span>{$t('goalsPage.rolloverDesc')}</span>
                  </button>
                  <button
                    class="ng-fail-btn"
                    class:active={newFailConfig === 'SNOWBALL'}
                    aria-pressed={newFailConfig === 'SNOWBALL'}
                    onclick={() => (newFailConfig = 'SNOWBALL')}
                  >
                    <strong>{$t('goalsPage.snowball')}</strong>
                    <span>{$t('goalsPage.snowballDesc')}</span>
                  </button>
                </div>
              </div>

              <div class="form-field">
                <label for="new-goal-note" class="label">{$t('goalsPage.linkToProject')}</label>
                <NoteLinkPicker
                  {notes}
                  bind:value={newNoteId}
                  id="new-goal-note"
                  placeholder={$t('goalsPage.searchNote')}
                  onCreateNote={createNoteAndLink}
                />
              </div>
              <div class="form-field">
                <label for="new-goal-tag" class="label">{$t('goalsPage.tagSync')}</label>
                <select id="new-goal-tag" class="input w-full" bind:value={newTagId}>
                  <option value={null}>{$t('goalsPage.manualUpdate')}</option>
                  {#each notes as n}
                    {@const tagId = tags.find((t) => t.name === n.title)?.id}
                    {#if tagId}
                      <option value={tagId}>{n.title} (Auto-rastreo)</option>
                    {/if}
                  {/each}
                </select>
              </div>
            </div>
          </div>

          <!-- Bottom Preview Section -->
          <div class="ng-bottom-preview">
            <span class="ng-preview-label">{$t('goalsPage.preview')}</span>
            <div
              class="goal-card preview-card-live"
              style="border-color: {newGoalColor}; background: color-mix(in srgb, {newGoalColor} 5%, var(--surface));"
            >
              <div class="goal-main">
                <div class="goal-title">
                  <span
                    class="emoji-badge"
                    style="display:flex; align-items:center; margin-right:8px;"
                  >
                    {#if useFailIcon}
                      <StreakIcon name={newFailIcon} size={16} color={newGoalColor} />
                    {:else}
                      {newFailEmoji}
                    {/if}
                  </span>
                  {newTitle || 'Nombre del Objetivo...'}
                </div>
              </div>
              <div class="goal-progress" style="width: 100px;">
                <div class="progress-meta">
                  <span class="mono caption">0/{newTargetValue}</span>
                </div>
                <div class="progress-track" style="height: 4px;">
                  <div class="progress-fill" style="width: 0%; background: {newGoalColor};"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="new-goal-footer">
          {#if addError}
            <span class="ng-error">{addError}</span>
          {:else}
            <span></span>
          {/if}
          <div class="new-goal-actions">
            <button class="btn btn-ghost" onclick={() => (showAddForm = false)}
              >{$t('goalsPage.cancel')}</button
            >
            <button class="btn btn-primary" onclick={addGoal} disabled={saving || !newTitle.trim()}>
              {saving ? 'Guardando...' : 'Crear objetivo'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  {#if pendingGoals.length > 0}
    <ModalDialog open={true} title="⚠ Objetivos Huérfanos" size="md" onClose={() => {}}>
      <p class="removal-desc">
        Los siguientes objetivos fueron eliminados del contenido de sus notas vinculadas. ¿Qué
        deseas hacer con cada uno?
      </p>
      {#each pendingGoals as pg (pg.id)}
        <div class="removal-item">
          <div class="removal-info">
            <span class="removal-title">{pg.title}</span>
            <span class="removal-meta">{pg.temporality} · {formatFailConfig(pg.fail_config)}</span>
          </div>
          <div class="removal-actions">
            <button
              class="btn btn-ghost removal-btn manual"
              title={$t('goalsPage.keepManual')}
              onclick={() => resolveRemoval(pg.id, 'manual')}
            >
              Manual
            </button>
            <button
              class="btn btn-ghost removal-btn cancel"
              title={$t('goalsPage.cancelArchive')}
              onclick={() => resolveRemoval(pg.id, 'cancel')}
            >
              Cancelar
            </button>
            <button
              class="btn btn-ghost removal-btn delete"
              title={$t('goalsPage.deletePermanent')}
              onclick={() => resolveRemoval(pg.id, 'delete')}
            >
              Eliminar
            </button>
          </div>
        </div>
      {/each}
    </ModalDialog>
  {/if}

  {#if goalToDelete}
    <ModalDialog
      open={true}
      title={$t('goalsPage.deleteGoalConfirmTitle')}
      size="sm"
      onClose={() => (goalToDelete = null)}
    >
      <p style="margin: 0 0 16px; font-size: 14px; line-height: 1.5; color: var(--text-primary);">
        {$t('goalsPage.deleteGoalConfirmMessage', { values: { title: goalToDelete.title } })}
      </p>
      {#snippet footer()}
        <button
          type="button"
          class="btn btn-ghost"
          onclick={() => (goalToDelete = null)}
        >
          {$t('goalsPage.cancel')}
        </button>
        <button
          type="button"
          class="btn btn-danger"
          onclick={handleConfirmDeleteGoal}
        >
          {$t('goalsPage.delete')}
        </button>
      {/snippet}
    </ModalDialog>
  {/if}

  {#if agendaDetail}
    {@const detail = agendaDetail}
    {@const detailColor = detail.kind === 'event'
      ? (detail.event.color ?? 'var(--text-muted)')
      : (detail.task.color ?? AGENDA_PRIORITY_COLORS[detail.task.priority] ?? 'var(--text-muted)')}
    <ModalDialog
      open={true}
      title={detail.kind === 'event'
        ? detail.event.summary || '—'
        : detail.task.title}
      size="md"
      footerAlign="center"
      titleAlign="center"
      onClose={() => (agendaDetail = null)}
    >
      <p class="agenda-detail-hint caption">
        <span class="agenda-detail-swatch" style="background: {detailColor}"></span
        >{$t('goalsPage.agendaReadOnly')}
      </p>
      <dl class="agenda-detail-list">
        {#if detail.kind === 'event'}
          {@const ev = detail.event}
          <div class="agenda-detail-row">
            <dt>{$t('goalsPage.fieldDate')}</dt>
            <dd>{new Date(`${eventDayKey(ev)}T12:00:00`).toLocaleDateString($locale, { weekday: 'long', day: 'numeric', month: 'long' })}</dd>
          </div>
          <div class="agenda-detail-row">
            <dt>{$t('goalsPage.fieldSchedule')}</dt>
            <dd>{eventTimeLabel(ev)}</dd>
          </div>
          {#if ev.location}
            <div class="agenda-detail-row">
              <dt>{$t('goalsPage.fieldLocation')}</dt>
              <dd>{ev.location}</dd>
            </div>
          {/if}
          {#if ev.description}
            <div class="agenda-detail-row">
              <dt>{$t('goalsPage.fieldDescription')}</dt>
              <dd class="agenda-detail-desc">{ev.description}</dd>
            </div>
          {/if}
        {:else}
          {@const task = detail.task}
          <div class="agenda-detail-row">
            <dt>{$t('goalsPage.fieldDate')}</dt>
            <dd>{task.date
              ? new Date(`${task.date}T12:00:00`).toLocaleDateString($locale, {
                  weekday: 'long',
                  day: 'numeric',
                  month: 'long',
                })
              : '—'}</dd>
          </div>
          <div class="agenda-detail-row">
            <dt>{$t('goalsPage.fieldSchedule')}</dt>
            <dd>{taskTimeLabel(task)}</dd>
          </div>
          <div class="agenda-detail-row">
            <dt>{$t('calendar.priority')}</dt>
            <dd>{task.priority}</dd>
          </div>
          <div class="agenda-detail-row">
            <dt>{$t('goalsPage.fieldStatus')}</dt>
            <dd>{task.done ? $t('goalsPage.statusDone') : $t('goalsPage.statusPending')}</dd>
          </div>
          {#if task.recurrence !== 'NONE'}
            <div class="agenda-detail-row">
              <dt>{$t('calendar.recurrence')}</dt>
              <dd>{$t(RECURRENCE_LABEL_KEYS[task.recurrence] ?? 'calendar.recurrenceNone')}</dd>
            </div>
          {/if}
          {#if task.reminder_minutes !== null}
            <div class="agenda-detail-row">
              <dt>{$t('calendar.reminder')}</dt>
              <dd>{reminderLabel(task.reminder_minutes)}</dd>
            </div>
          {/if}
          {#if task.goal_title}
            <div class="agenda-detail-row">
              <dt>{$t('goalsPage.linkedGoal')}</dt>
              <dd>{task.goal_title}</dd>
            </div>
          {/if}
        {/if}
      </dl>
      {#snippet footer()}
        {#if detail.kind === 'event' && detail.event.html_link}
          <a
            class="btn btn-ghost"
            href={detail.event.html_link}
            target="_blank"
            rel="noopener noreferrer">{$t('goalsPage.openInGoogle')}</a
          >
        {/if}
        {#if detail.kind === 'task' && detail.task.goal_id}
          <button
            type="button"
            class="btn btn-ghost"
            onclick={() => {
              const gid = detail.task.goal_id;
              agendaDetail = null;
              if (gid) goto(`/goals/${gid}`);
            }}
          >
            {$t('goalsPage.viewGoal')}
          </button>
        {/if}
        <button
          type="button"
          class="btn btn-ghost"
          onclick={() => {
            agendaDetail = null;
            goto('/calendar');
          }}
        >
          {$t('goalsPage.openCalendar')}
        </button>
        {#if detail.kind === 'event'}
          <button
            type="button"
            class="btn btn-primary"
            onclick={() => {
              const ev = detail.event;
              agendaDetail = null;
              goalFromEventSeed = {
                title: ev.summary || '—',
                description: ev.description,
                location: ev.location,
                color: ev.color,
                day: eventDayKey(ev),
                eventId: ev.google_id,
              };
            }}
          >
            <Target size={14} /> {$t('goalFromEvent.action')}
          </button>
        {/if}
      {/snippet}
    </ModalDialog>
  {/if}

  {#if goalFromEventSeed}
    <GoalFromEventModal
      event={goalFromEventSeed}
      onClose={() => (goalFromEventSeed = null)}
      onCreated={(goal) => {
        goals = [goal, ...goals];
        // The modal wrote the assignment (with its goal_event_ids link)
        // directly — force a refetch so the shared cache picks it up.
        void refreshAssignmentsForDate(goalFromEventSeed?.day ?? '');
        void loadRangeAgenda();
      }}
    />
  {/if}
</div>

<style>
  .goals-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }
  .error-banner {
    padding: 16px;
    color: var(--error);
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .goals-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--s5);
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    max-width: 800px;
    margin: 0 auto;
    width: 100%;
    transition: max-width 0.3s ease;
  }
  /* ── Planning v2 — toolbar + calendar/week board + detail + pool ── */
  .pln {
    display: flex;
    flex-direction: column;
    flex: 1;
    width: 100%;
    max-width: none;
    gap: var(--s3);
    min-height: 0;
  }

  .pln-toolbar {
    display: flex;
    align-items: center;
    gap: var(--s3);
    flex-wrap: wrap;
    flex-shrink: 0;
  }
  .pln-pool-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: calc(290px - var(--s3) * 2);
    margin-left: var(--s3);
    height: 28px;
    box-sizing: border-box;
    gap: 6px;
    padding: 0 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-muted);
    font-size: 11px;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    cursor: pointer;
    transition:
      color var(--t-fast),
      border-color var(--t-fast);
  }
  .pln-pool-toggle:hover {
    color: var(--text-primary);
  }
  .pln-pool-toggle.active {
    color: var(--text-primary);
    border-color: color-mix(in srgb, var(--link) 45%, var(--border));
  }
  .pln-pool-count {
    padding: 0 6px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--link) 15%, transparent);
    color: var(--link);
    font-size: 10px;
  }

  .pln-nav {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 28px;
  }
  .pln-nav-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    box-sizing: border-box;
    border-radius: var(--r);
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-muted);
    cursor: pointer;
    transition:
      color var(--t-fast),
      border-color var(--t-fast);
  }
  .pln-nav-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }
  .pln-period {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 28px;
    min-width: 170px;
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    font-family: var(--font-mono);
    line-height: 1;
    color: var(--text-primary);
    white-space: nowrap;
  }
  .pln-today-btn {
    display: inline-flex;
    align-items: center;
    height: 28px;
    box-sizing: border-box;
    margin-left: 6px;
    padding: 0 10px;
    font-size: 11px;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-muted);
    cursor: pointer;
    transition:
      color var(--t-fast),
      border-color var(--t-fast);
  }
  .pln-today-btn:hover {
    color: var(--xp);
    border-color: color-mix(in srgb, var(--xp) 45%, var(--border));
  }
  .pln-center {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .pln-right {
    width: 370px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--s3);
  }

  .pln-view-toggle {
    display: flex;
    align-items: center;
    height: 28px;
    box-sizing: border-box;
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }
  .pln-view-toggle button {
    display: inline-flex;
    align-items: center;
    height: 28px;
    box-sizing: border-box;
    padding: 0 12px;
    font-size: 11px;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    background: var(--surface);
    color: var(--text-muted);
    border: none;
    cursor: pointer;
    transition:
      color var(--t-fast),
      background var(--t-fast);
  }
  .pln-view-toggle button + button {
    border-left: 1px solid var(--border);
  }
  .pln-view-toggle button.active {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 10%, transparent);
  }

  .pln-main {
    flex: 1;
    min-height: 0;
    display: flex;
    gap: var(--s3);
    align-items: stretch;
  }

  /* Goal pool (unassigned, draggable) */
  .pln-pool {
    width: 290px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    min-height: 0;
    overflow: hidden;
  }
  .pln-pool-head {
    padding: var(--s2);
    border-bottom: 1px solid var(--border-light);
    display: flex;
  }
  .pln-pool-filter {
    display: flex;
    flex: 1;
    min-width: 0;
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }
  .pln-pool-filter button {
    flex: 8;
    min-width: 0;
    padding: 5px 2px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 10.5px;
    font-family: inherit;
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: all 0.15s;
  }
  .pln-pool-filter button + button {
    border-left: 1px solid var(--border);
  }
  .pln-pool-filter button:nth-child(1) {
    flex-grow: 9;
  }
  .pln-pool-filter button:nth-child(2) {
    flex-grow: 8;
  }
  .pln-pool-filter button:nth-child(3) {
    flex-grow: 10;
  }
  .pln-pool-filter button:hover {
    color: var(--text-secondary);
  }
  .pln-pool-filter button.active {
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
    font-weight: 600;
  }
  .pln-pool-list {
    flex: 1;
    overflow-y: auto;
    padding: var(--s2) var(--s3) var(--s3);
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-height: 0;
  }
  .pln-pool-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    text-align: left;
    padding: 11px 12px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-primary);
    font-size: 13px;
    cursor: grab;
    transition:
      background var(--t-fast),
      border-color var(--t-fast);
  }
  .pln-pool-item:hover {
    background: var(--surface-hover);
    border-color: var(--text-muted);
  }
  .pln-pool-item:active {
    cursor: grabbing;
  }
  .pln-item-icon {
    display: flex;
    flex-shrink: 0;
  }
  .pln-item-title {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 600;
  }
  .pln-item-temp {
    font-size: 9px;
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
    opacity: 0.85;
  }

  /* Infinite horizontal auto-scroll for overflowing goal titles. The track
     holds two copies; translating -50% loops seamlessly because the copy's
     trailing padding is the loop gap. Activated only when the text overflows
     (marquee action toggles the class). The action drives the loop via the
     Web Animations API so each cycle dwells --mq-dwell (default 1s) with the
     title start in view; the pln-marquee CSS animation below is a scroll-only
     fallback for engines without WAAPI. */
  .pln-mq {
    display: block;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }
  .pln-mq:global(.marquee-on) {
    mask-image: linear-gradient(
      90deg,
      transparent,
      #000 10px,
      #000 calc(100% - 10px),
      transparent
    );
    -webkit-mask-image: linear-gradient(
      90deg,
      transparent,
      #000 10px,
      #000 calc(100% - 10px),
      transparent
    );
  }
  .pln-mq-track {
    display: inline-flex;
    white-space: nowrap;
    will-change: transform;
  }
  .pln-mq-text {
    padding-right: 28px;
  }
  .pln-mq-dup {
    display: none;
  }
  .pln-mq:global(.marquee-on) .pln-mq-dup {
    display: inline;
  }
  .pln-mq:global(.marquee-on) .pln-mq-track {
    animation: pln-marquee linear infinite;
  }
  @keyframes pln-marquee {
    from {
      transform: translateX(0);
    }
    to {
      transform: translateX(-50%);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pln-mq:global(.marquee-on) .pln-mq-track {
      animation: none;
    }
  }
  .pln-pool-empty {
    text-align: center;
    padding: 12px 4px;
  }

  /* Month calendar */
  .pln-cal-wrap {
    flex: 1;
    min-width: 0;
    display: flex;
    min-height: 0;
  }
  /* Detail panel (selected day, grouped by temporality) */
  .pln-detail {
    width: 370px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
    min-height: 0;
  }
  .pln-detail .history-goal-list {
    flex: 1;
    overflow-y: auto;
    padding: var(--s3);
    min-height: 0;
  }
  .pln-detail-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    margin-bottom: 6px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    font-size: 13px;
  }
  .pln-day-name.line-through {
    text-decoration: line-through;
    color: var(--text-muted);
  }
  .pln-detail-item .status-badge {
    margin-left: 0;
    flex-shrink: 0;
  }

  /* Real-calendar agenda (read-only): Google events + joidy tasks */
  .pln-agenda-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    margin-bottom: 6px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    cursor: pointer;
    text-align: left;
    color: var(--text-primary);
    font-size: 13px;
  }
  .pln-agenda-item:hover {
    background: var(--hover);
    border-color: var(--text-muted);
  }
  .pln-agenda-icon {
    flex-shrink: 0;
    color: var(--text-muted);
  }
  .pln-agenda-done {
    color: var(--success);
  }
  .pln-agenda-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .pln-agenda-time {
    flex-shrink: 0;
    min-width: 44px;
    color: var(--text-muted);
  }
  .pln-agenda-body {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }
  .pln-agenda-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pln-agenda-goal {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    color: var(--link);
    font-size: 11px;
  }
  .pln-agenda-sub {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-muted);
  }
  .pln-agenda-empty {
    padding: 8px 12px;
    color: var(--text-muted);
  }
  .agenda-detail-hint {
    margin: 0 0 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    text-align: center;
  }
  .agenda-detail-swatch {
    width: 10px;
    height: 10px;
    border-radius: 3px;
    flex-shrink: 0;
    border: 1px solid var(--border);
  }
  .agenda-detail-list {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .agenda-detail-row {
    display: flex;
    justify-content: center;
    gap: 12px;
    font-size: 13px;
  }
  .agenda-detail-row dt {
    color: var(--text-muted);
    min-width: 90px;
    flex-shrink: 0;
  }
  .agenda-detail-row dd {
    margin: 0;
    color: var(--text-primary);
  }
  .agenda-detail-desc {
    white-space: pre-wrap;
    word-break: break-word;
  }


  /* Goal rows inside the detail panel */
  .pln-day-unassign {
    display: flex;
    padding: 2px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
  }
  .pln-day-unassign:hover {
    color: var(--error);
  }
  .pln-day-name {
    flex: 1;
    min-width: 0;
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    cursor: pointer;
    padding: 0;
    display: flex;
    min-width: 0;
  }
  .pln-day-name:hover {
    color: var(--link);
  }

  @media (max-width: 1100px) {
    .pln-detail {
      width: 320px;
    }
    .pln-right {
      width: 320px;
    }
    .pln-pool {
      width: 250px;
    }
    .pln-pool-toggle {
      width: 250px;
    }
  }

  @media (max-width: 900px) {
    .pln {
      height: auto;
      overflow: visible;
    }
    .pln-main {
      flex-direction: column;
      overflow-y: auto;
    }
    .pln-pool,
    .pln-detail {
      width: 100%;
      flex-shrink: 0;
    }
    .pln-cal-wrap {
      min-height: 380px;
    }
  }

  /* Left/Right columns sizing and scroll behaviour */
  .planning-section-header {
    font-size: 10px;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: 0.1em;
    padding: 16px 16px 8px;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 8px;
    background: color-mix(in srgb, var(--text-primary) 2%, transparent);
  }

  .status-badge {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 4px;
    text-transform: uppercase;
    font-weight: 600;
    margin-left: 8px;
  }
  .status-badge.success {
    background: color-mix(in srgb, var(--success) 10%, transparent);
    color: var(--success);
    border: 1px solid color-mix(in srgb, var(--success) 20%, transparent);
  }
  .status-badge.error {
    background: color-mix(in srgb, var(--error) 10%, transparent);
    color: var(--error);
    border: 1px solid color-mix(in srgb, var(--error) 20%, transparent);
  }

  .history-heatmap-wrap {
    width: 100%;
    display: flex;
    justify-content: center;
  }
  .heatmap-chunk-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 24px;
    color: var(--text-muted);
  }
  .goals-body.full-width {
    max-width: none;
    margin: 0;
    padding: 0 var(--s3) var(--s3);
    overflow: hidden;
    min-height: 0;
  }
  /* Framed canvas: the view area gets a mandatory border so inner components
     never visually collide with the app chrome. Testing in planning first. */
  .goals-body.framed {
    padding: var(--s3);
    width: auto;
  }
  /* Full-width tabs fill the whole tab height. */
  .goals-body.full-width .tab-content {
    flex: 1;
    min-height: 0;
  }
  .goals-body.full-width .tab-content:not(.pln):not(.history-layout) {
    display: flex;
    flex-direction: column;
  }

  .new-goal-cta-inline {
    height: 36px;
    padding: 0 14px;
    white-space: nowrap;
  }

  /* Editor tab — slim toolbar + KPI rail + dense goal rows (metrics-view
     layout). The tab keeps its framed container; the body splits into a
     fixed rail and a scrolling list. */
  .editor-tab {
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow: hidden;
    box-sizing: border-box;
  }
  .editor-toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 52px;
    box-sizing: border-box;
    padding: 10px 0;
    border-bottom: 1px solid var(--border-light);
    background: color-mix(in srgb, var(--surface) 72%, transparent);
    flex-shrink: 0;
    flex-wrap: wrap;
  }
  .editor-toolbar .new-goal-cta-inline {
    margin-left: auto;
    flex-shrink: 0;
    height: 32px;
    box-sizing: border-box;
    padding-block: 0;
  }
  .editor-body {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr);
    gap: var(--s3);
    padding: var(--s2) 0 var(--s3);
    align-items: stretch;
  }
  .editor-rail-col {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    min-height: 0;
    overflow: hidden;
  }
  @media (max-width: 900px) {
    .editor-body {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: none;
    }
  }
  /* ── New Goal Centered Modal ── */
  .new-goal-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal);
    background: color-mix(in srgb, var(--bg) 75%, transparent);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .new-goal-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: 0 24px 80px color-mix(in srgb, var(--bg) 60%, transparent);
    display: flex;
    flex-direction: column;
    max-height: calc(100vh - 24px);
    width: min(1280px, calc(100vw - 24px));
    border-radius: 12px;
    overflow: hidden;
  }
  .slide-down {
    animation: modalPopIn 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  }
  @keyframes modalPopIn {
    from {
      transform: scale(0.95) translateY(10px);
      opacity: 0;
    }
    to {
      transform: scale(1) translateY(0);
      opacity: 1;
    }
  }
  .new-goal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s6);
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }
  .new-goal-title-row {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }
  .new-goal-icon-wrap {
    width: 32px;
    height: 32px;
    background: var(--surface-active);
    border: 1px solid var(--border);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
    flex-shrink: 0;
  }
  .new-goal-heading {
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    margin: 0;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-family: var(--font-mono);
  }
  .new-goal-sub {
    display: none;
  }

  .history-close-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    line-height: 1;
    transition: all var(--duration-fast) ease;
    flex-shrink: 0;
  }

  .history-close-btn:hover {
    color: var(--text-primary);
    background: var(--surface-hover);
    border-color: var(--border-hover, var(--border));
  }

  .new-goal-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--s5) var(--s6);
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    min-height: 0;
    overscroll-behavior: contain;
  }

  .ng-bottom-preview {
    margin-top: var(--s4);
    padding-top: var(--s4);
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 8px;
    /* The preview is purely visual (no interactive children). Disable pointer
       events so it can never intercept clicks meant for the color dots above it
       when both share the same stacking context (#203). */
    pointer-events: none;
  }
  .ng-preview-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    text-align: center;
  }

  .ng-columns {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    align-items: stretch;
  }
  .ng-col {
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-width: 0;
  }
  .ng-col-title {
    font-size: 11px;
    font-family: var(--font-mono);
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    text-align: center;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }

  .ng-freq-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }
  .ng-priority-row {
    display: flex;
    gap: 6px;
  }
  .ng-priority-btn {
    flex: 1;
    padding: 8px 0;
    font-size: 12px;
    font-family: var(--font-mono);
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
  }
  .ng-priority-btn:hover {
    border-color: var(--text-muted);
  }
  .ng-priority-btn.active {
    background: var(--surface-active);
    color: var(--text-primary);
    border-color: var(--text-primary);
  }
  .ng-freq-btn {
    padding: 10px;
    font-size: 12px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
  }
  .ng-freq-btn:hover {
    border-color: var(--text-muted);
  }
  .ng-freq-btn.active {
    background: var(--surface-active);
    color: var(--text-primary);
    border-color: var(--text-primary);
  }

  /* Fixed-height picker container — switching between emoji and icon
     modes does not resize the modal (#726, matches StreakCreateModal pattern). */
  .ng-picker-field {
    height: 280px;
    min-height: 280px;
    max-height: 280px;
    overflow: hidden;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface-hover);
    padding: var(--s2);
  }
  .ng-picker-field > :global(*) {
    height: 100%;
    min-height: 0;
    max-height: 100%;
  }
  .ng-picker-icon {
    display: flex;
    flex-direction: column;
  }

  .ng-fail-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ng-fail-btn {
    display: flex;
    flex-direction: column;
    padding: 12px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: 8px;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s;
  }
  .ng-fail-btn strong {
    font-size: 13px;
    color: var(--text-secondary);
  }
  .ng-fail-btn span {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
  }
  .ng-fail-btn:hover {
    border-color: var(--text-muted);
  }
  .ng-fail-btn.active {
    background: rgba(var(--primary-rgb, 139, 92, 246), 0.1);
    border-color: var(--primary);
  }

  .new-goal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s6);
    border-top: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }
  .new-goal-actions {
    display: flex;
    gap: var(--s3);
  }
  .ng-error {
    font-size: 12px;
    color: var(--error);
    font-family: var(--font-mono);
  }
  .optional {
    font-size: 10px;
    color: var(--text-muted);
    font-style: italic;
  }

  /* Color picker — matches StreakCreateModal pattern */
  .ng-color-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(32px, 1fr));
    gap: 6px;
    padding: 4px;
  }
  .ng-color-btn {
    width: 32px;
    height: 32px;
    border: 2px solid transparent;
    border-radius: var(--r);
    cursor: pointer;
    transition: all 0.15s;
    padding: 0;
  }
  .ng-color-btn:hover {
    transform: scale(1.1);
    border-color: var(--text-muted);
  }
  .ng-color-btn.selected {
    border-color: var(--text-primary);
    box-shadow:
      0 0 0 1px var(--bg),
      0 0 0 3px var(--text-primary);
  }
  .ng-color-manual-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 8px;
  }
  .ng-color-swatch-wrapper {
    width: 36px;
    height: 36px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    flex-shrink: 0;
    overflow: hidden;
    position: relative;
    cursor: pointer;
  }
  .ng-color-swatch {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: none;
    padding: 0;
    cursor: pointer;
    opacity: 0;
  }
  .ng-color-swatch::-webkit-color-swatch-wrapper {
    padding: 0;
  }
  .ng-color-swatch::-webkit-color-swatch {
    border: none;
  }
  .ng-color-swatch::-moz-color-swatch {
    border: none;
  }
  .ng-hex-input {
    width: 90px;
    flex: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 13px;
    color: var(--text-primary);
    outline: none;
    transition: border-color 0.15s;
  }
  .ng-hex-input:focus {
    border-color: var(--text-muted);
  }
  .ng-hex-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }

  /* Responsive — stack columns on narrow viewports (#726) */
  @media (max-width: 900px) {
    .ng-columns {
      grid-template-columns: 1fr;
      gap: var(--s4);
    }
    .ng-col-title {
      text-align: left;
    }
    .new-goal-panel {
      width: calc(100vw - 16px);
    }
  }
  @media (max-width: 640px) {
    .new-goal-panel {
      max-height: calc(100vh - 16px);
      border-radius: var(--r-lg);
    }
    .new-goal-header,
    .new-goal-body,
    .new-goal-footer {
      padding-left: var(--s4);
      padding-right: var(--s4);
    }
    .ng-picker-field {
      height: 220px;
      min-height: 220px;
      max-height: 220px;
    }
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .label {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 6px;
    text-align: center;
    white-space: nowrap;
  }
  .w-full {
    width: 100%;
  }

  .icon-toggle-row {
    display: flex;
    gap: 6px;
  }
  .icon-type-btn {
    flex: 1;
    padding: 4px 12px;
    font-size: 11px;
    font-family: var(--font-mono);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .icon-type-btn.selected {
    border-color: var(--text-primary);
    color: var(--text-primary);
  }
  .icon-suggest-btn {
    padding: 4px 10px;
    font-size: 10px;
    font-family: var(--font-mono);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }
  .icon-suggest-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-primary);
  }

  .emoji-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
    gap: 4px;
    height: 100%;
    overflow-y: auto;
    align-content: start;
  }
  .emoji-btn {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .emoji-btn:hover {
    background: var(--elevated);
  }
  .emoji-btn.selected {
    border-color: var(--text-primary);
    background: var(--elevated);
  }

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: var(--s3);
  }
  .goal-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3) var(--s4);
    display: flex;
    align-items: center;
    gap: var(--s4);
    margin-bottom: var(--s2);
    transition: all 0.2s ease;
  }
  .goal-card.completed {
    opacity: 0.6;
    border-color: var(--success);
  }
  .goal-card.failed {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 2%, transparent);
  }
  .goal-main {
    flex: 1;
    min-width: 0;
  }
  .goal-title {
    font-size: 14px;
    color: var(--text-primary);
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .emoji-badge {
    font-size: 16px;
  }
  .goal-meta {
    display: flex;
    gap: 8px;
    margin-top: 6px;
    align-items: center;
  }
  .goal-progress {
    width: 140px;
    flex-shrink: 0;
  }
  .progress-meta {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .progress-track {
    background: color-mix(in srgb, var(--text-primary) 10%, transparent);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: var(--xp);
    transition: width 0.3s ease;
  }
  .goal-card.completed .progress-fill {
    background: var(--success);
  }
  .goal-card.failed .progress-fill {
    background: var(--error);
  }
  .empty-state {
    padding: 32px;
    text-align: center;
    color: var(--text-muted);
    font-size: 14px;
    background: var(--surface-hover);
    border-radius: var(--r);
    border: 1px dashed var(--border);
  }
  /* Planning Tabs */
  /* Hierarchical Planning */
  /* Modal de Consistencia */
  .removal-desc {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.5;
    margin: 0;
  }
  .removal-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--s3);
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: var(--r);
    gap: var(--s3);
    margin-top: var(--s3);
  }
  .removal-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .removal-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .removal-meta {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .removal-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
  .removal-btn {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: var(--r);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .removal-btn.manual {
    color: var(--success);
    border: 1px solid color-mix(in srgb, var(--success) 30%, transparent);
  }
  .removal-btn.manual:hover {
    background: color-mix(in srgb, var(--success) 10%, transparent);
  }
  .removal-btn.cancel {
    color: var(--warning);
    border: 1px solid color-mix(in srgb, var(--warning) 30%, transparent);
  }
  .removal-btn.cancel:hover {
    background: color-mix(in srgb, var(--warning) 10%, transparent);
  }
  .removal-btn.delete {
    color: var(--error);
    border: 1px solid color-mix(in srgb, var(--error) 30%, transparent);
  }
  .removal-btn.delete:hover {
    background: color-mix(in srgb, var(--error) 10%, transparent);
  }

  /* ── History Tab ── */
  .history-layout {
    display: grid;
    grid-template-columns: 1fr 440px;
    gap: var(--s4);
    align-items: stretch;
    flex: 1;
    min-height: 0;
    height: 100%;
  }

  @media (max-width: 900px) {
    .history-layout {
      grid-template-columns: 1fr;
    }
  }

  .history-calendar-col {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s4);
    min-height: 0;
    height: 100%;
  }

  .history-cal-header {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .history-hint {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    letter-spacing: 0.03em;
  }

  .history-heatmap-wrap {
    flex: 1;
    display: flex;
    align-items: stretch;
    min-height: 0;
  }

  .history-detail-col {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s4);
    min-height: 0;
    height: 100%;
    overflow-y: auto;
  }

  .history-detail-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--s3);
    flex: 1;
    height: 100%;
    padding: var(--s5);
    text-align: center;
  }

  .history-detail-icon {
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0.5;
  }

  .history-detail-msg {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.6;
    max-width: 220px;
  }

  .history-detail-header {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--s3) 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: var(--s3);
  }

  .history-detail-date {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    text-align: center;
  }

  .history-no-activity {
    font-size: 12px;
    color: var(--text-muted);
    padding: var(--s3);
    text-align: center;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .history-section-label {
    font-size: 11px;
    font-family: var(--font-mono);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 4px 0;
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .history-section-label.success {
    color: var(--success);
  }
  .history-section-label.failed {
    color: var(--error);
  }

  .history-goal-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  @media (max-width: 768px) {
    .goals-body,
    .goals-body.full-width {
      padding: var(--s3);
      overflow: visible !important;
      flex: none;
      min-height: auto !important;
    }
    .tab-content {
      overflow-x: hidden;
      max-width: 100%;
    }
    .editor-toolbar {
      flex-direction: column;
      align-items: stretch;
      gap: var(--s2);
    }
    .new-goal-cta-inline {
      width: 100%;
      justify-content: center;
    }
  }
</style>
