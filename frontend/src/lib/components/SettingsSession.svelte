<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import { session } from '$lib/stores/session';
  import { showNotification } from '$lib/stores/notifications';
  import { t } from 'svelte-i18n';

  // The JWT is stateless, so signing out is purely client-side: drop the stored
  // session and reload so +layout.svelte falls back to the login screen.
  function logout() {
    session.logout();
    showNotification($t('settings.session.loggedOut'), 'success');
    setTimeout(() => window.location.reload(), 400);
  }
</script>

<!-- Sesión -->
<section class="section">
  <div class="section-title" style="color: var(--xp, var(--accent));">
    <DynamicIcon name="UserRound" size={12} />
    {$t('settings.session.title')}
  </div>
  <div class="row">
    <div class="row-label">
      <DynamicIcon name="AtSign" size={13} />
      <span>{$session?.username || $t('settings.session.noUser')}</span>
    </div>
    <button class="power-btn logout" onclick={logout}>
      <DynamicIcon name="LogOut" size={12} />
      {$t('settings.session.logout')}
    </button>
  </div>
  <p class=":global(hint) code">{$t('settings.session:global(hint) code')}</p>
</section>

<style>
  .section {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-light);
  }

  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }

  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
  }

  .row-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-secondary);
  }

  .power-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }

  .power-btn:hover:not(:disabled) {
    background: var(--elevated);
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .power-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .power-btn.logout {
    border-color: color-mix(in srgb, var(--error) 40%, var(--border));
    color: var(--error);
  }

  .power-btn.logout:hover:not(:disabled) {
    background: color-mix(in srgb, var(--error) 10%, transparent);
    border-color: var(--error);
    color: var(--error);
  }
</style>
