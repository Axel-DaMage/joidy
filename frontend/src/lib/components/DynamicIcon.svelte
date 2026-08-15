<script lang="ts">
  import { activeIconPack } from '$lib/stores/settings';
  import { Circle } from 'lucide-svelte';
  import { getLucideIcon } from '$lib/utils/lucideIcons';

  export let name: string;
  export let size: number = 18;
  export let color: string | undefined = undefined;
  export let pack: string | undefined = undefined;

  const emojiRegex = /\p{Extended_Pictographic}/u;

  // ── Phosphor ──
  import {
    House as PHome,
    BookOpen as PBook,
    ShareNetwork as PNet,
    Lightning as PZap,
    Target as PTarget,
    Fire as PFlame,
    Gear as PCog,
    GridFour as PGrid,
    X as PX,
    Moon as PMoon,
    Sun as PSun,
    Database as PDB,
    GitBranch as PGit,
    Palette as PPal,
    Plus as PPlus,
    Minus as PMinus,
    ArrowCounterClockwise as PRot,
    FastForward as PSkip,
    File as PFile,
    CaretLeft as PLeft,
    CaretRight as PRight,
    Wrench as PWrench,
  } from 'phosphor-svelte';

  $: isEmoji = emojiRegex.test(name);

  const phosphorMap: Record<string, any> = {
    Home: PHome,
    BookOpen: PBook,
    Network: PNet,
    Zap: PZap,
    Target: PTarget,
    Flame: PFlame,
    Settings: PCog,
    LayoutGrid: PGrid,
    X: PX,
    Moon: PMoon,
    Sun: PSun,
    Database: PDB,
    GitBranch: PGit,
    Palette: PPal,
    Plus: PPlus,
    Minus: PMinus,
    RotateCcw: PRot,
    SkipForward: PSkip,
    File: PFile,
    ChevronLeft: PLeft,
    ChevronRight: PRight,
    Wrench: PWrench,
  };

  // Lucide icons are resolved synchronously from the eager glob — no async
  // placeholder flicker (#684). Falls back to `Circle` for unknown names.
  let comp: any = Circle;
  $: {
    const packName = pack || $activeIconPack;
    if (packName === 'phosphor' || packName === 'material') {
      comp = phosphorMap[name] || Circle;
    } else {
      comp = getLucideIcon(name) ?? Circle;
    }
  }
</script>

{#if isEmoji}
  <span
    style="width: {size}px; height: {size}px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: {size}px; line-height: 1;"
    aria-hidden="true"
  >
    {name}
  </span>
{:else}
  <svelte:component
    this={comp}
    {size}
    width={size}
    height={size}
    {color}
    style="width: {size}px; height: {size}px; color: {color
      ? color
      : 'inherit'}; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;"
  />
{/if}
