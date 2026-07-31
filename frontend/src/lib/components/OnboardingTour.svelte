<script lang="ts">
  import { onboarding, ONBOARDING_STEPS } from '$lib/stores/onboarding';
  import { highlightElement, clearHighlight } from '$lib/utils/spotlight';
  import { fly, fade } from 'svelte/transition';
  import { ArrowRight, ArrowLeft, X, Check } from 'lucide-svelte';

  $: step = ONBOARDING_STEPS[$onboarding.currentStep];
  $: isLastStep = $onboarding.currentStep === ONBOARDING_STEPS.length - 1;
  $: isFirstStep = $onboarding.currentStep === 0;
  $: progress = (($onboarding.currentStep + 1) / ONBOARDING_STEPS.length) * 100;

  // Reposition spotlight whenever the step (and thus the target) changes.
  $: if ($onboarding.active && step) {
    highlightElement(step.target);
  }

  function handleKeydown(event: KeyboardEvent) {
    if (!$onboarding.active) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      onboarding.skipTour();
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      handleNext();
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      onboarding.prevStep();
    }
  }

  function handleNext() {
    if (isLastStep) {
      onboarding.completeTour();
    } else {
      onboarding.nextStep();
    }
  }

  function handleSkip() {
    onboarding.skipTour();
  }

  function openSettings() {
    window.dispatchEvent(new CustomEvent('joidy:open-settings'));
    onboarding.completeTour();
  }

  // Clean up the spotlight overlay when the tour ends or component unmounts.
  $: if (!$onboarding.active) {
    clearHighlight();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if $onboarding.active && step}
  <div class="onboarding-tour" transition:fade={{ duration: 200 }}>
    <!-- Spotlight overlay is injected into <body> by spotlight.ts -->
    <div
      class="tour-card"
      class:centered={!step.target}
      transition:fly={{ y: 20, duration: 300 }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      <div class="progress-bar" aria-hidden="true">
        <div class="progress-fill" style="width: {progress}%"></div>
      </div>

      <button
        class="skip-btn"
        onclick={handleSkip}
        aria-label="Saltar tour de bienvenida"
      >
        <X size={16} />
        <span>Saltar</span>
      </button>

      <div class="content">
        <h2 id="onboarding-title" class="title">{step.title}</h2>
        <p class="description">{step.content}</p>
      </div>

      <div class="footer">
        <span class="step-indicator" aria-live="polite">
          Paso {$onboarding.currentStep + 1} de {ONBOARDING_STEPS.length}
        </span>

        <div class="actions">
          {#if !isFirstStep}
            <button
              class="btn btn-secondary"
              onclick={() => onboarding.prevStep()}
              aria-label="Paso anterior"
            >
              <ArrowLeft size={16} />
              <span>Anterior</span>
            </button>
          {/if}

          {#if isLastStep && step.id === 'obsidian'}
            <button class="btn btn-secondary" onclick={handleSkip}>
              Saltar por ahora
            </button>
            <button class="btn btn-primary" onclick={openSettings}>
              <span>Configurar Obsidian</span>
              <ArrowRight size={16} />
            </button>
          {:else if isLastStep}
            <button class="btn btn-primary" onclick={handleNext}>
              <Check size={16} />
              <span>Comenzar</span>
            </button>
          {:else}
            <button class="btn btn-primary" onclick={handleNext} aria-label="Siguiente paso">
              <span>Siguiente</span>
              <ArrowRight size={16} />
            </button>
          {/if}
        </div>
      </div>

      <div class="dots" aria-hidden="true">
        {#each ONBOARDING_STEPS as _, i}
          <span class="dot" class:active={i === $onboarding.currentStep}></span>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .onboarding-tour {
    position: fixed;
    inset: 0;
    z-index: 10001;
    pointer-events: none;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* The card re-enables pointer events; the dim overlay (in <body>) absorbs
     clicks outside the cutout, while the highlighted element stays interactive. */
  .tour-card {
    pointer-events: auto;
    position: relative;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    padding: 24px 28px 20px;
    max-width: 420px;
    width: 90%;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
  }

  .tour-card.centered {
    text-align: center;
  }

  .progress-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--border);
    border-radius: var(--r-xl) var(--r-xl) 0 0;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--xp);
    transition: width 0.3s ease;
  }

  .skip-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: var(--r);
    transition: all var(--t-normal);
  }

  .skip-btn:hover {
    color: var(--text-primary);
    background: var(--hover);
  }

  .content {
    margin: 16px 0 20px;
  }

  .title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 10px 0;
  }

  .description {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.55;
    margin: 0;
  }

  .footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .step-indicator {
    font-size: 11px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  .actions {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: var(--r);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--t-normal);
    border: 1px solid transparent;
  }

  .btn-primary {
    background: var(--xp);
    color: var(--bg);
  }

  .btn-primary:hover {
    background: color-mix(in srgb, var(--xp) 85%, black);
  }

  .btn-secondary {
    background: transparent;
    border-color: var(--border);
    color: var(--text-primary);
  }

  .btn-secondary:hover {
    background: var(--hover);
    border-color: var(--text-muted);
  }

  .dots {
    display: flex;
    justify-content: center;
    gap: 6px;
    margin-top: 16px;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--border);
    transition: all var(--t-normal);
  }

  .dot.active {
    background: var(--xp);
    transform: scale(1.3);
  }

  :global(#joidy-spotlight-overlay) {
    position: fixed;
    inset: 0;
    z-index: 10000;
    pointer-events: none;
  }

  :global(.joidy-spotlight-dim) {
    position: absolute;
    background: rgba(0, 0, 0, 0.72);
    pointer-events: auto;
  }

  :global(.joidy-spotlight-full) {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.72);
    pointer-events: auto;
  }

  :global(.joidy-spotlight-ring) {
    position: absolute;
    border: 2px solid var(--xp);
    border-radius: var(--r);
    box-shadow: 0 0 0 4px rgba(0, 0, 0, 0.4), 0 0 20px rgba(0, 0, 0, 0.5);
    pointer-events: none;
    transition: all 0.25s ease;
  }
</style>
