// Runtime icon resolution (#1311).
//
// `DynamicIcon`/`StreakIcon` resolve icon names at runtime, so the previous
// `import * as LucideIcons` materialized the full ~1,900-icon set into the
// entry chunk (~855 kB / ~125 kB gzip — first paint AND the SW precache).
// Instead, `getLucideIcon` resolves synchronously from a curated map of every
// icon name the app can actually produce (nav items, file-tree regexes,
// achievements, command palette, GitHub badges, streak suggestions, phosphor
// fallbacks, legacy aliases and `name="..."` literals). Anything outside the
// map loads the full set lazily in a single async chunk via `loadLucideIcon`.
//
// When adding a new `DynamicIcon name="..."` or a code path that can emit a
// new icon name, add it to the curated imports below so it stays synchronous
// (uncurated names still render — just after a lazy chunk fetch).

import Activity from 'lucide-svelte/icons/activity';
import AlarmClock from 'lucide-svelte/icons/alarm-clock';
import Apple from 'lucide-svelte/icons/apple';
import AtSign from 'lucide-svelte/icons/at-sign';
import Banknote from 'lucide-svelte/icons/banknote';
import BarChart from 'lucide-svelte/icons/bar-chart';
import Bike from 'lucide-svelte/icons/bike';
import Book from 'lucide-svelte/icons/book';
import BookOpen from 'lucide-svelte/icons/book-open';
import Box from 'lucide-svelte/icons/box';
import Brain from 'lucide-svelte/icons/brain';
import Briefcase from 'lucide-svelte/icons/briefcase';
import Calculator from 'lucide-svelte/icons/calculator';
import Calendar from 'lucide-svelte/icons/calendar';
import Camera from 'lucide-svelte/icons/camera';
import ChartColumn from 'lucide-svelte/icons/chart-column';
import ChartNoAxesColumn from 'lucide-svelte/icons/chart-no-axes-column';
import ChartPie from 'lucide-svelte/icons/chart-pie';
import Check from 'lucide-svelte/icons/check';
import ChevronLeft from 'lucide-svelte/icons/chevron-left';
import ChevronRight from 'lucide-svelte/icons/chevron-right';
import Circle from 'lucide-svelte/icons/circle';
import CircleCheckBig from 'lucide-svelte/icons/circle-check-big';
import CircleDot from 'lucide-svelte/icons/circle-dot';
import ClipboardList from 'lucide-svelte/icons/clipboard-list';
import Clock from 'lucide-svelte/icons/clock';
import Clock3 from 'lucide-svelte/icons/clock-3';
import Cloud from 'lucide-svelte/icons/cloud';
import CloudDownload from 'lucide-svelte/icons/cloud-download';
import CloudOff from 'lucide-svelte/icons/cloud-off';
import Code from 'lucide-svelte/icons/code';
import Coffee from 'lucide-svelte/icons/coffee';
import Database from 'lucide-svelte/icons/database';
import Download from 'lucide-svelte/icons/download';
import Droplets from 'lucide-svelte/icons/droplets';
import Dumbbell from 'lucide-svelte/icons/dumbbell';
import EyeOff from 'lucide-svelte/icons/eye-off';
import File from 'lucide-svelte/icons/file';
import FileCode from 'lucide-svelte/icons/file-code';
import FilePen from 'lucide-svelte/icons/file-pen';
import FileText from 'lucide-svelte/icons/file-text';
import Files from 'lucide-svelte/icons/files';
import Flame from 'lucide-svelte/icons/flame';
import Flower2 from 'lucide-svelte/icons/flower-2';
import Folder from 'lucide-svelte/icons/folder';
import FolderRoot from 'lucide-svelte/icons/folder-root';
import Footprints from 'lucide-svelte/icons/footprints';
import GitBranch from 'lucide-svelte/icons/git-branch';
import GitMerge from 'lucide-svelte/icons/git-merge';
import GitPullRequest from 'lucide-svelte/icons/git-pull-request';
import Globe from 'lucide-svelte/icons/globe';
import GraduationCap from 'lucide-svelte/icons/graduation-cap';
import Hash from 'lucide-svelte/icons/hash';
import Heart from 'lucide-svelte/icons/heart';
import HeartPulse from 'lucide-svelte/icons/heart-pulse';
import History from 'lucide-svelte/icons/history';
import Home from 'lucide-svelte/icons/home';
import House from 'lucide-svelte/icons/house';
import Info from 'lucide-svelte/icons/info';
import Languages from 'lucide-svelte/icons/languages';
import Layers from 'lucide-svelte/icons/layers';
import LayoutDashboard from 'lucide-svelte/icons/layout-dashboard';
import LayoutGrid from 'lucide-svelte/icons/layout-grid';
import Leaf from 'lucide-svelte/icons/leaf';
import Library from 'lucide-svelte/icons/library';
import Lightbulb from 'lucide-svelte/icons/lightbulb';
import ListFilter from 'lucide-svelte/icons/list-filter';
import LoaderCircle from 'lucide-svelte/icons/loader-circle';
import Lock from 'lucide-svelte/icons/lock';
import LogOut from 'lucide-svelte/icons/log-out';
import Mail from 'lucide-svelte/icons/mail';
import MapPin from 'lucide-svelte/icons/map-pin';
import Minus from 'lucide-svelte/icons/minus';
import Monitor from 'lucide-svelte/icons/monitor';
import Moon from 'lucide-svelte/icons/moon';
import Music from 'lucide-svelte/icons/music';
import Network from 'lucide-svelte/icons/network';
import Package from 'lucide-svelte/icons/package';
import Palette from 'lucide-svelte/icons/palette';
import PawPrint from 'lucide-svelte/icons/paw-print';
import Pen from 'lucide-svelte/icons/pen';
import PenLine from 'lucide-svelte/icons/pen-line';
import PenTool from 'lucide-svelte/icons/pen-tool';
import Plane from 'lucide-svelte/icons/plane';
import Plug from 'lucide-svelte/icons/plug';
import Plus from 'lucide-svelte/icons/plus';
import Power from 'lucide-svelte/icons/power';
import RefreshCw from 'lucide-svelte/icons/refresh-cw';
import Repeat from 'lucide-svelte/icons/repeat';
import Rocket from 'lucide-svelte/icons/rocket';
import RotateCcw from 'lucide-svelte/icons/rotate-ccw';
import Save from 'lucide-svelte/icons/save';
import Scale from 'lucide-svelte/icons/scale';
import Search from 'lucide-svelte/icons/search';
import Settings from 'lucide-svelte/icons/settings';
import SkipForward from 'lucide-svelte/icons/skip-forward';
import SlidersHorizontal from 'lucide-svelte/icons/sliders-horizontal';
import Sparkles from 'lucide-svelte/icons/sparkles';
import Sprout from 'lucide-svelte/icons/sprout';
import SquareCheckBig from 'lucide-svelte/icons/square-check-big';
import SquarePen from 'lucide-svelte/icons/square-pen';
import Star from 'lucide-svelte/icons/star';
import Sun from 'lucide-svelte/icons/sun';
import SunMoon from 'lucide-svelte/icons/sun-moon';
import Tag from 'lucide-svelte/icons/tag';
import Target from 'lucide-svelte/icons/target';
import Terminal from 'lucide-svelte/icons/terminal';
import Timer from 'lucide-svelte/icons/timer';
import Trash2 from 'lucide-svelte/icons/trash-2';
import TreeDeciduous from 'lucide-svelte/icons/tree-deciduous';
import TrendingUp from 'lucide-svelte/icons/trending-up';
import TriangleAlert from 'lucide-svelte/icons/triangle-alert';
import Trophy from 'lucide-svelte/icons/trophy';
import UserRound from 'lucide-svelte/icons/user-round';
import Users from 'lucide-svelte/icons/users';
import Waves from 'lucide-svelte/icons/waves';
import Wrench from 'lucide-svelte/icons/wrench';
import X from 'lucide-svelte/icons/x';
import XCircle from 'lucide-svelte/icons/x-circle';
import Zap from 'lucide-svelte/icons/zap';

// kebab-case file name → PascalCase (e.g. "a-arrow-down" → "AArrowDown",
// "file-audio-2" → "FileAudio2"). Matches the PascalCase keys that the
// lucide-svelte namespace export uses.
function kebabToPascal(kebab: string): string {
  return kebab
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join('');
}

// Curated synchronous set — see the module docstring for how to extend it.
const CURATED_ICONS: Record<string, any> = {
  Activity,
  AlarmClock,
  Apple,
  AtSign,
  Banknote,
  BarChart,
  Bike,
  Book,
  BookOpen,
  Box,
  Brain,
  Briefcase,
  Calculator,
  Calendar,
  Camera,
  ChartColumn,
  ChartNoAxesColumn,
  ChartPie,
  Check,
  ChevronLeft,
  ChevronRight,
  Circle,
  CircleCheckBig,
  CircleDot,
  ClipboardList,
  Clock,
  Clock3,
  Cloud,
  CloudDownload,
  CloudOff,
  Code,
  Coffee,
  Database,
  Download,
  Droplets,
  Dumbbell,
  EyeOff,
  File,
  FileCode,
  FilePen,
  FileText,
  Files,
  Flame,
  Flower2,
  Folder,
  FolderRoot,
  Footprints,
  GitBranch,
  GitMerge,
  GitPullRequest,
  Globe,
  GraduationCap,
  Hash,
  Heart,
  HeartPulse,
  History,
  Home,
  House,
  Info,
  Languages,
  Layers,
  LayoutDashboard,
  LayoutGrid,
  Leaf,
  Library,
  Lightbulb,
  ListFilter,
  LoaderCircle,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Minus,
  Monitor,
  Moon,
  Music,
  Network,
  Package,
  Palette,
  PawPrint,
  Pen,
  PenLine,
  PenTool,
  Plane,
  Plug,
  Plus,
  Power,
  RefreshCw,
  Repeat,
  Rocket,
  RotateCcw,
  Save,
  Scale,
  Search,
  Settings,
  SkipForward,
  SlidersHorizontal,
  Sparkles,
  Sprout,
  SquareCheckBig,
  SquarePen,
  Star,
  Sun,
  SunMoon,
  Tag,
  Target,
  Terminal,
  Timer,
  Trash2,
  TreeDeciduous,
  TrendingUp,
  TriangleAlert,
  Trophy,
  UserRound,
  Users,
  Waves,
  Wrench,
  X,
  XCircle,
  Zap,
};

const _icons = new Map<string, any>(Object.entries(CURATED_ICONS));

// ── Legacy alias map ────────────────────────────────────────────────────────
// lucide-svelte v1.0.0 renamed many icons (#783). Data-driven icon names
// (streaks, achievements, DynamicIcon name="…") may still reference the old
// PascalCase names — especially anything persisted in the DB. Map them to
// their current equivalents so existing data keeps rendering without a
// migration.
const LEGACY_ALIASES: Record<string, string> = {
  AlertTriangle: 'TriangleAlert',
  BarChart: 'ChartColumn',
  BarChart3: 'ChartNoAxesColumn',
  CheckCircle: 'CircleCheckBig',
  CheckSquare: 'SquareCheckBig',
  Edit: 'SquarePen',
  FileEdit: 'FilePen',
  Filter: 'ListFilter',
  Layout: 'LayoutDashboard',
  Loader2: 'LoaderCircle',
  PieChart: 'ChartPie',
  DownloadCloud: 'CloudDownload',
};

function resolveName(name: string): string {
  const alias = LEGACY_ALIASES[name] ?? LEGACY_ALIASES[kebabToPascal(name)];
  return alias ?? name;
}

function lookup(map: Map<string, any> | Record<string, any>, name: string): any | null {
  const resolved = resolveName(name);
  const get = map instanceof Map ? (k: string) => map.get(k) : (k: string) => map[k];
  return get(resolved) ?? get(kebabToPascal(resolved)) ?? null;
}

/**
 * Resolve a lucide icon component by name, synchronously, against the curated
 * set. Accepts either PascalCase ("FileText") or kebab-case ("file-text").
 * Returns the icon's Svelte component, or `null` when the name is unknown to
 * the curated map so callers can fall back (e.g. `Circle`) or call
 * {@link loadLucideIcon} to check the full set lazily.
 */
export function getLucideIcon(name: string): any | null {
  if (!name) return null;
  return lookup(_icons, name);
}

// Single shared promise for the lazily-loaded full set: the first uncurated
// name (or the icon picker opening) downloads one async chunk; every later
// resolution reuses the same module instance.
let _fullSetPromise: Promise<Record<string, any>> | null = null;
function loadFullSet(): Promise<Record<string, any>> {
  return (_fullSetPromise ??= import('lucide-svelte') as Promise<Record<string, any>>);
}

/**
 * Resolve any lucide icon component by name. Checks the curated set first;
 * on a miss the full `lucide-svelte` namespace is fetched as a single lazy
 * chunk (kept out of the entry bundle, #1311).
 */
export async function loadLucideIcon(name: string): Promise<any | null> {
  if (!name) return null;
  const hit = getLucideIcon(name);
  if (hit) return hit;
  const ns = await loadFullSet();
  const icon = lookup(ns, name);
  // Cache the lazy hit back into the curated map. Callers resolve via
  // `getLucideIcon` on every re-render — without this, a lazily-loaded icon
  // flips back to the `Circle` fallback on the next reactive pass and the
  // loader fires again, ping-ponging the component forever (#1311).
  if (icon) {
    const resolved = resolveName(name);
    _icons.set(resolved, icon);
    _icons.set(kebabToPascal(resolved), icon);
  }
  return icon;
}

/**
 * All lucide icon names in PascalCase (e.g. "Search", "FileText"), loaded
 * lazily — only the icon picker needs the full ~1,900-entry list, so the
 * namespace is fetched as an async chunk on first use.
 */
export async function loadAllLucideIconNames(): Promise<string[]> {
  const ns = await loadFullSet();
  return Object.keys(ns)
    .filter((k) => typeof ns[k] === 'function')
    .sort();
}
