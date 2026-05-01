<script lang="ts">
  import { activeIconPack } from '$lib/stores/settings';

  export let name: string;
  export let size: number = 18;
  export let color: string | undefined = undefined;
  export let pack: string | undefined = undefined;

  // ── Lucide ──
  import * as L from 'lucide-svelte';
  


  // ── Phosphor ──
  import {
    House as PHome, BookOpen as PBook, ShareNetwork as PNet, Lightning as PZap,
    Target as PTarget, Fire as PFlame, Gear as PCog, GridFour as PGrid,
    X as PX, Moon as PMoon, Sun as PSun, Database as PDB, GitBranch as PGit,
    Palette as PPal, Plus as PPlus, Minus as PMinus, ArrowCounterClockwise as PRot,
    FastForward as PSkip, File as PFile, CaretLeft as PLeft, CaretRight as PRight
  } from 'phosphor-svelte';



  // Note: project uses Svelte 5; avoid svelte-material-icons (incompatible)
  // We'll reuse Phosphor/ Lucide icons instead for the 'material' pack mapping.
  $: comp = getIconComponent(pack || $activeIconPack, name);

  function getIconComponent(pack: string, n: string) {


    if (pack === 'phosphor') {
      const map: Record<string, any> = {
        'Home': PHome, 'BookOpen': PBook, 'Network': PNet, 'Zap': PZap, 'Target': PTarget,
        'Flame': PFlame, 'Settings': PCog, 'LayoutGrid': PGrid, 'X': PX, 'Moon': PMoon,
        'Sun': PSun, 'Database': PDB, 'GitBranch': PGit, 'Palette': PPal, 'Plus': PPlus,
        'Minus': PMinus, 'RotateCcw': PRot, 'SkipForward': PSkip, 'File': PFile,
        'ChevronLeft': PLeft, 'ChevronRight': PRight,
      };
      return map[n] || (L as any)[n] || (L as any)['Circle'];
    }

    if (pack === 'material') {
      const map: Record<string, any> = {
        // map common material names to phosphor equivalents
        'Home': PHome, 'BookOpen': PBook, 'Network': PNet, 'Zap': PZap, 'Target': PTarget,
        'Flame': PFlame, 'Settings': PCog, 'LayoutGrid': PGrid, 'X': PX, 'Moon': PMoon,
        'Sun': PSun, 'Database': PDB, 'GitBranch': PGit, 'Palette': PPal, 'Plus': PPlus,
        'Minus': PMinus, 'RotateCcw': PRot, 'SkipForward': PSkip, 'File': PFile,
        'ChevronLeft': PLeft, 'ChevronRight': PRight,
      };
      return map[n] || (L as any)[n] || (L as any)['Circle'];
    }

    // Default fallback to Lucide (also handles 'lucide' implicitly or missing ones)
    const lMap = (L as any);
    return lMap[n] || lMap['Circle'];
  }
</script>

<svelte:component this={comp} size="{size}" width="{size}" height="{size}" color={color} style="width: {size}px; height: {size}px; color: {color ? color : 'inherit'}; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;" />
