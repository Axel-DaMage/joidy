<script lang="ts">
  import { plantStageName, globalLevel } from '$lib/stores/gamification';
  import { accentColors } from '$lib/stores/settings';

  // wilted if no activity for 3+ days — passed as prop
  export let wilted = false;
  export let size = 200;

  // Map 1-100 level to 0-6 visual stages (100 / 7 ≈ 14.3)
  $: stage = Math.min(6, Math.floor(($globalLevel - 1) / (100 / 7)));
  $: stageName = $plantStageName;

  $: colors = $accentColors;
  $: c1 = colors[0] || 'var(--plant)';
  $: c2 = colors[1] || colors[0] || 'var(--plant-2)';
  $: c3 = colors[2] || colors[1] || colors[0] || 'var(--plant-3)';
</script>

<div
  class="plant-container"
  class:wilted
  style="width:{size}px; height:{size}px;"
  title="Etapa: {stageName} (Nivel {$globalLevel})"
>
  <svg
    viewBox="0 0 100 120"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="plant-svg"
  >
    <!-- Stage 0: Seed -->
    {#if stage === 0}
      <!-- Ground line -->
      <line x1="20" y1="100" x2="80" y2="100" stroke={c1} stroke-width="0.8" opacity="0.4"/>
      <!-- Seed oval -->
      <ellipse cx="50" cy="96" rx="8" ry="5" stroke={c1} stroke-width="1.2" fill="none"/>
      <!-- Two sprouting dots -->
      <circle cx="46" cy="89" r="1.5" fill={c2} opacity="0.6"/>
      <circle cx="54" cy="87" r="1.5" fill={c2} opacity="0.6"/>

    <!-- Stage 1: Sprout -->
    {:else if stage === 1}
      <line x1="20" y1="100" x2="80" y2="100" stroke={c1} stroke-width="0.8" opacity="0.4"/>
      <!-- Stem -->
      <path d="M50 100 C50 92 50 85 50 78" stroke={c1} stroke-width="1.4" stroke-linecap="round"/>
      <!-- Left leaf -->
      <path d="M50 86 C44 82 38 80 36 84 C38 88 44 88 50 86" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <!-- Right leaf -->
      <path d="M50 82 C56 78 62 76 64 80 C62 84 56 84 50 82" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>

    <!-- Stage 2: Seedling -->
    {:else if stage === 2}
      <line x1="20" y1="100" x2="80" y2="100" stroke={c1} stroke-width="0.8" opacity="0.4"/>
      <path d="M50 100 C50 90 50 80 50 68" stroke={c1} stroke-width="1.5" stroke-linecap="round"/>
      <!-- 4 leaves, alternating -->
      <path d="M50 92 C43 88 38 85 36 89 C38 93 43 92 50 92" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 87 C57 83 62 80 64 84 C62 88 57 88 50 87" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 80 C43 76 37 74 36 78 C38 82 43 81 50 80" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 75 C57 71 63 69 65 73 C63 77 57 76 50 75" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>

    <!-- Stage 3: Young plant -->
    {:else if stage === 3}
      <line x1="20" y1="100" x2="80" y2="100" stroke={c1} stroke-width="0.8" opacity="0.4"/>
      <!-- Main stem -->
      <path d="M50 100 C50 88 50 75 50 62" stroke={c1} stroke-width="1.8" stroke-linecap="round"/>
      <!-- Side branch left -->
      <path d="M50 80 C45 76 40 72 36 74" stroke={c1} stroke-width="1.2" stroke-linecap="round"/>
      <!-- Side branch right -->
      <path d="M50 73 C55 68 60 64 65 66" stroke={c1} stroke-width="1.2" stroke-linecap="round"/>
      <!-- Leaves on main -->
      <path d="M50 92 C43 88 37 86 36 90 C38 94 43 93 50 92" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 85 C57 81 63 79 64 83 C62 87 57 86 50 85" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>
      <!-- Leaves on branches -->
      <path d="M38 73 C34 69 31 66 33 63 C36 65 38 69 38 73" stroke={c2} stroke-width="0.9" fill="none" stroke-linecap="round"/>
      <path d="M63 65 C67 61 70 59 68 56 C65 58 63 62 63 65" stroke={c3} stroke-width="0.9" fill="none" stroke-linecap="round"/>
      <!-- Top leaves -->
      <path d="M50 68 C44 63 39 61 38 65 C40 69 45 68 50 68" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 63 C56 58 61 57 62 61 C60 65 55 64 50 63" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>

    <!-- Stage 4: Mature plant -->
    {:else if stage === 4}
      <line x1="15" y1="100" x2="85" y2="100" stroke={c1} stroke-width="0.8" opacity="0.4"/>
      <path d="M50 100 C50 86 50 72 50 55" stroke={c1} stroke-width="2" stroke-linecap="round"/>
      <!-- Two side branches each side -->
      <path d="M50 85 C44 80 38 76 32 78" stroke={c1} stroke-width="1.3" stroke-linecap="round"/>
      <path d="M50 75 C56 70 62 66 68 68" stroke={c1} stroke-width="1.3" stroke-linecap="round"/>
      <path d="M50 68 C43 63 37 60 32 62" stroke={c1} stroke-width="1.1" stroke-linecap="round"/>
      <path d="M50 62 C57 57 63 55 68 57" stroke={c1} stroke-width="1.1" stroke-linecap="round"/>
      <!-- Leaf clusters -->
      <path d="M50 92 C42 87 36 85 34 89 C36 93 42 92 50 92" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 87 C58 82 64 80 66 84 C64 88 58 87 50 87" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M33 77 C28 73 25 70 27 67 C30 69 33 73 33 77" stroke={c2} stroke-width="0.9" fill="none" stroke-linecap="round"/>
      <path d="M67 67 C72 63 75 61 73 58 C70 60 67 64 67 67" stroke={c3} stroke-width="0.9" fill="none" stroke-linecap="round"/>
      <path d="M33 61 C28 57 26 54 28 51 C31 53 33 57 33 61" stroke={c2} stroke-width="0.9" fill="none" stroke-linecap="round"/>
      <path d="M67 56 C72 52 74 50 72 47 C69 49 67 53 67 56" stroke={c3} stroke-width="0.9" fill="none" stroke-linecap="round"/>
      <path d="M50 62 C43 57 37 55 36 59 C38 63 43 62 50 62" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 56 C57 51 63 50 64 54 C62 58 57 57 50 56" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>

    <!-- Stage 5: Flowering -->
    {:else if stage === 5}
      <line x1="10" y1="100" x2="90" y2="100" stroke={c1} stroke-width="0.8" opacity="0.4"/>
      <path d="M50 100 C50 84 50 68 50 50" stroke={c1} stroke-width="2.2" stroke-linecap="round"/>
      <!-- Branches -->
      <path d="M50 88 C43 83 36 79 28 80" stroke={c1} stroke-width="1.4" stroke-linecap="round"/>
      <path d="M50 78 C57 73 64 69 72 70" stroke={c1} stroke-width="1.4" stroke-linecap="round"/>
      <path d="M50 70 C42 65 35 62 28 64" stroke={c1} stroke-width="1.2" stroke-linecap="round"/>
      <path d="M50 63 C58 58 65 56 73 58" stroke={c1} stroke-width="1.2" stroke-linecap="round"/>
      <path d="M50 55 C44 50 38 48 32 50" stroke={c2} stroke-width="1" stroke-linecap="round"/>
      <path d="M50 52 C56 47 62 46 68 48" stroke={c3} stroke-width="1" stroke-linecap="round"/>
      <!-- Leaves -->
      <path d="M50 94 C41 89 34 87 32 91 C34 95 41 94 50 94" stroke={c2} stroke-width="1" fill="none" stroke-linecap="round"/>
      <path d="M50 89 C59 84 66 82 68 86 C66 90 59 89 50 89" stroke={c3} stroke-width="1" fill="none" stroke-linecap="round"/>
      <!-- Flowers — small circles at branch ends -->
      <circle cx="27" cy="79" r="3.5" stroke={c3} stroke-width="0.9" fill="none"/>
      <circle cx="27" cy="79" r="1.2" fill={c3} opacity="0.7"/>
      <circle cx="73" cy="69" r="3.5" stroke={c2} stroke-width="0.9" fill="none"/>
      <circle cx="73" cy="69" r="1.2" fill={c2} opacity="0.7"/>
      <circle cx="27" cy="63" r="3" stroke={c3} stroke-width="0.9" fill="none"/>
      <circle cx="27" cy="63" r="1" fill={c3} opacity="0.7"/>
      <circle cx="74" cy="57" r="3" stroke={c2} stroke-width="0.9" fill="none"/>
      <circle cx="74" cy="57" r="1" fill={c2} opacity="0.7"/>
      <circle cx="50" cy="48" r="4" stroke={c1} stroke-width="1" fill="none"/>
      <circle cx="50" cy="48" r="1.5" fill={c1} opacity="0.6"/>

    <!-- Stage 6: Tree -->
    {:else if stage === 6}
      <line x1="10" y1="100" x2="90" y2="100" stroke={c1} stroke-width="0.8" opacity="0.4"/>
      <!-- Trunk -->
      <path d="M50 100 C50 92 49 84 48 76 C47 68 48 60 50 52" stroke={c1} stroke-width="3" stroke-linecap="round"/>
      <!-- Trunk split -->
      <path d="M50 72 C44 66 38 62 32 64" stroke={c1} stroke-width="2" stroke-linecap="round"/>
      <path d="M50 66 C56 60 62 58 68 60" stroke={c1} stroke-width="2" stroke-linecap="round"/>
      <!-- Second level -->
      <path d="M34 63 C28 57 24 53 26 48 C28 52 30 58 34 63" stroke={c2} stroke-width="1.5" stroke-linecap="round"/>
      <path d="M34 63 C30 57 32 52 36 50" stroke={c2} stroke-width="1.4" stroke-linecap="round"/>
      <path d="M66 59 C72 53 76 50 74 45 C72 49 70 55 66 59" stroke={c3} stroke-width="1.5" stroke-linecap="round"/>
      <path d="M66 59 C70 53 68 48 64 46" stroke={c3} stroke-width="1.4" stroke-linecap="round"/>
      <!-- Top canopy -->
      <path d="M50 52 C44 46 40 42 38 38 C42 36 46 40 50 44 C54 40 58 36 62 38 C60 42 56 46 50 52" stroke={c2} stroke-width="1.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      <!-- Canopy fill (leaves mass) -->
      <ellipse cx="38" cy="44" rx="8" ry="6" stroke={c3} stroke-width="1" fill="none" opacity="0.7"/>
      <ellipse cx="62" cy="43" rx="8" ry="6" stroke={c3} stroke-width="1" fill="none" opacity="0.7"/>
      <ellipse cx="50" cy="38" rx="9" ry="7" stroke={c2} stroke-width="1.2" fill="none"/>
      <!-- Small root hints -->
      <path d="M49 100 C46 103 42 104 40 103" stroke={c1} stroke-width="0.8" opacity="0.5" stroke-linecap="round"/>
      <path d="M51 100 C54 103 58 104 60 103" stroke={c1} stroke-width="0.8" opacity="0.5" stroke-linecap="round"/>
    {/if}
  </svg>
</div>

<style>
  .plant-container {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .plant-svg {
    width: 100%;
    height: 100%;
    animation: breathe 4s ease-in-out infinite;
    transform-origin: center bottom;
  }

  .wilted .plant-svg {
    animation: wilt 6s ease-in-out infinite;
    opacity: 0.6;
  }

  @keyframes breathe {
    0%, 100% { transform: scale(1) translateY(0); }
    50%       { transform: scale(1.015) translateY(-2px); }
  }

  @keyframes wilt {
    0%, 100% { transform: rotate(0deg) translateY(0); }
    30%       { transform: rotate(-1.5deg) translateY(1px); }
    70%       { transform: rotate(1deg) translateY(0.5px); }
  }
</style>
