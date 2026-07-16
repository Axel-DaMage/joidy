<script lang="ts">
  import { api } from '$lib/api';
  import { session, saveToken } from '$lib/stores/session';
  import { showNotification } from '$lib/stores/notifications';
  import { logger } from '$lib/utils/logger';

  let password = '';
  let username = $session?.username || 'user';
  let loading = false;

  async function handleLogin() {
    loading = true;
    try {
      const res = await api.auth.login(password, username);
      saveToken(res.access_token);

      session.login({
        id: '1',
        username,
        token: res.access_token,
        preferences: { theme: 'dark', timezone: 'UTC', language: 'es' },
        createdAt: new Date().toISOString()
      });

      try {
        const status = await api.auth.status();
        logger.info('Auth status confirmed:', status);
      } catch {
        logger.warn('Auth status check failed, using fallback session data');
      }

      showNotification('Inicio de sesión exitoso', 'success');
      setTimeout(() => {
        window.location.reload();
      }, 500);
    } catch (e) {
      // API handler already shows error notification
    } finally {
      loading = false;
    }
  }
</script>

<div class="login-wrapper">
  <div class="login-card">
    <div class="logo mono">JOIDY</div>
    <p class="subtitle">Conocimiento Gamificado</p>
    
    <form on:submit|preventDefault={handleLogin}>
      <div class="field">
        <label for="username">Usuario</label>
        <input id="username" type="text" bind:value={username} class="input" />
      </div>
      <div class="field">
        <label for="password">Contraseña</label>
        <input id="password" type="password" bind:value={password} class="input" placeholder="Tu contraseña maestra" />
      </div>
      
      <button type="submit" class="btn btn-primary" disabled={loading}>
        {loading ? 'Entrando...' : 'Entrar'}
      </button>
    </form>
  </div>
</div>

<style>
  .login-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: var(--bg);
    color: var(--text-primary);
  }
  
  .login-card {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 32px;
    border-radius: var(--r);
    width: 100%;
    max-width: 400px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    text-align: center;
  }
  
  .logo {
    font-size: 24px;
    letter-spacing: 0.12em;
    font-weight: 700;
    background: var(--accent-gradient, var(--xp));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 8px;
  }
  
  .subtitle {
    color: var(--text-muted);
    font-size: 14px;
    margin-bottom: 24px;
  }
  
  form {
    display: flex;
    flex-direction: column;
    gap: 16px;
    text-align: left;
  }
  
  .field {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .field label {
    font-size: 13px;
    color: var(--text-secondary);
  }
  
  .input {
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 10px 12px;
    border-radius: var(--r);
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
  }
  
  .input:focus {
    border-color: var(--xp);
  }
  
  .btn-primary {
    background: var(--xp);
    color: #000;
    border: none;
    padding: 12px;
    border-radius: var(--r);
    font-weight: 600;
    cursor: pointer;
    margin-top: 8px;
    transition: opacity 0.2s;
  }
  
  .btn-primary:hover {
    opacity: 0.9;
  }
  
  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
