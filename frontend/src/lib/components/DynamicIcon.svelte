<script lang="ts">
  import { activeIconPack } from '$lib/stores/settings';
  import Circle from 'lucide-svelte/icons/circle';
  import { getLucideIcon, loadLucideIcon } from '$lib/utils/lucideIcons';
  import { logger } from '$lib/utils/logger';

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

  // Lucide icons resolve synchronously from the curated map (#1311). Names
  // outside it (e.g. user-picked picker icons not referenced in code) load
  // the full set as a single lazy chunk — `Circle` shows until it lands.
  let comp: any = Circle;
  $: {
    const packName = pack || $activeIconPack;
    let resolved: any;
    if (packName === 'phosphor' || packName === 'material') {
      // Phosphor/Material only ship a curated subset. When the requested
      // name isn't in the map, degrade gracefully to the matching lucide
      // icon instead of a generic Circle so the UI never shows a blank
      // circle (#783).
      resolved = phosphorMap[name] || (getLucideIcon(name) ?? Circle);
    } else {
      resolved = getLucideIcon(name) ?? Circle;
    }
    comp = resolved;
    // NB: test the local `resolved`, never `comp` — reading `comp` inside
    // this block makes it a dependency of its own reactive statement, and
    // since component values are objects Svelte treats every assignment as
    // a change → infinite render loop (#freeze).
    if (!isEmoji && (!resolved || resolved === Circle)) {
      const requested = name;
      loadLucideIcon(requested)
        .then((loaded) => {
          if (loaded && name === requested) comp = loaded;
        })
        // Failed lazy chunk: keep the Circle fallback — no unhandled
        // rejection and no broken icon slot (#1459).
        .catch((err) => logger.warn('[DynamicIcon] lazy icon load failed:', err));
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
