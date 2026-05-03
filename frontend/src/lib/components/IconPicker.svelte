<script lang="ts">
	import { createIconPickerStore } from '$lib/stores/iconPicker';
	import DynamicIcon from './DynamicIcon.svelte';
	import * as L from 'lucide-svelte';

	interface Props {
		selected?: string;
		color?: string;
		onSelect: (icon: string) => void;
	}

	let { selected = '', color, onSelect }: Props = $props();

	const picker = createIconPickerStore();
	const { searchTerm, visibleIcons, filteredAll } = picker;

	function select(icon: string) {
		onSelect(icon);
	}
</script>

<div class="icon-picker">
	<div class="search-box">
		<L.Search size={16} class="search-icon" />
		<input
			type="text"
			placeholder="Buscar iconos..."
			bind:value={$searchTerm}
			onfocus={() => picker.visibleLimit.set(150)}
		/>
		<span class="count">{$filteredAll.length}</span>
	</div>

	<div class="icon-grid scrollbar-hide" onscroll={(e) => picker.handleScroll(e)}>
		{#each $visibleIcons as icon}
			<button
				type="button"
				class="icon-btn"
				class:active={selected === icon}
				onclick={() => select(icon)}
				title={icon}
			>
				<DynamicIcon name={icon} size={20} {color} />
			</button>
		{/each}

		{#if $visibleIcons.length < $filteredAll.length}
			<div class="loading-trigger">...</div>
		{/if}
	</div>
</div>

<style>
	.icon-picker {
		display: flex;
		flex-direction: column;
		gap: 12px;
		height: 100%;
		min-height: 300px;
	}

	.search-box {
		display: flex;
		align-items: center;
		width: 100%;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 8px;
		padding: 0 12px;
		transition: all 0.2s;
		box-sizing: border-box;
	}

	.search-box:focus-within {
		border-color: var(--accent);
		background: rgba(255, 255, 255, 0.08);
	}

	.search-icon {
		opacity: 0.5;
		flex-shrink: 0;
	}

	input {
		flex: 1;
		background: transparent;
		border: none;
		padding: 10px 8px;
		color: white;
		outline: none;
		font-family: inherit;
		box-sizing: border-box;
	}

	.count {
		font-size: 0.7rem;
		opacity: 0.4;
		flex-shrink: 0;
	}

	.icon-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(44px, 1fr));
		gap: 8px;
		overflow-y: auto;
		flex: 1;
		min-height: 0;
		padding: 4px;
		align-content: start;
	}

	.icon-btn {
		aspect-ratio: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid rgba(255, 255, 255, 0.05);
		border-radius: 8px;
		color: rgba(255, 255, 255, 0.6);
		cursor: pointer;
		transition: all 0.2s;
	}

	.icon-btn:hover {
		background: rgba(255, 255, 255, 0.1);
		color: white;
		border-color: rgba(255, 255, 255, 0.2);
	}

	.icon-btn.active {
		background: var(--accent);
		color: black;
		border-color: var(--accent);
	}

	.loading-trigger {
		grid-column: 1 / -1;
		text-align: center;
		padding: 20px;
		opacity: 0.2;
	}

	/* Hide scrollbar for Chrome, Safari and Opera */
	.scrollbar-hide::-webkit-scrollbar {
		display: none;
	}

	/* Hide scrollbar for IE, Edge and Firefox */
	.scrollbar-hide {
		-ms-overflow-style: none; /* IE and Edge */
		scrollbar-width: none; /* Firefox */
	}
</style>
