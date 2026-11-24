import type { SettingsSourceName } from '../types'

export const SETTINGS_SOURCES: readonly SettingsSourceName[] = [
  'policy',
  'flag',
  'local',
  'project',
  'user',
]

export const SOURCE_LABELS: Readonly<Record<SettingsSourceName, string>> = {
  policy: 'managed settings',
  flag: '--settings flag',
  local: 'local settings (.claude/settings.local.json)',
  project: 'project settings (.claude/settings.json)',
  user: 'user settings (~/.claude/settings.json)',
}
