import { describe, it, expect } from 'vitest';
import { ICON_EMOJIS, ICON_SUGGESTIONS, suggestEmoji, suggestIcon, suggestIconKey } from './iconSuggest';

describe('suggestIconKey', () => {
  it('returns null for empty and unknown titles', () => {
    expect(suggestIconKey('')).toBeNull();
    expect(suggestIconKey('   ')).toBeNull();
    expect(suggestIconKey('Algo genérico sin keywords')).toBeNull();
  });

  it('matches Spanish keywords ignoring case and accents', () => {
    expect(suggestIconKey('Correr 5 km')).toBe('Footprints');
    expect(suggestIconKey('SUEÑO REPARADOR')).toBe('Moon');
    expect(suggestIconKey('Meditación diaria')).toBe('Flower2');
    expect(suggestIconKey('Hidratación')).toBe('Droplets');
    expect(suggestIconKey('Llevar contador de pesos')).toBe('Scale');
    expect(suggestIconKey('Practicar inglés')).toBe('Languages');
  });

  it('matches English keywords', () => {
    expect(suggestIconKey('Drink water daily')).toBe('Droplets');
    expect(suggestIconKey('Save money every month')).toBe('Banknote');
    expect(suggestIconKey('Read 30 pages')).toBe('BookOpen');
    expect(suggestIconKey('Sleep before 12')).toBe('Moon');
    expect(suggestIconKey('Work out 3x a week')).toBe('Dumbbell');
  });

  it('first matching keyword wins', () => {
    expect(suggestIconKey('Leer antes de dormir')).toBe('BookOpen');
    expect(suggestIconKey('Ir en bici y correr')).toBe('Bike');
    expect(suggestIconKey('Rutina de lectura nocturna')).toBe('BookOpen');
    expect(suggestIconKey('Racha de correr')).toBe('Footprints');
  });
});

describe('suggestIcon', () => {
  it('returns the suggested lucide name', () => {
    expect(suggestIcon('Ir al gym')).toBe('Dumbbell');
    expect(suggestIcon('Estudiar para el examen')).toBe('GraduationCap');
    expect(suggestIcon('Programar el scraper')).toBe('Code');
    expect(suggestIcon('Ahorrar dinero')).toBe('Banknote');
  });

  it('returns the fallback when there is no keyword match', () => {
    expect(suggestIcon('Algo aleatorio')).toBe('Activity');
    expect(suggestIcon('')).toBe('Activity');
    expect(suggestIcon('Algo aleatorio', 'Flame')).toBe('Flame');
  });
});

describe('suggestEmoji', () => {
  it('derives the emoji from the suggested icon', () => {
    expect(suggestEmoji('Ir al gym')).toBe('💪');
    expect(suggestEmoji('Leer 20 páginas')).toBe('📚');
    expect(suggestEmoji('Beber 2 litros de agua')).toBe('💧');
    expect(suggestEmoji('Dormir 8 horas')).toBe('🌙');
  });

  it('returns the fallback when there is no keyword match', () => {
    expect(suggestEmoji('Algo aleatorio')).toBe('🔴');
    expect(suggestEmoji('Algo aleatorio', '🔥')).toBe('🔥');
  });
});

describe('suggestion table coherence', () => {
  it('every icon in the table has an emoji mapping', () => {
    for (const [, icon] of ICON_SUGGESTIONS) {
      expect(ICON_EMOJIS[icon], `falta emoji para el icono ${icon}`).toBeTruthy();
    }
  });
});
