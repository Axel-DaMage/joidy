<script lang="ts">
  import { t } from 'svelte-i18n';
  import AnalyticsDashboard from '$lib/components/analytics/AnalyticsDashboard.svelte';
</script>

<svelte:head>
  <title>{$t('analyticsPage.pageTitle')}</title>
  <meta name="description" content={$t('analyticsPage.description')} />
</svelte:head>

<AnalyticsDashboard />
