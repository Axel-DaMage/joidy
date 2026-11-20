import type { CalendarTask, CalendarTaskPriority, Goal, GoalContext } from '$lib/api';

/**
 * Execution-mode helpers (#1201).
 *
 * The "Modo Ejecución" view merges two backend queues into a single
 * prioritized list:
 *   - `GET /goals/execution-queue` — active goals ordered by priority DESC.
 *   - `GET /calendar/tasks/execution-queue` — today's open calendar tasks
 *     ordered URGENT > HIGH > MEDIUM > LOW, then start_time.
 *
 * Calendar-task priorities are mapped onto the goal priority scale (0-99) so
 * both item kinds can be interleaved deterministically. The top of the merged
 * queue drives the "Siguiente" hero card.
 */

/** Mirrors EXECUTION_QUEUE_MORNING_CUTOFF_HOUR in api/routers/goals.py (#1198). */
export const EXECUTION_QUEUE_MORNING_CUTOFF_HOUR = 15;

/**
 * Same rule as the backend's `context=auto` resolution: before the cutoff
 * hour the morning context applies (low-friction ramp-up), otherwise the
 * night context (deep work).
 */
export function resolveExecutionContext(hour: number): 'MORNING' | 'NIGHT' {
  return hour < EXECUTION_QUEUE_MORNING_CUTOFF_HOUR ? 'MORNING' : 'NIGHT';
}

/** Task priority mapped onto the 0-99 goal priority scale for merged sorting. */
export const TASK_PRIORITY_SCORE: Record<CalendarTaskPriority, number> = {
  URGENT: 95,
  HIGH: 75,
  MEDIUM: 50,
  LOW: 25,
};

export function goalQueueKey(id: number): string {
  return `goal-${id}`;
}

export function taskQueueKey(id: number): string {
  return `task-${id}`;
}

interface ExecutionItemBase {
  /** Stable identity for promotion/reordering: `goal-<id>` or `task-<id>`. */
  key: string;
  title: string;
  /** Unified priority score — higher executes first. */
  score: number;
  /** 'HH:mm' start time for timed tasks; `null` sorts last within a score. */
  startTime: string | null;
}

export type ExecutionItem =
  | (ExecutionItemBase & { kind: 'goal'; goal: Goal })
  | (ExecutionItemBase & { kind: 'task'; task: CalendarTask });

function taskStartTime(task: CalendarTask): string | null {
  return task.start_time ? task.start_time.slice(0, 5) : null;
}

/**
 * Merge goal queue items and calendar tasks into one execution list.
 * Order: score DESC → startTime ASC (timeless last) → title ASC → key.
 */
export function buildExecutionQueue(goals: Goal[], tasks: CalendarTask[]): ExecutionItem[] {
  const items: ExecutionItem[] = [
    ...goals.map((goal) => ({
      kind: 'goal' as const,
      key: goalQueueKey(goal.id),
      title: goal.title,
      score: goal.priority,
      startTime: null,
      goal,
    })),
    ...tasks.map((task) => ({
      kind: 'task' as const,
      key: taskQueueKey(task.id),
      title: task.title,
      score: TASK_PRIORITY_SCORE[task.priority] ?? 0,
      startTime: taskStartTime(task),
      task,
    })),
  ];
  items.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    const at = a.startTime ?? '99:99';
    const bt = b.startTime ?? '99:99';
    if (at !== bt) return at.localeCompare(bt);
    const byTitle = a.title.localeCompare(b.title);
    if (byTitle !== 0) return byTitle;
    return a.key.localeCompare(b.key);
  });
  return items;
}
