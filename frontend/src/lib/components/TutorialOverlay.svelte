<script lang="ts">
  import { onboarding, ONBOARDING_STEPS } from '$lib/stores/onboarding';
  import { fly, fade } from 'svelte/transition';
  import DynamicIcon from './DynamicIcon.svelte';

  $: step = ONBOARDING_STEPS[$onboarding.currentStep];
  $: isLastStep = $onboarding.currentStep === ONBOARDING_STEPS.length - 1;
  $: progress = (($onboarding.currentStep + 1) / ONBOARDING_STEPS.length) * 100;
</script>

{#if $onboarding.seen && !$onboarding.completed && step}
  <div class="overlay" transition:fade={{ duration: 200 }}>
    <div class="tutorial-card" transition:fly={{ y: 20, duration: 300 }}>
      <div class="progress-bar">
        <div class="progress-fill" style="width: {progress}%"></div>
      </div>

      <button class="skip-btn" on:click={() => onboarding.skip()}>
        Saltar
      </button>

      <div class="content">
        <div class="icon-wrapper">
          <DynamicIcon
            name={$onboarding.currentStep === 0 ? 'Sparkles' :
                  $onboarding.currentStep === 1 ? 'FileText' :
                  $onboarding.currentStep === 2 ? 'Target' : 'Flame'}
            size={32}
          />
        </div>

        <h2 class="title">{step.title}</h2>
        <p class="description">{step.content}</p>
      </div>

      <div class="actions">
        {#if $onboarding.currentStep > 0}
          <button class="btn btn-secondary" on:click={() => onboarding.prevStep()}>
            Anterior
          </button>
        {/if}

        <button
          class="btn btn-primary"
          on:click={() => isLastStep ? onboarding.skip() : onboarding.nextStep()}
        >
          {isLastStep ? 'Comenzar' : 'Siguiente'}
        </button>
      </div>

      <div class="dots">
        {#each ONBOARDING_STEPS as _, i}
          <span class="dot" class:active={i === $onboarding.currentStep}></span>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    backdrop-filter: blur(4px);
  }

  .tutorial-card {
    background: var(--elevated, #1a1a1a);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 28px 32px;
    max-width: 400px;
    width: 90%;
    position: relative;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
  }

  .progress-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: var(--border);
    border-radius: 16px 16px 0 0;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--accent, #6366f1);
    transition: width 0.3s ease;
  }

  .skip-btn {
    position: absolute;
    top: 16px;
    right: 16px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 0.2s;
  }

  .skip-btn:hover {
    color: var(--text-primary);
    background: var(--hover);
  }

  .content {
    text-align: center;
    margin: 20px 0;
  }

  .icon-wrapper {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: color-mix(in srgb, var(--accent, #6366f1) 15%, transparent);
    margin-bottom: 16px;
  }

  .icon-wrapper :global(svg) {
    color: var(--accent, #6366f1);
  }

  .title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary, #e0e0e0);
    margin: 0 0 10px 0;
  }

  .description {
    font-size: 14px;
    color: var(--text-secondary, #a0a0a0);
    line-height: 1.5;
    margin: 0;
  }

  .actions {
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 24px;
  }

  .btn {
    padding: 10px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid transparent;
  }

  .btn-primary {
    background: var(--accent, #6366f1);
    color: white;
  }

  .btn-primary:hover {
    background: color-mix(in srgb, var(--accent, #6366f1) 85%, black);
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
    gap: 8px;
    margin-top: 20px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--border);
    transition: all 0.2s;
  }

  .dot.active {
    background: var(--accent, #6366f1);
    transform: scale(1.2);
  }
</style>