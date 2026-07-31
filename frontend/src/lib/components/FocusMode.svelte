<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import { Target } from 'lucide-svelte';
  import {
    isActive, focusSession, queuedNotifications, stopFocusMode,
  } from '$lib/stores/focusMode';
  import {
    phase, running, secondsLeft, totalSec, pomodorosDone,
    toggleTimer,
  } from '$lib/stores/pomodoro';
  import { notes } from '$lib/stores/notes';

  let reducedMotion = $state(false);

  function updateMotion() {
    if (typeof window === 'undefined') return;
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  $effect(() => {
    if (typeof window === 'undefined') return;
    updateMotion();
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = () => updateMotion();
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  });

  const R = 90;
  const CIRC = 2 * Math.PI * R;

  let progress = $derived($secondsLeft / $totalSec);
  let dashOffset = $derived(CIRC * (1 - progress));
  let mins = $derived(String(Math.floor($secondsLeft / 60)).padStart(2, '0'));
  let secs = $derived(String($secondsLeft % 60).padStart(2, '0'));

  const PHASE_LABEL: Record<string, string> = {
    work: 'TRABAJO',
    break: 'DESCANSO',
    longBreak: 'DESCANSO LARGO',
  };

  let activeNoteTitle = $derived.by(() => {
    const session = $focusSession;
    if (!session?.noteId) return null;
    const n = $notes.find((note) => String(note.id) === String(session.noteId));
    return n?.title ?? null;
  });

  let completed = $state(false);
  let earnedXp = $state(0);
  let autoStopTimeout: ReturnType<typeof setTimeout> | null = null;

  $effect(() => {
    const secLeft = $secondsLeft;
    const isWork = $phase === 'work';
    const active = $isActive;
    if (active && isWork && secLeft === 0 && !completed) {
      completed = true;
      const session = $focusSession;
      earnedXp = Math.max(5, session?.duration ?? 5);
      if (autoStopTimeout) clearTimeout(autoStopTimeout);
      autoStopTimeout = setTimeout(() => {
        stopFocusMode();
      }, 3000);
    }
  });

  $effect(() => {
    if (!$isActive) {
      completed = false;
      earnedXp = 0;
      if (autoStopTimeout) {
        clearTimeout(autoStopTimeout);
        autoStopTimeout = null;
      }
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (!$isActive) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      stopFocusMode();
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown, true);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKeydown, true);
    if (autoStopTimeout) clearTimeout(autoStopTimeout);
  });

  function handleExit() {
    stopFocusMode();
  }
</script>

{#if $isActive}
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="focus-overlay"
    role="dialog"
    aria-modal="true"
    aria-label="Modo enfoque"
    in:fade={reducedMotion ? { duration: 0 } : { duration: 220 }}
    out:fade={reducedMotion ? { duration: 0 } : { duration: 180 }}
  >
    <div class="focus-content">
      {#if activeNoteTitle}
        <div class="focus-note-title" in:fade={{ duration: 200 }}>
          <Target size={13} />
          <span class="note-title-text">{activeNoteTitle}</span>
        </div>
      {:else}
        <div class="focus-note-title placeholder">
          <Target size={13} />
          <span class="note-title-text">Sesión de enfoque</span>
        </div>
      {/if}

      {#if !completed}
        <div class="ring-wrap" in:scale={reducedMotion ? { duration: 0 } : { duration: 300, start: 0.92, opacity: 0 }}>
          <svg width="220" height="220" viewBox="0 0 220 220" class="ring-svg">
            <defs>
              <linearGradient id="focusRingBlend" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="var(--xp)" />
                <stop offset="52%" stop-color="var(--xp-2)" />
                <stop offset="100%" stop-color="var(--xp-3)" />
              </linearGradient>
            </defs>
            <circle cx="110" cy="110" r={R} stroke="var(--border)" stroke-width="5" fill="none" />
            <circle
              cx="110" cy="110" r={R}
              stroke="url(#focusRingBlend)"
              stroke-width="5"
              fill="none"
              stroke-linecap="round"
              stroke-dasharray={CIRC}
              stroke-dashoffset={dashOffset}
              transform="rotate(-90 110 110)"
              style="transition: stroke-dashoffset 950ms linear;"
            />
          </svg>
          <div class="ring-overlay">
            <span class="timer mono">{mins}:{secs}</span>
            <span class="phase-label mono">{PHASE_LABEL[$phase] ?? ''}</span>
            <div class="pomo-dots">
              {#each Array(4) as _, i}
                <span class="pdot" class:lit={i < $pomodorosDone % 4}></span>
              {/each}
            </div>
          </div>
        </div>

        <button class="ctrl-main" class:active={$running} onclick={toggleTimer}>
          {$running ? 'Pausar' : 'Reanudar'}
        </button>
      {:else}
        <div class="completion" in:scale={reducedMotion ? { duration: 0 } : { duration: 300, start: 0.9, opacity: 0 }}>
          <div class="completion-badge">
            <Target size={28} />
          </div>
          <span class="completion-title">¡Sesión completada!</span>
          <span class="completion-xp mono">+{earnedXp} XP</span>
        </div>
      {/if}

      {#if $queuedNotifications.length > 0}
        <div class="queued-count" title="Notificaciones en cola">
          {$queuedNotifications.length} notificación{#if $queuedNotifications.length !== 1}s{/if} en cola
        </div>
      {/if}

      <button class="exit-btn" onclick={handleExit} aria-label="Salir del modo enfoque">
        Salir del modo enfoque
      </button>
    </div>
  </div>
{/if}

<style>
  .focus-overlay {
    position: fixed; inset: 0; z-index: 9999;
    display: flex; align-items: center; justify-content: center;
    background: var(--bg);
    backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
  }
  .focus-content {
    display: flex; flex-direction: column; align-items: center;
    gap: var(--s5); padding: var(--s6); max-width: 480px; width: 100%;
  }
  .focus-note-title {
    display: flex; align-items: center; gap: 8px;
    color: var(--text-secondary); font-size: 13px;
    max-width: 100%; text-align: center;
  }
  .focus-note-title.placeholder { color: var(--text-muted); }
  .note-title-text {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 380px;
  }
  .ring-wrap { position: relative; width: 220px; height: 220px; flex-shrink: 0; }
  .ring-svg { display: block; }
  .ring-overlay {
    position: absolute; inset: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 6px;
  }
  .timer {
    font-size: 48px; font-weight: 300; color: var(--text-primary);
    line-height: 1; letter-spacing: 0.04em;
  }
  .phase-label {
    font-size: 11px; font-weight: 500; color: var(--text-muted); letter-spacing: 0.14em;
  }
  .pomo-dots { display: flex; gap: 6px; margin-top: 4px; }
  .pdot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--border); transition: background var(--t-normal);
  }
  .pdot.lit { background: var(--xp); }
  .ctrl-main {
    padding: 8px 28px; font-size: 13px; font-family: var(--font-sans);
    border: 1px solid var(--xp); border-radius: var(--r);
    background: var(--xp); color: var(--xp-contrast-text, var(--bg));
    cursor: pointer; transition: all var(--t-fast); min-width: 100px;
  }
  .ctrl-main:hover { background: var(--xp-2); border-color: var(--xp-2); }
  .ctrl-main.active { background: var(--xp-2); border-color: var(--xp-2); }
  .ctrl-main.active:hover { background: var(--xp-3); border-color: var(--xp-3); }
  .completion {
    display: flex; flex-direction: column; align-items: center;
    gap: var(--s3); padding: var(--s5) 0;
  }
  .completion-badge {
    display: flex; align-items: center; justify-content: center;
    width: 64px; height: 64px; border-radius: 50%;
    background: color-mix(in srgb, var(--xp) 15%, transparent);
    border: 2px solid var(--xp); color: var(--xp);
  }
  .completion-title { font-size: 20px; font-weight: 500; color: var(--text-primary); }
  .completion-xp { font-size: 18px; font-weight: 600; color: var(--xp); }
  .queued-count {
    font-size: 11px; color: var(--text-muted); padding: 4px 12px;
    border: 1px solid var(--border); border-radius: var(--r-full); background: var(--elevated);
  }
  .exit-btn {
    margin-top: var(--s3); padding: 8px 20px; font-size: 12px;
    font-family: var(--font-sans); color: var(--text-muted);
    background: transparent; border: 1px solid var(--border);
    border-radius: var(--r); cursor: pointer; transition: all var(--t-fast);
  }
  .exit-btn:hover {
    color: var(--text-primary); border-color: var(--text-muted); background: var(--elevated);
  }
  .exit-btn:focus-visible { outline: 2px solid var(--xp); outline-offset: 2px; }
</style>
