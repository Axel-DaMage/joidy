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



  // ── Material ──
  import MHome from 'svelte-material-icons/Home.svelte';
  import MBook from 'svelte-material-icons/BookOpenOutline.svelte';
  import MNet from 'svelte-material-icons/Network.svelte';
  import MZap from 'svelte-material-icons/Flash.svelte';
  import MTarget from 'svelte-material-icons/Target.svelte';
  import MFlame from 'svelte-material-icons/Fire.svelte';
  import MCog from 'svelte-material-icons/Cog.svelte';
  import MGrid from 'svelte-material-icons/ViewGrid.svelte';
  import MX from 'svelte-material-icons/Close.svelte';
  import MMoon from 'svelte-material-icons/WeatherNight.svelte';
  import MSun from 'svelte-material-icons/WeatherSunny.svelte';
  import MDB from 'svelte-material-icons/Database.svelte';
  import MGit from 'svelte-material-icons/SourceBranch.svelte';
  import MPal from 'svelte-material-icons/Palette.svelte';
  import MPlus from 'svelte-material-icons/Plus.svelte';
  import MMinus from 'svelte-material-icons/Minus.svelte';
  import MRot from 'svelte-material-icons/Refresh.svelte';
  import MSkip from 'svelte-material-icons/SkipNext.svelte';
  import MFile from 'svelte-material-icons/FileDocumentOutline.svelte';
  import MLeft from 'svelte-material-icons/ChevronLeft.svelte';
  import MRight from 'svelte-material-icons/ChevronRight.svelte';
  
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
        'Home': MHome, 'BookOpen': MBook, 'Network': MNet, 'Zap': MZap, 'Target': MTarget,
        'Flame': MFlame, 'Settings': MCog, 'LayoutGrid': MGrid, 'X': MX, 'Moon': MMoon,
        'Sun': MSun, 'Database': MDB, 'GitBranch': MGit, 'Palette': MPal, 'Plus': MPlus,
        'Minus': MMinus, 'RotateCcw': MRot, 'SkipForward': MSkip, 'File': MFile,
        'ChevronLeft': MLeft, 'ChevronRight': MRight,
      };
      return map[n] || (L as any)[n] || (L as any)['Circle'];
    }

    // Default fallback to Lucide (also handles 'lucide' implicitly or missing ones)
    const lMap = (L as any);
    return lMap[n] || lMap['Circle'];
  }
</script>

<svelte:component this={comp} size="{size}" width="{size}" height="{size}" color={color} style="width: {size}px; height: {size}px; color: {color ? color : 'inherit'}; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;" />
