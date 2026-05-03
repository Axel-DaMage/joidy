<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { Plus, Check, ChevronDown, Calendar, BarChart, Clock, Layout, Pause, Play, Ban, Pencil, X, Flame, ChevronRight, ChevronLeft, TrendingUp, TrendingDown, PieChart, Activity, Target, Trophy, Settings, Palette, Hexagon, Filter, AlertTriangle, FileEdit } from 'lucide-svelte';
  import { api, type Goal, type Tag, type Note } from '$lib/api';
  import { applyGamificationResult, showXPGain } from '$lib/stores/gamification';
  import { getCachedData, setCachedData } from '$lib/utils/userSettings';
  import StreakIcon from '$lib/components/StreakIcon.svelte';
  import StreakHeatmap from '$lib/components/StreakHeatmap.svelte';
  import IconPicker from '$lib/components/IconPicker.svelte';
  import GoalEditor from '$lib/components/GoalEditor.svelte';

  let goals = $state<Goal[]>([]);
  let tags = $state<Tag[]>([]);
  let notes = $state<Note[]>([]);
  let currentTab = $state<'today' | 'planning' | 'history' | 'analytics' | 'editor'>('today');
  let currentPlanningTab = $state<'WEEKLY' | 'MONTHLY' | 'ANNUAL'>('ANNUAL');
  let showAddForm = $state(false);
  let editorGoal: Goal | null = $state(null);
  let editorContent: string = $state('');

  const EMOJIS = Array.from(new Set([
    '🔴','❌','⚠️','📉','⛔','🌧️','🔥','💪','🏃','🚴','🏊','🏋️','🤸','🧘',
    '❤️','💚','💙','💛','🧠','👁️','👂','👃','💊','💉','🩹','🩺',
    '📚','📖','📝','✍️','📓','📔','📕','📗','📘','🖊️','🖍️','📜','📋','🗂️',
    '🎨','🎭','🎬','🎤','🎧','🎵','🎶','🎸','🎹','🎺','🎷','📸','🖼️',
    '🌿','🍀','🌱','🌲','🌳','🌴','🌵','🌾','🌻','🌺','🌸','🌼','🌷','🌹','🌎',
    '🍎','🍊','🍋','🍌','🍇','🍓','🥗','🥙','🍕','🍔','🍟','🌮','☕','🍵',
    '💻','📱','⌚','🎮','🧩','🪀','🪁','🎯','🔐','🔒','🔓','🔑','⚙️','🔧','🔨','⚒️',
    '✈️','🚂','🚗','🚙','🚕','🚌','🚎','🏎️','🚓','🚑','🚒','🚐','🛻','🚚','🚛','🚜',
    '☀️','🌤️','⛅','🌥️','☁️','🌦️','🌧️','⛈️','🌩️','🌨️','❄️','☃️','⛄','🌊','💧','💦',
    '😀','😃','😄','😁','😆','😊','☺️','😉','😌','😚','😍','🤩','😘','🥰','😏','😐',
    '🥇','🥈','🥉','🏆','🎖️','🏅','⭐','🌟','✨','💫','🎊','🎉','🎁'
  ]));

  const TEMPORALITIES: Goal['temporality'][] = ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'];
  const TEMPORALITY_LABELS: Record<string, string> = {
    'DAILY': 'Diario',
    'WEEKLY': 'Semanal',
    'MONTHLY': 'Mensual',
    'ANNUAL': 'Anual'
  };
  const STATE_LABELS: Record<string, string> = {
    'ACTIVE': 'Activo',
    'PAUSED': 'Pausado',
    'COMPLETED': 'Completado',
    'FAILED': 'Fallido',
    'CANCELLED': 'Cancelado'
  };
  const COLOR_PRESETS = [
    { name: 'Gold',      hex: '#c8a96e' },
    { name: 'Esmeralda', hex: '#10b981' },
    { name: 'Cyan',      hex: '#06b6d4' },
    { name: 'Azul',      hex: '#3b82f6' },
    { name: 'Violeta',   hex: '#8b5cf6' },
    { name: 'Rosa',      hex: '#ec4899' },
    { name: 'Ámbar',     hex: '#f59e0b' },
    { name: 'Coral',     hex: '#ef4444' },
    { name: 'Lima',      hex: '#84cc16' },
    { name: 'Slate',     hex: '#64748b' },
    { name: 'Teal',      hex: '#14b8a6' },
    { name: 'Blanco',    hex: '#e2e8f0' },
  ];

  // New goal form
  let newTitle = $state('');
  let newDescription = $state('');
  let newTargetValue = $state(1);
  let newTemporality = $state<Goal['temporality']>('DAILY');
  let newMeasurement = $state<Goal['measurement_type']>('COUNT');
  let newFailConfig = $state<Goal['fail_config']>('STATIC');
  let newFailEmoji = $state('🔴');
  let newFailIcon = $state('Activity');
  let newGoalColor = $state('#c8a96e');
  let newMaxAssignmentDays = $state<number | null>(null);
  let useFailIcon = $state(false);
  let newTagId = $state<number | null>(null);
  let newNoteId = $state<number | null>(null);
  let saving = $state(false);
  let ngActiveSection = $state<'basics' | 'appearance' | 'advanced'>('basics');

  let dailyGoals = $derived(goals.filter(g => g.temporality === 'DAILY' && g.state !== 'CANCELLED'));
  let planningGoals = $derived(goals.filter(g => g.state !== 'CANCELLED'));
  let pendingGoals = $derived(goals.filter(g => g.pending_removal));

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
  let selectedHistoryDate = $state<string | null>(`${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}-${String(_now.getDate()).padStart(2, '0')}`);

  let goalsForDate = $derived.by(() => {
    if (!selectedHistoryDate) return { completed: [], failed: [] };
    const completed = goals.filter(g =>
      (g.state === 'COMPLETED' || g.is_completed) &&
      g.completed_at?.startsWith(selectedHistoryDate!)
    );
    const failed = goals.filter(g =>
      g.state === 'FAILED' &&
      g.updated_at?.startsWith(selectedHistoryDate!)
    );
    return { completed, failed };
  });

  function formatHistoryDate(iso: string | null): string {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    const DAYS = ['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
    const MONTHS = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
    return `${DAYS[date.getDay()]}, ${d} de ${MONTHS[m-1]} de ${y}`;
  }

  let loadError = $state('');
  let streakData = $state({ current_streak: 0, best_streak: 0 });

  onMount(async () => {
    const cachedGoals = getCachedData<Goal[]>('goals');
    const cachedTags = getCachedData<Tag[]>('tags');
    if (cachedGoals) goals = cachedGoals;
    if (cachedTags) tags = cachedTags;
    
    try {
      [goals, tags, notes, streakData] = await Promise.all([
        api.goals.list(),
        api.tags.list(),
        api.notes.list(),
        api.goals.streak()
      ]);
      setCachedData('goals', goals);
      setCachedData('tags', tags);
      // restore UI state (keep planning tab and selected date)
      try {
        const savedTab = localStorage.getItem('goals.currentTab');
        if (savedTab) currentTab = savedTab as typeof currentTab;
        const savedDate = localStorage.getItem('goals.selectedPlanningDate');
        if (savedDate) selectedPlanningDate = savedDate;
        const savedHistoryDate = localStorage.getItem('goals.selectedHistoryDate');
        if (savedHistoryDate) selectedHistoryDate = savedHistoryDate;
        // if we are on planning, pre-load assignments for the selected date
        if (currentTab === 'planning' && selectedPlanningDate) {
          await loadAssignmentsForDate(selectedPlanningDate);
        }
      } catch (e) {
        // ignore storage errors
      }
    } catch (e) {
      if (goals.length === 0) {
        loadError = 'No se pudo cargar los objetivos.';
        console.error('[goals] onMount failed:', e);
      }
    }
  });

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
      newTitle = ''; newTargetValue = 1;
      newTagId = null; newNoteId = null;
      newMaxAssignmentDays = null;
    } catch (e) {
      addError = 'Error al crear el objetivo.';
    } finally {
      saving = false;
    }
  }

  async function completeGoal(id: number) {
    const result = await api.goals.complete(id);
    goals = goals.map(g => g.id === id ? result.goal : g);
    applyGamificationResult(result.gamification);
    showXPGain(result.gamification.xp_awarded);
  }

  async function updateGoalState(id: number, state: 'ACTIVE' | 'PAUSED' | 'CANCELLED') {
    try {
      const result = await api.goals.update(id, { state });
      goals = goals.map(g => g.id === id ? result : g);
    } catch (e) {
      console.error('Error al actualizar estado:', e);
    }
  }

  async function deleteGoal(id: number) {
    await api.goals.delete(id);
    goals = goals.filter(g => g.id !== id);
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
      goals = goals.map(g => g.id === id ? result : g);
    } catch (e) {
      console.error('Error al actualizar temporalidad:', e);
    }
  }

  // ── Edit goal modal state ──
  let editingGoal = $state<Goal | null>(null);
  let editTitle = $state('');
  let editDescription = $state('');
  let editTargetValue = $state(1);
  let editFailConfig = $state<Goal['fail_config']>('STATIC');
  let editMeasurement = $state<Goal['measurement_type']>('COUNT');
  let editColor = $state('#c8a96e');
  let editMaxAssignmentDays = $state<number | null>(null);
  let editSaving = $state(false);

  // ── Analytics expandable state ──
  let showPerformanceChart = $state(true);

  // ── Dashboard State ──
  let activeWidgetIndex = $state(0);
  const widgetTitles = [
    'Predicción y Tendencia',
    'Actividad por Día',
    'Distribución de Éxito',
    'Deuda de Objetivos',
    'Embudo de Retención'
  ];

  let upcomingTasks = $derived.by(() => {
    const futureAssignments: { date: string, goal: Goal }[] = [];
    const sortedDates = Object.keys(assignments).filter(d => d >= todayIso).sort();
    
    for (const date of sortedDates) {
      for (const id of assignments[date]) {
        const goal = goals.find(g => g.id === id);
        if (goal && goal.state !== 'COMPLETED' && goal.state !== 'FAILED') {
          if (!futureAssignments.some(a => a.goal.id === id && a.date === date)) {
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
      const hData = historyData.find(h => h.date === dateStr);
      dates.push({
        dateStr,
        isToday,
        dayName: ['L', 'M', 'X', 'J', 'V', 'S', 'D'][i],
        hasActivity: hData?.checked || false
      });
    }
    return dates;
  });

  // ── Hierarchical planning helpers ──
  function getParentGoals(goalList: Goal[]) {
    return goalList.filter(g => !g.parent_id || !goalList.some(p => p.id === g.parent_id));
  }
  function getChildGoals(parentId: number, goalList: Goal[]) {
    return goalList.filter(g => g.parent_id === parentId);
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
    let unassigned = goals.filter(g => g.state !== 'CANCELLED' && !isAssigned(g.id, selectedPlanningDate));
    if (listSortBy === 'alpha') {
      unassigned.sort((a, b) => a.title.localeCompare(b.title));
    } else if (listSortBy === 'state') {
      const stateOrder: Record<string, number> = { 'ACTIVE': 1, 'PAUSED': 2, 'COMPLETED': 3, 'FAILED': 4 };
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
    const goal = goals.find(g => g.id === goalId);
    if (!goal) return false;
    const normDate = getNormalizedDate(date, goal.temporality);
    return assignments[normDate] && assignments[normDate].includes(goalId);
  }

  // persist current tab and selected planning date in localStorage
  $effect(() => {
    if (typeof localStorage !== 'undefined') localStorage.setItem('goals.currentTab', currentTab);
  });

  $effect(() => {
    if (selectedPlanningDate) {
      if (typeof localStorage !== 'undefined') localStorage.setItem('goals.selectedPlanningDate', selectedPlanningDate);
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
      getNormalizedDate(date, 'ANNUAL')
    ];
    const uniqueDates = Array.from(new Set(datesToLoad));
    
    const fetchedResults = await Promise.all(uniqueDates.map(async (d) => {
      try {
        const res = await api.planning.getAssignments(d);
        return { date: d, ids: res.goal_ids };
      } catch (e) {
        return { date: d, ids: [] };
      }
    }));

    assignments = {
      ...assignments,
      ...Object.fromEntries(fetchedResults.map(r => [r.date, r.ids]))
    };
  }

  async function assignGoalToDate(goalId: number, date: string) {
    if (!date) return;
    const goal = goals.find(g => g.id === goalId);
    if (!goal) return;
    
    const normDate = getNormalizedDate(date, goal.temporality);
    assignments = { ...assignments };
    if (!assignments[normDate]) assignments[normDate] = [];
    if (!assignments[normDate].includes(goalId)) assignments[normDate].push(goalId);
    
    try {
      await api.planning.setAssignments(normDate, assignments[normDate]);
    } catch (e) {
      console.error('Error saving assignment:', e);
    }
  }

  async function unassignGoalFromDate(goalId: number, date: string) {
    if (!date) return;
    const goal = goals.find(g => g.id === goalId);
    if (!goal) return;
    
    const normDate = getNormalizedDate(date, goal.temporality);
    if (!assignments[normDate]) return;
    
    assignments = { ...assignments, [normDate]: assignments[normDate].filter(id => id !== goalId) };
    try {
      await api.planning.setAssignments(normDate, assignments[normDate]);
    } catch (e) {
      console.error('Error saving assignment removal:', e);
    }
  }

  // ── Modal de Consistencia (pending removal resolver) ──
  async function resolveRemoval(goalId: number, action: 'delete' | 'manual' | 'cancel') {
    try {
      const result = await api.goals.resolveRemoval(goalId, action);
      if (action === 'delete' || ('status' in result && result.status === 'deleted')) {
        goals = goals.filter(g => g.id !== goalId);
      } else {
        goals = goals.map(g => g.id === goalId ? (result as Goal) : g);
      }
    } catch (e) {
      console.error('Error al resolver objetivo huérfano:', e);
    }
  }

  function openEditModal(goal: Goal) {
    currentTab = 'editor';
    editorGoal = goal;
    api.goals.getContent(goal.id).then(res => {
      editorContent = res?.content || goal.description || '';
    });
  }

  // ── Advanced Analytics Calculations ──
  let completedGoalsCount = $derived(goals.filter(g => g.state === 'COMPLETED' || g.is_completed).length);
  let failedGoalsCount = $derived(goals.filter(g => g.state === 'FAILED').length);
  let successRate = $derived((completedGoalsCount + failedGoalsCount) > 0 
    ? Math.round((completedGoalsCount / (completedGoalsCount + failedGoalsCount)) * 100) 
    : 0);

  let completionsByDay = $derived.by(() => {
    const days = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
    const counts = [0, 0, 0, 0, 0, 0, 0];
    goals.filter(g => (g.state === 'COMPLETED' || g.is_completed) && g.completed_at).forEach(g => {
      const dateParts = g.completed_at!.split('T')[0].split('-');
      const d = new Date(Number(dateParts[0]), Number(dateParts[1]) - 1, Number(dateParts[2]));
      counts[d.getDay()]++;
    });
    return days.map((label, i) => ({ label, value: counts[i] }));
  });

  let topTagsBySuccess = $derived.by(() => {
    const tagMap = new Map();
    goals.filter(g => (g.state === 'COMPLETED' || g.is_completed) && (g.tag_id || g.note_id)).forEach(g => {
      let name = 'Sin Etiqueta';
      if (g.tag_id) {
        name = tags.find(t => t.id === g.tag_id)?.name || 'Sin Etiqueta';
      } else if (g.note_id) {
        name = notes.find(n => n.id === g.note_id)?.title || 'Nota';
      }
      tagMap.set(name, (tagMap.get(name) || 0) + 1);
    });
    return Array.from(tagMap.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  });

  let progressOverview = $derived.by(() => {
    return ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'].map(temp => {
      const tempGoals = goals.filter(g => g.temporality === temp);
      const avgProgress = tempGoals.length > 0 
        ? Math.round(tempGoals.reduce((acc, g) => acc + (g.state === 'COMPLETED' || g.is_completed ? 100 : (g.progress_pct || 0)), 0) / tempGoals.length)
        : 0;
      const completed = tempGoals.filter(g => g.state === 'COMPLETED' || g.is_completed).length;
      const failed = tempGoals.filter(g => g.state === 'FAILED').length;
      return { temp, avgProgress, count: tempGoals.length, completed, failed };
    });
  });

  let prediction = $derived.by(() => {
    const now = new Date();
    const last7Days = historyData.filter(d => {
      const date = new Date(d.date);
      const diffTime = Math.abs(now.getTime() - date.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays <= 7 && d.checked;
    }).length;

    const prev7Days = historyData.filter(d => {
      const date = new Date(d.date);
      const diffTime = Math.abs(now.getTime() - date.getTime());
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
      return diffDays > 7 && diffDays <= 14 && d.checked;
    }).length;

    const trend = last7Days >= prev7Days ? 'UP' : 'DOWN';
    const percentChange = prev7Days > 0 ? Math.round(((last7Days - prev7Days) / prev7Days) * 100) : (last7Days > 0 ? 100 : 0);
    
    return { trend, percentChange, estimateNextMonth: Math.round(last7Days * 4), last7Days, prev7Days };
  });

  let candleData = $derived.by(() => {
    let currentPrice = 1000;
    const results: { date: string; open: number; close: number; high: number; low: number }[] = [];
    const last30Days = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const day = String(d.getDate()).padStart(2, '0');
      last30Days.push(`${d.getFullYear()}-${m}-${day}`);
    }

    last30Days.forEach((date: string) => {
      const comps = goals.filter(g => (g.state === 'COMPLETED' || g.is_completed) && g.completed_at?.startsWith(date)).length;
      const fails = goals.filter(g => g.state === 'FAILED' && g.updated_at?.startsWith(date)).length;
      
      const open = currentPrice;
      const close = currentPrice + (comps * 10) - (fails * 15);
      const high = Math.max(open, close) + (comps > 0 ? 5 : 2);
      const low = Math.min(open, close) - (fails > 0 ? 5 : 2);
      
      results.push({ date, open, close, high, low });
      currentPrice = close;
    });
    return results;
  });

  let candleScale = $derived.by(() => {
    const allVals = candleData.flatMap(c => [c.high, c.low]);
    const min = Math.min(...allVals) - 10;
    const max = Math.max(...allVals) + 10;
    return { min, max, range: max - min };
  });

  let activityByHour = $derived.by(() => {
    const counts = new Array(24).fill(0);
    goals.forEach(g => {
      if ((g.state === 'COMPLETED' || g.is_completed) && g.completed_at) {
        const hour = new Date(g.completed_at).getHours();
        if(!isNaN(hour)) counts[hour]++;
      }
    });
    const maxVal = Math.max(...counts) || 1;
    return counts.map((c, i) => ({
      hour: i,
      label: `${i.toString().padStart(2, '0')}:00`,
      val: c,
      pct: c / maxVal
    }));
  });

  let radarData = $derived.by(() => {
    const categories = topTagsBySuccess.slice(0, 6);
    while(categories.length > 0 && categories.length < 3) {
      categories.push({name: '', count: 0});
    }
    if(categories.length === 0) return [];
    const maxVal = Math.max(...categories.map(c => c.count)) || 1;
    return categories.map((c, i) => {
      const angle = (Math.PI * 2 * i) / categories.length - Math.PI / 2;
      return {
        name: c.name,
        value: c.count,
        pct: c.count / maxVal,
        x: 50 + 40 * Math.cos(angle),
        y: 50 + 40 * Math.sin(angle),
        labelX: 50 + 50 * Math.cos(angle),
        labelY: 50 + 50 * Math.sin(angle)
      };
    });
  });

  let debtData = $derived.by(() => {
    const dGoals = goals.filter(g => (g.fail_config === 'ROLLOVER' || g.fail_config === 'SNOWBALL') && g.state === 'ACTIVE');
    const total = dGoals.reduce((acc, g) => acc + Math.max(0, g.target_value - g.current_value), 0);
    return {
      goals: dGoals.map(g => ({ title: g.title, debt: Math.max(0, g.target_value - g.current_value) })).sort((a,b)=>b.debt-a.debt).slice(0, 5),
      total
    };
  });

  let funnelData = $derived.by(() => {
    const total = goals.length || 1;
    const completed = goals.filter(g => g.state === 'COMPLETED' || g.is_completed).length;
    const failed = goals.filter(g => g.state === 'FAILED').length;
    const active = goals.filter(g => g.state === 'ACTIVE').length;
    const cancelled = goals.filter(g => g.state === 'CANCELLED' || g.state === 'PAUSED').length;
    return [
      { label: 'Iniciados', value: total, color: 'var(--text-disabled)' },
      { label: 'Activos', value: active, color: 'var(--xp)' },
      { label: 'Completados', value: completed, color: 'var(--success)' },
      { label: 'Abandonados', value: cancelled + failed, color: 'var(--error)' }
    ];
  });

  function getY(val: number) {
    return 150 - ((val - candleScale.min) / candleScale.range) * 150;
  }

  async function saveEdit() {
    if (!editingGoal) return;
    editSaving = true;
    try {
      const result = await api.goals.update(editingGoal.id, {
        title: editTitle,
        description: editDescription,
        target_value: editTargetValue,
        fail_config: editFailConfig,
        measurement_type: editMeasurement,
        color: editColor,
        max_assignment_days: editMaxAssignmentDays,
      });
      goals = goals.map(g => g.id === editingGoal!.id ? result : g);
      editingGoal = null;
    } catch (e) {
      console.error('Error al editar:', e);
    } finally {
      editSaving = false;
    }
  }

  function getGoalColor(goal: Goal): string {
    const colorMap: Record<string, string> = {
      'DAILY': '#fbbf24',
      'WEEKLY': '#22d3d3',
      'MONTHLY': '#60a5fa',
      'ANNUAL': '#3b82f6',
      'ACTIVE': '#fbbf24',
      'COMPLETED': '#10b981',
      'PAUSED': '#ef4444',
      'CANCELLED': '#ef4444',
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

<svelte:window on:keydown={(e) => {
  if (e.key === 'Escape') {
    showAddForm = false;
    editingGoal = null;
  }
}} />

<div class="goals-page">
  {#if loadError}
    <div class="error-banner">{loadError}</div>
  {/if}

  <div class="goals-header">
    <div class="tabs">
      <button class="tab" class:active={currentTab === 'editor'} on:click={() => currentTab = 'editor'}>
        <Pencil size={14} /> Editor
      </button>
      <button class="tab" class:active={currentTab === 'today'} on:click={() => currentTab = 'today'}>
        <Layout size={14} /> Inicio
      </button>
      <button class="tab" class:active={currentTab === 'planning'} on:click={() => currentTab = 'planning'}>
        <Clock size={14} /> Planificación
      </button>
      <button class="tab" class:active={currentTab === 'history'} on:click={() => currentTab = 'history'}>
        <Calendar size={14} /> Historial
      </button>
      <button class="tab" class:active={currentTab === 'analytics'} on:click={() => currentTab = 'analytics'}>
        <BarChart size={14} /> Análisis
      </button>
    </div>
  </div>

  <div class="goals-body" class:full-width={currentTab === 'analytics' || currentTab === 'history' || currentTab === 'planning' || currentTab === 'today' || currentTab === 'editor'}>


    {#if currentTab === 'today'}
      <div class="tab-content fade-in" style="display: grid; grid-template-columns: 1fr 300px; gap: 24px; max-width: 1200px; margin: 0 auto; width: 100%;">
        <div class="dashboard-main-col" style="display: flex; flex-direction: column;">
          <h3 class="section-title" style="margin-top: 0;">Objetivos del Día</h3>
        {#if dailyGoals.length === 0}
          <div class="empty-state">No hay objetivos diarios activos.</div>
        {/if}
        {#each dailyGoals as goal (goal.id)}
          <div class="goal-card" class:completed={goal.state === 'COMPLETED'} class:failed={goal.state === 'FAILED'} class:paused={goal.state === 'PAUSED'} style="border-left: 3px solid {getGoalColor(goal)}">
            <div class="goal-main">
              <div class="goal-title">
                <button
                  class="btn btn-ghost"
                  style="font-size: inherit; font-weight: inherit; padding: 0; margin: 0; height: auto; color: inherit;"
                  title="Editar en el editor"
                  on:click|stopPropagation={() => goto(`/goals/${goal.id}`)}
                >
                  {#if goal.fail_emoji}
                    <span class="emoji-badge" style="display:flex; align-items:center; margin-right:8px;">
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
                {#if goal.note_id}
                  <span class="tag-chip" style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(goal)}; color: {getGoalColor(goal)};">{notes.find(n => n.id === goal.note_id)?.title || 'Nota vinculada'}</span>
                {:else if goal.tag_id}
                  <span class="tag-chip" style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(goal)}; color: {getGoalColor(goal)};">{tags.find(t => t.id === goal.tag_id)?.name}</span>
                {/if}
                {#if goal.fail_config !== 'STATIC'}
                  <span class="config-badge">{formatFailConfig(goal.fail_config)}</span>
                {/if}
                {#if goal.measurement_type !== 'COUNT'}
                  <span class="config-badge" style="background:transparent; border: 1px solid var(--border);">{goal.measurement_type}</span>
                {/if}
                {#if goal.max_assignment_days}
                  <span class="config-badge" style="background: rgba(59, 130, 246, 0.1); color: var(--text-muted); border: 1px solid rgba(59, 130, 246, 0.2);">Límite: {goal.max_assignment_days}d</span>
                {/if}
              </div>
              {#if goal.description}
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">{goal.description}</div>
              {/if}
            </div>
            <div class="goal-progress">
              <div class="progress-meta">
                <span class="mono caption">
                  {#if goal.measurement_type === 'BOOLEAN'}
                    {goal.current_value >= 1 ? 'Sí' : 'No'}
                  {:else if goal.measurement_type === 'PERCENT'}
                    {goal.current_value}%
                  {:else}
                    {goal.current_value}/{goal.target_value}
                  {/if}
                </span>
                <span class="caption">{goal.progress_pct}%</span>
              </div>
              <div class="progress-track" style="height: 4px;">
                <div class="progress-fill" style="width:{goal.progress_pct}%"></div>
              </div>
            </div>
            <div class="goal-actions">
              {#if goal.state === 'ACTIVE'}
                <button class="btn btn-ghost text-muted" title="Pausar" on:click={() => updateGoalState(goal.id, 'PAUSED')}>
                  <Pause size={14} />
                </button>
                <button class="btn btn-ghost text-success" title="Completar" on:click={() => completeGoal(goal.id)}>
                  <Check size={14} />
                </button>
              {:else if goal.state === 'PAUSED'}
                <button class="btn btn-ghost text-muted" title="Reanudar" on:click={() => updateGoalState(goal.id, 'ACTIVE')}>
                  <Play size={14} />
                </button>
              {/if}
              {#if goal.state !== 'COMPLETED' && goal.state !== 'FAILED'}
                <button class="btn btn-ghost text-muted" title="Cancelar" on:click={() => updateGoalState(goal.id, 'CANCELLED')}>
                  <Ban size={14} />
                </button>
              {/if}
              <button class="btn btn-ghost text-muted" title="Eliminar" on:click={() => deleteGoal(goal.id)}>×</button>
              <button class="btn btn-ghost text-muted" title="Editar" on:click={() => openEditModal(goal)}>
                <Pencil size={13} />
              </button>
            </div>
          </div>
        {/each}

        <!-- Next Assigned Tasks -->
        <h3 class="section-title" style="margin-top: 24px;">Próximos Asignados</h3>
        <div class="history-goal-list" style="width:100%">
          {#if upcomingTasks.length === 0}
            <div class="empty-state">No hay tareas próximas planificadas.</div>
          {/if}
          {#each upcomingTasks as task}
            {@const g = task.goal}
            <button class="history-goal-item assigned" style="border-left-color: {getGoalColor(g)}; display:flex; align-items:center; background: transparent; border: none; width: 100%;" on:click={() => goto(`/goals/${g.id}`)}>
              <div class="hgi-info" style="flex: 1;">
                <div class="hgi-title">{g.title}</div>
                <div class="hgi-meta">
                  <span class="config-badge">{task.date}</span>
                  <span class="config-badge" style="margin-left: 8px; background: {getGoalColor(g)}20; border: 1px solid {getGoalColor(g)}; color: {getGoalColor(g)};">{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span>
                </div>
              </div>
            </button>
          {/each}
        </div>
      </div>

      <!-- Dashboard Right Column -->
      <div class="dashboard-side-col" style="display: flex; flex-direction: column; gap: 16px;">
        <button class="btn btn-primary" style="width: 100%; justify-content: center; padding: 12px;" on:click={() => showAddForm = !showAddForm}>
          <Plus size={16} /> Nuevo Objetivo
        </button>

        <div class="dash-card">
          <div class="dash-card-header">
            <Calendar size={14} />
            <span>Mapa de la Semana</span>
          </div>
          <div style="display: flex; gap: 6px; justify-content: space-between; margin-top: 12px;">
            {#each currentWeekDates as day}
              <button 
                class="week-day-box" 
                title={day.dateStr}
                on:click={() => {
                  currentTab = 'history';
                  selectedHistoryDate = day.dateStr;
                }}
                style="flex: 1; aspect-ratio: 1; border-radius: 4px; border: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; background: {day.hasActivity ? 'var(--success)' : 'var(--surface)'}; color: {day.hasActivity ? 'var(--bg)' : 'var(--text-muted)'}; opacity: {day.isToday ? '1' : '0.8'}; {day.isToday ? 'box-shadow: 0 0 0 2px var(--border);' : ''}"
              >
                <span style="font-size: 10px; font-weight: bold; margin-bottom: 2px;">{day.dayName}</span>
                <span style="font-size: 12px; font-weight: {day.isToday ? 'bold' : 'normal'};">{day.dateStr.split('-')[2]}</span>
              </button>
            {/each}
          </div>
        </div>

        <div class="dash-card" style="aspect-ratio: 1; display: flex; flex-direction: column; padding: 0; overflow: hidden;">
          <div class="widget-header" style="display: flex; justify-content: space-between; align-items: center; padding: 12px; border-bottom: 1px solid var(--border-light); background: var(--bg-card);">
            <button class="btn btn-ghost text-muted" style="padding: 4px;" on:click={() => activeWidgetIndex = (activeWidgetIndex - 1 + 5) % 5}><ChevronLeft size={14}/></button>
            <span class="widget-title" style="font-size: 12px; font-weight: 600; text-align: center; flex: 1;">{widgetTitles[activeWidgetIndex]}</span>
            <button class="btn btn-ghost text-muted" style="padding: 4px;" on:click={() => activeWidgetIndex = (activeWidgetIndex + 1) % 5}><ChevronRight size={14}/></button>
          </div>
          <div class="widget-content" style="flex: 1; position: relative; padding: 16px; overflow: hidden; display: flex; align-items: center; justify-content: center;">
            {#if activeWidgetIndex === 0}
              <div class="prediction-hero" style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                <div class="prediction-stats-row" style="margin-top: 0; justify-content: space-around;">
                  <div class="trend-summary">
                    <div class="trend-icon-wrap {prediction.trend.toLowerCase()}">
                      {#if prediction.trend === 'UP'} <TrendingUp size={14} /> {:else} <TrendingDown size={14} /> {/if}
                      <span class="trend-pct">{prediction.percentChange > 0 ? '+' : ''}{prediction.percentChange}%</span>
                    </div>
                    <span class="trend-label">Disciplina</span>
                  </div>
                  <div class="prediction-estimate">
                    <span class="pred-lab">Próx. 30d</span>
                    <span class="pred-val">~{prediction.estimateNextMonth}✓</span>
                  </div>
                </div>
              </div>
            {:else if activeWidgetIndex === 1}
              <div class="weekday-chart" style="width: 100%; height: 100%; padding-top: 10px;">
                {#each completionsByDay as day}
                  {@const maxVal = Math.max(...completionsByDay.map(d => d.value)) || 1}
                  {@const intensity = day.value > 0 ? Math.max(30, (day.value / maxVal) * 100) : 0}
                  <div class="day-col">
                    <span class="day-val" style="color: {day.value > 0 ? 'var(--text-primary)' : 'var(--text-disabled)'}">{day.value}</span>
                    <div class="day-bar-wrap" style="height: 60px;">
                      <div class="day-bar" style="height: {day.value > 0 ? Math.max(8, intensity) : 0}%; background: {day.value > 0 ? `color-mix(in srgb, var(--xp) ${intensity}%, transparent)` : 'transparent'}; border: {day.value === 0 ? '1px dashed var(--border)' : 'none'};"></div>
                    </div>
                    <span class="day-label">{day.label[0]}</span>
                  </div>
                {/each}
              </div>
            {:else if activeWidgetIndex === 2}
              <div class="radar-container" style="width: 100%; height: 100%;">
                {#if radarData.length === 0}
                  <div class="empty-state mini">Sin datos suficientes</div>
                {:else}
                  <svg viewBox="0 0 100 100" class="radar-svg" style="max-height: 100%; margin: 0 auto; display: block;">
                    {#each [20, 40, 60, 80, 100] as r}
                      <polygon points={radarData.map(d => `${50 + (r/100)*40*Math.cos(d.angle)},${50 + (r/100)*40*Math.sin(d.angle)}`).join(' ')} fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="0.5" />
                    {/each}
                    <polygon points={radarData.map(d => `${50 + d.pct*40*Math.cos(d.angle)},${50 + d.pct*40*Math.sin(d.angle)}`).join(' ')} fill="var(--xp)" fill-opacity="0.3" stroke="var(--xp)" stroke-width="1" stroke-linejoin="round" />
                    {#each radarData as d}
                      <circle cx={50 + d.pct*40*Math.cos(d.angle)} cy={50 + d.pct*40*Math.sin(d.angle)} r="1.5" fill="var(--surface)" stroke="var(--xp)" stroke-width="1" />
                    {/each}
                  </svg>
                {/if}
              </div>
            {:else if activeWidgetIndex === 3}
              <div class="debt-content" style="width: 100%; height: 100%; display: flex; flex-direction: column;">
                <div class="debt-total" style="padding-bottom: 8px;">
                  <span class="debt-val" style="font-size: 24px;">{debtData.total}</span>
                  <span class="debt-lab">Pendientes</span>
                </div>
                <div class="debt-list" style="flex: 1; overflow: hidden;">
                  {#if debtData.goals.length === 0}
                     <div class="empty-state mini">Cero deudas.</div>
                  {:else}
                    {#each debtData.goals.slice(0,3) as d}
                      <div class="debt-item" style="margin-bottom: 8px;">
                        <span class="debt-title" style="font-size: 11px;">{d.title}</span>
                        <div class="debt-bar-wrap" style="height: 4px; margin-top: 4px;">
                          <div class="debt-bar" style="width: {(d.debt / (debtData.goals[0]?.debt || 1)) * 100}%"></div>
                        </div>
                      </div>
                    {/each}
                  {/if}
                </div>
              </div>
            {:else if activeWidgetIndex === 4}
              <div class="funnel-chart" style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; gap: 8px;">
                {#each funnelData.slice(0,3) as f}
                  <div class="funnel-row" style="margin-bottom: 0;">
                    <div class="funnel-label-col" style="flex: 1; display: flex; justify-content: space-between;">
                      <span class="funnel-name" style="font-size: 11px;">{f.label}</span>
                      <span class="funnel-val" style="color: {f.color}; font-size: 11px;">{f.value}</span>
                    </div>
                    <div class="funnel-bar-col" style="flex: 2; height: 6px;">
                      <div class="funnel-bar" style="width: {(f.value / (funnelData[0]?.value || 1)) * 100}%; background: {f.color};"></div>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
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
            <div class="history-detail-date" style="text-transform:none;">Lista de Objetivos</div>
          </div>
          <div style="padding: 0 var(--s3) 8px; display: flex; justify-content: flex-end; border-bottom: 1px solid var(--border-light); margin-bottom: 8px;">
            <select class="input" style="padding: 2px 8px; font-size: 11px; height: auto;" bind:value={listSortBy}>
              <option value="recent">Orden: Reciente</option>
              <option value="alpha">Orden: Alfabético</option>
              <option value="state">Orden: Estado</option>
            </select>
          </div>

          <div class="history-goal-list" style="width: 100%;">
            {#each filteredUnassignedGoals as goal (goal.id)}
              <button
                class="history-goal-item assigned"
                style="width: 100%; border-left-color: {getGoalColor(goal)}; display: flex; align-items:center; justify-content:space-between; text-align: left;"
                on:click={() => assignGoalToDate(goal.id, selectedPlanningDate)}
                title="Asignar al día seleccionado"
              >
                <div class="hgi-info">
                  <div class="hgi-title" style="color: var(--text-primary);">{goal.title}</div>
                  <div class="hgi-meta">
                    <span class="config-badge" style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(goal)}; color: {getGoalColor(goal)};">{goal.temporality}</span>
                    {#if goal.state === 'PAUSED'}
                      <span class="status-badge" style="background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.1);">Pausado</span>
                    {/if}
                    {#if goal.max_assignment_days}
                      <span class="config-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.1); color: var(--text-muted); border: 1px solid rgba(59, 130, 246, 0.2);">Límite: {goal.max_assignment_days}d</span>
                    {/if}
                  </div>
                </div>
                <div style="display:flex; gap:6px;">
                  <span class="btn btn-ghost text-muted" title="Asignar"><ChevronRight size={14} /></span>
                </div>
              </button>
            {/each}
          </div>
        </div>

        <!-- Center: Calendar (fixed year view, allow future months) -->
        <div class="planning-center-col history-detail-col">
          <div class="history-detail-header">
            <span class="section-title" style="margin:0;">Calendario</span>
          </div>
          <div class="history-heatmap-wrap">
            <StreakHeatmap
              history={historyData}
              color="var(--success)"
              selectedDate={selectedPlanningDate}
              onselect={(date) => selectedPlanningDate = date}
              maxFutureMonths={1200}
            />
          </div>
        </div>

        <!-- Right: Assigned for selected date -->
        <div class="planning-right-col history-detail-col">
          <div class="history-detail-header">
            <div class="history-detail-date" style="text-transform:none;">Asignados · {selectedPlanningDate}</div>
          </div>

          <div class="history-goal-list" style="width:100%">
            {#each ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'] as temp}
              {@const normDate = getNormalizedDate(selectedPlanningDate, temp as 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'ANNUAL')}
              {@const assignedIds = assignments[normDate] || []}
              {@const filteredGoals = assignedIds.map(id => goals.find(g => g.id === id)).filter((g): g is Goal => g !== undefined && Boolean(g) && g.temporality === temp)}
              
              {#if filteredGoals.length > 0}
                <div class="planning-section-header">
                  {temp === 'DAILY' ? 'Día' : temp === 'WEEKLY' ? 'Semana' : temp === 'MONTHLY' ? 'Mes' : 'Año'}
                </div>
                {#each filteredGoals as g (g.id)}
                  {@const status = getGoalStatusOnDate(g, selectedPlanningDate)}
                  <div class="history-goal-item assigned" class:status-completed={status === 'COMPLETED'} class:status-failed={status === 'FAILED'} style="border-left-color: {status === 'FAILED' ? '#ef4444' : (status === 'COMPLETED' ? '#10b981' : getGoalColor(g))}; display:flex; align-items:center;">
                    <div style="display:flex; gap:6px; margin-right: 8px;">
                      <button class="btn btn-ghost text-muted" style="padding: 4px;" on:click={() => unassignGoalFromDate(g.id, selectedPlanningDate)} title="Quitar"><ChevronLeft size={14} /></button>
                    </div>
                    <div class="hgi-info" style="flex: 1;">
                      <div class="hgi-title">{g.title}</div>
                      <div class="hgi-meta">
                        <span class="config-badge" style="background: {getGoalColor(g)}20; border: 1px solid {getGoalColor(g)}; color: {getGoalColor(g)};">{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span>
                        {#if status === 'COMPLETED'}
                          <span class="status-badge success">Completado</span>
                        {:else if status === 'FAILED'}
                          <span class="status-badge error">Fallido</span>
                        {/if}
                        {#if g.max_assignment_days}
                          <span class="config-badge" style="margin-left: 8px; background: rgba(59, 130, 246, 0.1); color: var(--text-muted); border: 1px solid rgba(59, 130, 246, 0.2);">Límite: {g.max_assignment_days}d</span>
                        {/if}
                      </div>
                    </div>
                  </div>
                {/each}
              {/if}
            {/each}

            {#if !(['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'] as const).some(temp => (assignments[getNormalizedDate(selectedPlanningDate, temp as 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'ANNUAL')] || []).some(id => goals.find(g => g.id === id)?.temporality === temp))}
              <div class="history-detail-empty" style="padding: 2rem; border: 1px dashed var(--border); border-radius: var(--r); margin: 1rem;">
                <span class="history-detail-msg" style="font-size: 12px; text-align: center; display: block;">No hay objetivos asignados para este periodo.</span>
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
            <span class="section-title" style="margin:0;">Mapa Anual</span>
            <span class="history-hint">Selecciona un día para ver sus objetivos</span>
          </div>
          {#if historyData.length === 0}
            <div class="empty-state">Aún no hay actividad registrada.</div>
          {:else}
            <div class="history-heatmap-wrap">
              <StreakHeatmap
                history={historyData}
                color="var(--success)"
                selectedDate={selectedHistoryDate}
                onselect={(date) => selectedHistoryDate = date}
              />
            </div>
          {/if}
        </div>

        <!-- Right: Detail Panel -->
        <div class="history-detail-col">
          {#if !selectedHistoryDate}
            <div class="history-detail-empty">
              <div class="history-detail-icon"><Calendar size={40} strokeWidth={1} /></div>
              <span class="history-detail-msg">Selecciona un día en el calendario para ver los objetivos de esa fecha.</span>
            </div>
          {:else}
            <div class="history-detail-header">
              <div class="history-detail-date" style="text-transform:none;">{formatHistoryDate(selectedHistoryDate)}</div>
            </div>

            {#if goalsForDate.completed.length === 0 && goalsForDate.failed.length === 0}
              <div class="history-no-activity">
                <span>Sin actividad registrada para este día.</span>
              </div>
            {/if}

            {#if goalsForDate.completed.length > 0}
              <div class="history-section-label success"><Check size={12} /> Completados ({goalsForDate.completed.length})</div>
              <div class="history-goal-list">
                {#each goalsForDate.completed as g (g.id)}
                  <div class="history-goal-item completed" style="border-left-color: {getGoalColor(g)};">
                    <div class="hgi-icon-left">
                      <StreakIcon name={g.fail_emoji} size={16} color={getGoalColor(g)} />
                    </div>
                    <div class="hgi-info">
                      <div class="hgi-title">{g.title}</div>
                      <div class="hgi-meta">
                        <span class="config-badge" style="background: {getGoalColor(g)}20; border: 1px solid {getGoalColor(g)}; color: {getGoalColor(g)};">{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span>
                        <div class="hgi-bar">
                          <div class="hgi-bar-fill" style="width:100%; background:{getGoalColor(g)};"></div>
                        </div>
                        <span class="hgi-pct" style="color: {getGoalColor(g)};">100%</span>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}

            {#if goalsForDate.failed.length > 0}
              <div class="history-section-label failed"><X size={12} /> Fallidos ({goalsForDate.failed.length})</div>
              <div class="history-goal-list">
                {#each goalsForDate.failed as g (g.id)}
                  <div class="history-goal-item failed" style="border-left-color: #ef4444;">
                    <div class="hgi-icon-left">
                      <StreakIcon name={g.fail_emoji} size={16} color="#ef4444" />
                    </div>
                    <div class="hgi-info">
                      <div class="hgi-title">{g.title}</div>
                      <div class="hgi-meta">
                        <span class="config-badge" style="background: #ef444420; border: 1px solid #ef4444; color: #ef4444;">{TEMPORALITY_LABELS[g.temporality] || g.temporality}</span>
                        <div class="hgi-bar">
                          <div class="hgi-bar-fill" style="width:{g.progress_pct}%; background: #ef4444;"></div>
                        </div>
                        <span class="hgi-pct" style="color:#ef4444;">{g.progress_pct}%</span>
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
              <span class="stb-label">Completados</span>
            </div>
          </div>
          <div class="stb-item">
            <X size={16} class="text-error" />
            <div style="display:flex; flex-direction:column; gap:2px;">
              <span class="stb-val text-error">{failedGoalsCount}</span>
              <span class="stb-label">Fallidos</span>
            </div>
          </div>
          <div class="stb-item" style="flex: 1; flex-direction: column; align-items: stretch; justify-content: center; gap: 8px;">
            <div style="display:flex; justify-content:space-between; align-items: flex-end;">
              <span class="stb-label">Efectividad Global</span>
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
              <span>Predicción y Tendencia</span>
            </div>
            <div class="prediction-hero">
              <div class="candle-chart-container">
                <svg viewBox="0 0 500 150" class="candle-svg">
                  <!-- Grid Lines -->
                  {#each [0, 0.25, 0.5, 0.75, 1] as p}
                    <line x1="0" y1={p * 150} x2="480" y2={p * 150} stroke="rgba(255,255,255,0.03)" stroke-width="1" />
                    <text x="485" y={p * 150 + 4} font-size="8" fill="var(--text-muted)" font-family="var(--font-mono)">
                      {Math.round(candleScale.max - p * candleScale.range)}
                    </text>
                  {/each}

                  <!-- Trend Line (Moving Average simulated) -->
                  <path 
                    d={candleData.map((c, i) => `${i === 0 ? 'M' : 'L'} ${(i/29)*470} ${getY((c.open+c.close)/2)}`).join(' ')} 
                    fill="none" 
                    stroke="rgba(255,255,255,0.1)" 
                    stroke-width="1"
                  />

                  {#each candleData as candle, i}
                    {@const x = (i / 29) * 470}
                    {@const yOpen = getY(candle.open)}
                    {@const yClose = getY(candle.close)}
                    {@const yHigh = getY(candle.high)}
                    {@const yLow = getY(candle.low)}
                    {@const isUp = candle.close >= candle.open}
                    {@const color = isUp ? 'var(--success)' : 'var(--error)'}
                    
                    <!-- Wick -->
                    <line x1={x + 4} y1={yHigh} x2={x + 4} y2={yLow} stroke={color} stroke-width="1" opacity="0.4" />
                    <!-- Body -->
                    <rect 
                      x={x} 
                      y={Math.min(yOpen, yClose)} 
                      width="6" 
                      height={Math.max(1.5, Math.abs(yOpen - yClose))} 
                      fill={color} 
                      rx="0.5"
                    />
                  {/each}
                </svg>
              </div>

              <div class="prediction-stats-row">
                <div class="trend-summary">
                  <div class="trend-icon-wrap {prediction.trend.toLowerCase()}">
                    {#if prediction.trend === 'UP'} <TrendingUp size={14} /> {:else} <TrendingDown size={14} /> {/if}
                    <span class="trend-pct">{prediction.percentChange > 0 ? '+' : ''}{prediction.percentChange}%</span>
                  </div>
                  <span class="trend-label">Ratio Disciplina</span>
                </div>
                <div class="prediction-estimate">
                  <span class="pred-lab">Próx. 30d</span>
                  <span class="pred-val">~{prediction.estimateNextMonth}✓</span>
                </div>
              </div>
            </div>
          </div>

          <div class="dash-card weekday-card">
            <div class="dash-card-header">
              <Activity size={16} />
              <span>Actividad por Día</span>
            </div>
            <div class="weekday-chart">
              {#each completionsByDay as day}
                {@const maxVal = Math.max(...completionsByDay.map(d => d.value)) || 1}
                {@const intensity = day.value > 0 ? Math.max(30, (day.value / maxVal) * 100) : 0}
                <div class="day-col">
                  <span class="day-val" style="color: {day.value > 0 ? 'var(--text-primary)' : 'var(--text-disabled)'}">{day.value}</span>
                  <div class="day-bar-wrap">
                    <div class="day-bar" style="height: {day.value > 0 ? Math.max(8, intensity) : 0}%; background: {day.value > 0 ? `color-mix(in srgb, var(--xp) ${intensity}%, transparent)` : 'transparent'}; border: {day.value === 0 ? '1px dashed var(--border)' : 'none'};"></div>
                  </div>
                  <span class="day-label">{day.label}</span>
                </div>
              {/each}
            </div>
          </div>

          <div class="dash-card temporality-card">
            <div class="dash-card-header">
              <Target size={16} />
              <span>Progreso por Periodo</span>
            </div>
            <div class="temporality-rows">
              {#each progressOverview as p}
                <div class="temp-row">
                  <div class="temp-info">
                    <span class="temp-name">{p.temp}</span>
                    <span class="temp-stats">
                      <span class="text-success">{p.completed} ✓</span> / <span class="text-error">{p.failed} ✗</span>
                    </span>
                  </div>
                  <div class="temp-bar-container">
                    <div class="temp-bar" style="width: {p.avgProgress}%"></div>
                    <span class="temp-perc">{p.avgProgress}%</span>
                  </div>
                </div>
              {/each}
            </div>
          </div>

          <div class="dash-card hourly-card">
            <div class="dash-card-header">
              <Clock size={16} />
              <span>Actividad Horaria</span>
            </div>
            <div class="hourly-chart">
              {#each activityByHour as hour}
                <div class="hour-col" title="{hour.label}: {hour.val} completados">
                  <div class="hour-bar-wrap">
                    <div class="hour-bar" style="height: {hour.pct * 100}%; opacity: {Math.max(0.15, hour.pct)};"></div>
                  </div>
                  {#if hour.hour % 4 === 0}
                    <span class="hour-label">{hour.hour}h</span>
                  {/if}
                </div>
              {/each}
            </div>
          </div>

          <div class="dash-card radar-card">
            <div class="dash-card-header">
              <Hexagon size={16} />
              <span>Radar de Foco</span>
            </div>
            <div class="radar-container">
              {#if radarData.length === 0}
                <div class="empty-state mini">Sin datos suficientes</div>
              {:else}
                <svg viewBox="0 0 100 100" class="radar-svg">
                  {#each [20, 40, 60, 80, 100] as r}
                    <polygon points={radarData.map(d => `${50 + (r/100)*40*Math.cos(d.angle)},${50 + (r/100)*40*Math.sin(d.angle)}`).join(' ')} fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="0.5" />
                  {/each}
                  {#each radarData as d}
                    <line x1="50" y1="50" x2={50 + 40*Math.cos(d.angle)} y2={50 + 40*Math.sin(d.angle)} stroke="rgba(255,255,255,0.05)" stroke-width="0.5" />
                    <text x={d.labelX} y={d.labelY} font-size="4" fill="var(--text-muted)" text-anchor="middle" dominant-baseline="middle" font-family="var(--font-mono)">
                      {d.name.substring(0,8)}
                    </text>
                  {/each}
                  <polygon points={radarData.map(d => `${50 + d.pct*40*Math.cos(d.angle)},${50 + d.pct*40*Math.sin(d.angle)}`).join(' ')} fill="var(--xp)" fill-opacity="0.3" stroke="var(--xp)" stroke-width="1" stroke-linejoin="round" />
                  {#each radarData as d}
                    <circle cx={50 + d.pct*40*Math.cos(d.angle)} cy={50 + d.pct*40*Math.sin(d.angle)} r="1.5" fill="var(--surface)" stroke="var(--xp)" stroke-width="1" />
                  {/each}
                </svg>
              {/if}
            </div>
          </div>

          <div class="dash-card debt-card">
            <div class="dash-card-header">
              <Flame size={16} class="text-error" />
              <span>Deuda Acumulada</span>
            </div>
            <div class="debt-content">
              <div class="debt-total">
                <span class="debt-val">{debtData.total}</span>
                <span class="debt-lab">Pendientes</span>
              </div>
              <div class="debt-list">
                {#if debtData.goals.length === 0}
                   <div class="empty-state mini">Cero deudas. ¡Excelente!</div>
                {:else}
                  {#each debtData.goals as d}
                    <div class="debt-item">
                      <span class="debt-title">{d.title}</span>
                      <div class="debt-bar-wrap">
                        <div class="debt-bar" style="width: {(d.debt / (debtData.goals[0]?.debt || 1)) * 100}%"></div>
                      </div>
                      <span class="debt-count">{d.debt}</span>
                    </div>
                  {/each}
                {/if}
              </div>
            </div>
          </div>

          <div class="dash-card funnel-card">
            <div class="dash-card-header">
              <Filter size={16} />
              <span>Conversión y Abandono</span>
            </div>
            <div class="funnel-chart">
              {#each funnelData as f}
                <div class="funnel-row">
                  <div class="funnel-label-col">
                    <span class="funnel-name">{f.label}</span>
                    <span class="funnel-val" style="color: {f.color}">{f.value}</span>
                  </div>
                  <div class="funnel-bar-col">
                    <div class="funnel-bar" style="width: {(f.value / (funnelData[0]?.value || 1)) * 100}%; background: {f.color};"></div>
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
    <div class="new-goal-backdrop" on:click|self={() => showAddForm = false} role="dialog" tabindex="-1">
      <div class="new-goal-panel slide-down">
        <div class="new-goal-header">
          <div class="new-goal-title-row">
            <div class="new-goal-icon-wrap">
              <Plus size={16} />
            </div>
            <div>
              <h3 class="new-goal-heading">Nuevo Objetivo</h3>
              <span class="new-goal-sub">Define un nuevo hábito o meta a seguir</span>
            </div>
          </div>
          <button class="history-close-btn" on:click={() => showAddForm = false} title="Cerrar">
            <X size={15} />
          </button>
        </div>

        <div class="new-goal-body">
          <!-- Section Tabs -->
          <div class="ng-tabs-container">
            <button class="ng-tab" class:active={ngActiveSection === 'basics'} on:click={() => ngActiveSection = 'basics'}>Básico</button>
            <button class="ng-tab" class:active={ngActiveSection === 'appearance'} on:click={() => ngActiveSection = 'appearance'}>Apariencia</button>
            <button class="ng-tab" class:active={ngActiveSection === 'advanced'} on:click={() => ngActiveSection = 'advanced'}>Avanzado</button>
          </div>

          <div class="ng-content-area">
            {#if ngActiveSection === 'basics'}
              <div class="ng-section-fade">
                <div class="form-field">
                  <label class="label">Título del objetivo</label>
                  <input class="input w-full" bind:value={newTitle} placeholder="Ej: Leer 10 páginas, Correr 5km..." maxlength="38" autofocus />
                </div>
                <div class="form-field">
                  <label class="label">Descripción <span class="optional">(Opcional)</span></label>
                  <textarea 
                    class="input w-full" 
                    bind:value={newDescription} 
                    placeholder="Motivación, detalles o reglas de este objetivo..." 
                    maxlength="63" 
                    rows="2"
                    on:keydown={(e) => e.key === 'Enter' && e.preventDefault()}
                    on:input={(e) => newDescription = e.currentTarget.value.replace(/\n/g, '')}
                  ></textarea>
                </div>
                <div class="form-field">
                  <label class="label">Frecuencia de Repetición</label>
                  <div class="ng-freq-grid">
                    {#each TEMPORALITIES as temp}
                      <button class="ng-freq-btn" class:active={newTemporality === temp} on:click={() => newTemporality = temp}>
                        {temp === 'DAILY' ? 'Diario' : temp === 'WEEKLY' ? 'Semanal' : temp === 'MONTHLY' ? 'Mensual' : 'Anual'}
                      </button>
                    {/each}
                  </div>
                </div>
              </div>
            {/if}

            {#if ngActiveSection === 'appearance'}
              <div class="ng-section-fade">
                <div class="form-field">
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <label class="label" style="margin:0;">Icono / Emoji de Fallo</label>
                    <div class="icon-toggle-row">
                      <button class="icon-type-btn" class:selected={!useFailIcon} on:click={() => useFailIcon = false}>Emoji</button>
                      <button class="icon-type-btn" class:selected={useFailIcon} on:click={() => useFailIcon = true}>Icono</button>
                    </div>
                  </div>
                  {#if !useFailIcon}
                    <div class="emoji-grid ng-large-grid">
                      {#each EMOJIS as e}
                        <button class="emoji-btn" class:selected={newFailEmoji === e} on:click={() => newFailEmoji = e}>{e}</button>
                      {/each}
                    </div>
                  {:else}
                    <div class="field ng-large-grid">
                      <IconPicker selected={newFailIcon} color={newGoalColor} onSelect={(ic) => newFailIcon = ic} />
                    </div>
                  {/if}
                </div>

                <div class="form-field">
                  <label class="label">Color de Identidad</label>
                  <div class="color-presets ng-expanded-presets">
                    {#each COLOR_PRESETS as c}
                      <button
                        class="color-dot"
                        class:selected={newGoalColor === c.hex}
                        style="background: {c.hex}; color: {c.hex};"
                        on:click={() => newGoalColor = c.hex}
                      ></button>
                    {/each}
                    <div class="color-custom" style="background: {newGoalColor};">
                      <input type="color" bind:value={newGoalColor} class="color-picker" />
                    </div>
                  </div>
                </div>
              </div>
            {/if}

            {#if ngActiveSection === 'advanced'}
              <div class="ng-section-fade">
                <div class="form-row">
                  <div class="form-field" style="flex:1;">
                    <label class="label">Tipo de Medición</label>
                    <select class="input w-full" bind:value={newMeasurement}>
                      <option value="COUNT">Cuenta Numérica</option>
                      <option value="BOOLEAN">Hecho / No Hecho</option>
                      <option value="PERCENT">Porcentaje</option>
                    </select>
                  </div>
                  <div class="form-field" style="width: 140px;">
                    <label class="label">Meta a Alcanzar</label>
                    <input class="input w-full" type="number" bind:value={newTargetValue} min="1" disabled={newMeasurement === 'BOOLEAN'} />
                  </div>
                  <div class="form-field" style="width: 140px;">
                    <label class="label">Límite días <span class="optional">(Opc)</span></label>
                    <input class="input w-full" type="number" bind:value={newMaxAssignmentDays} min="1" placeholder="Ilimitado" />
                  </div>
                </div>

                <div class="form-field">
                  <label class="label">Política de Incumplimiento (Fallo)</label>
                  <div class="ng-fail-options">
                    <button class="ng-fail-btn" class:active={newFailConfig === 'STATIC'} on:click={() => newFailConfig = 'STATIC'}>
                      <strong>Estático</strong>
                      <span>Se reinicia a cero cada periodo</span>
                    </button>
                    <button class="ng-fail-btn" class:active={newFailConfig === 'ROLLOVER'} on:click={() => newFailConfig = 'ROLLOVER'}>
                      <strong>Traspaso</strong>
                      <span>La meta pendiente pasa al siguiente día</span>
                    </button>
                    <button class="ng-fail-btn" class:active={newFailConfig === 'SNOWBALL'} on:click={() => newFailConfig = 'SNOWBALL'}>
                      <strong>Acumulativo</strong>
                      <span>La deuda se acumula exponencialmente</span>
                    </button>
                  </div>
                </div>

                <div class="form-row">
                  <div class="form-field" style="flex:1;">
                    <label class="label">Vincular a Proyecto (Nota)</label>
                    <select class="input w-full" bind:value={newNoteId}>
                      <option value={null}>Sin nota vinculada</option>
                      {#each notes as n}
                        <option value={n.id}>{n.title}</option>
                      {/each}
                    </select>
                  </div>
                  <div class="form-field" style="flex:1;">
                    <label class="label">Sincronización de Tag</label>
                    <select class="input w-full" bind:value={newTagId}>
                      <option value={null}>Actualización manual</option>
                      {#each notes as n}
                        {@const tagId = tags.find(t => t.name === n.title)?.id}
                        {#if tagId}
                          <option value={tagId}>{n.title} (Auto-rastreo)</option>
                        {/if}
                      {/each}
                    </select>
                  </div>
                </div>
              </div>
            {/if}
          </div>

          <!-- Bottom Preview Section (Moved from top) -->
          <div class="ng-bottom-preview">
            <span class="ng-preview-label">Vista Previa</span>
            <div class="goal-card preview-card-live" style="border-color: {newGoalColor}; background: color-mix(in srgb, {newGoalColor} 5%, var(--surface));">
              <div class="goal-main">
                <div class="goal-title">
                  <span class="emoji-badge" style="display:flex; align-items:center; margin-right:8px;">
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
            <button class="btn btn-ghost" on:click={() => showAddForm = false}>Cancelar</button>
            <button class="btn btn-primary" on:click={addGoal} disabled={saving || !newTitle.trim()}>
              {saving ? 'Guardando...' : 'Crear objetivo'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}

  {#if editingGoal}
    <div class="modal-overlay" on:click|self={() => editingGoal = null} role="dialog" tabindex="-1">
      <div class="modal-card fade-in">
        <div class="modal-header">
          <h3 class="section-title" style="margin:0;">Editar Objetivo</h3>
          <button class="btn btn-ghost" on:click={() => editingGoal = null}><X size={16} /></button>
        </div>
        <div class="form-field">
          <label class="label">Título</label>
          <input class="input w-full" bind:value={editTitle} />
        </div>
        <div class="form-field">
          <label class="label">Descripción</label>
          <textarea class="input w-full" bind:value={editDescription} rows="2"></textarea>
        </div>
        <div class="form-row">
          <div class="form-field" style="flex:1;">
            <label class="label">Medición</label>
            <select class="input w-full" bind:value={editMeasurement}>
              <option value="COUNT">Cuenta Numérica</option>
              <option value="BOOLEAN">Hecho / No Hecho</option>
              <option value="PERCENT">Porcentaje</option>
            </select>
          </div>
          <div class="form-field" style="width:120px;">
            <label class="label">Meta</label>
            <input class="input w-full" type="number" bind:value={editTargetValue} min="1" />
          </div>
          <div class="form-field" style="width:100px;">
            <label class="label">Límite (días)</label>
            <input class="input w-full" type="number" bind:value={editMaxAssignmentDays} min="1" placeholder="∞" />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field" style="flex:1;">
            <label class="label">Regla de Fallo</label>
            <select class="input w-full" bind:value={editFailConfig}>
              <option value="STATIC">Estático (Se reinicia)</option>
              <option value="ROLLOVER">Traspaso (Pasa al día sig.)</option>
              <option value="SNOWBALL">Acumulativo (Suma la deuda)</option>
            </select>
          </div>
          <div class="form-field" style="width:80px;">
            <label class="label">Color</label>
            <div class="color-custom" style="background: {editColor}; width:36px; height:36px;">
              <input type="color" bind:value={editColor} class="color-picker" />
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn btn-primary" on:click={saveEdit} disabled={editSaving || !editTitle.trim()}>
            {editSaving ? 'Guardando...' : 'Guardar cambios'}
          </button>
          <button class="btn btn-ghost" on:click={() => editingGoal = null}>Cancelar</button>
        </div>
      </div>
    </div>
  {/if}

  {#if pendingGoals.length > 0}
    <div class="modal-overlay" role="dialog" tabindex="-1">
      <div class="modal-card fade-in" style="max-width: 520px;">
        <div class="modal-header">
          <h3 class="section-title" style="margin:0; color: var(--warning, #f59e0b);">⚠ Objetivos Huérfanos</h3>
        </div>
        <p class="removal-desc">
          Los siguientes objetivos fueron eliminados del contenido de sus notas vinculadas. ¿Qué deseas hacer con cada uno?
        </p>
        {#each pendingGoals as pg (pg.id)}
          <div class="removal-item">
            <div class="removal-info">
              <span class="removal-title">{pg.title}</span>
              <span class="removal-meta">{pg.temporality} · {formatFailConfig(pg.fail_config)}</span>
            </div>
            <div class="removal-actions">
              <button class="btn btn-ghost removal-btn manual" title="Mantener como progreso manual" on:click={() => resolveRemoval(pg.id, 'manual')}>
                Manual
              </button>
              <button class="btn btn-ghost removal-btn cancel" title="Cancelar (archivar sin penalización)" on:click={() => resolveRemoval(pg.id, 'cancel')}>
                Cancelar
              </button>
              <button class="btn btn-ghost removal-btn delete" title="Eliminar permanentemente" on:click={() => resolveRemoval(pg.id, 'delete')}>
                Eliminar
              </button>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  {#if currentTab === 'editor'}
    <div class="tab-content fade-in" style="padding: 30px; height: 100%; box-sizing: border-box;">
      {#if editorGoal}
        <GoalEditor
          goal={editorGoal}
          content={editorContent}
          on:save={async (e) => {
            await api.goals.saveContent(editorGoal!.id, {
              title: e.detail.title,
              content: e.detail.content,
              temporality: editorGoal!.temporality,
              measurement_type: editorGoal!.measurement_type,
              target_value: editorGoal!.target_value,
              state: editorGoal!.state,
              fail_config: editorGoal!.fail_config,
              fail_emoji: editorGoal!.fail_emoji,
              color: editorGoal!.color,
              theme: editorGoal!.theme,
              note_id: editorGoal!.note_id,
              tag_id: editorGoal!.tag_id,
              parent_id: editorGoal!.parent_id,
              max_assignment_days: editorGoal!.max_assignment_days,
              description: e.detail.content,
            });
            goals = await api.goals.list();
            editorGoal = null;
          }}
          on:cancel={() => editorGoal = null}
        />
      {:else}
        <div style="height: 100%; display: flex; flex-direction: column;">
          <h3 class="section-title" style="margin: 0 0 30px 0; text-align: center;">Editor de Objetivos</h3>
          <div style="flex: 1; overflow: auto;">
            {#if goals.length === 0}
              <div class="empty-state">No hay objetivos. Crea uno desde Dashboard.</div>
            {:else}
              <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; height: 100%;">
                {#each goals as goal (goal.id)}
                  <button
                    class="goal-card"
                    style="text-align: left; cursor: pointer; height: fit-content; border-left: 3px solid {getGoalColor(goal)};"
                    on:click={async () => {
                      const res = await api.goals.getContent(goal.id);
                      editorGoal = goal;
                      editorContent = res?.content || goal.description || '';
                    }}
                  >
                    <div class="goal-main">
                      <div class="goal-title">{goal.title}</div>
                      <div class="goal-meta">
                        <span class="tag-chip" style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(goal)}; color: {getGoalColor(goal)};">{TEMPORALITY_LABELS[goal.temporality] || goal.temporality}</span>
                        <span class="tag-chip" style="background: {getGoalColor(goal)}20; border: 1px solid {getGoalColor(goal)}; color: {getGoalColor(goal)};">{STATE_LABELS[goal.state] || goal.state}</span>
                      </div>
                    </div>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}
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
    display: grid !important;
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
    background: rgba(255,255,255,0.02);
  }

  .status-badge {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 4px;
    text-transform: uppercase;
    font-weight: 600;
    margin-left: 8px;
  }
  .status-badge.success { background: rgba(16, 185, 129, 0.1); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.2); }
  .status-badge.error { background: rgba(239, 68, 68, 0.1); color: var(--error); border: 1px solid rgba(239, 68, 68, 0.2); }

  .history-heatmap-wrap {
    width: 100%;
    display: flex;
    justify-content: center;
  }
  .goals-body.full-width {
    max-width: none;
    margin: 0;
    padding: var(--s3) var(--s4);
    overflow: hidden;
    height: calc(100vh - 80px);
  }
  /* ── New Goal Centered Modal ── */
  .new-goal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 1100;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--s4);
  }
  .new-goal-panel {
    background: var(--surface);
    border: 1px solid var(--border);
    box-shadow: 0 24px 80px rgba(0,0,0,0.6);
    display: flex;
    flex-direction: column;
    max-height: 90vh;
    width: 620px;
    border-radius: 16px;
    overflow: hidden;
  }
  .slide-down {
    animation: modalPopIn 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  }
  @keyframes modalPopIn {
    from { transform: scale(0.95) translateY(10px); opacity: 0; }
    to { transform: scale(1) translateY(0); opacity: 1; }
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
    width: 32px; height: 32px; background: var(--surface-active);
    border: 1px solid var(--border); border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    color: var(--text-secondary); flex-shrink: 0;
  }
  .new-goal-heading {
    font-size: 11px; font-weight: 700; color: var(--text-muted);
    margin: 0; text-transform: uppercase; letter-spacing: 0.1em;
    font-family: var(--font-mono);
  }
  .new-goal-sub { display: none; }

  .new-goal-body {
    flex: 1;
    overflow-y: auto;
    padding: var(--s5) var(--s6);
    display: flex;
    flex-direction: column;
    gap: var(--s4);
  }

  .ng-bottom-preview {
    margin-top: var(--s2);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ng-preview-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-disabled);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    text-align: center;
  }

  .ng-tabs-container {
    display: flex;
    gap: 4px;
    background: var(--surface-hover);
    padding: 3px;
    border-radius: 8px;
    border: 1px solid var(--border);
  }
  .ng-tab {
    flex: 1;
    padding: 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    font-weight: 600;
    color: var(--text-disabled);
    background: transparent;
    border: none;
    cursor: pointer;
    border-radius: 6px;
    transition: all 0.2s;
  }
  .ng-tab:hover { color: var(--text-secondary); }
  .ng-tab.active { background: var(--surface); color: var(--text-primary); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }

  .ng-content-area {
    min-height: 380px;
  }

  .ng-section-fade {
    display: flex;
    flex-direction: column;
    gap: var(--s4);
    animation: ngFadeIn 0.3s ease;
  }
  @keyframes ngFadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
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
  .ng-freq-btn:hover { border-color: var(--text-muted); }
  .ng-freq-btn.active { background: var(--surface-active); color: var(--text-primary); border-color: var(--text-primary); }

  .ng-large-grid {
    max-height: 280px !important;
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
  .ng-fail-btn strong { font-size: 13px; color: var(--text-secondary); }
  .ng-fail-btn span { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
  .ng-fail-btn:hover { border-color: var(--text-muted); }
  .ng-fail-btn.active { background: rgba(var(--primary-rgb, 139, 92, 246), 0.1); border-color: var(--primary); }

  .new-goal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s6);
    border-top: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }
  .new-goal-actions { display: flex; gap: var(--s3); }
  .ng-error { font-size: 12px; color: var(--error); font-family: var(--font-mono); }
  .optional { font-size: 10px; color: var(--text-disabled); font-style: italic; }

  .ng-expanded-presets {
    justify-content: center;
    gap: 12px;
    padding: 12px;
    background: var(--surface-hover);
    border-radius: 8px;
    border: 1px solid var(--border);
  }
  .form-row {
    display: flex;
    gap: var(--s3);
    align-items: flex-start;
  }
  .form-field {
    display: flex;
    flex-direction: column;
    gap: 0px;
  }
  .label {
    display: block;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 6px;
  }
  .w-full {
    width: 100%;
  }
  
  .icon-toggle-row { display: flex; gap: 6px; }
  .icon-type-btn {
    flex: 1; padding: 4px 12px; font-size: 11px; font-family: var(--font-mono);
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; color: var(--text-muted); cursor: pointer;
    transition: all 0.15s;
  }
  .icon-type-btn.selected { border-color: var(--text-primary); color: var(--text-primary); }

  .emoji-grid {
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
  .emoji-btn:hover { background: var(--elevated); }
  .emoji-btn.selected { border-color: var(--text-primary); background: var(--elevated); }

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
    width: 32px; height: 32px; background: none;
    border: 1px solid transparent; cursor: pointer;
    border-radius: 4px; display: flex; align-items: center;
    justify-content: center; color: var(--text-muted);
    transition: all 0.15s;
  }
  .lucide-btn:hover { background: var(--elevated); color: var(--text-secondary); }
  .lucide-btn.selected { border-color: var(--text-primary); color: var(--text-primary); background: var(--elevated); }

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
  }
  .color-dot:hover { transform: scale(1.15); }
  .color-dot.selected { 
    border-color: var(--text-primary); 
    box-shadow: 0 0 0 2px var(--bg), 0 0 0 4px currentColor; 
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
  .color-custom:hover { transform: scale(1.1); border-color: var(--text-muted); }
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
  .theme-btn:hover { border-color: var(--text-muted); color: var(--text-secondary); }
  .theme-btn.selected { border-color: var(--text-primary); color: var(--text-primary); background: var(--elevated); }
  
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
  .goal-card.failed {
    border-color: var(--error);
    background: rgba(255,0,0,0.02);
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
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning, #f59e0b);
    border: 1px solid rgba(245, 158, 11, 0.3);
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
    background: var(--border);
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
  .text-success { color: var(--success) !important; }
  .text-muted { color: var(--text-muted) !important; }
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

  .planning-tabs-centered {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 24px;
    font-family: var(--font-serif, serif);
    color: var(--text-muted);
  }

  .planning-tabs-centered .planning-tab {
    font-size: 32px;
    padding: 0 10px;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .planning-tabs-centered .planning-tab.active {
    color: var(--text-primary);
    transform: scale(1.1);
    background: none;
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

  /* Edit Modal */
  .modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.55);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s5);
    width: 100%;
    max-width: 480px;
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    box-shadow: 0 16px 48px rgba(0,0,0,0.3);
  }
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
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
    padding: var(--s2) var(--s3) !important;
    font-size: 13px;
    margin-bottom: 4px !important;
    background: var(--surface-hover) !important;
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
  .expand-header:hover .section-title {
    color: var(--text-primary);
  }

  /* Advanced Dashboard Styles */
  .full-height-dashboard {
    height: calc(100vh - 150px);
    overflow-y: auto;
    padding-bottom: var(--s4);
    display: flex;
    flex-direction: column;
  }
  .dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    grid-auto-rows: minmax(180px, auto);
    gap: var(--s3);
    flex: 1;
  }
  .dash-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: var(--s3);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    backdrop-filter: blur(10px);
    transition: transform 0.2s, border-color 0.2s;
    min-height: 0; /* Allow shrinking */
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
    padding: var(--s4) var(--s5);
    margin-bottom: var(--s3);
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
    background: linear-gradient(90deg, var(--success), #34d399);
    border-radius: 2px;
    transition: width 1s ease-out;
  }

  /* Prediction Card Styles */
  .prediction-card {
    grid-column: span 2;
    background: var(--surface);
  }
  .prediction-hero {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    flex: 1;
    min-height: 0;
  }
  .candle-chart-container {
    flex: 1;
    min-height: 100px;
    background: rgba(0,0,0,0.15);
    border-radius: var(--r-sm, 8px);
    padding: var(--s3);
    position: relative;
    overflow: hidden;
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
  .trend-icon-wrap.up { color: var(--success); }
  .trend-icon-wrap.down { color: var(--error); }
  
  .prediction-estimate {
    text-align: right;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .trend-label, .pred-lab {
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

  .candle-svg rect {
    filter: drop-shadow(0 0 2px rgba(0,0,0,0.2));
  }
  .candle-svg rect:hover {
    filter: brightness(1.3);
    cursor: crosshair;
  }

  /* Weekday Chart */
  .weekday-card {
    grid-column: span 1;
  }
  .weekday-chart {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    height: 100%;
    max-height: 80px;
    padding: var(--s2) 0;
  }
  .day-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    flex: 1;
  }
  .day-bar-wrap {
    width: 10px;
    height: 100%;
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
    gap: var(--s2);
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
    background: var(--success);
    border-radius: 5px;
    transition: width 0.5s;
  }
  .temp-perc {
    position: absolute;
    right: 6px;
    font-size: 8px;
    font-weight: 700;
    color: #fff;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
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

  @media (max-width: 1024px) {
    .dashboard-grid {
      grid-template-columns: 1fr 1fr;
    }
  }
  @media (max-width: 640px) {
    .dashboard-grid {
      grid-template-columns: 1fr;
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
    font-size: 11px !important;
    padding: 4px 10px !important;
    border-radius: 4px !important;
    font-family: var(--font-mono) !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .removal-btn.manual {
    color: var(--success) !important;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }
  .removal-btn.manual:hover { background: rgba(16, 185, 129, 0.1); }
  .removal-btn.cancel {
    color: var(--warning, #f59e0b) !important;
    border: 1px solid rgba(245, 158, 11, 0.3);
  }
  .removal-btn.cancel:hover { background: rgba(245, 158, 11, 0.1); }
  .removal-btn.delete {
    color: var(--error) !important;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
  .removal-btn.delete:hover { background: rgba(239, 68, 68, 0.1); }

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

  .history-section-label.success { color: var(--success); }
  .history-section-label.failed  { color: var(--error); }

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

  .history-goal-item.completed { border-left: 3px solid var(--success); }
  .history-goal-item.failed    { border-left: 3px solid var(--error); }

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

  .hgi-meta .config-badge {
    margin-left: -6px;
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
  .dash-card { grid-column: span 2; }
  .radar-card { grid-column: span 1; }
  .funnel-card { grid-column: span 1; }
  
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
    background: rgba(255,255,255,0.02);
    border-radius: 5px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
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
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
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

</style>
