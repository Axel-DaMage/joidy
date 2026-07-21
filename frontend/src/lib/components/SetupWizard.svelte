<script lang="ts">
  import { api } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import DynamicIcon from './DynamicIcon.svelte';

  let password = '';
  let confirmPassword = '';
  let vaultPath = '';
  let loading = false;
  let step = 1; // 1: Welcome, 2: Password, 3: Vault, 4: Done

  async function handleSetup() {
    if (password !== confirmPassword) {
      showNotification('Las contraseñas no coinciden', 'error');
      return;
    }
    
    if (password.length < 4) {
      showNotification('La contraseña debe tener al menos 4 caracteres', 'error');
      return;
    }

    loading = true;
    try {
      await api.config.setup(password, vaultPath || undefined);
      showNotification('¡Configuración completada!', 'success');
      step = 4;
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (e: any) {
      showNotification(e.message || 'Error al configurar el sistema', 'error');
    } finally {
      loading = false;
    }
  }
</script>

<div class="setup-wrapper">
  <div class="setup-card">
    <div class="logo mono">JOIDY</div>
    
    {#if step === 1}
      <div class="step-content slide-in">
        <div class="icon-wrap">
          <DynamicIcon name="Sparkles" size={32} color="var(--xp)" />
        </div>
        <h2 class="title">¡Bienvenido a Joidy!</h2>
        <p class="desc">Parece que es tu primera vez aquí. Vamos a realizar una configuración rápida para asegurar tu sistema antes de comenzar.</p>
        <button class="btn btn-primary" on:click={() => step = 2}>Comenzar Setup</button>
      </div>
    {:else if step === 2}
      <div class="step-content slide-in">
        <h2 class="title">Asegura tu sistema</h2>
        <p class="desc">Define una contraseña maestra. Esta será la única forma de acceder a Joidy.</p>
        
        <form on:submit|preventDefault={() => { if(password && confirmPassword) step = 3; }}>
          <div class="field">
            <label for="pwd">Contraseña Maestra</label>
            <input id="pwd" type="password" bind:value={password} class="input" required autofocus />
          </div>
          <div class="field" style="margin-top: 12px;">
            <label for="pwd2">Confirmar Contraseña</label>
            <input id="pwd2" type="password" bind:value={confirmPassword} class="input" required />
          </div>
          
          <div class="actions">
            <button type="button" class="btn btn-ghost" on:click={() => step = 1}>Atrás</button>
            <button type="submit" class="btn btn-primary" disabled={!password || !confirmPassword}>Siguiente</button>
          </div>
        </form>
      </div>
    {:else if step === 3}
      <div class="step-content slide-in">
        <h2 class="title">Conecta tu Vault (Opcional)</h2>
        <p class="desc">Si usas Obsidian, introduce la ruta absoluta a tu bóveda. Si no, déjalo en blanco y Joidy usará su almacenamiento interno.</p>
        
        <form on:submit|preventDefault={handleSetup}>
          <div class="field">
            <label for="vault">Ruta Absoluta (Ej. /home/user/Documents/Vault)</label>
            <input id="vault" type="text" bind:value={vaultPath} class="input mono" placeholder="/Ruta/a/tu/vault" />
          </div>
          
          <div class="actions">
            <button type="button" class="btn btn-ghost" on:click={() => step = 2} disabled={loading}>Atrás</button>
            <button type="submit" class="btn btn-primary" disabled={loading}>
              {loading ? 'Guardando...' : 'Finalizar Configuración'}
            </button>
          </div>
        </form>
      </div>
    {:else if step === 4}
      <div class="step-content slide-in">
        <div class="icon-wrap">
          <DynamicIcon name="CheckCircle" size={40} color="var(--success)" />
        </div>
        <h2 class="title" style="color: var(--success);">¡Todo Listo!</h2>
        <p class="desc">Tu entorno ha sido asegurado y configurado con éxito. Redirigiendo al sistema...</p>
      </div>
    {/if}
  </div>
</div>

<style>
  .setup-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: var(--bg);
    color: var(--text-primary);
  }
  
  .setup-card {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 40px;
    border-radius: var(--r);
    width: 100%;
    max-width: 440px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
    text-align: center;
    overflow: hidden;
  }
  
  .logo {
    font-size: 20px;
    letter-spacing: 0.12em;
    font-weight: 700;
    background: var(--accent-gradient, var(--xp));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 24px;
  }

  .icon-wrap {
    margin-bottom: 16px;
    display: flex;
    justify-content: center;
  }
  
  .title {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 12px 0;
    color: var(--text-primary);
  }

  .desc {
    color: var(--text-secondary);
    font-size: 13px;
    line-height: 1.5;
    margin-bottom: 24px;
  }
  
  .step-content {
    display: flex;
    flex-direction: column;
    text-align: left;
  }

  .step-content.slide-in {
    animation: slideIn 0.3s ease-out forwards;
  }

  @keyframes slideIn {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
  }
  
  .field {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .field label {
    font-size: 12px;
    font-weight: 500;
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
  
  .actions {
    display: flex;
    justify-content: space-between;
    margin-top: 24px;
    gap: 12px;
  }

  .btn {
    padding: 10px 16px;
    border-radius: var(--r);
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    border: none;
    flex: 1;
  }
  
  .btn-primary {
    background: var(--xp);
    color: #000;
  }
  
  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
    transform: translateY(-1px);
  }
  
  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-ghost {
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border);
  }

  .btn-ghost:hover:not(:disabled) {
    background: var(--elevated);
    color: var(--text-primary);
  }
</style>
