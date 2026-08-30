<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    Plus,
    Check,
    ChevronDown,
    Calendar,
    ChartColumn,
    Clock,
    LayoutDashboard,
    Pause,
    Play,
    Ban,
    Pencil,
    X,
    Flame,
    ChevronRight,
    ChevronLeft,
    TrendingUp,
    TrendingDown,
    ChartPie,
    Activity,
    Target,
    Trophy,
    Settings,
    Palette,
    Hexagon,
    ListFilter,
    TriangleAlert,
    FilePen,
    Tag,
    FileText,
    Pin,
    PinOff,
  } from 'lucide-svelte';
  import { api, type Goal, type Tag as TagType, type Note } from '$lib/api';
  import GoalFilters from '$lib/components/GoalFilters.svelte';
  import GoalList from '$lib/components/GoalList.svelte';
  import { use24HourClock } from '$lib/stores/settings';
  import { getLocale } from '$lib/stores/locale';
  import { applyGamificationResult, showXPGain } from '$lib/stores/gamification';
  import {
    getCachedData,
    setCachedData,
    loadUserSettings,
    patchUserSettings,
  } from '$lib/utils/userSettings';
  import { logger } from '$lib/utils/logger';
  import {
    GOALS_SPECIFIC_COLOR_PRESETS,
    DEFAULT_GOAL_COLOR,
    TEMPORALITY_COLORS,
  } from '$lib/utils/goalColors';
  import StreakIcon from '$lib/components/StreakIcon.svelte';
  import GoalCard from '$lib/components/GoalCard.svelte';
  import LazyIconPicker from '$lib/components/LazyIconPicker.svelte';
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import { t } from 'svelte-i18n';

  // Lazy-load the heavy StreakHeatmap (561 lines) so it is split into a
  // separate chunk and only downloaded when the planning or history tab is
  // active — the only tabs that render it (#347).
  let StreakHeatmap = $state<typeof import('$lib/components/StreakHeatmap.svelte').default | null>(
    null
  );
  $effect(() => {
    if ((currentTab === 'planning' || currentTab === 'history') && !StreakHeatmap) {
      import('$lib/components/StreakHeatmap.svelte').then((m) => (StreakHeatmap = m.default));
    }
  });

  let goals = $state<Goal[]>([]);
  let tags = $state<TagType[]>([]);
  let notes = $state<Note[]>([]);
  // XP events from gamification — used for real activity timestamps
  let xpEvents = $state<{ type: string; xp: number; at: string }[]>([]);
  let currentTab = $state<'today' | 'planning' | 'history' | 'analytics' | 'editor'>('editor');
  let currentPlanningTab = $state<'WEEKLY' | 'MONTHLY' | 'ANNUAL'>('ANNUAL');
  let showAddForm = $state(false);
  let goalSearchQuery = $state('');
  let goalFilterState = $state<string | null>(null);
  let pinnedGoals = $state<Set<number>>(new Set());
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

  const TEMPORALITIES: Goal['temporality'][] = ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'];
  const TEMPORALITY_LABELS: Record<string, string> = {
    DAILY: 'Diario',
    WEEKLY: 'Semanal',
    MONTHLY: 'Mensual',
    ANNUAL: 'Anual',
  };
  const STATE_LABELS: Record<string, string> = {
    ACTIVE: 'Activo',
    PAUSED: 'Pausado',
    COMPLETED: 'Completado',
    FAILED: 'Fallido',
    CANCELLED: 'Cancelado',
  };
  const COLOR_PRESETS = GOALS_SPECIFIC_COLOR_PRESETS;

  // New goal form
  let newTitle = $state('');
  let newDescription = $state('');
  let newTargetValue = $state(1);
  let newTemporality = $state<Goal['temporality']>('DAILY');
  let newMeasurement = $state<Goal['measurement_type']>('COUNT');
  let newFailConfig = $state<Goal['fail_config']>('STATIC');
  let newFailEmoji = $state('🔴');
  let newFailIcon = $state('Activity');
  let newGoalColor = $state(DEFAULT_GOAL_COLOR);
  let newMaxAssignmentDays = $state<number | null>(null);
  let useFailIcon = $state(false);
  let newTagId = $state<number | null>(null);
  let newNoteId = $state<number | null>(null);
  let saving = $state(false);

  let _todayStr = $derived.by(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  });
  let dailyGoals = $derived(
    goals.filter((g) => g.state !== 'CANCELLED' && isAssigned(g.id, _todayStr))
  );
  let planningGoals = $derived(goals.filter((g) => g.state !== 'CANCELLED'));
  let pendingGoals = $derived(goals.filter((g) => g.pending_removal));

  let historyData = $state<any[]>([]);
  $effect(() => {
    const dataMap = new Map();
    // Procesar completados
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
    // Procesar fallidos (los fallos sobrescriben o se añaden a la visualización)
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
    historyData = Array.from(dataMap.values());
  });

  // ── History tab state ──
  const _now = new Date();
  let selectedHistoryDate = $state<string | null>(
    `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}-${String(_now.getDate()).padStart(2, '0')}`
  );

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
  let streakData = $state({ current_streak: 0, best_streak: 0 });

  onMount(async () => {
    // restore UI state immediately to prevent flash
    try {
      const savedTab = localStorage.getItem('goals.currentTab');
      if (savedTab) currentTab = savedTab as typeof currentTab;
      const savedDate = localStorage.getItem('goals.selectedPlanningDate');
      if (savedDate) selectedPlanningDate = savedDate;
      const savedHistoryDate = localStorage.getItem('goals.selectedHistoryDate');
      if (savedHistoryDate) selectedHistoryDate = savedHistoryDate;
      // if we are on planning, pre-load assignments for the selected date
      if (currentTab === 'planning' && selectedPlanningDate) {
        loadAssignmentsForDate(selectedPlanningDate).catch(logger.error);
      }
    } catch (e) {
      // ignore storage errors
    }

    const cachedGoals = getCachedData<Goal[]>('goals');
    const cachedTags = getCachedData<TagType[]>('tags');
    if (cachedGoals) goals = cachedGoals;
    if (cachedTags) tags = cachedTags;

    // Restore pinned goals from localStorage
    try {
      const saved = loadUserSettings().goalsUi;
      if (saved?.pinnedGoalIds && Array.isArray(saved.pinnedGoalIds)) {
        pinnedGoals = new Set(saved.pinnedGoalIds);
      }
    } catch {
      // ignore storage errors
    }

    try {
      // Load only essential data immediately (goals + tags)
      [goals, tags] = await Promise.all([api.goals.list(), api.tags.list()]);
      setCachedData('goals', goals);
      setCachedData('tags', tags);
    } catch (e) {
      if (goals.length === 0) {
        loadError = 'No se pudo cargar los objetivos.';
        logger.error('[goals] onMount failed:', e);
      }
    }

    // Lazy-load analytics data only when needed
    if (currentTab === 'analytics') {
      loadAnalyticsData();
    }
  });

  let analyticsLoaded = false;
  async function loadAnalyticsData() {
    if (analyticsLoaded) return;
    analyticsLoaded = true;
    try {
      [notes, streakData, xpEvents] = await Promise.all([
        api.notes.list(),
        api.goals.streak(),
        api.gamification.events(500),
      ]);
    } catch (e) {
      logger.error('[goals] loadAnalyticsData failed:', e);
    }
  }

  let addError = $state('');

  async function addGoal() {
    if (!newTitle.trim()) return;
    saving = true;
    addError = '';
    try {
      const g = await api.goals.create({
        title: newTitle.trim(),
        description: newDescription,
        target_value: newTargetValue,
        temporality: newTemporality,
        measurement_type: newMeasurement,
        fail_config: newFailConfig,
        fail_emoji: useFailIcon ? newFailIcon : newFailEmoji,
        color: newGoalColor,
        tag_id: newTagId,
        note_id: newNoteId,
        max_assignment_days: newMaxAssignmentDays,
      });
      goals = [g, ...goals];
      showAddForm = false;
      newTitle = '';
      newTargetValue = 1;
      newTagId = null;
      newNoteId = null;
      newMaxAssignmentDays = null;
    } catch (e) {
      addError = 'Error al crear el objetivo.';
    } finally {
      saving = false;
    }
  }

  async function completeGoal(id: number) {
    const result = await api.goals.complete(id);
    goals = goals.map((g) => (g.id === id ? result.goal : g));
    applyGamificationResult(result.gamification);
    showXPGain(result.gamification.xp_awarded);
  }

  async function updateGoalState(id: number, state: 'ACTIVE' | 'PAUSED' | 'CANCELLED') {
    try {
      const result = await api.goals.update(id, { state });
      goals = goals.map((g) => (g.id === id ? result : g));
    } catch (e) {
      logger.error('Error al actualizar estado:', e);
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

  // ── Analytics expandable state ──
  let showPerformanceChart = $state(true);

  // ── Dashboard State ──
  let upcomingTasks = $derived.by(() => {
    const futureAssignments: { date: string; goal: Goal }[] = [];
    const sortedDates = Object.keys(assignments)
      .filter((d) => d >= todayIso)
      .sort();

    for (const date of sortedDates) {
      for (const id of assignments[date]) {
        const goal = goals.find((g) => g.id === id);
        if (goal && goal.state !== 'COMPLETED' && goal.state !== 'FAILED') {
          if (!futureAssignments.some((a) => a.goal.id === id && a.date === date)) {
            futureAssignments.push({ date, goal });
          }
        }
      }
    }
    return futureAssignments.slice(0, 5);
  });

  let currentWeekDates = $derived.by(() => {
    const dates = [];
    const today = new Date();
    const day = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(new Date().setDate(diff));

    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      const dateStr = d.toISOString().split('T')[0];
      const isToday = dateStr === todayIso;
      const hData = historyData.find((h) => h.date === dateStr);
      dates.push({
        dateStr,
        isToday,
        dayName: ['L', 'M', 'X', 'J', 'V', 'S', 'D'][i],
        hasActivity: hData?.checked || false,
      });
    }
    return dates;
  });

  // ── Monthly map state (#790) ──
  let monthMapDate = $state(new Date());

  let monthMapCells = $derived.by(() => {
    const year = monthMapDate.getFullYear();
    const month = monthMapDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    // Leading blanks: Mon=0 .. Sun=6
    let startWeekday = firstDay.getDay() - 1;
    if (startWeekday < 0) startWeekday = 6;
    const cells: {
      dateStr: string | null;
      day: number | null;
      isToday: boolean;
      status: 'none' | 'assigned' | 'completed' | 'failed';
    }[] = [];
    for (let i = 0; i < startWeekday; i++) {
      cells.push({ dateStr: null, day: null, isToday: false, status: 'none' });
    }
    for (let d = 1; d <= lastDay.getDate(); d++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const isToday = dateStr === todayIso;
      const hData = historyData.find((h) => h.date === dateStr);
      const hasAssignment = !!(assignments[dateStr] && assignments[dateStr].length > 0);
      let status: 'none' | 'assigned' | 'completed' | 'failed' = hasAssignment
        ? 'assigned'
        : 'none';
      if (hData?.failed) status = 'failed';
      else if (hData?.checked) status = 'completed';
      cells.push({ dateStr, day: d, isToday, status });
    }
    return cells;
  });

  function prevMonth() {
    monthMapDate = new Date(monthMapDate.getFullYear(), monthMapDate.getMonth() - 1, 1);
  }
  function nextMonth() {
    monthMapDate = new Date(monthMapDate.getFullYear(), monthMapDate.getMonth() + 1, 1);
  }

  // ── Hierarchical planning helpers ──
  function getParentGoals(goalList: Goal[]) {
    return goalList.filter((g) => !g.parent_id || !goalList.some((p) => p.id === g.parent_id));
  }
  function getChildGoals(parentId: number, goalList: Goal[]) {
    return goalList.filter((g) => g.parent_id === parentId);
  }

  // Planning assignment state (frontend-only mapping date -> goal ids)
  const todayIso = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}-${String(_now.getDate()).padStart(2, '0')}`;
  let selectedPlanningDate = $state(todayIso);
  let assignments = $state<Record<string, number[]>>({});

  function getNormalizedDate(date: string, temporality: Goal['temporality']): string {
    if (!date) return date;
    const d = new Date(date + 'T12:00:00');
    if (temporality === 'DAILY') return date;
    if (temporality === 'WEEKLY') {
      const day = d.getDay();
      const diff = d.getDate() - day + (day === 0 ? -6 : 1);
      const monday = new Date(d.setDate(diff));
      return monday.toISOString().split('T')[0];
    }
    if (temporality === 'MONTHLY') return date.substring(0, 7) + '-01';
    if (temporality === 'ANNUAL') return date.substring(0, 4) + '-01-01';
    return date;
  }

  let listSortBy = $state<'recent' | 'alpha' | 'state'>('recent');

  let filteredUnassignedGoals = $derived.by(() => {
    let unassigned = goals.filter(
      (g) => g.state !== 'CANCELLED' && !isAssigned(g.id, selectedPlanningDate)
    );
    if (listSortBy === 'alpha') {
      unassigned.sort((a, b) => a.title.localeCompare(b.title));
    } else if (listSortBy === 'state') {
      const stateOrder: Record<string, number> = { ACTIVE: 1, PAUSED: 2, COMPLETED: 3, FAILED: 4 };
      unassigned.sort((a, b) => (stateOrder[a.state] || 9) - (stateOrder[b.state] || 9));
    } else {
      unassigned.sort((a, b) => b.id - a.id);
    }
    return unassigned;
  });

  function getGoalStatusOnDate(goal: Goal, dateStr: string) {
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
    return assignments[normDate] && assignments[normDate].includes(goalId);
  }

  // persist current tab and selected planning date in localStorage
  $effect(() => {
    if (typeof localStorage !== 'undefined') localStorage.setItem('goals.currentTab', currentTab);
    // Lazy-load analytics data when analytics tab is opened
    if (currentTab === 'analytics') loadAnalyticsData();
  });

  $effect(() => {
    if (selectedPlanningDate) {
      if (typeof localStorage !== 'undefined')
        localStorage.setItem('goals.selectedPlanningDate', selectedPlanningDate);
      loadAssignmentsForDate(selectedPlanningDate);
    }
    // Preload upcoming assignments for dashboard
    const today = new Date();
    for (let i = 0; i < 7; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      loadAssignmentsForDate(d.toISOString().split('T')[0]);
    }
  });

  $effect(() => {
    if (selectedHistoryDate && typeof localStorage !== 'undefined') {
      localStorage.setItem('goals.selectedHistoryDate', selectedHistoryDate);
    }
  });

  async function loadAssignmentsForDate(date: string) {
    if (!date) return;
    const datesToLoad = [
      date,
      getNormalizedDate(date, 'WEEKLY'),
      getNormalizedDate(date, 'MONTHLY'),
      getNormalizedDate(date, 'ANNUAL'),
    ];
    const uniqueDates = Array.from(new Set(datesToLoad));

    const fetchedResults = await Promise.all(
      uniqueDates.map(async (d) => {
        try {
          const res = await api.planning.getAssignments(d);
          return { date: d, ids: res.goal_ids };
        } catch (e) {
          return { date: d, ids: [] };
        }
      })
    );

    assignments = {
      ...assignments,
      ...Object.fromEntries(fetchedResults.map((r) => [r.date, r.ids])),
    };
  }

  async function assignGoalToDate(goalId: number, date: string) {
    if (!date) return;
    const goal = goals.find((g) => g.id === goalId);
    if (!goal) return;

    const normDate = getNormalizedDate(date, goal.temporality);
    assignments = { ...assignments };
    if (!assignments[normDate]) assignments[normDate] = [];
    if (!assignments[normDate].includes(goalId)) assignments[normDate].push(goalId);

    try {
      await api.planning.setAssignments(normDate, assignments[normDate]);
    } catch (e) {
      logger.error('Error saving assignment:', e);
    }
  }

  async function unassignGoalFromDate(goalId: number, date: string) {
    if (!date) return;
    const goal = goals.find((g) => g.id === goalId);
    if (!goal) return;

    const normDate = getNormalizedDate(date, goal.temporality);
    if (!assignments[normDate]) return;

    assignments = {
      ...assignments,
      [normDate]: assignments[normDate].filter((id) => id !== goalId),
    };
    try {
      await api.planning.setAssignments(normDate, assignments[normDate]);
    } catch (e) {
      logger.error('Error saving assignment removal:', e);
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
    goto(`/goals/${goal.id}`);
  }

  // ── Advanced Analytics Calculations ──
  let completedGoalsCount = $derived(
    goals.filter((g) => g.state === 'COMPLETED' || g.is_completed).length
  );
  let failedGoalsCount = $derived(goals.filter((g) => g.state === 'FAILED').length);
  let successRate = $derived(
    completedGoalsCount + failedGoalsCount > 0
      ? Math.round((completedGoalsCount / (completedGoalsCount + failedGoalsCount)) * 100)
      : 0
  );

  let completionsByDay = $derived.by(() => {
    const days = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
    const counts = [0, 0, 0, 0, 0, 0, 0];
    goals
      .filter((g) => (g.state === 'COMPLETED' || g.is_completed) && g.completed_at)
      .forEach((g) => {
        const dateParts = g.completed_at!.split('T')[0].split('-');
        const d = new Date(Number(dateParts[0]), Number(dateParts[1]) - 1, Number(dateParts[2]));
        counts[d.getDay()]++;
      });
    return days.map((label, i) => ({ label, value: counts[i] }));
  });

  let topTagsBySuccess = $derived.by(() => {
    const tagMap = new Map();
    goals
      .filter((g) => (g.state === 'COMPLETED' || g.is_completed) && (g.tag_id || g.note_id))
      .forEach((g) => {
        let name = 'Sin Etiqueta';
        if (g.tag_id) {
          name = tags.find((t) => t.id === g.tag_id)?.name || 'Sin Etiqueta';
        } else if (g.note_id) {
          name = notes.find((n) => n.id === g.note_id)?.title || 'Nota';
        }
        tagMap.set(name, (tagMap.get(name) || 0) + 1);
      });
    return Array.from(tagMap.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  });

  let progressOverview = $derived.by(() => {
    return ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'].map((temp) => {
      const tempGoals = goals.filter((g) => g.temporality === temp && g.state !== 'CANCELLED');
      const avgProgress =
        tempGoals.length > 0
          ? Math.round(
              tempGoals.reduce(
                (acc, g) =>
                  acc + (g.state === 'COMPLETED' || g.is_completed ? 100 : g.progress_pct || 0),
                0
              ) / tempGoals.length
            )
          : 0;
      const completed = tempGoals.filter((g) => g.state === 'COMPLETED' || g.is_completed).length;
      const failed = tempGoals.filter((g) => g.state === 'FAILED').length;
      return { temp, avgProgress, count: tempGoals.length, completed, failed };
    });
  });

  let prediction = $derived.by(() => {
    const nowMs = Date.now();
    const MS_PER_DAY = 1000 * 60 * 60 * 24;
    const last7Start = nowMs - 7 * MS_PER_DAY;
    const prev7Start = nowMs - 14 * MS_PER_DAY;

    const completionEvents = xpEvents.filter((e) => e.type === 'goal_completed');

    const countCompletionsInRange = (startMs: number, endMs: number) => {
      if (completionEvents.length > 0) {
        return completionEvents.filter((e) => {
          const t = new Date(e.at).getTime();
          return t >= startMs && t < endMs;
        }).length;
      }
      return goals.filter(
        (g) =>
          (g.state === 'COMPLETED' || g.is_completed) &&
          g.completed_at &&
          new Date(g.completed_at).getTime() >= startMs &&
          new Date(g.completed_at).getTime() < endMs
      ).length;
    };

    const last7 = countCompletionsInRange(last7Start, nowMs);
    const prev7 = countCompletionsInRange(prev7Start, last7Start);

    const trend = last7 >= prev7 ? 'UP' : 'DOWN';
    const percentChange =
      prev7 > 0 ? Math.round(((last7 - prev7) / prev7) * 100) : last7 > 0 ? 100 : 0;

    return {
      trend,
      percentChange,
      estimateNextMonth: Math.round(last7 * 4),
      last7Days: last7,
      prev7Days: prev7,
    };
  });

  let dailyActivity = $derived.by(() => {
    const results: { date: string; label: string; completed: number; failed: number }[] = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      const dateStr = `${d.getFullYear()}-${m}-${day}`;
      const comps = goals.filter(
        (g) => (g.state === 'COMPLETED' || g.is_completed) && g.completed_at?.startsWith(dateStr)
      ).length;
      const fails = goals.filter(
        (g) => g.state === 'FAILED' && g.updated_at?.startsWith(dateStr)
      ).length;
      results.push({
        date: dateStr,
        label: `${d.getDate()}/${d.getMonth() + 1}`,
        completed: comps,
        failed: fails,
      });
    }
    return results;
  });

  let maxDaily = $derived(Math.max(1, ...dailyActivity.flatMap((d) => [d.completed, d.failed])));

  let activityTab = $state<'horas' | 'dias'>('horas');
  let activityDayOfWeek = $state(new Date().getDay());
  const daysOfWeek = ['Domingos', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábados'];

  function prevActivityDay() {
    activityDayOfWeek = (activityDayOfWeek - 1 + 7) % 7;
  }
  function nextActivityDay() {
    activityDayOfWeek = (activityDayOfWeek + 1) % 7;
  }

  function formatHourLabel(hour: number) {
    const safeHour = ((hour % 24) + 24) % 24;
    if ($use24HourClock) {
      return `${String(safeHour).padStart(2, '0')}:00`;
    }
    const d = new Date(2020, 0, 1, safeHour, 0, 0, 0);
    return d.toLocaleTimeString(getLocale(), {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  }

  function formatHourRange(startHour: number, endHour: number) {
    return `${formatHourLabel(startHour)} - ${formatHourLabel(endHour)}`;
  }

  // Activity charts use XP events (written at exact user-action time) instead of
  // goals[*].completed_at which is set by the backend evaluate_active_goals() batch
  // call — meaning all goals get the same timestamp (the moment the page loaded).
  let activityBinnedByHour = $derived.by(() => {
    const bins = new Array(8).fill(0);
    // Use goal_completed XP events for real user-action timestamps
    const completionEvents = xpEvents.filter((e) => e.type === 'goal_completed');
    completionEvents.forEach((e) => {
      const d = new Date(e.at);
      if (d.getDay() === activityDayOfWeek) {
        const hour = d.getHours();
        if (!isNaN(hour)) {
          const binIndex = Math.floor(hour / 3);
          if (binIndex >= 0 && binIndex < 8) bins[binIndex]++;
        }
      }
    });
    // Fallback: if no XP events exist yet, try goals completed_at (legacy)
    if (completionEvents.length === 0) {
      goals.forEach((g) => {
        if ((g.state === 'COMPLETED' || g.is_completed) && g.completed_at) {
          const d = new Date(g.completed_at);
          if (d.getDay() === activityDayOfWeek) {
            const hour = d.getHours();
            if (!isNaN(hour)) {
              const binIndex = Math.floor(hour / 3);
              if (binIndex >= 0 && binIndex < 8) bins[binIndex]++;
            }
          }
        }
      });
    }
    return bins.map((c, i) => {
      const startHour = i * 3;
      const endHour = (startHour + 3) % 24;
      return {
        hour: startHour,
        label: formatHourLabel(startHour),
        rangeLabel: formatHourRange(startHour, endHour),
        val: c,
        pct: Math.min(1, c / 5),
      };
    });
  });

  let activityByDay = $derived.by(() => {
    const days = new Array(7).fill(0);
    const completionEvents = xpEvents.filter((e) => e.type === 'goal_completed');
    completionEvents.forEach((e) => {
      const d = new Date(e.at);
      const day = d.getDay();
      if (!isNaN(day) && day >= 0 && day < 7) {
        days[day]++;
      }
    });
    // Fallback: if no XP events exist yet, use goals completed_at
    if (completionEvents.length === 0) {
      goals.forEach((g) => {
        if ((g.state === 'COMPLETED' || g.is_completed) && g.completed_at) {
          const d = new Date(g.completed_at);
          const day = d.getDay();
          if (!isNaN(day) && day >= 0 && day < 7) {
            days[day]++;
          }
        }
      });
    }
    return days.map((c, i) => ({
      label: daysOfWeek[i].substring(0, 3),
      val: c,
      pct: Math.min(1, c / 5),
    }));
  });

  let radarData = $derived.by(() => {
    const categories = topTagsBySuccess.slice(0, 6);
    while (categories.length > 0 && categories.length < 3) {
      categories.push({ name: '', count: 0 });
    }
    if (categories.length === 0) return [];
    const maxVal = Math.max(...categories.map((c) => c.count)) || 1;
    return categories.map((c, i) => {
      const angle = (Math.PI * 2 * i) / categories.length - Math.PI / 2;
      return {
        name: c.name,
        value: c.count,
        pct: c.count / maxVal,
        x: 50 + 40 * Math.cos(angle),
        y: 50 + 40 * Math.sin(angle),
        labelX: 50 + 50 * Math.cos(angle),
        labelY: 50 + 50 * Math.sin(angle),
        angle,
      };
    });
  });

  let debtData = $derived.by(() => {
    const dGoals = goals.filter(
      (g) => (g.fail_config === 'ROLLOVER' || g.fail_config === 'SNOWBALL') && g.state === 'ACTIVE'
    );
    const total = dGoals.reduce((acc, g) => acc + Math.max(0, g.target_value - g.current_value), 0);
    return {
      goals: dGoals
        .map((g) => ({ title: g.title, debt: Math.max(0, g.target_value - g.current_value) }))
        .sort((a, b) => b.debt - a.debt)
        .slice(0, 5),
      total,
    };
  });

  let funnelData = $derived.by(() => {
    const total = goals.length || 1;
    const completed = goals.filter((g) => g.state === 'COMPLETED' || g.is_completed).length;
    const failed = goals.filter((g) => g.state === 'FAILED').length;
    const active = goals.filter((g) => g.state === 'ACTIVE').length;
    const cancelled = goals.filter((g) => g.state === 'CANCELLED' || g.state === 'PAUSED').length;
    return [
      { label: 'Iniciados', value: total, color: 'var(--text-disabled)' },
      { label: 'Activos', value: active, color: 'var(--xp)' },
      { label: 'Completados', value: completed, color: 'var(--success)' },
      { label: 'Abandonados', value: cancelled + failed, color: 'var(--error)' },
    ];
  });

  function getGoalColor(goal: Goal): string {
    const colorMap: Record<string, string> = {
      DAILY: 'var(--today)',
      WEEKLY: TEMPORALITY_COLORS['WEEKLY'],
      MONTHLY: 'var(--link)',
      ANNUAL: TEMPORALITY_COLORS['ANNUAL'],
      ACTIVE: 'var(--today)',
      COMPLETED: 'var(--target)',
      PAUSED: 'var(--error)',
      CANCELLED: 'var(--error)',
    };

    if (goal.state === 'ACTIVE' || goal.state === 'PAUSED' || goal.state === 'CANCELLED') {
      return colorMap[goal.state] || goal.color || 'var(--border)';
    }
    if (goal.state === 'COMPLETED' || goal.is_completed) {
      return colorMap['COMPLETED'];
    }
    if (goal.temporality) {
      return colorMap[goal.temporality];
    }
    return goal.color || 'var(--border)';
  }
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key === 'Escape') {
      if (deleteConfirm !== null) {
        deleteConfirm = null;
        return;
      }
      showAddForm = false;
    }
  }}
/>

<div class="goals-page">
  {#if loadError}
    <div class="error-banner">{loadError}</div>
  {/if}

  <div class="goals-header">
    <div class="tabs">
      <button
        class="tab"
        class:active={currentTab === 'editor'}
        onclick={() => (currentTab = 'editor')}
      >
        <Pencil size={14} /> Editor
      </button>
      <button
        class="tab"
        class:active={currentTab === 'today'}
        onclick={() => (currentTab = 'today')}
      >
        <LayoutDashboard size={14} /> Inicio
      </button>
      <button
        class="tab"
        class:active={currentTab === 'planning'}
        onclick={() => (currentTab = 'planning')}
      >
        <Clock size={14} /> Planificación
      </button>
      <button
        class="tab"
        class:active={currentTab === 'history'}
        onclick={() => (currentTab = 'history')}
      >
        <Calendar size={14} /> Historial
      </button>
      <button
        class="tab"
        class:active={currentTab === 'analytics'}
        onclick={() => (currentTab = 'analytics')}
      >
        <ChartColumn size={14} /> Análisis
      </button>
    </div>
  </div>

  <div
    class="goals-body"
    class:full-width={currentTab === 'analytics' ||
      currentTab === 'history' ||
      currentTab === 'planning' ||
      currentTab === 'today' ||
      currentTab === 'editor'}
  >
    {#if currentTab === 'today'}
      <div class="tab-content fade-in today-layout">
        <div class="dashboard-main-col">
          <div class="today-header">
            <h3 class="section-title" style="margin: 0;">{$t('goalsPage.dayGoals')}</h3>
            <button
              class="btn btn-primary new-goal-cta new-goal-cta-inline"
              onclick={() => (showAddForm = !showAddForm)}
            >
              <Plus size={16} /> Nuevo Objetivo
            </button>
          </div>
          {#if dailyGoals.length === 0}
            <div class="empty-state">{$t('goalsPage.noActiveGoals')}</div>
          {/if}
          {#each dailyGoals as goal (goal.id)}
            <div
              class="goal-card"
              class:completed={goal.state === 'COMPLETED' || goal.is_completed}
              class:failed={goal.state === 'FAILED'}
              class:paused={goal.state === 'PAUSED'}
              style="border-left: 3px solid {getGoalColor(goal)}"
            >
              <div class="goal-main">
                <div class="goal-title">
                  <button
                    class="btn btn-ghost"
                    style="font-size: inherit; font-weight: inherit; padding: 0; margin: 0; height: auto; color: inherit;"
                    title={$t('goalsPage.editInEditor')}
                    onclick={(e) => {
                      e.stopPropagation();
                      goto(`/goals/${goal.id}`);
                    }}
                  >
                    {#if goal.fail_emoji}
                      <span
                        class="emoji-badge"
                        style="display:flex; align-items:center; margin-right:8px;"
                      >
                        <StreakIcon name={goal.fail_emoji} size={16} color={getGoalColor(goal)} />
                      </span>
                    {/if}
                    {goal.title}
                  </button>
                  {#if goal.state === 'PAUSED'}
                    <span class="state-badge paused-badge">PAUSADO</span>
                  {/if}
                </div>
                <div class="goal-meta">
                  <span
                    class="tag-chip"
                    style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(
                      goal
                    )}; color: {getGoalColor(goal)};"
                    >{TEMPORALITY_LABELS[goal.temporality] || goal.temporality}</span
                  >
                  {#if goal.state === 'COMPLETED' || goal.is_completed}
                    <span
                      class="status-badge success"
                      style="background: color-mix(in srgb, var(--success) 10%, transparent); color: var(--success); border: 1px solid color-mix(in srgb, var(--success) 20%, transparent);"
                      >{$t('goalsPage.completed')}</span
                    >
                  {:else if goal.state === 'FAILED'}
                    <span
                      class="status-badge error"
                      style="background: color-mix(in srgb, var(--error) 10%, transparent); color: var(--error); border: 1px solid color-mix(in srgb, var(--error) 20%, transparent);"
                      >{$t('goalsPage.failed')}</span
                    >
                  {/if}
                  {#if goal.note_id}
                    <span
                      class="tag-chip"
                      style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(
                        goal
                      )}; color: {getGoalColor(goal)};"
                      >{notes.find((n) => n.id === goal.note_id)?.title || 'Nota vinculada'}</span
                    >
                  {:else if goal.tag_id}
                    <span
                      class="tag-chip"
                      style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(
                        goal
                      )}; color: {getGoalColor(goal)};"
                      >{tags.find((t) => t.id === goal.tag_id)?.name}</span
                    >
                  {/if}
                  {#if goal.fail_config !== 'STATIC'}
                    <span class="config-badge">{formatFailConfig(goal.fail_config)}</span>
                  {/if}
                  {#if goal.measurement_type !== 'COUNT'}
                    <span
                      class="config-badge"
                      style="background:transparent; border: 1px solid var(--border);"
                      >{goal.measurement_type}</span
                    >
                  {/if}
                  {#if goal.max_assignment_days}
                    <span
                      class="config-badge"
                      style="background: color-mix(in srgb, var(--link) 10%, transparent); color: var(--text-muted); border: 1px solid color-mix(in srgb, var(--link) 20%, transparent);"
                      >{$t('goalsPage.limit', { values: { days: goal.max_assignment_days } })}</span
                    >
                  {/if}
                </div>
                {#if goal.description}
                  <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                    {goal.description}
                  </div>
                {/if}
              </div>
              <div class="goal-progress">
                <div class="progress-meta">
                  <span class="mono caption">
                    {#if goal.state === 'COMPLETED' || goal.is_completed}
                      {goal.target_value}/{goal.target_value}
                    {:else if goal.measurement_type === 'BOOLEAN'}
                      {goal.current_value >= 1 ? 'Sí' : 'No'}
                    {:else if goal.measurement_type === 'PERCENT'}
                      {goal.current_value}%
                    {:else}
                      {goal.current_value}/{goal.target_value}
                    {/if}
                  </span>
                  <span class="caption"
                    >{goal.state === 'COMPLETED' || goal.is_completed
                      ? 100
                      : goal.progress_pct}%</span
                  >
                </div>
                <div class="progress-track" style="height: 4px;">
                  <div
                    class="progress-fill"
                    style="width:{goal.state === 'COMPLETED' || goal.is_completed
                      ? 100
                      : goal.progress_pct}%"
                  ></div>
                </div>
              </div>
              <div class="goal-actions">
                {#if goal.state === 'ACTIVE'}
                  <button
                    class="btn btn-ghost text-muted"
                    title={$t('goalsPage.pause')}
                    aria-label={$t('goalsPage.pauseGoal')}
                    onclick={() => updateGoalState(goal.id, 'PAUSED')}
                  >
                    <Pause size={14} />
                  </button>
                  <button
                    class="btn btn-ghost text-success"
                    title={$t('goalsPage.complete')}
                    aria-label={$t('goalsPage.completeGoal')}
                    onclick={() => completeGoal(goal.id)}
                  >
                    <Check size={14} />
                  </button>
                {:else if goal.state === 'PAUSED'}
                  <button
                    class="btn btn-ghost text-muted"
                    title={$t('goalsPage.resume')}
                    aria-label={$t('goalsPage.resumeGoal')}
                    onclick={() => updateGoalState(goal.id, 'ACTIVE')}
                  >
                    <Play size={14} />
                  </button>
                {/if}
                {#if goal.state !== 'COMPLETED' && goal.state !== 'FAILED'}
                  <button
                    class="btn btn-ghost text-muted"
                    title={$t('goalsPage.cancel')}
                    aria-label={$t('goalsPage.cancelGoal')}
                    onclick={() => updateGoalState(goal.id, 'CANCELLED')}
                  >
                    <Ban size={14} />
                  </button>
                {/if}
                {#if deleteConfirm === goal.id}
                  <button class="btn btn-ghost text-danger" onclick={() => deleteGoal(goal.id)}
                    >¿Eliminar?</button
                  >
                  <button class="btn btn-ghost text-muted" onclick={() => (deleteConfirm = null)}
                    >{$t('goalsPage.cancel')}</button
                  >
                {:else}
                  <button
                    class="btn btn-ghost text-muted"
                    title={$t('goalsPage.delete')}
                    aria-label={$t('goalsPage.deleteGoal')}
                    onclick={() => deleteGoal(goal.id)}>×</button
                  >
                {/if}
                <button
                  class="btn btn-ghost text-muted"
                  title={$t('goalsPage.edit')}
                  aria-label={$t('goalsPage.editGoal')}
                  onclick={() => openGoalEditor(goal)}
                >
                  <Pencil size={13} />
                </button>
              </div>
            </div>
          {/each}

          <!-- Next Assigned Tasks -->
          <h3 class="section-title" style="margin-top: 24px;">
            {$t('goalsPage.upcomingAssigned')}
          </h3>
          <div class="history-goal-list" style="width:100%">
            {#if upcomingTasks.length === 0}
              <div class="empty-state">{$t('goalsPage.noUpcomingTasks')}</div>
            {/if}
            {#each upcomingTasks as task}
              {@const g = task.goal}
              <button
                class="goal-card"
                style="text-align: left; cursor: pointer; height: fit-content; border-left: 3px solid {getGoalColor(
                  g
                )}; display:flex; align-items:center; width: 100%;"
                onclick={() => goto(`/goals/${g.id}`)}
              >
                <div class="goal-main" style="flex: 1;">
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
                    <span class="config-badge">{task.date}</span>
                    <span
                      class="tag-chip"
                      style="background: {getGoalColor(g)}20; border: 1px solid {getGoalColor(
                        g
                      )}; color: {getGoalColor(g)};"
                      >{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span
                    >
                  </div>
                </div>
              </button>
            {/each}
          </div>
        </div>

        <!-- Dashboard Right Column -->
        <div class="dashboard-side-col">
          <div class="dash-card week-map-card">
            <div class="dash-card-header">
              <Calendar size={14} />
              <span>{$t('goalsPage.weekMap')}</span>
            </div>
            <div style="display: flex; gap: 6px; justify-content: space-between; margin-top: 12px;">
              {#each currentWeekDates as day}
                <button
                  class="week-day-box"
                  title={day.dateStr}
                  onclick={() => {
                    currentTab = 'history';
                    selectedHistoryDate = day.dateStr;
                  }}
                  style="flex: 1; aspect-ratio: 1; border-radius: 4px; border: 1px solid {day.isToday
                    ? 'var(--today)'
                    : 'var(--border)'}; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; background: {day.isToday
                    ? 'var(--today)'
                    : day.hasActivity
                      ? 'var(--success)'
                      : 'var(--surface)'}; color: {day.isToday
                    ? '#000'
                    : day.hasActivity
                      ? 'var(--bg)'
                      : 'var(--text-muted)'}; opacity: 1; {day.isToday
                    ? 'box-shadow: 0 0 0 2px var(--today);'
                    : ''}"
                >
                  <span style="font-size: 10px; font-weight: bold; margin-bottom: 2px;"
                    >{day.dayName}</span
                  >
                  <span style="font-size: 12px; font-weight: {day.isToday ? 'bold' : 'normal'};"
                    >{day.dateStr.split('-')[2]}</span
                  >
                </button>
              {/each}
            </div>
          </div>

          <!-- Monthly map (#790) -->
          <div class="dash-card month-map-card">
            <div class="dash-card-header month-map-header">
              <Calendar size={14} />
              <span
                >{monthMapDate.toLocaleDateString(undefined, {
                  month: 'long',
                  year: 'numeric',
                })}</span
              >
              <div class="month-map-nav">
                <button
                  class="month-nav-btn"
                  onclick={prevMonth}
                  aria-label={$t('goalsPage.prevDay')}>‹</button
                >
                <button
                  class="month-nav-btn"
                  onclick={nextMonth}
                  aria-label={$t('goalsPage.nextDay')}>›</button
                >
              </div>
            </div>
            <div class="month-map-grid">
              {#each ['L', 'M', 'X', 'J', 'V', 'S', 'D'] as dn}
                <span class="month-map-dow">{dn}</span>
              {/each}
              {#each monthMapCells as cell}
                {#if cell.dateStr}
                  <button
                    class="month-map-cell month-{cell.status}"
                    class:month-today={cell.isToday}
                    onclick={() => {
                      currentTab = 'planning';
                      selectedPlanningDate = cell.dateStr!;
                    }}
                    title={cell.dateStr}
                  >
                    {cell.day}
                  </button>
                {:else}
                  <span class="month-map-cell month-empty"></span>
                {/if}
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}

    {#if currentTab === 'planning'}
      <div class="tab-content fade-in planning-3col">
        <!-- Left: All Goals List (click => assign to selectedPlanningDate) -->
        <div class="planning-left-col history-detail-col">
          <div class="history-detail-header">
            <div class="history-detail-date" style="text-transform:none;">
              {$t('goalsPage.goalList')}
            </div>
          </div>
          <div class="sort-control-centered">
            <select class="input sort-select-square" bind:value={listSortBy}>
              <option value="recent">{$t('goalsPage.sortRecent')}</option>
              <option value="alpha">{$t('goalsPage.sortAlpha')}</option>
              <option value="state">{$t('goalsPage.sortState')}</option>
            </select>
          </div>

          <div class="history-goal-list" style="width: 100%;">
            {#each filteredUnassignedGoals as goal (goal.id)}
              <button
                class="goal-card"
                style="text-align: left; cursor: pointer; height: fit-content; border-left: 3px solid {getGoalColor(
                  goal
                )}; display: flex; align-items:center; justify-content:space-between; width: 100%;"
                onclick={() => assignGoalToDate(goal.id, selectedPlanningDate)}
                title={$t('goalsPage.assignToDay')}
              >
                <div class="goal-main" style="flex:1;">
                  <div class="goal-title">
                    {#if goal.fail_emoji}
                      <span
                        class="emoji-badge"
                        style="display:flex; align-items:center; margin-right:8px;"
                      >
                        <StreakIcon name={goal.fail_emoji} size={16} color={getGoalColor(goal)} />
                      </span>
                    {/if}
                    {goal.title}
                  </div>
                  <div class="goal-meta">
                    <span
                      class="tag-chip"
                      style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(
                        goal
                      )}; color: {getGoalColor(goal)};"
                      >{TEMPORALITY_LABELS[goal.temporality] || goal.temporality}</span
                    >
                    {#if goal.state === 'PAUSED'}
                      <span
                        class="status-badge"
                        style="background: color-mix(in srgb, var(--text-primary) 5%, transparent); color: var(--text-muted); border: 1px solid color-mix(in srgb, var(--text-primary) 10%, transparent);"
                        >{$t('goalsPage.paused')}</span
                      >
                    {/if}
                    {#if goal.max_assignment_days}
                      <span
                        class="config-badge"
                        style="margin-left: 8px; background: color-mix(in srgb, var(--link) 10%, transparent); color: var(--text-muted); border: 1px solid color-mix(in srgb, var(--link) 20%, transparent);"
                        >{$t('goalsPage.limit', {
                          values: { days: goal.max_assignment_days },
                        })}</span
                      >
                    {/if}
                  </div>
                </div>
                <div style="display:flex; gap:6px;">
                  <span class="btn btn-ghost text-muted" title={$t('goalsPage.assign')}
                    ><ChevronRight size={14} /></span
                  >
                </div>
              </button>
            {/each}
          </div>
        </div>

        <!-- Center: Calendar (fixed year view, allow future months) -->
        <div class="planning-center-col history-detail-col">
          <div class="history-detail-header">
            <span class="section-title" style="margin:0;">{$t('goalsPage.calendar')}</span>
          </div>
          <div class="history-heatmap-wrap">
            {#if StreakHeatmap}
              <svelte:component
                this={StreakHeatmap}
                history={historyData}
                color="var(--success)"
                selectedDate={selectedPlanningDate}
                onselect={(date) => (selectedPlanningDate = date)}
                maxFutureMonths={1200}
              />
            {/if}
          </div>
        </div>

        <!-- Right: Assigned for selected date -->
        <div class="planning-right-col history-detail-col">
          <div class="history-detail-header">
            <div class="history-detail-date" style="text-transform:none;">
              {$t('goalsPage.assignedOn', { values: { date: selectedPlanningDate } })}
            </div>
          </div>

          <div class="history-goal-list" style="width:100%">
            {#each ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'] as temp}
              {@const normDate = getNormalizedDate(
                selectedPlanningDate,
                temp as 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'ANNUAL'
              )}
              {@const assignedIds = assignments[normDate] || []}
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
                        : 'Año'}
                </div>
                {#each filteredGoals as g (g.id)}
                  {@const status = getGoalStatusOnDate(g, selectedPlanningDate)}
                  <div
                    class="goal-card"
                    class:completed={status === 'COMPLETED'}
                    class:failed={status === 'FAILED'}
                    style="border-left: 3px solid {status === 'FAILED'
                      ? 'var(--error)'
                      : status === 'COMPLETED'
                        ? 'var(--success)'
                        : getGoalColor(g)}; display:flex; align-items:center;"
                  >
                    <div style="display:flex; gap:6px; margin-right: 8px;">
                      <button
                        class="btn btn-ghost text-muted"
                        style="padding: 4px;"
                        onclick={() => unassignGoalFromDate(g.id, selectedPlanningDate)}
                        title={$t('goalsPage.remove')}
                        aria-label={$t('goalsPage.remove')}><ChevronLeft size={14} /></button
                      >
                    </div>
                    <div class="goal-main" style="flex: 1;">
                      <div class="goal-title">
                        {#if g.fail_emoji}
                          <span
                            class="emoji-badge"
                            style="display:flex; align-items:center; margin-right:8px;"
                          >
                            <StreakIcon
                              name={g.fail_emoji}
                              size={16}
                              color={status === 'FAILED'
                                ? 'var(--error)'
                                : status === 'COMPLETED'
                                  ? 'var(--success)'
                                  : getGoalColor(g)}
                            />
                          </span>
                        {/if}
                        {g.title}
                      </div>
                      <div class="goal-meta">
                        <span
                          class="tag-chip"
                          style="background: {getGoalColor(g)}20; border: 1px solid {getGoalColor(
                            g
                          )}; color: {getGoalColor(g)};"
                          >{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span
                        >
                        {#if status === 'COMPLETED'}
                          <span class="status-badge success">{$t('goalsPage.completed')}</span>
                        {:else if status === 'FAILED'}
                          <span class="status-badge error">{$t('goalsPage.failed')}</span>
                        {/if}
                        {#if g.max_assignment_days}
                          <span
                            class="config-badge"
                            style="margin-left: 8px; background: color-mix(in srgb, var(--link) 10%, transparent); color: var(--text-muted); border: 1px solid color-mix(in srgb, var(--link) 20%, transparent);"
                            >{$t('goalsPage.limit', {
                              values: { days: g.max_assignment_days },
                            })}</span
                          >
                        {/if}
                      </div>
                    </div>
                  </div>
                {/each}
              {/if}
            {/each}

            {#if !(['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'] as const).some( (temp) => (assignments[getNormalizedDate(selectedPlanningDate, temp as 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'ANNUAL')] || []).some((id) => goals.find((g) => g.id === id)?.temporality === temp) )}
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
          </div>
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
                <svelte:component
                  this={StreakHeatmap}
                  history={historyData}
                  color="var(--success)"
                  selectedDate={selectedHistoryDate}
                  onselect={(date) => (selectedHistoryDate = date)}
                />
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
                          style="background: {getGoalColor(g)}20; border: 1px solid {getGoalColor(
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

    {#if currentTab === 'analytics'}
      <div class="tab-content fade-in full-height-dashboard">
        <!-- Main Stats Bar -->
        <div class="stats-top-bar">
          <div class="stb-item">
            <Trophy size={16} class="text-xp" />
            <div style="display:flex; flex-direction:column; gap:2px;">
              <span class="stb-val text-success">{completedGoalsCount}</span>
              <span class="stb-label">{$t('goalsPage.completedLabel')}</span>
            </div>
          </div>
          <div class="stb-item">
            <X size={16} class="text-error" />
            <div style="display:flex; flex-direction:column; gap:2px;">
              <span class="stb-val text-error">{failedGoalsCount}</span>
              <span class="stb-label">{$t('goalsPage.failedLabel')}</span>
            </div>
          </div>
          <div
            class="stb-item"
            style="flex: 1; flex-direction: column; align-items: stretch; justify-content: center; gap: 8px;"
          >
            <div style="display:flex; justify-content:space-between; align-items: flex-end;">
              <span class="stb-label">{$t('goalsPage.globalEffectiveness')}</span>
              <span class="stb-val" style="line-height: 1;">{successRate}%</span>
            </div>
            <div class="success-meter" style="margin-top: 0;">
              <div class="meter-fill" style="width: {successRate}%"></div>
            </div>
          </div>
        </div>

        <div class="dashboard-grid">
          <div class="dash-card prediction-card">
            <div class="dash-card-header">
              <TrendingUp size={16} />
              <span>{$t('goalsPage.predictionTrend')}</span>
              <span class="pred-period-badge">30 días</span>
            </div>
            <div class="prediction-hero">
              <div class="bar-chart-container">
                {#if dailyActivity.every((d) => d.completed === 0 && d.failed === 0)}
                  <div class="bar-empty-state">
                    <TrendingUp size={24} style="opacity:0.2" />
                    <span>{$t('goalsPage.insufficientDataYet')}</span>
                    <small>{$t('goalsPage.completeOrFailHint')}</small>
                  </div>
                {:else}
                  <svg viewBox="0 0 420 130" class="bar-svg" preserveAspectRatio="xMidYMid meet">
                    <defs>
                      <linearGradient id="compGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="var(--success)" stop-opacity="0.7" />
                        <stop offset="100%" stop-color="var(--success)" stop-opacity="0.2" />
                      </linearGradient>
                      <linearGradient id="failGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="var(--error)" stop-opacity="0.7" />
                        <stop offset="100%" stop-color="var(--error)" stop-opacity="0.2" />
                      </linearGradient>
                    </defs>

                    {#each dailyActivity as day, i}
                      {@const barW = 420 / dailyActivity.length}
                      {@const barX = i * barW}
                      {@const compH = (day.completed / maxDaily) * 100}
                      {@const failH = (day.failed / maxDaily) * 100}
                      {@const compY = 115 - compH}
                      {@const failY = 115 - compH - failH}

                      {#if day.failed > 0}
                        <rect
                          x={barX + 2}
                          y={failY}
                          width={barW * 0.35}
                          height={failH}
                          fill="url(#failGrad)"
                          rx="2"
                        />
                      {/if}
                      {#if day.completed > 0}
                        <rect
                          x={barX + barW * 0.5 + 1}
                          y={compY}
                          width={barW * 0.35}
                          height={compH}
                          fill="url(#compGrad)"
                          rx="2"
                        />
                      {/if}

                      {#if i % 2 === 0 || i === dailyActivity.length - 1}
                        <text
                          x={barX + barW / 2}
                          y="124"
                          font-size="6"
                          fill="var(--text-muted)"
                          text-anchor="middle"
                          font-family="var(--font-mono)">{day.label}</text
                        >
                      {/if}
                    {/each}

                    <line
                      x1="0"
                      y1="115"
                      x2="420"
                      y2="115"
                      stroke="var(--border)"
                      stroke-width="0.5"
                      opacity="0.3"
                    />
                  </svg>

                  <div class="bar-legend">
                    <span class="legend-item"
                      ><span class="legend-dot" style="background:var(--success)"></span> Completados</span
                    >
                    <span class="legend-item"
                      ><span class="legend-dot" style="background:var(--error)"></span> Fallados</span
                    >
                  </div>
                {/if}
              </div>

              <div class="prediction-stats-row">
                <div class="trend-summary">
                  <div class="trend-icon-wrap {prediction.trend.toLowerCase()}">
                    {#if prediction.trend === 'UP'}
                      <TrendingUp size={14} />
                    {:else}
                      <TrendingDown size={14} />
                    {/if}
                    <span class="trend-pct"
                      >{prediction.percentChange > 0 ? '+' : ''}{prediction.percentChange}%</span
                    >
                  </div>
                  <span class="trend-label">vs semana anterior</span>
                </div>
                <div class="prediction-kpis">
                  <div class="pred-kpi">
                    <span class="pred-lab">{$t('goalsPage.last7d')}</span>
                    <span class="pred-val">{prediction.last7Days} ✓</span>
                  </div>
                  <div class="pred-kpi">
                    <span class="pred-lab">{$t('goalsPage.next30d')}</span>
                    <span class="pred-val">~{prediction.estimateNextMonth} ✓</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="dash-card weekday-card">
            <div class="dash-card-header">
              <Activity size={16} />
              <span>{$t('goalsPage.activityByDay')}</span>
            </div>
            <div class="weekday-chart">
              {#each completionsByDay as day}
                {@const maxVal = Math.max(...completionsByDay.map((d) => d.value)) || 1}
                {@const intensity = day.value > 0 ? Math.max(30, (day.value / maxVal) * 100) : 0}
                <div class="day-col">
                  <span
                    class="day-val"
                    style="color: {day.value > 0 ? 'var(--text-primary)' : 'var(--text-disabled)'}"
                    >{day.value}</span
                  >
                  <div class="day-bar-wrap">
                    <div
                      class="day-bar"
                      style="height: {day.value > 0
                        ? Math.max(8, intensity)
                        : 0}%; background: {day.value > 0
                        ? `color-mix(in srgb, var(--xp) ${intensity}%, transparent)`
                        : 'transparent'}; border: {day.value === 0
                        ? '1px dashed var(--border)'
                        : 'none'};"
                    ></div>
                  </div>
                  <span class="day-label">{day.label}</span>
                </div>
              {/each}
            </div>
          </div>

          <div class="dash-card temporality-card">
            <div class="dash-card-header">
              <Target size={16} />
              <span>{$t('goalsPage.effectivenessByPeriod')}</span>
            </div>
            <div class="temporality-rows">
              {#each progressOverview as p}
                <div class="temp-row">
                  <div class="temp-info">
                    <span class="temp-name">{TEMPORALITY_LABELS[p.temp] || p.temp}</span>
                    <span class="temp-stats">
                      <span class="text-success">{p.completed} ✓</span> /
                      <span class="text-error">{p.failed} ✗</span>
                    </span>
                  </div>
                  <div
                    class="temp-bar-wrapper"
                    style="display: flex; align-items: center; gap: 8px;"
                  >
                    <div class="temp-bar-container" style="flex: 1;">
                      {#if p.completed + p.failed > 0}
                        <div
                          class="temp-bar"
                          style="width: {(p.completed / (p.completed + p.failed)) *
                            100}%; background: var(--success);"
                        ></div>
                        <div
                          class="temp-bar"
                          style="width: {(p.failed / (p.completed + p.failed)) *
                            100}%; background: var(--error);"
                        ></div>
                      {/if}
                    </div>
                    <span class="temp-perc-out"
                      >{p.completed + p.failed > 0
                        ? Math.round((p.completed / (p.completed + p.failed)) * 100)
                        : 0}%</span
                    >
                  </div>
                </div>
              {/each}
            </div>
          </div>

          <div
            class="dash-card hourly-card"
            style="padding: 20px; display: flex; flex-direction: column;"
          >
            <div
              style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 12px;"
            >
              <div class="dash-card-header" style="flex-shrink: 0;">
                <Activity size={16} />
                <span>{$t('goalsPage.peakActivity')}</span>
              </div>

              <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                <div class="activity-tabs" style="display: flex; gap: 8px;">
                  <button
                    class="activity-tab {activityTab === 'horas' ? 'active' : ''}"
                    onclick={() => (activityTab = 'horas')}>{$t('goalsPage.hours')}</button
                  >
                  <button
                    class="activity-tab {activityTab === 'dias' ? 'active' : ''}"
                    onclick={() => (activityTab = 'dias')}>{$t('goalsPage.days')}</button
                  >
                </div>

                {#if activityTab === 'horas'}
                  <div
                    class="activity-day-selector"
                    style="display: flex; justify-content: center; align-items: center; gap: 8px; background: var(--surface); padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border);"
                  >
                    <button
                      class="icon-btn"
                      onclick={prevActivityDay}
                      aria-label={$t('goalsPage.prevDay')}
                      style="background: none; border: none; cursor: pointer; color: var(--text-muted); display: flex; align-items: center; padding: 4px;"
                      ><ChevronLeft size={16} /></button
                    >
                    <span
                      style="font-size: 0.75rem; color: var(--text-secondary); min-width: 80px; text-align: center; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; font-family: var(--font-mono);"
                      >{daysOfWeek[activityDayOfWeek]}</span
                    >
                    <button
                      class="icon-btn"
                      onclick={nextActivityDay}
                      aria-label={$t('goalsPage.nextDay')}
                      style="background: none; border: none; cursor: pointer; color: var(--text-muted); display: flex; align-items: center; padding: 4px;"
                      ><ChevronRight size={16} /></button
                    >
                  </div>
                {/if}
              </div>
            </div>

            <div
              class="hourly-chart"
              style="display: flex; align-items: flex-end; gap: 2px; height: 160px; width: 100%; flex: 1;"
            >
              {#if activityTab === 'horas'}
                {#each activityBinnedByHour as bin}
                  <div
                    class="hour-col"
                    title="{bin.rangeLabel}: {bin.val} completados"
                    style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; height: 100%;"
                  >
                    <span
                      class="bar-value"
                      style="font-size: 0.75rem; font-weight: 700; color: {bin.val > 0
                        ? 'var(--text-primary)'
                        : 'transparent'};">{bin.val}</span
                    >
                    <div
                      class="hour-bar-wrap"
                      style="flex: 1; width: 100%; display: flex; align-items: flex-end; background: none;"
                    >
                      <div
                        class="hour-bar"
                        style="height: {bin.val > 0
                          ? Math.max(6, bin.pct * 100)
                          : 0}%; width: 100%; background: {bin.val > 0
                          ? 'var(--xp)'
                          : 'var(--border)'}; border-radius: 4px 4px 0 0; opacity: {bin.val > 0
                          ? '1'
                          : '0.3'};"
                      ></div>
                    </div>
                    <span
                      class="hour-label"
                      style="font-size: 0.85rem; color: var(--text-muted); font-family: var(--font-mono);"
                      >{bin.label}</span
                    >
                  </div>
                {/each}
              {:else}
                {#each activityByDay as day}
                  <div
                    class="hour-col"
                    title="{day.label}: {day.val} completados"
                    style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; height: 100%;"
                  >
                    <span
                      class="bar-value"
                      style="font-size: 0.75rem; font-weight: 700; color: {day.val > 0
                        ? 'var(--text-primary)'
                        : 'transparent'};">{day.val}</span
                    >
                    <div
                      class="hour-bar-wrap"
                      style="flex: 1; width: 100%; display: flex; align-items: flex-end; background: none;"
                    >
                      <div
                        class="hour-bar"
                        style="height: {day.val > 0
                          ? Math.max(6, day.pct * 100)
                          : 0}%; width: 100%; background: {day.val > 0
                          ? 'var(--xp)'
                          : 'var(--border)'}; border-radius: 4px 4px 0 0; opacity: {day.val > 0
                          ? '1'
                          : '0.3'};"
                      ></div>
                    </div>
                    <span
                      class="hour-label"
                      style="font-size: 0.85rem; color: var(--text-muted); font-weight: 500;"
                      >{day.label}</span
                    >
                  </div>
                {/each}
              {/if}
            </div>
          </div>

          <div class="dash-card funnel-card">
            <div class="dash-card-header">
              <ListFilter size={16} />
              <span>{$t('goalsPage.conversionAbandon')}</span>
            </div>
            <div class="funnel-chart">
              {#each funnelData as f}
                <div class="funnel-row">
                  <div class="funnel-label-col">
                    <span class="funnel-name">{f.label}</span>
                    <span class="funnel-val" style="color: {f.color}">{f.value}</span>
                  </div>
                  <div class="funnel-bar-col">
                    <div
                      class="funnel-bar"
                      style="width: {(f.value / (funnelData[0]?.value || 1)) *
                        100}%; background: {f.color};"
                    ></div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}
  </div>

  <!-- ── New Goal Slide-Down Panel ── -->
  {#if showAddForm}
    <div
      class="new-goal-backdrop"
      onclick={(e) => {
        if (e.target === e.currentTarget) showAddForm = false;
      }}
      role="dialog"
      tabindex="-1"
    >
      <div class="new-goal-panel slide-down">
        <div class="new-goal-header">
          <div class="new-goal-title-row">
            <div class="new-goal-icon-wrap">
              <Plus size={16} />
            </div>
            <div>
              <h3 class="new-goal-heading">{$t('goalsPage.newGoal')}</h3>
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
                <label class="label">{$t('goalsPage.goalTitle')}</label>
                <input
                  class="input w-full"
                  bind:value={newTitle}
                  placeholder={$t('goalsPage.goalTitlePlaceholder')}
                  maxlength="38"
                  autofocus
                />
              </div>
              <div class="form-field">
                <label class="label"
                  >{$t('goalsPage.description')}
                  <span class="optional">{$t('goalsPage.optional')}</span></label
                >
                <textarea
                  class="input w-full"
                  bind:value={newDescription}
                  placeholder={$t('goalsPage.descriptionPlaceholder')}
                  maxlength="63"
                  rows="2"
                  onkeydown={(e) => e.key === 'Enter' && e.preventDefault()}
                  oninput={(e) => (newDescription = e.currentTarget.value.replace(/\n/g, ''))}
                ></textarea>
              </div>
              <div class="form-field">
                <label class="label">{$t('goalsPage.repeatFrequency')}</label>
                <div class="ng-freq-grid">
                  {#each TEMPORALITIES as temp}
                    <button
                      class="ng-freq-btn"
                      class:active={newTemporality === temp}
                      onclick={() => (newTemporality = temp)}
                    >
                      {temp === 'DAILY'
                        ? 'Diario'
                        : temp === 'WEEKLY'
                          ? 'Semanal'
                          : temp === 'MONTHLY'
                            ? 'Mensual'
                            : 'Anual'}
                    </button>
                  {/each}
                </div>
              </div>
              <div class="form-field">
                <label class="label">{$t('goalsPage.measurementType')}</label>
                <select class="input w-full" bind:value={newMeasurement}>
                  <option value="COUNT">{$t('goalsPage.countNumeric')}</option>
                  <option value="BOOLEAN">{$t('goalsPage.booleanDone')}</option>
                  <option value="PERCENT">{$t('goalsPage.percent')}</option>
                </select>
              </div>
              <div class="form-field">
                <label class="label">{$t('goalsPage.targetGoal')}</label>
                <input
                  class="input w-full"
                  type="number"
                  bind:value={newTargetValue}
                  min="1"
                  disabled={newMeasurement === 'BOOLEAN'}
                />
              </div>
            </div>

            <!-- Column 2: Appearance -->
            <div class="ng-col">
              <span class="ng-col-title">{$t('goalsPage.appearance')}</span>
              <div class="form-field">
                <div
                  style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;"
                >
                  <label class="label" style="margin:0;">{$t('goalsPage.failIconEmoji')}</label>
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
                {#if !useFailIcon}
                  <div class="ng-picker-field">
                    <div class="emoji-grid">
                      {#each EMOJIS as e}
                        <button
                          class="emoji-btn"
                          class:selected={newFailEmoji === e}
                          onclick={() => (newFailEmoji = e)}>{e}</button
                        >
                      {/each}
                    </div>
                  </div>
                {:else}
                  <div class="ng-picker-field ng-picker-icon">
                    <LazyIconPicker
                      selected={newFailIcon}
                      color={newGoalColor}
                      onSelect={(ic) => (newFailIcon = ic)}
                    />
                  </div>
                {/if}
              </div>

              <div class="form-field">
                <label class="label">{$t('goalsPage.identityColor')}</label>
                <div class="ng-color-grid">
                  {#each COLOR_PRESETS as c}
                    <button
                      class="ng-color-btn"
                      class:selected={newGoalColor === c.hex}
                      style="background: {c.hex};"
                      onclick={() => (newGoalColor = c.hex)}
                      title={c.name}
                      aria-label={c.name}
                    />
                  {/each}
                </div>
                <div class="ng-color-manual-row">
                  <div class="ng-color-swatch-wrapper" style="background: {newGoalColor};">
                    <input
                      type="color"
                      class="ng-color-swatch"
                      value={newGoalColor}
                      oninput={(e) => (newGoalColor = e.currentTarget.value)}
                    />
                  </div>
                  <input
                    type="text"
                    class="ng-hex-input mono"
                    maxlength="7"
                    bind:value={newGoalColor}
                    placeholder="#c8a96e"
                  />
                </div>
              </div>
            </div>

            <!-- Column 3: Advanced -->
            <div class="ng-col">
              <span class="ng-col-title">{$t('goalsPage.advanced')}</span>
              <div class="form-field">
                <label class="label"
                  >{$t('goalsPage.limitDays')}
                  <span class="optional">{$t('goalsPage.limitDaysOptional')}</span></label
                >
                <input
                  class="input w-full"
                  type="number"
                  bind:value={newMaxAssignmentDays}
                  min="1"
                  placeholder={$t('goalsPage.unlimited')}
                />
              </div>

              <div class="form-field">
                <label class="label">{$t('goalsPage.failPolicy')}</label>
                <div class="ng-fail-options">
                  <button
                    class="ng-fail-btn"
                    class:active={newFailConfig === 'STATIC'}
                    onclick={() => (newFailConfig = 'STATIC')}
                  >
                    <strong>{$t('goalsPage.static')}</strong>
                    <span>{$t('goalsPage.staticDesc')}</span>
                  </button>
                  <button
                    class="ng-fail-btn"
                    class:active={newFailConfig === 'ROLLOVER'}
                    onclick={() => (newFailConfig = 'ROLLOVER')}
                  >
                    <strong>{$t('goalsPage.rollover')}</strong>
                    <span>{$t('goalsPage.rolloverDesc')}</span>
                  </button>
                  <button
                    class="ng-fail-btn"
                    class:active={newFailConfig === 'SNOWBALL'}
                    onclick={() => (newFailConfig = 'SNOWBALL')}
                  >
                    <strong>{$t('goalsPage.snowball')}</strong>
                    <span>{$t('goalsPage.snowballDesc')}</span>
                  </button>
                </div>
              </div>

              <div class="form-field">
                <label class="label">{$t('goalsPage.linkToProject')}</label>
                <select class="input w-full" bind:value={newNoteId}>
                  <option value={null}>{$t('goalsPage.noLinkedNote')}</option>
                  {#each notes as n}
                    <option value={n.id}>{n.title}</option>
                  {/each}
                </select>
              </div>
              <div class="form-field">
                <label class="label">{$t('goalsPage.tagSync')}</label>
                <select class="input w-full" bind:value={newTagId}>
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

  {#if currentTab === 'editor'}
    <div class="tab-content fade-in editor-tab">
      <div class="editor-header-row">
        <GoalFilters bind:query={goalSearchQuery} bind:filter={goalFilterState} />
        <button
          class="btn btn-primary new-goal-cta-inline"
          onclick={() => (showAddForm = !showAddForm)}
        >
          <Plus size={16} />
          {$t('goalsPage.newGoal')}
        </button>
      </div>
      <GoalList
        {goals}
        query={goalSearchQuery}
        filter={goalFilterState}
        pinned={pinnedGoals}
        {tags}
        {notes}
        {getGoalColor}
        {TEMPORALITY_LABELS}
        {STATE_LABELS}
        {formatFailConfig}
        onTogglePin={togglePinned}
        onClick={openGoalEditor}
      />
    </div>
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
  .goals-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s3) var(--s5);
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }
  .tabs {
    display: flex;
    gap: var(--s2);
  }
  .tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    border-radius: var(--r);
    transition: all 0.2s ease;
  }
  .tab:hover {
    background: var(--surface-hover);
    color: var(--text-primary);
  }
  .tab.active {
    background: var(--surface-active);
    color: var(--text-primary);
    font-weight: 500;
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
  /* Planning 3-col layout - One Page Style */
  .planning-3col {
    display: grid;
    grid-template-columns: 1fr 1.4fr 1fr;
    gap: var(--s4);
    height: calc(100vh - 160px);
    width: 100%;
    max-width: none;
    align-items: stretch;
  }

  .planning-left-col,
  .planning-center-col,
  .planning-right-col {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    overflow: hidden; /* Header stays fixed, list scrolls */
  }

  .planning-left-col .history-goal-list,
  .planning-right-col .history-goal-list,
  .planning-center-col .history-heatmap-wrap {
    flex: 1;
    overflow-y: auto;
    padding: var(--s3);
  }

  .planning-center-col .history-heatmap-wrap {
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: var(--s5);
  }

  @media (max-width: 1100px) {
    .planning-3col {
      grid-template-columns: 300px minmax(420px, 1fr) 300px;
    }
  }

  @media (max-width: 900px) {
    .planning-3col {
      display: flex;
      flex-direction: column;
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
  .goals-body.full-width {
    max-width: none;
    margin: 0;
    padding: 0 var(--s3) var(--s3);
    overflow: hidden;
    min-height: 0;
  }

  .today-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: 24px;
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
    align-items: start;
  }

  .dashboard-main-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
  }

  .today-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 12px;
    margin-bottom: 4px;
    border-top: 1px solid var(--border);
  }

  .new-goal-cta-inline {
    height: 36px;
    padding: 0 14px;
    white-space: nowrap;
  }

  .week-map-card {
    margin-top: 12px;
  }

  .dashboard-side-col {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 320px;
  }

  .dashboard-side-col > .dash-card {
    width: 100%;
  }

  .sort-control-centered {
    display: flex;
    justify-content: center;
    padding: 0 0 8px 0;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 8px;
  }
  .sort-select-square {
    padding: 6px 10px;
    font-size: 11px;
    height: auto;
    width: auto;
    min-width: 140px;
    text-align: center;
  }

  /* ── Monthly map (#790) ── */
  .month-map-card {
    padding: 12px;
  }
  .month-map-header {
    display: flex;
    align-items: center;
    gap: 6px;
    position: relative;
  }
  .month-map-header > span {
    flex: 1;
    font-size: 12px;
    text-transform: capitalize;
  }
  .month-map-nav {
    display: flex;
    gap: 4px;
  }
  .month-nav-btn {
    width: 22px;
    height: 22px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-secondary);
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }
  .month-nav-btn:hover {
    background: var(--surface-hover);
    color: var(--text-primary);
  }
  .month-map-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
    margin-top: 10px;
  }
  .month-map-dow {
    text-align: center;
    font-size: 9px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    padding: 2px 0;
  }
  .month-map-cell {
    aspect-ratio: 1;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 10px;
    font-family: var(--font-mono);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.15s;
    background: var(--surface);
    color: var(--text-muted);
  }
  .month-map-cell:hover {
    border-color: var(--text-muted);
  }
  .month-empty {
    background: transparent;
    border: none;
    cursor: default;
  }
  .month-empty:hover {
    border: none;
  }
  .month-assigned {
    background: color-mix(in srgb, var(--today) 25%, var(--surface));
    border-color: var(--today);
    color: var(--warning);
  }
  .month-completed {
    background: var(--success);
    border-color: var(--success);
    color: var(--bg);
  }
  .month-failed {
    background: var(--error);
    border-color: var(--error);
    color: var(--bg);
  }
  .month-today {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: var(--bg) !important;
    font-weight: 700;
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent);
  }

  .new-goal-cta {
    justify-content: center;
    padding: 12px;
  }
  .editor-tab {
    padding: var(--s3);
    height: 100%;
    box-sizing: border-box;
    border: 1px solid var(--border-light);
    border-radius: var(--r);
  }
  .editor-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
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
    width: min(1100px, calc(100vw - 24px));
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
    color: var(--text-disabled);
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
  .ng-freq-btn {
    padding: 10px;
    font-size: 12px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: 6px;
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
    color: var(--text-disabled);
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
    border-radius: 6px;
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
    border-radius: 6px;
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

  .form-row {
    display: flex;
    gap: var(--s3);
    align-items: flex-start;
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

  .icon-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
    gap: 4px;
    background: var(--surface-hover);
    padding: 8px;
    border-radius: var(--r);
    border: 1px solid var(--border);
    max-height: 200px;
    overflow-y: auto;
  }
  .lucide-btn {
    width: 32px;
    height: 32px;
    background: none;
    border: 1px solid transparent;
    cursor: pointer;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    transition: all 0.15s;
  }
  .lucide-btn:hover {
    background: var(--elevated);
    color: var(--text-secondary);
  }
  .lucide-btn.selected {
    border-color: var(--text-primary);
    color: var(--text-primary);
    background: var(--elevated);
  }

  .color-presets {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 6px 0;
    align-items: center;
  }
  .color-dot {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
    /* Raise above the non-interactive preview so clicks always land on the dot (#203). */
    position: relative;
    z-index: 2;
  }
  .color-dot:hover {
    transform: scale(1.15);
  }
  .color-dot.selected {
    border-color: var(--text-primary);
    box-shadow:
      0 0 0 2px var(--bg),
      0 0 0 4px currentColor;
  }

  .color-custom {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid var(--border);
    position: relative;
    cursor: pointer;
    transition: all 0.15s;
  }
  .color-custom:hover {
    transform: scale(1.1);
    border-color: var(--text-muted);
  }
  .color-picker {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    cursor: pointer;
    border: none;
    padding: 0;
  }

  .theme-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 4px 0;
  }
  .theme-btn {
    padding: 4px 12px;
    font-size: 11px;
    font-family: var(--font-mono);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .theme-btn:hover {
    border-color: var(--text-muted);
    color: var(--text-secondary);
  }
  .theme-btn.selected {
    border-color: var(--text-primary);
    color: var(--text-primary);
    background: var(--elevated);
  }

  .form-actions {
    display: flex;
    gap: var(--s2);
    margin-top: var(--s2);
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
  .today-layout .goal-card.completed {
    opacity: 1;
  }
  .goal-card.failed {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 2%, transparent);
  }
  .goal-card.paused {
    opacity: 0.55;
    border-color: var(--warning, #f59e0b);
    border-style: dashed;
  }
  .state-badge {
    font-size: 9px;
    font-family: var(--font-mono);
    padding: 1px 6px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    line-height: 1.4;
  }
  .paused-badge {
    background: color-mix(in srgb, var(--warning) 15%, transparent);
    color: var(--warning, #f59e0b);
    border: 1px solid color-mix(in srgb, var(--warning) 30%, transparent);
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
  .config-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--surface-active);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
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
  .goal-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }
  .text-success {
    color: var(--success);
  }
  .text-muted {
    color: var(--text-muted);
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
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--s3);
    margin-bottom: var(--s2);
  }
  .metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s4);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
  }
  .metric-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.2;
    font-family: var(--font-mono);
  }
  .metric-label {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
  }

  /* Planning Tabs */
  .planning-tabs {
    display: flex;
    gap: var(--s2);
    margin-bottom: var(--s3);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--s2);
  }
  .planning-tab {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: var(--r);
    transition: all 0.2s;
  }
  .planning-tab:hover {
    color: var(--text-primary);
    background: var(--surface-hover);
  }
  .planning-tab.active {
    color: var(--text-primary);
    background: var(--surface-active);
    font-weight: 500;
  }

  .planning-nav-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s4);
  }

  .planning-nav-controls {
    display: flex;
    justify-content: center;
    width: 100%;
  }

  .nav-sep {
    opacity: 0.3;
    font-weight: 200;
  }

  .planning-calendar-wrap {
    width: 100%;
    max-width: 600px;
    margin: 0 auto;
    background: var(--surface-hover);
    padding: var(--s4);
    border-radius: 12px;
    border: 1px solid var(--border);
  }

  .planning-goals-list {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    width: 100%;
  }

  /* Analytics Charts */
  .analytics-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s4);
  }
  .bar-chart {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }
  .bar-row {
    display: flex;
    align-items: center;
    gap: var(--s3);
  }
  .bar-label {
    width: 60px;
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .bar-track {
    flex: 1;
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    position: relative;
    overflow: hidden;
  }
  .bar-fill {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    transition: width 0.3s ease;
  }
  .bar-fill.success {
    background: var(--success);
  }
  .bar-fill.error {
    background: var(--error);
  }
  .bar-value {
    width: 40px;
    text-align: right;
    font-size: 11px;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  /* Hierarchical Planning */
  .goal-group {
    margin-bottom: var(--s3);
  }
  .goal-children {
    margin-left: 20px;
    padding-left: 12px;
    border-left: 2px solid var(--border);
  }
  .child-card {
    padding: var(--s2) var(--s3);
    font-size: 13px;
    margin-bottom: 4px;
    background: var(--surface-hover);
  }
  .child-indent {
    color: var(--text-muted);
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  /* Expandable Analytics */
  .expandable {
    overflow: hidden;
  }
  .expand-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: inherit;
  }
  /* Advanced Dashboard Styles */
  .full-height-dashboard {
    height: calc(100vh - 56px - 44px - var(--s3) * 2);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }
  .dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    grid-template-rows: 1fr 1fr 1fr;
    grid-template-areas:
      'pred pred pred temp'
      'pred pred pred funnel'
      'hourly hourly hourly weekday';
    gap: var(--s2);
    flex: 1;
    min-height: 0;
  }
  .dash-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s2) var(--s3);
    display: flex;
    flex-direction: column;
    gap: var(--s1);
    backdrop-filter: blur(10px);
    transition:
      transform 0.2s,
      border-color 0.2s;
    min-height: 0;
    overflow: hidden;
  }
  .dash-card:hover {
    border-color: var(--primary);
    background: var(--surface-hover);
  }
  .dash-card-header {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  /* Stats Top Bar */
  .stats-top-bar {
    display: flex;
    align-items: center;
    gap: var(--s6);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s2) var(--s4);
    margin-bottom: 0;
    flex-shrink: 0;
  }
  .stb-item {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .stb-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .stb-val {
    font-size: 18px;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .success-meter {
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    margin-top: auto;
  }
  .meter-fill {
    height: 100%;
    background: linear-gradient(
      90deg,
      var(--success),
      color-mix(in srgb, var(--success) 70%, var(--bg))
    );
    border-radius: 2px;
    transition: width 1s ease-out;
  }

  /* Prediction Card Styles */
  .prediction-card {
    /* grid-area: pred is set in Advanced Analytics Styles below */
  }
  .prediction-hero {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  .candle-chart-container {
    flex: 1;
    min-height: 80px;
    background: color-mix(in srgb, var(--text-primary) 15%, transparent);
    border-radius: var(--r-sm, 8px);
    padding: var(--s2) var(--s3);
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .candle-svg {
    width: 100%;
    height: 100%;
    display: block;
  }
  .prediction-stats-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 var(--s1);
  }
  .trend-summary {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .trend-icon-wrap {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .trend-icon-wrap.up {
    color: var(--success);
  }
  .trend-icon-wrap.down {
    color: var(--error);
  }

  .prediction-estimate {
    text-align: right;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .trend-label,
  .pred-lab {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .pred-val {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .candle-svg {
    filter: drop-shadow(0 0 2px color-mix(in srgb, var(--text-primary) 15%, transparent));
  }
  .candle-empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    color: var(--text-disabled);
    font-size: 11px;
    height: 100%;
    text-align: center;
  }
  .pred-period-badge {
    margin-left: auto;
    font-size: 9px;
    padding: 2px 6px;
    background: color-mix(in srgb, var(--text-primary) 5%, transparent);
    border: 1px solid var(--border);
    border-radius: 4px;
    font-family: var(--font-mono);
    color: var(--text-disabled);
    text-transform: none;
    font-weight: 400;
    letter-spacing: 0;
  }
  .prediction-kpis {
    display: flex;
    gap: var(--s4);
  }
  .pred-kpi {
    display: flex;
    flex-direction: column;
    gap: 1px;
    align-items: flex-end;
  }

  /* Weekday Chart */
  .weekday-card {
    grid-column: span 1;
  }
  .weekday-chart {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex: 1;
    min-height: 0;
    height: 100%;
    padding: var(--s2) 0;
  }
  .day-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
    height: 100%;
  }
  .day-bar-wrap {
    flex: 1;
    width: 10px;
    min-height: 0;
    background: var(--border);
    border-radius: 5px;
    display: flex;
    align-items: flex-end;
    overflow: hidden;
  }
  .day-bar {
    width: 100%;
    background: var(--success);
    border-radius: 5px;
    transition: height 0.5s ease-out;
  }
  .day-val {
    font-size: 10px;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .day-label {
    font-size: 8px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  /* Temporality Rows */
  .temporality-card {
    grid-column: span 1;
  }
  .temporality-rows {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 100%;
    gap: var(--s2);
    padding-bottom: 8px;
  }
  .temp-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .temp-info {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
  }
  .temp-name {
    font-weight: 600;
    color: var(--text-secondary);
  }
  .temp-stats {
    color: var(--text-muted);
    font-family: var(--font-mono);
  }
  .temp-bar-container {
    height: 10px;
    background: var(--border);
    border-radius: 5px;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
  }
  .temp-bar {
    height: 100%;
    transition: width 0.5s;
  }
  .temp-perc-out {
    font-size: 10px;
    font-weight: 700;
    color: var(--text-secondary);
    font-family: var(--font-mono);
    min-width: 28px;
    text-align: right;
  }

  /* Tags List */
  .tags-card {
    grid-column: span 1;
  }
  .tags-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .tag-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .tag-rank {
    width: 16px;
    height: 16px;
    background: var(--surface-active);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    font-weight: 700;
    color: var(--text-muted);
  }
  .tag-name-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .tag-name {
    font-size: 11px;
    color: var(--text-secondary);
  }
  .tag-bar-wrap {
    height: 3px;
    background: var(--border);
    border-radius: 1.5px;
  }
  .tag-bar {
    height: 100%;
    background: var(--success);
    border-radius: 1.5px;
    opacity: 0.6;
  }
  .tag-count {
    font-size: 11px;
    font-weight: 600;
    color: var(--success);
    font-family: var(--font-mono);
  }

  /* Summary Grid */
  .projection-content {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s2);
    margin-top: var(--s1);
  }
  .proj-item {
    border-radius: var(--r);
    margin-top: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .proj-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .proj-val {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary);
  }

  @media (max-width: 900px) {
    .full-height-dashboard {
      height: auto;
      overflow-y: auto;
    }
    .dashboard-grid {
      grid-template-columns: 1fr 1fr;
      grid-template-rows: unset;
      grid-template-areas: unset;
    }
    .prediction-card,
    .weekday-card,
    .temporality-card,
    .hourly-card,
    .funnel-card {
      grid-area: unset;
      grid-column: span 2;
    }
    .weekday-card,
    .temporality-card,
    .funnel-card {
      grid-column: span 1;
    }
    /* Today tab: stack sidebar below main content */
    .today-layout {
      grid-template-columns: 1fr;
      gap: var(--s4);
    }
    /* Analytics projection: stack 2-col grid */
    .projection-content {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 768px) {
    .dashboard-grid {
      grid-template-columns: 1fr;
    }
    .prediction-card,
    .weekday-card,
    .temporality-card,
    .hourly-card,
    .funnel-card {
      grid-column: span 1;
    }
  }

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
    color: var(--text-disabled);
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
    color: var(--text-disabled);
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0.5;
  }

  .history-detail-msg {
    font-size: 12px;
    color: var(--text-disabled);
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
    color: var(--text-disabled);
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

  .history-goal-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 12px;
    border-radius: var(--r);
    border: 1px solid var(--border);
    background: var(--elevated);
    transition: border-color 0.15s;
  }

  .history-goal-item.completed {
    border-left: 3px solid var(--success);
  }
  .history-goal-item.failed {
    border-left: 3px solid var(--error);
  }

  .hgi-icon-left {
    width: 24px;
    display: flex;
    justify-content: center;
    align-items: center;
    flex-shrink: 0;
  }

  .hgi-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .hgi-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .hgi-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    margin-top: 2px;
  }

  .hgi-bar {
    flex: 1;
    height: 4px;
    background: var(--surface-active);
    border-radius: 4px;
    overflow: hidden;
  }

  .hgi-bar-fill {
    height: 100%;
    transition: width 0.3s ease;
  }

  .hgi-pct {
    font-size: 10px;
    font-family: var(--font-mono);
    font-weight: 700;
    flex-shrink: 0;
    min-width: 32px;
    text-align: right;
  }

  /* Advanced Analytics Styles */
  .prediction-card {
    grid-area: pred;
  }
  .weekday-card {
    grid-area: weekday;
  }
  .temporality-card {
    grid-area: temp;
  }
  .hourly-card {
    grid-area: hourly;
  }
  .funnel-card {
    grid-area: funnel;
  }

  .hourly-chart {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    height: 100%;
    padding-top: var(--s2);
  }
  .hour-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
  }
  .hour-bar-wrap {
    flex: 1;
    width: 10px;
    background: color-mix(in srgb, var(--text-primary) 2%, transparent);
    border-radius: 5px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
  }
  .hourly-card {
    padding: 20px;
  }
  .activity-tabs {
    display: flex;
    gap: 8px;
  }
  .activity-tab {
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    background: var(--surface);
    color: var(--text-muted);
    transition: all 0.2s;
  }
  .activity-tab:hover {
    background: var(--elevated);
    color: var(--text-secondary);
  }
  .activity-tab.active {
    background: color-mix(in srgb, var(--xp) 15%, transparent);
    color: var(--xp);
    border-color: var(--xp);
  }

  .hour-bar {
    width: 100%;
    background: linear-gradient(0deg, transparent, var(--xp));
    border-radius: 5px;
    transition: height 0.5s;
  }
  .hour-label {
    font-size: 8px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .radar-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--s2);
  }
  .radar-svg {
    width: 100%;
    height: 100%;
    max-height: 180px;
    overflow: visible;
  }

  .debt-content {
    display: flex;
    gap: var(--s4);
    height: 100%;
    align-items: center;
  }
  .debt-total {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: color-mix(in srgb, var(--error) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--error) 20%, transparent);
    border-radius: 50%;
    width: 80px;
    height: 80px;
    flex-shrink: 0;
  }
  .debt-val {
    font-size: 24px;
    font-weight: 700;
    color: var(--error);
    font-family: var(--font-mono);
    line-height: 1;
  }
  .debt-lab {
    font-size: 9px;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  .debt-list {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .debt-item {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .debt-title {
    font-size: 11px;
    color: var(--text-primary);
    width: 80px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .debt-bar-wrap {
    flex: 1;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
  }
  .debt-bar {
    height: 100%;
    background: var(--error);
    border-radius: 3px;
  }
  .debt-count {
    font-size: 11px;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--error);
  }

  .funnel-chart {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    height: 100%;
    justify-content: center;
  }
  .funnel-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .funnel-label-col {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
  }
  .funnel-name {
    color: var(--text-muted);
    text-transform: uppercase;
    font-size: 9px;
    letter-spacing: 0.05em;
  }
  .funnel-val {
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .funnel-bar-col {
    height: 8px;
    background: var(--border);
    border-radius: 4px;
  }
  .funnel-bar {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s;
  }

  /* Editor de Objetivos - Nuevo Diseño */
  .editor-tab {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow: hidden;
  }

  .goal-date {
    font-size: 10px;
  }

  @media (max-width: 768px) {
    .editor-stats {
      flex-wrap: wrap;
    }
    .tabs {
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
      gap: var(--s1);
    }
    .tabs::-webkit-scrollbar {
      display: none;
    }
    .tab {
      padding: var(--s1) var(--s2);
      font-size: 12px;
      white-space: nowrap;
      flex-shrink: 0;
    }
    .goals-header {
      flex-direction: column;
      align-items: stretch;
      gap: var(--s2);
      padding: var(--s2) var(--s3);
    }
    .goals-body,
    .goals-body.full-width {
      padding: var(--s3);
      overflow: visible !important;
      flex: none;
      min-height: auto !important;
    }
    .editor-header,
    .editor-controls,
    .search-box,
    .filter-buttons {
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      overflow-x: hidden;
    }
    .tab-content {
      overflow-x: hidden;
      max-width: 100%;
    }
    .editor-header-row {
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
