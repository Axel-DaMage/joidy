<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { Home, BookOpen, Network, Zap, Target, Flame, Settings } from 'lucide-svelte';
  import StreakCounter from '$lib/components/StreakCounter.svelte';
  import SettingsPanel from '$lib/components/SettingsPanel.svelte';
  import { totalXP, currentStreak, plantStageName, loadStats, pingActivity } from '$lib/stores/gamification';

  const navItems = [
    { href: '/',        label: 'Dashboard', Icon: Home },
    { href: '/notes',   label: 'Notas',     Icon: BookOpen },
    { href: '/graph',   label: 'Grafo',     Icon: Network },
    { href: '/skills',  label: 'Skills',    Icon: Zap },
    { href: '/goals',   label: 'Objetivos', Icon: Target },
    { href: '/streaks', label: 'Rachas',    Icon: Flame  },
  ];

  let settingsOpen = false;

  onMount(async () => {
    try { await loadStats(); } catch (e) { console.error('[layout] loadStats failed:', e); }
    try { await pingActivity(); } catch (e) { console.error('[layout] pingActivity failed:', e); }
  });
</script>

<div class="app-shell">
  <!-- Header -->
  <header class="app-header">
    <span class="logo mono" style="font-size:15px; letter-spacing:0.12em; color: var(--text-primary); font-weight:500;">JOIDY</span>
    <div style="flex:1;"></div>
    <StreakCounter />
    <div class="xp-header mono" title="XP total">
      <span style="color: var(--xp); font-size:13px;">{$totalXP.toLocaleString()}</span>
      <span style="color: var(--text-muted); font-size:10px; margin-left:3px;">xp</span>
    </div>
    <button
      class="btn btn-ghost btn-icon"
      title="Ajustes"
      style="color: var(--text-muted);"
      on:click={() => settingsOpen = true}
    >
      <Settings size={14} />
    </button>
  </header>

  <!-- Sidebar -->
  <nav class="app-sidebar">
    {#each navItems as { href, label, Icon }}
      {@const active = $page.url.pathname === href || ($page.url.pathname.startsWith(href) && href !== '/')}
      <a {href} class="nav-item" class:active title={label}>
        <Icon size={16} />
        <span class="tooltip">{label}</span>
      </a>
    {/each}
  </nav>

  <!-- Main content -->
  <main class="app-main">
    <slot />
  </main>

  <!-- Status bar -->
  <footer class="app-statusbar">
    <span>◈ {$plantStageName}</span>
    <span style="color: var(--border);">·</span>
    <span>{$currentStreak} días de racha</span>
    <span style="color: var(--border);">·</span>
    <span style="color: var(--text-muted);">joidy v0.1</span>
  </footer>
</div>

<SettingsPanel bind:open={settingsOpen} on:close={() => settingsOpen = false} />

<style>
  .logo { user-select: none; }
  .xp-header { display: flex; align-items: baseline; }
</style>
