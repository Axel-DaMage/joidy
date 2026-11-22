import Activity from 'lucide-svelte/icons/activity';
import Archive from 'lucide-svelte/icons/archive';
import Award from 'lucide-svelte/icons/award';
import Briefcase from 'lucide-svelte/icons/briefcase';
import Calendar from 'lucide-svelte/icons/calendar';
import CalendarCheck from 'lucide-svelte/icons/calendar-check';
import CircleCheck from 'lucide-svelte/icons/circle-check';
import Clock from 'lucide-svelte/icons/clock';
import CloudRain from 'lucide-svelte/icons/cloud-rain';
import Database from 'lucide-svelte/icons/database';
import Flame from 'lucide-svelte/icons/flame';
import Focus from 'lucide-svelte/icons/focus';
import GitCommitHorizontal from 'lucide-svelte/icons/git-commit-horizontal';
import GitPullRequest from 'lucide-svelte/icons/git-pull-request';
import Heart from 'lucide-svelte/icons/heart';
import Lightbulb from 'lucide-svelte/icons/lightbulb';
import Medal from 'lucide-svelte/icons/medal';
import Minus from 'lucide-svelte/icons/minus';
import PartyPopper from 'lucide-svelte/icons/party-popper';
import Pencil from 'lucide-svelte/icons/pencil';
import ChartPie from 'lucide-svelte/icons/chart-pie';
import Shuffle from 'lucide-svelte/icons/shuffle';
import Smile from 'lucide-svelte/icons/smile';
import Sparkles from 'lucide-svelte/icons/sparkles';
import Sprout from 'lucide-svelte/icons/sprout';
import Sun from 'lucide-svelte/icons/sun';
import Target from 'lucide-svelte/icons/target';
import ThumbsUp from 'lucide-svelte/icons/thumbs-up';
import Trophy from 'lucide-svelte/icons/trophy';
import TrendingDown from 'lucide-svelte/icons/trending-down';
import TrendingUp from 'lucide-svelte/icons/trending-up';
import Zap from 'lucide-svelte/icons/zap';

/**
 * Icons the insight rules can emit (lib/utils/insights.ts), imported
 * statically so they paint with the first frame. `DynamicIcon` would fall
 * back to a blank circle while it lazy-loads the full lucide set for any name
 * outside its curated map.
 */
type IconComponent = typeof Activity;

export const INSIGHT_ICONS: Record<string, IconComponent> = {
  activity: Activity,
  archive: Archive,
  award: Award,
  briefcase: Briefcase,
  calendar: Calendar,
  'calendar-check': CalendarCheck,
  'circle-check': CircleCheck,
  clock: Clock,
  'cloud-rain': CloudRain,
  database: Database,
  flame: Flame,
  focus: Focus,
  'git-commit-horizontal': GitCommitHorizontal,
  'git-pull-request': GitPullRequest,
  heart: Heart,
  lightbulb: Lightbulb,
  medal: Medal,
  minus: Minus,
  'party-popper': PartyPopper,
  pencil: Pencil,
  'pie-chart': ChartPie,
  shuffle: Shuffle,
  smile: Smile,
  sparkles: Sparkles,
  sprout: Sprout,
  sun: Sun,
  target: Target,
  'thumbs-up': ThumbsUp,
  trophy: Trophy,
  'trending-down': TrendingDown,
  'trending-up': TrendingUp,
  zap: Zap,
};

export const insightIcon = (name: string): IconComponent =>
  INSIGHT_ICONS[name] ?? Sparkles;
