<script lang="ts">
  import { toPng } from 'html-to-image';
  import { Download, Copy, X } from 'lucide-svelte';
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import AchievementCard from '$lib/components/AchievementCard.svelte';
  import { currentAchievement, closeShare } from '$lib/stores/shareAchievement';
  import { showNotification } from '$lib/stores/gamification';
  import { logger } from '$lib/utils/logger';
  import { t } from 'svelte-i18n';

  let cardEl: HTMLElement | null = $state(null);
  let busy = $state(false);

  let achievement = $derived($currentAchievement);

  async function exportPng(): Promise<Blob | null> {
    if (!cardEl) return null;
    try {
      const dataUrl = await toPng(cardEl, {
        pixelRatio: 2,
        cacheBust: true,
        backgroundColor: '#000000',
      });
      const res = await fetch(dataUrl);
      return await res.blob();
    } catch (e) {
      logger.error('[share] export PNG failed:', e);
      showNotification('No se pudo generar la imagen.', 'error');
      return null;
    }
  }

  async function handleDownload() {
    if (busy) return;
    busy = true;
    try {
      const blob = await exportPng();
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const safeName = (achievement?.title || 'logro')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
      a.download = `joidy-${safeName || 'logro'}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showNotification('Imagen descargada.', 'success');
    } finally {
      busy = false;
    }
  }

  async function handleCopy() {
    if (busy) return;
    busy = true;
    try {
      const blob = await exportPng();
      if (!blob) return;
      if (!navigator.clipboard || !window.ClipboardItem) {
        showNotification('Tu navegador no soporta copiar imágenes.', 'error');
        return;
      }
      const item = new ClipboardItem({ 'image/png': blob });
      await navigator.clipboard.write([item]);
      showNotification('Imagen copiada al portapapeles.', 'success');
    } catch (e) {
      logger.error('[share] copy to clipboard failed:', e);
      showNotification('No se pudo copiar al portapapeles.', 'error');
    } finally {
      busy = false;
    }
  }
</script>

<ModalDialog
  open={achievement !== null}
  title={$t('shareAchievement.title')}
  size="md"
  onClose={closeShare}
>
  {#snippet children()}
    {#if achievement}
      <div class="share-body">
        <div class="card-preview" bind:this={cardEl}>
          <AchievementCard
            title={achievement.title}
            icon={achievement.icon}
            value={achievement.value}
            subtitle={achievement.subtitle}
            color={achievement.color}
          />
        </div>

        <p class="privacy-notice">
          Se compartirá solo el logro, no tus datos personales.
        </p>

        <div class="share-actions">
          <button
            class="share-btn primary"
            onclick={handleDownload}
            disabled={busy}
            aria-label={$t('shareAchievement.downloadPng')}
          >
            <Download size={15} />
            <span>{$t('shareAchievement.downloadPng')}</span>
          </button>
          <button
            class="share-btn"
            onclick={handleCopy}
            disabled={busy}
            aria-label={$t('shareAchievement.copyClipboard')}
          >
            <Copy size={15} />
            <span>{$t('shareAchievement.copyClipboard')}</span>
          </button>
          <button
            class="share-btn ghost"
            onclick={closeShare}
            disabled={busy}
            aria-label={$t('shareAchievement.close')}
          >
            <X size={15} />
            <span>{$t('shareAchievement.close')}</span>
          </button>
        </div>
      </div>
    {/if}
  {/snippet}
</ModalDialog>

<style>
  .share-body {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s4);
  }

  .card-preview {
    display: flex;
    justify-content: center;
    padding: var(--s2);
  }

  .privacy-notice {
    margin: 0;
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
  }

  .share-actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
    width: 100%;
    justify-content: center;
  }

  .share-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: var(--surface);
    color: var(--text-secondary);
    font-size: 12px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }

  .share-btn:hover:not(:disabled) {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }

  .share-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .share-btn.primary {
    background: var(--xp);
    border-color: var(--xp);
    color: var(--bg);
  }

  .share-btn.primary:hover:not(:disabled) {
    background: var(--xp-dark);
    border-color: var(--xp-dark);
    color: var(--bg);
  }

  .share-btn.ghost {
    background: transparent;
    color: var(--text-muted);
  }
</style>
