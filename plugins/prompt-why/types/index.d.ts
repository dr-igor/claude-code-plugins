export type SettingsSourceName = 'user' | 'project' | 'local' | 'flag' | 'policy'

export type Verdict = 'allow' | 'ask' | 'deny'

export type RuleSource = { source: SettingsSourceName; list: Verdict }

export type HookCandidate = { origin: string; matcher: string; handler: string }

export type Decider =
  | { kind: 'classifier'; decision: Verdict; reason?: string }
  | { kind: 'plugin-check'; plugin: string }
  | { kind: 'hook'; event: string; candidates: readonly HookCandidate[] }
  | { kind: 'rule'; rule: string; sources: readonly RuleSource[] }
  | { kind: 'setting'; key: string }
  | { kind: 'ceiling'; ceiling: Verdict }
  | { kind: 'tool-check' }
  | { kind: 'unseen' }

export type PermissionRequestAnswer = {
  behavior: 'allow' | 'deny'
  candidates: readonly HookCandidate[]
}

export type Diagnosis = {
  id: string
  at: number
  tool: string
  input: string
  agentId?: string
  reason?: string
  deciders: readonly Decider[]
  isRequeried?: true
  permissionMode?: string
  isPrompted?: true
  isRefused?: true
  requestAnswer?: PermissionRequestAnswer
}

declare module 'claude-code' {
  interface PluginState {
    'prompt-why': { history: Shaped<Diagnosis[]> }
  }
}
