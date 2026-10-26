// #1092 — Sugerencia automática de icono/emoji según el título de objetivos
// y rachas. Mismo patrón que `getFileIcon()` de `fileTree.ts`: tabla estática
// [regex → nombre de icono Lucide] donde la primera coincidencia gana.

function normalizeTitle(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

export const ICON_SUGGESTIONS: [RegExp, string][] = [
  // Anotar / escribir / registrar
  [/registrar|registro|anot|apunte|notas?\b|journal|\bdiario\b/,             'Book'],
  [/escrib|redact|blog|articul|poema|poesia|manuscrito|writing|\bwrite/,     'PenLine'],

  // Deporte / movimiento
  [/gym|gimnasio|entrena|pesas|muscula|fitness|workout|work.?out|\bdeporte|ejercicio|\bexercis/, 'Dumbbell'],
  [/ciclism|cycling|bici\b|\bbike\b|pedale/,                                 'Bike'],
  [/correr|corriendo|corredor|\bcorro\b|\bcorres\b|\bcorre\b|running|trotar|caminar|\bandar\b|maraton|\bpasos?\b|\bwalk/, 'Footprints'],
  [/nadar|natacio|\bswim/,                                                   'Waves'],
  [/yoga|pilates|estira|stretch|medita|mindful|respira/,                     'Flower2'],

  // Comida / hidratación / peso
  [/comida|\bcomer\b|\bdieta|nutri|saludable|desayun|almuerz|\bcenar?\b/,    'Apple'],
  [/beber|hidrat|\bagua\b|water\b|\blitros?\b|\bdrink|botella|vasos?\b|ducha/, 'Droplets'],
  [/\bpesos?\b|pesarse|\bkilos?\b|balanza/,                                  'Scale'],

  // Leer / estudiar / código / idiomas
  [/leer|lectura|reading|\bread\b|libros?\b|\bbook|\bpages?\b|\bpagin/,      'BookOpen'],
  [/codigo|\bcode\b|programar|programaci|desarroll|python|javascript|typescript|\bkotlin\b|\bsql\b/, 'Code'],
  [/idioma|vocabular|\baleman\b|\bportugues\b|\bjapones\b|\bchino\b|\bingles\b|\bfrances\b|\blanguage|\benglish\b|\bfrench\b|\bspanish\b/, 'Languages'],
  [/estudi|examen|\bexam\b|certific|universidad|clases?\b|aprend|\blearn|stud(y|ying|ies)/, 'GraduationCap'],

  // Dinero / trabajo / proyectos
  [/dinero|money|ahorr|\bsav|\binver|presupuesto|gastos?\b|finanzas|\bbudget/, 'Banknote'],
  [/trabajo|oficina|cliente|empresa|\bwork\b|freelance/,                     'Briefcase'],
  [/proyecto|startup|lanzamiento|\blaunch/,                                  'Rocket'],

  // Sueño / salud
  [/dormir|sueno|sleep|siesta|descansa|acostar/,                             'Moon'],
  [/salud|medic|doctor|dentista|vitamin|\bhealth/,                           'HeartPulse'],

  // Personas / familia / hogar
  [/reunion|meeting|\bteam\b|familia|amigos|pareja|hijos?\b|\bsocial\b/,     'Users'],
  [/\bamor\b|novios?\b|romance|besos?\b/,                                    'Heart'],
  [/limpia|organiz|tareas?\b|chores?\b|casa\b|hogar/,                        'House'],
  [/mascota|\bperro\b|\bgato\b|\bdog\b|\bcat\b|veterinar/,                   'PawPrint'],
  [/jardin|plantas?\b|plantar|semilla|riego|regar/,                          'Sprout'],

  // Creatividad / ocio
  [/musica|piano|guitarra|canta(r|nd)|cancion|\bsong\b/,                     'Music'],
  [/dibuj|\bpaint|\bpint|\barte\b|\bsketch/,                                 'Palette'],
  [/fotogra|fotos?\b|photos?\b|camara\b/,                                    'Camera'],
  [/viaj|vacaciones|\btrip\b|avion|vuelos?\b/,                               'Plane'],
  [/correo|\bmail|email/,                                                    'Mail'],

  // Mente / metas genéricas
  [/\bpensar|\bmente\b|cerebro|memoria|\bmind\b/,                            'Brain'],
  [/objetivo|\bgoals?\b|\bmetas?\b|\btargets?\b/,                            'Target'],

  // Rutina / rachas (baja prioridad: los temas concretos ganan)
  [/rutina|\bhabito|\bhabits?\b|routine/,                                    'Calendar'],
  [/rachas?\b|\bstreaks?\b/,                                                 'Flame'],
];

// Emojis equivalentes por nombre de icono; usado en modo emoji.
export const ICON_EMOJIS: Record<string, string> = {
  Book: '📖',
  PenLine: '✍️',
  Dumbbell: '💪',
  Bike: '🚴',
  Footprints: '🏃',
  Waves: '🌊',
  Flower2: '🧘',
  Apple: '🍎',
  Droplets: '💧',
  Scale: '⚖️',
  BookOpen: '📚',
  Code: '💻',
  Languages: '🌍',
  GraduationCap: '🎓',
  Banknote: '💰',
  Briefcase: '💼',
  Rocket: '🚀',
  Moon: '🌙',
  HeartPulse: '❤️',
  Users: '👥',
  Heart: '❤️',
  House: '🏠',
  PawPrint: '🐾',
  Sprout: '🌱',
  Music: '🎵',
  Palette: '🎨',
  Camera: '📸',
  Plane: '✈️',
  Mail: '📧',
  Brain: '🧠',
  Target: '🎯',
  Calendar: '📅',
  Flame: '🔥',
};

// Devuelve el nombre Lucide sugerido para el título, o null si no hay match.
export function suggestIconKey(title: string): string | null {
  const n = normalizeTitle(title);
  if (!n) return null;
  for (const [re, icon] of ICON_SUGGESTIONS) {
    if (re.test(n)) return icon;
  }
  return null;
}

// Nombre Lucide sugerido; devuelve `fallback` si no hay match (p. ej. 'Activity').
export function suggestIcon(title: string, fallback = 'Activity'): string {
  return suggestIconKey(title) ?? fallback;
}

// Emoji sugerido (derivado del nombre de icono); `fallback` de lo contrario
// ('🔴' en objetivos, '🔥' en rachas).
export function suggestEmoji(title: string, fallback = '🔴'): string {
  const key = suggestIconKey(title);
  return (key && ICON_EMOJIS[key]) || fallback;
}
