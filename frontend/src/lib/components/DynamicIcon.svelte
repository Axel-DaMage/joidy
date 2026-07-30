<script lang="ts">
  import { activeIconPack } from '$lib/stores/settings';
  import { Circle } from 'lucide-svelte';

  export let name: string;
  export let size: number = 18;
  export let color: string | undefined = undefined;
  export let pack: string | undefined = undefined;

  const emojiRegex = /\p{Extended_Pictographic}/u;

  // ── Phosphor ──
  import {
    House as PHome, BookOpen as PBook, ShareNetwork as PNet, Lightning as PZap,
    Target as PTarget, Fire as PFlame, Gear as PCog, GridFour as PGrid,
    X as PX, Moon as PMoon, Sun as PSun, Database as PDB, GitBranch as PGit,
    Palette as PPal, Plus as PPlus, Minus as PMinus, ArrowCounterClockwise as PRot,
    FastForward as PSkip, File as PFile, CaretLeft as PLeft, CaretRight as PRight,
    Wrench as PWrench
  } from 'phosphor-svelte';

  $: isEmoji = emojiRegex.test(name);

  let lucideComp: any = Circle;
  let phosphorComp: any = null;

  async function loadLucide(n: string) {
    const mod = await import('lucide-svelte');
    lucideComp = mod[n as keyof typeof mod] || Circle;
  }

  $: if (!isEmoji && (pack || $activeIconPack) !== 'phosphor' && (pack || $activeIconPack) !== 'material') {
    loadLucide(name);
  }

  function getIconComponent(packName: string, n: string) {
    if (packName === 'phosphor' || packName === 'material') {
      const map: Record<string, any> = {
        'Home': PHome, 'BookOpen': PBook, 'Network': PNet, 'Zap': PZap, 'Target': PTarget,
        'Flame': PFlame, 'Settings': PCog, 'LayoutGrid': PGrid, 'X': PX, 'Moon': PMoon,
        'Sun': PSun, 'Database': PDB, 'GitBranch': PGit, 'Palette': PPal, 'Plus': PPlus,
        'Minus': PMinus, 'RotateCcw': PRot, 'SkipForward': PSkip, 'File': PFile,
        'ChevronLeft': PLeft, 'ChevronRight': PRight, 'Wrench': PWrench,
      };
      phosphorComp = map[n] || null;
      return phosphorComp || Circle;
    }
    return lucideComp || Circle;
  }

  $: comp = getIconComponent(pack || $activeIconPack, name);
</script>

{#if isEmoji}
  <span
    style="width: {size}px; height: {size}px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: {size}px; line-height: 1;"
    aria-hidden="true"
  >
    {name}
  </span>
{:else}
  <svelte:component this={comp} size="{size}" width="{size}" height="{size}" color={color} style="width: {size}px; height: {size}px; color: {color ? color : 'inherit'}; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;" />
{/if}
