import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/svelte';
import { tick } from 'svelte';

vi.mock('./DynamicIcon.svelte', () => ({ default: () => null }));
vi.mock('./NoteCard.svelte', () => ({ default: () => null }));

import GithubWidget from './GithubWidget.svelte';

function makeIssue(id: number, state: string, title: string) {
  return {
    id,
    number: id,
    title,
    repo: 'acme/repo',
    url: `https://github.com/acme/repo/issues/${id}`,
    state,
  };
}

function makePr(id: number, state: string, merged_at: string | null = null, title = `PR ${id}`) {
  return {
    id,
    number: id,
    title,
    repo: 'acme/repo',
    url: `https://github.com/acme/repo/pull/${id}`,
    state,
    merged_at,
  };
}

const ISSUES = [
  makeIssue(1, 'open', 'Fix login flow'),
  makeIssue(2, 'closed', 'Deploy pipeline broken'),
];

const PRS = [
  makePr(10, 'open'),
  makePr(11, 'closed', '2026-01-02T00:00:00Z'),
];

function stateButtons(container: HTMLElement) {
  const rows = container.querySelectorAll('.gh-filters-stack .gh-filters');
  return rows[rows.length - 1].querySelectorAll('button');
}

async function clickState(container: HTMLElement, index: number) {
  fireEvent.click(stateButtons(container)[index]);
  await tick();
}

describe('GithubWidget — filtros de estado y búsqueda (#1094)', () => {
  beforeEach(() => {
    cleanup();
  });

  it('muestra todos los items por defecto (estado = Todas)', () => {
    const { container } = render(GithubWidget, {
      githubConnected: true,
      githubIssues: ISSUES,
      githubPRs: PRS,
      onSetFilter: vi.fn(),
      onSetType: vi.fn(),
    });
    expect(container.querySelectorAll('.gh-item').length).toBe(4);
  });

  it('filtra por Abiertas', async () => {
    const { container } = render(GithubWidget, {
      githubConnected: true,
      githubIssues: ISSUES,
      githubPRs: PRS,
      onSetFilter: vi.fn(),
      onSetType: vi.fn(),
    });
    await clickState(container, 1);
    expect(container.querySelectorAll('.gh-item').length).toBe(2);
  });

  it('filtra por Cerradas excluyendo PRs mergeados', async () => {
    const { container } = render(GithubWidget, {
      githubConnected: true,
      githubIssues: ISSUES,
      githubPRs: PRS,
      onSetFilter: vi.fn(),
      onSetType: vi.fn(),
    });
    await clickState(container, 2);
    const items = container.querySelectorAll('.gh-item');
    expect(items.length).toBe(1);
    expect(items[0].getAttribute('href')).toContain('/issues/2');
  });

  it('filtra por Mergeados', async () => {
    const { container } = render(GithubWidget, {
      githubConnected: true,
      githubIssues: ISSUES,
      githubPRs: PRS,
      onSetFilter: vi.fn(),
      onSetType: vi.fn(),
    });
    await clickState(container, 3);
    const items = container.querySelectorAll('.gh-item');
    expect(items.length).toBe(1);
    expect(items[0].getAttribute('href')).toContain('/pull/11');
  });

  it('busca por texto en título, repo y número', async () => {
    const { container } = render(GithubWidget, {
      githubConnected: true,
      githubIssues: ISSUES,
      githubPRs: PRS,
      onSetFilter: vi.fn(),
      onSetType: vi.fn(),
    });
    const input = container.querySelector('.gh-search') as HTMLInputElement;
    fireEvent.input(input, { target: { value: 'deploy' } });
    await tick();
    expect(container.querySelectorAll('.gh-item').length).toBe(1);
    fireEvent.input(input, { target: { value: '#10' } });
    await tick();
    const items = container.querySelectorAll('.gh-item');
    expect(items.length).toBe(1);
    expect(items[0].getAttribute('href')).toContain('/pull/10');
  });

  it('muestra mensaje cuando ningún item pasa los filtros', async () => {
    const { container } = render(GithubWidget, {
      githubConnected: true,
      githubIssues: ISSUES,
      githubPRs: PRS,
      onSetFilter: vi.fn(),
      onSetType: vi.fn(),
    });
    const input = container.querySelector('.gh-search') as HTMLInputElement;
    fireEvent.input(input, { target: { value: 'zzz-sin-coincidencias' } });
    await tick();
    expect(container.querySelectorAll('.gh-item').length).toBe(0);
    expect(container.querySelector('.github-list .empty-state')).not.toBeNull();
  });

  // #1164 — ghState/ghSearch son props bindeables: el dashboard las restaura
  // de UserSettings y el widget debe respetarlas al montar.
  it('respeta ghState y ghSearch restaurados por el padre', () => {
    const { container } = render(GithubWidget, {
      githubConnected: true,
      githubIssues: ISSUES,
      githubPRs: PRS,
      ghState: 'open',
      ghSearch: 'login',
      onSetFilter: vi.fn(),
      onSetType: vi.fn(),
    });
    const items = container.querySelectorAll('.gh-item');
    expect(items.length).toBe(1);
    expect(items[0].getAttribute('href')).toContain('/issues/1');
  });
});
