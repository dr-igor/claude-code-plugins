import type { ResultOf, Settings } from 'claude-code'

import type { Diagnosis, SettingsSourceName } from '../types'

export type CheckVerdict = ResultOf['tool.check']

export type Host = {
  readSettings: (source?: SettingsSourceName) => Promise<Settings>
  readFile: (path: string) => Promise<string>
  checkTool: (tool: string, input: unknown) => Promise<CheckVerdict>
  readHistory: () => Promise<readonly Diagnosis[]>
  updateHistory: (change: (entries: Diagnosis[]) => Diagnosis[]) => Promise<void>
  notice: (id: string, text: string) => void
  toast: (text: string, timeoutMs: number) => void
  log: (text: string) => void
  debug: (text: string) => void
}

export type Session = { cwd: string; claudeDir?: string; host: Host }
