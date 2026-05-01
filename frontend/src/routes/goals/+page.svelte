<script lang="ts">
  import { onMount } from 'svelte';
  import { Plus, Check, ChevronDown, Calendar, BarChart, Clock, Layout, Pause, Play, Ban, Pencil, X, Flame, ChevronRight, TrendingUp, TrendingDown, PieChart, Activity, Target, Trophy, Settings, Palette } from 'lucide-svelte';
  import { api, type Goal, type Tag, type Note } from '$lib/api';
  import { applyGamificationResult, showXPGain } from '$lib/stores/gamification';
  import StreakIcon from '$lib/components/StreakIcon.svelte';

  import StreakHeatmap from '$lib/components/StreakHeatmap.svelte';

  let goals: Goal[] = [];
  let tags: Tag[] = [];
  let notes: Note[] = [];
  let currentTab: 'today' | 'planning' | 'history' | 'analytics' = 'today';
  let currentPlanningTab: 'WEEKLY' | 'MONTHLY' | 'ANNUAL' = 'ANNUAL';
  let showAddForm = false;

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

  const ICON_OPTIONS = Array.from(new Set([
    'Flame', 'Zap', 'Activity', 'Heart', 'Pill', 'Droplet', 'Cloud',
    'BookOpen', 'Book', 'Bookmark', 'FileText', 'Layers', 'Grid',
    'Palette', 'Pen', 'PenTool', 'Music', 'Music2', 'Music3', 'Music4',
    'Briefcase', 'Code', 'Code2', 'Cpu', 'Database', 'HardDrive', 'Monitor',
    'Dumbbell', 'Bike', 'Target', 'Trophy', 'Award', 'Medal',
    'Leaf', 'Flower', 'Clover', 'Sprout', 'Tree', 'CloudRain', 'Sun',
    'Plane', 'Map', 'Navigation', 'Compass', 'Anchor', 'Waves',
    'MessageSquare', 'MessageCircle', 'Send', 'Phone', 'Share', 'Share2',
    'Clock', 'Watch', 'Timer', 'Hourglass', 'Calendar', 'CalendarDays', 'Moon',
    'Star', 'Smile', 'Eye', 'Lightbulb', 'Shield', 'Lock', 'Unlock', 'Key',
    'Wifi', 'Settings', 'Bell', 'BellOff', 'Volume2', 'VolumeX', 'Mic', 'MicOff',
    'Camera', 'Video', 'Play', 'Pause', 'SkipBack', 'SkipForward',
    'ThumbsUp', 'ThumbsDown', 'Hand', 'CheckCircle', 'AlertCircle', 'HelpCircle',
    'Info', 'Package', 'Gift', 'Inbox', 'Layout', 'LayoutGrid', 'Columns',
    'Brain', 'Gauge', 'Sliders', 'Gamepad2', 'Coffee', 'Pencil', 'GraduationCap'
  ]));

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

  const TEMPORALITIES: Goal['temporality'][] = ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'];

  // New goal form
  let newTitle = '';
  let newDescription = '';
  let newTargetValue = 1;
  let newTemporality: Goal['temporality'] = 'DAILY';
  let newMeasurement: Goal['measurement_type'] = 'COUNT';
  let newFailConfig: Goal['fail_config'] = 'STATIC';
  let newFailEmoji = '🔴';
  let newFailIcon = 'Activity';
  let newGoalColor = '#c8a96e';
  let useFailIcon = false;
  let newTagId: number | null = null;
  let newNoteId: number | null = null;
  let saving = false;
  let ngActiveSection: 'basics' | 'appearance' | 'advanced' = 'basics';

  $: dailyGoals = goals.filter(g => g.temporality === 'DAILY' && g.state !== 'CANCELLED');
  $: planningGoals = goals.filter(g => g.state !== 'CANCELLED');
  $: pendingGoals = goals.filter(g => g.pending_removal);

  let historyData: any[] = [];
  $: {
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
  }

  // ── History tab state ──
  const _now = new Date();
  let selectedHistoryDate: string | null = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}-${String(_now.getDate()).padStart(2, '0')}`;

  $: goalsForDate = (() => {
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
  })();

  function formatHistoryDate(iso: string | null): string {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    const date = new Date(y, m - 1, d);
    const DAYS = ['Domingo','Lunes','Martes','Miércoles','Jueves','Viernes','Sábado'];
    const MONTHS = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
    return `${DAYS[date.getDay()]}, ${d} de ${MONTHS[m-1]} de ${y}`;
  }

  let loadError = '';
  let streakData = { current_streak: 0, best_streak: 0 };

  onMount(async () => {
    try {
      [goals, tags, notes, streakData] = await Promise.all([
        api.goals.list(),
        api.tags.list(),
        api.notes.list(),
        api.goals.streak()
      ]);
      // restore UI state (keep planning tab and selected date)
      try {
        const savedTab = localStorage.getItem('goals.currentTab');
        if (savedTab) currentTab = savedTab as typeof currentTab;
        const savedDate = localStorage.getItem('goals.selectedPlanningDate');
        if (savedDate) selectedPlanningDate = savedDate;
        // if we are on planning, pre-load assignments for the selected date
        if (currentTab === 'planning' && selectedPlanningDate) {
          await loadAssignmentsForDate(selectedPlanningDate);
        }
      } catch (e) {
        // ignore storage errors
      }
    } catch (e) {
      loadError = 'No se pudo cargar los objetivos.';
      console.error('[goals] onMount failed:', e);
    }
  });

  let addError = '';

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
      });
      goals = [g, ...goals];
      showAddForm = false;
      newTitle = ''; newTargetValue = 1;
      newTagId = null; newNoteId = null;
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
  let editingGoal: Goal | null = null;
  let editTitle = '';
  let editDescription = '';
  let editTargetValue = 1;
  let editFailConfig: Goal['fail_config'] = 'STATIC';
  let editMeasurement: Goal['measurement_type'] = 'COUNT';
  let editColor = '#c8a96e';
  let editSaving = false;

  // ── Analytics expandable state ──
  let showPerformanceChart = true;

  // ── Hierarchical planning helpers ──
  function getParentGoals(goalList: Goal[]) {
    return goalList.filter(g => !g.parent_id || !goalList.some(p => p.id === g.parent_id));
  }
  function getChildGoals(parentId: number, goalList: Goal[]) {
    return goalList.filter(g => g.parent_id === parentId);
  }

  // Planning assignment state (frontend-only mapping date -> goal ids)
  const todayIso = `${_now.getFullYear()}-${String(_now.getMonth() + 1).padStart(2, '0')}-${String(_now.getDate()).padStart(2, '0')}`;
  let selectedPlanningDate: string = todayIso;
  let assignments: Record<string, number[]> = {};

  function isAssigned(goalId: number, date: string) {
    return assignments[date] && assignments[date].includes(goalId);
  }

  // persist current tab and selected planning date in localStorage
  $: try {
    if (typeof localStorage !== 'undefined') localStorage.setItem('goals.currentTab', currentTab);
  } catch (e) {}

  $: if (selectedPlanningDate) {
    try { if (typeof localStorage !== 'undefined') localStorage.setItem('goals.selectedPlanningDate', selectedPlanningDate); } catch (e) {}
    // load assignments for the newly selected date
    loadAssignmentsForDate(selectedPlanningDate);
  }

  async function loadAssignmentsForDate(date: string) {
    if (!date) return;
    try {
      const res = await api.planning.getAssignments(date);
      assignments = { ...assignments, [date]: res.goal_ids };
    } catch (e) {
      // If 404 or no assignments, ensure empty array
      assignments = { ...assignments, [date]: [] };
    }
  }

  async function assignGoalToDate(goalId: number, date: string) {
    if (!date) return;
    assignments = { ...assignments };
    if (!assignments[date]) assignments[date] = [];
    if (!assignments[date].includes(goalId)) assignments[date].push(goalId);
    try {
      await api.planning.setAssignments(date, assignments[date]);
    } catch (e) {
      console.error('Error saving assignment:', e);
    }
  }

  async function unassignGoalFromDate(goalId: number, date: string) {
    if (!date) return;
    if (!assignments[date]) return;
    assignments = { ...assignments, [date]: assignments[date].filter(id => id !== goalId) };
    try {
      await api.planning.setAssignments(date, assignments[date]);
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
    editingGoal = goal;
    editTitle = goal.title;
    editDescription = goal.description || '';
    editTargetValue = goal.target_value;
    editFailConfig = goal.fail_config;
    editMeasurement = goal.measurement_type;
    editColor = goal.color || '#c8a96e';
  }

  // ── Advanced Analytics Calculations ──
  $: completedGoalsCount = goals.filter(g => g.state === 'COMPLETED').length;
  $: failedGoalsCount = goals.filter(g => g.state === 'FAILED').length;
  $: successRate = (completedGoalsCount + failedGoalsCount) > 0 
    ? Math.round((completedGoalsCount / (completedGoalsCount + failedGoalsCount)) * 100) 
    : 0;

  $: completionsByDay = (() => {
    const days = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
    const counts = [0, 0, 0, 0, 0, 0, 0];
    goals.filter(g => g.state === 'COMPLETED' && g.completed_at).forEach(g => {
      const d = new Date(g.completed_at!);
      counts[d.getDay()]++;
    });
    return days.map((label, i) => ({ label, value: counts[i] }));
  })();

  $: topTagsBySuccess = (() => {
    const tagMap = new Map();
    goals.filter(g => g.state === 'COMPLETED' && g.tag_id).forEach(g => {
      const tagName = tags.find(t => t.id === g.tag_id)?.name || 'Sin Tag';
      tagMap.set(tagName, (tagMap.get(tagName) || 0) + 1);
    });
    return Array.from(tagMap.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  })();

  $: progressOverview = (() => {
    return ['DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'].map(temp => {
      const tempGoals = goals.filter(g => g.temporality === temp);
      const avgProgress = tempGoals.length > 0 
        ? Math.round(tempGoals.reduce((acc, g) => acc + g.progress_pct, 0) / tempGoals.length)
        : 0;
      const completed = tempGoals.filter(g => g.state === 'COMPLETED').length;
      const failed = tempGoals.filter(g => g.state === 'FAILED').length;
      return { temp, avgProgress, count: tempGoals.length, completed, failed };
    });
  })();

  $: prediction = (() => {
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
  })();

  $: candleData = (() => {
    let currentPrice = 1000;
    const results: { date: string; open: number; close: number; high: number; low: number }[] = [];
    const last30Days = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      last30Days.push(d.toISOString().split('T')[0]);
    }

    last30Days.forEach((date: string) => {
      const comps = goals.filter(g => g.state === 'COMPLETED' && g.completed_at?.startsWith(date)).length;
      const fails = goals.filter(g => g.state === 'FAILED' && g.updated_at?.startsWith(date)).length;
      
      const open = currentPrice;
      const close = currentPrice + (comps * 10) - (fails * 15);
      const high = Math.max(open, close) + (comps > 0 ? 5 : 2);
      const low = Math.min(open, close) - (fails > 0 ? 5 : 2);
      
      results.push({ date, open, close, high, low });
      currentPrice = close;
    });
    return results;
  })();

  $: candleScale = (() => {
    const allVals = candleData.flatMap(c => [c.high, c.low]);
    const min = Math.min(...allVals) - 10;
    const max = Math.max(...allVals) + 10;
    return { min, max, range: max - min };
  })();

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
      });
      goals = goals.map(g => g.id === editingGoal!.id ? result : g);
      editingGoal = null;
    } catch (e) {
      console.error('Error al editar:', e);
    } finally {
      editSaving = false;
    }
  }
</script>

<div class="goals-page">
  {#if loadError}
    <div class="error-banner">{loadError}</div>
  {/if}

  <div class="goals-header">
    <div class="tabs">
      <button class="tab" class:active={currentTab === 'today'} on:click={() => currentTab = 'today'}>
        <Layout size={14} /> Dashboard
      </button>
      <button class="tab" class:active={currentTab === 'planning'} on:click={() => currentTab = 'planning'}>
        <Clock size={14} /> Planificación
      </button>
      <button class="tab" class:active={currentTab === 'history'} on:click={() => currentTab = 'history'}>
        <Calendar size={14} /> Historial
      </button>
      <button class="tab" class:active={currentTab === 'analytics'} on:click={() => currentTab = 'analytics'}>
        <BarChart size={14} /> Analytics
      </button>
    </div>
    <button class="btn btn-primary" on:click={() => showAddForm = !showAddForm}>
      <Plus size={13} /> Nuevo objetivo
    </button>
  </div>

  <div class="goals-body" class:full-width={currentTab === 'analytics' || currentTab === 'history' || currentTab === 'planning'}>


    {#if currentTab === 'today'}
      <div class="tab-content fade-in">
        <!-- Quick Metrics Dashboard -->
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-value">{dailyGoals.filter(g => g.state === 'COMPLETED').length}</span>
            <span class="metric-label">Completados Hoy</span>
          </div>
          <div class="metric-card">
            <span class="metric-value">{dailyGoals.length > 0 ? Math.round((dailyGoals.filter(g => g.state === 'COMPLETED').length / dailyGoals.length) * 100) : 0}%</span>
            <span class="metric-label">Tasa de Disciplina</span>
          </div>
          <div class="metric-card">
            <span class="metric-value">{goals.filter(g => g.state === 'FAILED').length}</span>
            <span class="metric-label">Objetivos Fallidos</span>
          </div>
        </div>

        <h3 class="section-title" style="margin-top: var(--s4);">Objetivos del Día</h3>
        {#if dailyGoals.length === 0}
          <div class="empty-state">No hay objetivos diarios activos.</div>
        {/if}
        {#each dailyGoals as goal (goal.id)}
          <div class="goal-card" class:completed={goal.state === 'COMPLETED'} class:failed={goal.state === 'FAILED'} class:paused={goal.state === 'PAUSED'}>
            <div class="goal-main">
              <div class="goal-title">
                {#if goal.fail_emoji}
                  {#if ICON_OPTIONS.includes(goal.fail_emoji)}
                    <span class="emoji-badge" style="display:flex; align-items:center; margin-right:8px;"><StreakIcon name={goal.fail_emoji} size={16} color={goal.color || 'var(--text-muted)'} /></span>
                  {:else}
                    <span class="emoji-badge" style="margin-right:8px;">{goal.fail_emoji}</span>
                  {/if}
                {/if}
                {goal.title}
                {#if goal.state === 'PAUSED'}
                  <span class="state-badge paused-badge">PAUSADO</span>
                {/if}
              </div>
              <div class="goal-meta">
                {#if goal.note_id}
                  <span class="tag-chip">{notes.find(n => n.id === goal.note_id)?.title || 'Nota vinculada'}</span>
                {:else if goal.tag_id}
                  <span class="tag-chip">{tags.find(t => t.id === goal.tag_id)?.name}</span>
                {/if}
                {#if goal.fail_config !== 'STATIC'}
                  <span class="config-badge">{formatFailConfig(goal.fail_config)}</span>
                {/if}
                {#if goal.measurement_type !== 'COUNT'}
                  <span class="config-badge" style="background:transparent; border: 1px solid var(--border);">{goal.measurement_type}</span>
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
      </div>
    {/if}

    {#if currentTab === 'planning'}
      <div class="tab-content fade-in history-layout planning-3col">
        <!-- Left: Assigned for selected date (or copy of list if none) -->
        <div class="planning-left-col history-detail-col">
          <div class="history-detail-header">
            <div class="history-detail-date" style="text-transform:none;">Asignados · {selectedPlanningDate}</div>
          </div>

          <div class="history-goal-list" style="width:100%">
            {#if assignments[selectedPlanningDate] && assignments[selectedPlanningDate].length > 0}
              {#each assignments[selectedPlanningDate].map(id => goals.find(g => g.id === id)).filter((g): g is Goal => Boolean(g)) as g (g.id)}
                <div class="history-goal-item assigned" style="border-left-color: {g.color || 'var(--success)'}; display:flex; align-items:center; justify-content:space-between;">
                  <div class="hgi-info">
                    <div class="hgi-title">{g.title}</div>
                    <div class="hgi-meta"><span class="config-badge">{g.temporality}</span></div>
                  </div>
                  <div style="display:flex; gap:6px;">
                    <button class="btn btn-ghost" on:click={() => unassignGoalFromDate(g.id, selectedPlanningDate)} title="Quitar">×</button>
                  </div>
                </div>
              {/each}
            {:else}
              <!-- If none assigned, show a copy of the full list -->
              {#each goals.filter(g => g.state !== 'CANCELLED') as goal (goal.id)}
                <div class="history-goal-item" style="width:100%; display:flex; text-align:left;">
                  <div class="hgi-info">
                    <div class="hgi-title">{goal.title}</div>
                    <div class="hgi-meta"><span class="config-badge">{goal.temporality}</span></div>
                  </div>
                </div>
              {/each}
            {/if}
          </div>
        </div>

        <!-- Center: Calendar (fixed year view, allow future months) -->
        <div class="planning-center-col history-calendar-col">
          <div class="history-cal-header">
            <span class="section-title" style="margin:0;">Calendario</span>
            <span class="history-hint">Selecciona un día (puedes navegar futuro)</span>
          </div>
          <div class="history-heatmap-wrap">
            <StreakHeatmap
              history={historyData}
              color="var(--success)"
              selectedDate={selectedPlanningDate}
              onselect={(date) => selectedPlanningDate = date}
              maxFutureMonths={12}
            />
          </div>
        </div>

        <!-- Right: All Goals List (click => assign to selectedPlanningDate) -->
        <div class="planning-right-col history-detail-col">
          <div class="history-detail-header">
            <div class="history-detail-date" style="text-transform:none;">Lista de Objetivos</div>
          </div>

          <div class="history-goal-list" style="width: 100%;">
            {#each goals.filter(g => g.state !== 'CANCELLED') as goal (goal.id)}
              {#if !isAssigned(goal.id, selectedPlanningDate)}
                <button
                  class="history-goal-item"
                  style="width: 100%; border-left: 3px solid var(--border); display: flex; text-align: left;"
                  on:click={() => assignGoalToDate(goal.id, selectedPlanningDate)}
                  title="Asignar al día seleccionado"
                >
                  <div class="hgi-info">
                    <div class="hgi-title">{goal.title}</div>
                    <div class="hgi-meta"><span class="config-badge">{goal.temporality}</span></div>
                  </div>
                </button>
              {/if}
            {/each}
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
                  <div class="history-goal-item completed" style="border-left-color: {g.color || 'var(--success)'};">
                    <div class="hgi-icon-left">
                      {#if ICON_OPTIONS.includes(g.fail_emoji)}
                        <StreakIcon name={g.fail_emoji} size={16} color={g.color || 'var(--success)'} />
                      {:else}
                        <span style="font-size:16px;">{g.fail_emoji}</span>
                      {/if}
                    </div>
                    <div class="hgi-info">
                      <div class="hgi-title">{g.title}</div>
                      <div class="hgi-meta">
                        <span class="config-badge">{g.temporality}</span>
                        <div class="hgi-bar">
                          <div class="hgi-bar-fill" style="width:100%; background:{g.color || 'var(--success)'};"></div>
                        </div>
                        <span class="hgi-pct" style="color: {g.color || 'var(--success)'};">100%</span>
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
                  <div class="history-goal-item failed">
                    <div class="hgi-icon-left">
                      {#if ICON_OPTIONS.includes(g.fail_emoji)}
                        <StreakIcon name={g.fail_emoji} size={16} color="var(--error)" />
                      {:else}
                        <span style="font-size:16px;">{g.fail_emoji}</span>
                      {/if}
                    </div>
                    <div class="hgi-info">
                      <div class="hgi-title">{g.title}</div>
                      <div class="hgi-meta">
                        <span class="config-badge">{g.temporality}</span>
                        <div class="hgi-bar">
                          <div class="hgi-bar-fill" style="width:{g.progress_pct}%; background: var(--error);"></div>
                        </div>
                        <span class="hgi-pct" style="color:var(--error);">{g.progress_pct}%</span>
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
        <div class="dashboard-grid">
          
          <div class="dash-card stats-summary">
            <div class="dash-card-header">
              <Trophy size={16} />
              <span>Resumen de Logros</span>
            </div>
            <div class="stats-row">
              <div class="stat-item">
                <span class="stat-val" style="color: var(--success);">{completedGoalsCount}</span>
                <span class="stat-lab">Completados</span>
              </div>
              <div class="stat-item">
                <span class="stat-val" style="color: var(--error);">{failedGoalsCount}</span>
                <span class="stat-lab">Fallidos</span>
              </div>
              <div class="stat-item">
                <span class="stat-val">{successRate}%</span>
                <span class="stat-lab">Efectividad</span>
              </div>
            </div>
            <div class="success-meter">
              <div class="meter-fill" style="width: {successRate}%"></div>
            </div>
          </div>

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
                <div class="day-col">
                  <div class="day-bar-wrap">
                    <div class="day-bar" style="height: {(day.value / maxVal) * 100}%" title="{day.value} completados"></div>
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
                    <span class="temp-stats">{p.completed} ✓ / {p.failed} ✗</span>
                  </div>
                  <div class="temp-bar-container">
                    <div class="temp-bar" style="width: {p.avgProgress}%"></div>
                    <span class="temp-perc">{p.avgProgress}%</span>
                  </div>
                </div>
              {/each}
            </div>
          </div>

          <div class="dash-card tags-card">
            <div class="dash-card-header">
              <PieChart size={16} />
              <span>Top Categorías</span>
            </div>
            <div class="tags-list">
              {#if topTagsBySuccess.length === 0}
                <div class="empty-state mini">Sin datos de etiquetas</div>
              {:else}
                {#each topTagsBySuccess as tag, i}
                  {@const maxTag = topTagsBySuccess[0].count}
                  <div class="tag-row">
                    <div class="tag-rank">{i + 1}</div>
                    <div class="tag-name-wrap">
                      <span class="tag-name">{tag.name}</span>
                      <div class="tag-bar-wrap">
                        <div class="tag-bar" style="width: {(tag.count / maxTag) * 100}%"></div>
                      </div>
                    </div>
                    <span class="tag-count">{tag.count}</span>
                  </div>
                {/each}
              {/if}
            </div>
          </div>

          <div class="dash-card summary-card">
            <div class="dash-card-header">
              <BarChart size={16} />
              <span>Estado Operativo</span>
            </div>
            <div class="projection-content">
              <div class="proj-item">
                <span class="proj-label">Activos</span>
                <span class="proj-val">{goals.filter(g => g.state === 'ACTIVE').length}</span>
              </div>
              <div class="proj-item">
                <span class="proj-label">Pausados</span>
                <span class="proj-val">{goals.filter(g => g.state === 'PAUSED').length}</span>
              </div>
              <div class="proj-item">
                <span class="proj-label">Frecuencia</span>
                <span class="proj-val">{prediction.last7Days} <small>/ sem</small></span>
              </div>
              <div class="proj-item">
                <span class="proj-label">Disciplina</span>
                <span class="proj-val" style="color: {successRate > 70 ? 'var(--success)' : 'var(--warning)'}">{successRate > 80 ? 'Alta' : successRate > 50 ? 'Media' : 'Baja'}</span>
              </div>
            </div>
          </div>

        </div>
      </div>
    {/if}
  </div>

  <!-- ── New Goal Slide-Down Panel ── -->
  {#if showAddForm}
    <div class="new-goal-backdrop" on:click|self={() => showAddForm = false} on:keydown={(e) => e.key === 'Escape' && (showAddForm = false)} role="dialog" tabindex="-1">
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
                    <div class="icon-grid ng-large-grid">
                      {#each ICON_OPTIONS as ic}
                        <button class="lucide-btn" class:selected={newFailIcon === ic} on:click={() => newFailIcon = ic} title={ic}>
                          <StreakIcon name={ic} size={16} color={newGoalColor} />
                        </button>
                      {/each}
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
                  {#if ICON_OPTIONS.includes(useFailIcon ? newFailIcon : newFailEmoji)}
                    <span class="emoji-badge" style="display:flex; align-items:center; margin-right:8px;">
                      <StreakIcon name={useFailIcon ? newFailIcon : newFailEmoji} size={16} color={newGoalColor} />
                    </span>
                  {:else}
                    <span class="emoji-badge" style="margin-right:8px;">{newFailEmoji}</span>
                  {/if}
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
    <div class="modal-overlay" on:click|self={() => editingGoal = null} on:keydown={(e) => e.key === 'Escape' && (editingGoal = null)} role="dialog" tabindex="-1">
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
  /* Planning 3-col layout */
  .planning-3col {
    display: grid;
    grid-template-columns: 360px minmax(520px, 780px) 360px;
    gap: 20px;
    align-items: start;
    width: 100%;
    max-width: none;
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
  .planning-left-col,
  .planning-right-col {
    max-height: 68vh;
    overflow-y: auto;
    background: transparent;
  }

  .planning-center-col {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .history-heatmap-wrap {
    width: 100%;
    display: flex;
    justify-content: center;
  }
  .goals-body.full-width {
    max-width: none;
    margin: 0;
    padding: var(--s4) var(--s6);
    overflow-y: hidden;
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
    overflow: hidden;
    padding-bottom: var(--s4);
  }
  .dashboard-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(2, 1fr);
    gap: var(--s3);
    margin-top: var(--s3);
    height: 100%;
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
  
  /* Stats Summary */
  .stats-summary {
    grid-column: span 1;
  }
  .stats-row {
    display: flex;
    justify-content: space-between;
    padding: var(--s1) 0;
  }
  .stat-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .stat-val {
    font-size: 18px;
    font-weight: 700;
    font-family: var(--font-mono);
  }
  .stat-lab {
    font-size: 9px;
    color: var(--text-muted);
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
    background: var(--primary);
    border-radius: 5px;
    transition: height 0.5s ease-out;
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
    background: var(--primary);
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

</style>
