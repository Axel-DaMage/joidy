import { describe, it, expect, beforeEach } from 'vitest';
import { render, cleanup } from '@testing-library/svelte';
import AiDisclosure from './AiDisclosure.svelte';

describe('AiDisclosure', () => {
  beforeEach(() => cleanup());

  it('renders the AI-generated notice and docs link', () => {
    const { getByRole, getByText } = render(AiDisclosure);

    // role="note" marks the disclosure as an annotation for assistive tech.
    const note = getByRole('note');
    expect(note).toBeTruthy();
    expect(note.textContent).toContain('Generado por IA');

    const link = getByText('Transparencia de IA');
    expect(link.tagName).toBe('A');
    expect(link.getAttribute('href')).toContain('docs/ai-transparency.md');
    expect(link.getAttribute('rel')).toContain('noopener');
  });

  it('renders the provider name when provided', () => {
    const { getByText } = render(AiDisclosure, { provider: 'gemini' });
    expect(getByText(/Proveedor: gemini/)).toBeTruthy();
  });

  it('hides the docs link when showLink is false', () => {
    const { queryByText } = render(AiDisclosure, { showLink: false });
    expect(queryByText('Transparencia de IA')).toBeNull();
  });

  it('applies the compact variant class', () => {
    const { container } = render(AiDisclosure, { compact: true });
    expect(container.querySelector('.ai-disclosure.compact')).toBeTruthy();
  });
});