# Modelo de Datos - Joidy

## Entidades Principales

### Note
```typescript
interface Note {
  id: number;
  title: string;
  content: string;
  source: 'joidy' | 'obsidian';
  source_path: string | null;
  tags: string[];
  created_at: string;  // ISO 8601
  updated_at: string;  // ISO 8601
}
```

### Tag
```typescript
interface Tag {
  id: number;
  name: string;
  parent_id: number | null;
  note_count: number;
  created_at: string;
}
```

### Goal
```typescript
interface Goal {
  id: number;
  title: string;
  content: string;
  target_date: string | null;
  completed: boolean;
  state: 'pending' | 'completed' | 'archived' | 'cancelled';
  temporality: 'daily' | 'weekly' | 'monthly' | 'one-time';
  created_at: string;
}
```

### Skill
```typescript
interface Skill {
  id: number;
  name: string;
  parent_id: number | null;
  xp_needed: number;
  icon: string | null;
  unlocked: boolean;
  unlocked_at: string | null;
}
```

### UserStats (Singleton)
```typescript
interface UserStats {
  id: number;  // siempre 1
  total_xp: number;
  current_streak: number;
  longest_streak: number;
  plant_stage: number;  // 0-6
  last_activity_date: string | null;
}
```

### XPEvent
```typescript
interface XPEvent {
  id: number;
  event_type: string;
  xp: number;
  metadata_json: string | null;
  created_at: string;
}
```

### StreakRecord
```typescript
interface StreakRecord {
  id: number;
  activity_date: string;
  xp_earned: number;
}
```

### PersonalStreak
```typescript
interface PersonalStreak {
  id: number;
  name: string;
  goal_type: 'daily_checkin' | 'streak_counter';
  target_count: number;
  current_count: number;
  is_archived: boolean;
  today_checked: boolean;
  last_checked_at: string | null;
  created_at: string;
}
```

### TagCooccurrence
```typescript
interface TagCooccurrence {
  tag_a_id: number;
  tag_b_id: number;
  weight: number;
}
```

### EmbeddingFailure
```typescript
interface EmbeddingFailure {
  note_id: number;
  attempts: number;
  last_error: string | null;
  next_retry_at: string | null;
}
```

## Tablas de Configuración

### SystemConfig
```typescript
interface SystemConfig {
  key: string;
  value: string;
  updated_at: string;
}
```

### GitHub Integration
```typescript
interface GithubRepo {
  id: number;
  full_name: string;
  name: string;
  private: boolean;
  color: string | null;
}

interface GithubItem {
  id: number;
  repo_id: number;
  external_id: number;
  number: number;
  title: string;
  state: string;
  type: 'issue' | 'pr';
  url: string;
}

interface GithubEvent {
  id: number;
  repo_id: number;
  action: string;
  created_at: string;
}
```

## Relaciones

```
Notes 1---N NoteTags N---1 Tags
Notes 1---N NoteLinks (self-referential)
Tags 1---N TagCooccurrences (self)
Tags 1---N Skills (via tag_id)
UserStats 1---N XPEvents
UserStats 1---N StreakRecords
Goals N---1 Notes (via note_id)
```

## Índices Principales

- `ix_notes_updated_at` en notes(updated_at)
- `ix_tags_name` en tags(name)
- `ix_note_tags_note_id` en note_tags(note_id)
- `ix_note_tags_tag_id` en note_tags(tag_id)
- `ix_xp_events_created_at` en xp_events(created_at)
- `ix_streak_records_activity_date` en streak_records(activity_date)
- `ix_tag_cooccurrences_weight` en tag_cooccurrences(weight)