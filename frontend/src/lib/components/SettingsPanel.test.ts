import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, cleanup, waitFor } from '@testing-library/svelte';

// Regression (#1134 follow-up): SettingsPanel estaba en legacy-mode y
// configuredKeys era un array plano — los hijos runes (SettingsGoogle, etc.)
// llaman isConfigured() dentro de sus $derived y como la variable no crea
// señal, nunca veían las actualizaciones de loadConfig(): el botón
// «Conectar con Google» no aparecía aunque el backend reportara las creds.

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    config: {
      get: vi.fn(),
      update: vi.fn(),
    },
  },
}));

vi.mock('$lib/api', () => ({ api: apiMock }));

vi.mock('$lib/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), log: vi.fn(), debug: vi.fn() },
}));

vi.mock('svelte-i18n', () => ({
  t: {
    subscribe: (fn: (v: unknown) => void) => {
      fn((k: string) => k);
      return { unsubscribe() {} };
    },
  },
}));

// Hijos pesados sin lógica bajo test → stubs nulos.
vi.mock('./SettingsAppearance.svelte', () => ({ default: () => null }));
vi.mock('./SettingsAdvanced.svelte', () => ({ default: () => null }));
vi.mock('./SettingsVault.svelte', () => ({ default: () => null }));
vi.mock('./SettingsGithub.svelte', () => ({ default: () => null }));
vi.mock('./SettingsApp.svelte', () => ({ default: () => null }));
vi.mock('./SettingsSession.svelte', () => ({ default: () => null }));
vi.mock('./SettingsServices.svelte', () => ({ default: () => null }));
vi.mock('./SettingsDeveloper.svelte', () => ({ default: () => null }));

// Hijos que consumen isConfigured, reemplazados por stubs runes.
vi.mock('./SettingsIntegrations.svelte', () => ({ default: SettingsIntegrationsStub }));
vi.mock('./SettingsAI.svelte', () => ({ default: SettingsAIStub }));

import SettingsIntegrationsStub from './__stubs__/SettingsIntegrationsStub.svelte';
import SettingsAIStub from './__stubs__/SettingsAIStub.svelte';
import SettingsPanel from './SettingsPanel.svelte';

describe('SettingsPanel — reactividad de configuredKeys', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it('muestra «Conectar con Google» cuando la API reporta google_client_id configurado', async () => {
    apiMock.config.get.mockResolvedValue({
      configured_keys: ['google_client_id', 'google_client_secret', 'google_redirect_uri'],
      google_redirect_uri: 'http://localhost:8000/integrations/google/callback',
      github_username: 'axel-damage',
      obsidian_vault_path: '/vault',
      llm_model: '',
      embedding_model: '',
      openai_base_url: '',
    });

    const { getByText, getByTestId } = render(SettingsPanel, {
      open: true,
      onClose: vi.fn(),
    });

    await waitFor(() => expect(getByTestId('google-connect')).toBeTruthy());
    expect(getByText('Conectar con Google')).toBeTruthy();
  });

  it('muestra «Configurar» cuando Google no está configurado', async () => {
    apiMock.config.get.mockResolvedValue({
      configured_keys: ['obsidian_vault_path'],
      obsidian_vault_path: '/vault',
      llm_model: '',
      embedding_model: '',
      openai_base_url: '',
    });

    const { getByTestId } = render(SettingsPanel, {
      open: true,
      onClose: vi.fn(),
    });

    await waitFor(() => expect(getByTestId('google-setup')).toBeTruthy());
  });

  it('marca la IA como configurada cuando openai_api_key está en configured_keys', async () => {
    apiMock.config.get.mockResolvedValue({
      configured_keys: ['openai_api_key'],
      llm_model: '',
      embedding_model: '',
      openai_base_url: '',
    });

    const { getByTestId } = render(SettingsPanel, {
      open: true,
      onClose: vi.fn(),
    });

    await waitFor(() => expect(getByTestId('ai-configured')).toBeTruthy());
  });
});

// #1304 — el listener global de Ctrl+S no comprobaba `open`: el panel vive
// montado en +layout, así que Ctrl+S en cualquier página disparaba saveConfig()
// y posteaba systemConfig con los secretos en '' (GET /config no los devuelve),
// borrando GEMINI_API_KEY, OBSIDIAN_VAULT_PATH y la config de Telegram en .env.
describe('SettingsPanel — guard de Ctrl+S (#1304)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
    apiMock.config.update.mockResolvedValue({ status: 'ok' });
  });

  it('ignora Ctrl+S con el panel cerrado aunque esté montado', async () => {
    render(SettingsPanel, { open: false, onClose: vi.fn() });

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true }));
    // Give a hypothetical unguarded handler a tick to run.
    await new Promise((r) => setTimeout(r, 20));

    expect(apiMock.config.update).not.toHaveBeenCalled();
    expect(apiMock.config.get).not.toHaveBeenCalled();
  });

  it('Ctrl+S sí guarda con el panel abierto y la config cargada', async () => {
    apiMock.config.get.mockResolvedValue({
      configured_keys: ['obsidian_vault_path'],
      obsidian_vault_path: '/vault',
      daily_notes_folder: 'daily',
      llm_model: '',
      embedding_model: '',
      openai_base_url: '',
    });

    render(SettingsPanel, { open: true, onClose: vi.fn() });
    await waitFor(() => expect(apiMock.config.get).toHaveBeenCalled());

    // Re-dispatch until loadConfig() flips configLoaded — the guard requires
    // both `open` and a finished initial load before honouring Ctrl+S.
    await waitFor(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true }));
      expect(apiMock.config.update).toHaveBeenCalled();
    });
    // Los secretos vacíos no se envían (GET /config nunca los devuelve).
    const payload = apiMock.config.update.mock.calls[0][0];
    expect(payload).not.toHaveProperty('gemini_api_key');
    expect(payload).not.toHaveProperty('telegram_bot_token');
    expect(payload).not.toHaveProperty('telegram_allowed_user_id');
  });
});
