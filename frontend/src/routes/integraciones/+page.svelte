<script lang="ts">
  import { onMount } from 'svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import { api } from '$lib/api';
  import { logger } from '$lib/utils/logger';

  interface IntegrationInfo {
    id: string;
    label: string;
    icon: string;
    color: string;
    description: string;
    status: 'connected' | 'available' | 'development' | 'planned';
    configurable: boolean;
  }

  let integrations = $state<IntegrationInfo[]>([
    { id: 'github', label: 'GitHub', icon: 'GitBranch', color: '#333', description: 'Autenticación y respaldo de notas', status: 'planned', configurable: true },
    { id: 'ai', label: 'Inteligencia Artificial', icon: 'Brain', color: '#a855f7', description: 'Asistentes y modelos de lenguaje (Gemini, OpenAI, Anthropic, Cohere, Ollama)', status: 'development', configurable: false },
    { id: 'gmail', label: 'Gmail', icon: 'Mail', color: '#EA4335', description: 'Correo electrónico de Google', status: 'planned', configurable: false },
    { id: 'contactos', label: 'Google Contacts', icon: 'Users', color: '#34A853', description: 'Contactos de Google', status: 'planned', configurable: false },
    { id: 'strava', label: 'Strava', icon: 'Activity', color: '#FC4C02', description: 'Actividad deportiva y fitness', status: 'planned', configurable: false },
    { id: 'spotify', label: 'Spotify', icon: 'Music', color: '#1DB954', description: 'Música y playlists', status: 'planned', configurable: false },
    { id: 'calendar', label: 'Google Calendar', icon: 'Calendar', color: '#4285F4', description: 'Calendario y eventos', status: 'planned', configurable: false },
    { id: 'tasks', label: 'Google Tasks', icon: 'CheckSquare', color: '#F9AB00', description: 'Tareas de Google', status: 'planned', configurable: false },
  ]);

  let githubStatus = $state<{ connected: boolean; username: string } | null>(null);

  onMount(async () => {
    try {
      const status = await api.github.status();
      githubStatus = status;
      integrations = integrations.map(i => {
        if (i.id === 'github') {
          return { ...i, status: status.connected ? 'connected' : 'available' };
        }
        return i;
      });
    } catch (e) {
      logger.error('Failed to check GitHub status', e);
    }
  });

  function statusBadge(status: string): string {
    switch (status) {
      case 'connected': return 'badge badge-on';
      case 'available': return 'badge badge-off';
      case 'development': return 'badge badge-dev';
      default: return 'badge badge-off';
    }
  }

  function statusLabel(status: string): string {
    switch (status) {
      case 'connected': return 'Conectado';
      case 'available': return 'Disponible';
      case 'development': return 'En desarrollo';
      default: return 'Planificado';
    }
  }
</script>

<div class="integrations-page">
  <div class="page-header">
    <div class="header-icon">
      <DynamicIcon name="Puzzle" size={28} color="var(--accent)" />
    </div>
    <div class="header-text">
      <h2>Integraciones</h2>
      <span class="caption">Conecta Joidy con tus servicios favoritos</span>
    </div>
  </div>

  <div class="integrations-grid">
    {#each integrations as integration (integration.id)}
      <div class="integration-card" class:connected={integration.status === 'connected'}>
        <div class="card-icon" style="color: {integration.color};">
          <DynamicIcon name={integration.icon} size={24} color={integration.status === 'connected' ? integration.color : undefined} />
        </div>
        <div class="card-body">
          <div class="card-header">
            <h3>{integration.label}</h3>
            <span class={statusBadge(integration.status)}>{statusLabel(integration.status)}</span>
          </div>
          <p class="card-desc">{integration.description}</p>
          {#if integration.configurable}
            <div class="card-action">
              {#if integration.id === 'github'}
                {#if githubStatus?.connected}
                  <span class="mono" style="font-size:12px; color: var(--xp);">{githubStatus.username}</span>
                {:else}
                  <span class="text-muted" style="font-size:12px;">Configurable en Ajustes</span>
                {/if}
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/each}
  </div>
</div>

<style>
  .integrations-page {
    padding: 24px;
    max-width: 900px;
    margin: 0 auto;
  }

  .page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 32px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }

  .header-icon {
    width: 56px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
  }

  .header-text h2 {
    font-size: 20px;
    font-weight: 600;
    margin: 0;
    color: var(--text-primary);
  }

  .header-text .caption {
    font-size: 13px;
    color: var(--text-muted);
  }

  .integrations-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  .integration-card {
    display: flex;
    gap: 14px;
    padding: 16px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    transition: all 0.2s;
  }

  .integration-card.connected {
    border-color: var(--xp);
    background: color-mix(in srgb, var(--xp) 4%, var(--elevated));
  }

  .card-icon {
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    flex-shrink: 0;
  }

  .card-body {
    flex: 1;
    min-width: 0;
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    flex-wrap: wrap;
  }

  .card-header h3 {
    font-size: 14px;
    font-weight: 600;
    margin: 0;
    color: var(--text-primary);
  }

  .card-desc {
    font-size: 12px;
    color: var(--text-muted);
    margin: 0 0 8px 0;
    line-height: 1.4;
  }

  .card-action {
    margin-top: 4px;
  }

  :global(.badge) {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  :global(.badge-on) {
    background: color-mix(in srgb, var(--xp) 15%, transparent);
    color: var(--xp);
  }

  :global(.badge-off) {
    background: color-mix(in srgb, var(--text-muted) 10%, transparent);
    color: var(--text-muted);
  }

  :global(.badge-dev) {
    background: color-mix(in srgb, #a855f7 15%, transparent);
    color: #a855f7;
  }

  .mono {
    font-family: var(--font-mono);
  }

  .text-muted {
    color: var(--text-muted);
  }
</style>
