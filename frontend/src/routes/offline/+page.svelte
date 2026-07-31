<script lang="ts">
  import { browser } from '$app/environment';

  function reload() {
    if (browser) {
      window.location.reload();
    }
  }
</script>

<svelte:head>
  <title>Sin conexión — Joidy</title>
</svelte:head>

<section class="offline-page">
  <h1>Sin conexión</h1>
  <p>No se pudo conectar con Joidy. Algunas funciones pueden no estar disponibles sin internet.</p>
  <button onclick={reload} class="reload-button">Reintentar</button>
</section>

<style>
  .offline-page {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: var(--space-lg, 1.5rem);
    text-align: center;
    color: var(--text-primary, #f1f5f9);
    background: var(--bg-primary, #0f172a);
  }

  h1 {
    margin-bottom: var(--space-md, 1rem);
    font-size: 2rem;
  }

  p {
    max-width: 30rem;
    margin-bottom: var(--space-lg, 1.5rem);
    color: var(--text-secondary, #94a3b8);
  }

  .reload-button {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: var(--radius-md, 0.5rem);
    background: var(--accent, #8b5cf6);
    color: white;
    font-weight: 600;
    cursor: pointer;
  }

  .reload-button:hover {
    background: var(--accent-hover, #7c3aed);
  }

  /* ── Responsive ── */
  @media (max-width: 768px) {
    .offline-page {
      padding: var(--space-md, 1rem);
    }

    h1 {
      font-size: 1.6rem;
    }

    p {
      max-width: 100%;
      font-size: 0.95rem;
    }
  }

  @media (max-width: 480px) {
    .offline-page {
      padding: var(--space-sm, 0.75rem);
    }

    h1 {
      font-size: 1.4rem;
    }

    p {
      font-size: 0.85rem;
    }

    .reload-button {
      padding: 0.6rem 1.2rem;
      font-size: 0.9rem;
    }
  }
</style>
