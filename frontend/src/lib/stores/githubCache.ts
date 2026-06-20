import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';

export interface GithubCacheEntry {
  issues: any[];
  prs: any[];
  repoColors: Record<string, string>;
  timestamp: number;
}

const GITHUB_CACHE_KEY = 'joidy_github_cache';
const GITHUB_CACHE_TTL = 1000 * 60 * 5; // 5 minutes

function loadGithubCache(): GithubCacheEntry | null {
  if (!browser) return null;
  try {
    const raw = localStorage.getItem(GITHUB_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as GithubCacheEntry;
    if (Date.now() - parsed.timestamp > GITHUB_CACHE_TTL) {
      localStorage.removeItem(GITHUB_CACHE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function saveGithubCache(entry: GithubCacheEntry) {
  if (!browser) return;
  try {
    localStorage.setItem(GITHUB_CACHE_KEY, JSON.stringify(entry));
  } catch {}
}

export const githubCache = writable<GithubCacheEntry | null>(loadGithubCache());

export function setGithubCache(data: { issues: any[]; prs: any[]; repoColors: Record<string, string> }) {
  const entry: GithubCacheEntry = {
    ...data,
    timestamp: Date.now(),
  };
  githubCache.set(entry);
  saveGithubCache(entry);
}

export function getGithubCache(): GithubCacheEntry | null {
  return get(githubCache);
}

export function clearGithubCache() {
  if (!browser) return;
  localStorage.removeItem(GITHUB_CACHE_KEY);
  githubCache.set(null);
}