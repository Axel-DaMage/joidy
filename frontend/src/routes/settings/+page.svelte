<script lang="ts">
  import { page } from '$app/state';
  import { goto, replaceState } from '$app/navigation';
  import { resolve } from '$app/paths';
  import SettingsPanel from '$lib/components/SettingsPanel.svelte';

  // Deep-linking (#1671): /settings#vault opens the Vault section directly.
  // The panel validates the slug against its visible-section list and falls
  // back to the first section for unknown hashes, so no guard is needed here.
  let section = $state(page.url.hash.slice(1) || 'appearance');

  // URL → state: pasted/back-forward hash updates select the section.
  $effect(() => {
    const fromHash = page.url.hash.slice(1);
    if (fromHash && fromHash !== section) {
      section = fromHash;
    }
  });

  // State → URL: keep the hash in sync via replaceState (no history entries),
  // so Escape/back leaves Settings entirely instead of stepping back through
  // every visited section.
  $effect(() => {
    if (section && page.url.hash.slice(1) !== section) {
      // eslint-disable-next-line svelte/no-navigation-without-resolve -- dynamic section hash; resolve() cannot express fragments
      replaceState(`${resolve('/settings')}#${section}`, page.state);
    }
  });

  function close() {
    if (window.history.length > 1) {
      history.back();
    } else {
      goto(resolve('/'));
    }
  }
</script>

<SettingsPanel bind:section onClose={close} />
