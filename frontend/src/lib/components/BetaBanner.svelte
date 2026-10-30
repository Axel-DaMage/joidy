<script lang="ts">
  import { FlaskConical } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
</script>

<div class="beta-banner" role="note">
  <FlaskConical size={12} />
  <span>{$t('common.betaNotice')}</span>
</div>

<style>
  .beta-banner {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 6px 14px;
    flex-shrink: 0;
    background: color-mix(in srgb, var(--xp, #f59e0b) 10%, var(--surface));
    border-bottom: 1px solid color-mix(in srgb, var(--xp, #f59e0b) 25%, var(--border));
    font-size: 11px;
    color: var(--text-muted);
  }
</style>
