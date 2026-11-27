<script lang="ts">
  import { untrack } from 'svelte';
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import SettingsPanel from '$lib/components/SettingsPanel.svelte';

  // Deep-linking (#1671): /settings#vault opens the Vault section directly.
  // The panel validates the slug against its visible-section list and falls
  // back to the first section for unknown hashes, so no guard is needed here.
  let section = $state(page.url.hash.slice(1) || 'appearance');

  // URL → state: pasted/back-forward hash updates select the section. The
  // `section` read is untracked — this effect must only react to router URL
  // changes. If section were a dependency, a rail click would re-run it
  // before the hash write below lands and snap the selection back to the
  // stale page.url hash.
  $effect(() => {
    const fromHash = page.url.hash.slice(1);
    if (fromHash && fromHash !== untrack(() => section)) {
      section = fromHash;
    }
  });

  // State → URL: sync the hash via a shallow, replace-mode goto (no history
  // entries, so Escape/back leaves Settings in one step). The guard reads
  // window.location.hash — deliberately NOT page.url — so the router's own
  // page.url update cannot re-invalidate this effect and loop (a reactive
  // page.url read here deadlocked the renderer: frozen boot screen in E2E,
  // #1671).
  $effect(() => {
    if (section && window.location.hash.slice(1) !== section) {
      // eslint-disable-next-line svelte/no-navigation-without-resolve -- dynamic section hash; resolve() cannot express fragments
      void goto(`${resolve('/settings')}#${section}`, { replace: true, reset: false });
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
