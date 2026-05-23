const STORAGE_PREFIX = 'joidy_';

export async function getAsync<T>(key: string, defaultValue: T): Promise<T> {
  if (typeof localStorage === 'undefined') return defaultValue;
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + key);
    return raw ? JSON.parse(raw) : defaultValue;
  } catch {
    return defaultValue;
  }
}

export async function setAsync<T>(key: string, value: T): Promise<void> {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
  } catch (e) {
    console.error('Storage error:', e);
  }
}

export async function removeAsync(key: string): Promise<void> {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(STORAGE_PREFIX + key);
}

export async function clearAsync(): Promise<void> {
  if (typeof localStorage === 'undefined') return;
  const keys = Object.keys(localStorage).filter(k => k.startsWith(STORAGE_PREFIX));
  keys.forEach(k => localStorage.removeItem(k));
}

export async function getAllKeys(): Promise<string[]> {
  if (typeof localStorage === 'undefined') return [];
  return Object.keys(localStorage)
    .filter(k => k.startsWith(STORAGE_PREFIX))
    .map(k => k.replace(STORAGE_PREFIX, ''));
}