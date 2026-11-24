import type { Decider, Diagnosis, HookCandidate, RuleSource } from '../types'
import { SOURCE_LABELS } from './settings-sources'
import { isRecord, stringAt } from './shapes'

const NOTICE_LIMIT = 220
const HANDLER_LIMIT = 80
const INPUT_LIMIT = 120
const SALIENT_INPUT_KEYS = ['command', 'file_path', 'notebook_path', 'path', 'url', 'pattern']
const GENERIC_REASON = /^Claude requested permissions to .*, but you haven't granted it yet\.?$/

export function summarizeInput(input: unknown): string {
  const record = isRecord(input) ? input : {}
  const salient = SALIENT_INPUT_KEYS.map(key => stringAt(record, key)).find(
    value => value !== undefined,
  )
  return clip(salient ?? JSON.stringify(input) ?? '', INPUT_LIMIT)
}

export function noticeLine(diagnosis: Diagnosis, { subject }: { subject?: string } = {}): string {
  const [primary, ...others] = diagnosis.deciders
  const verb = diagnosis.isRefused ? 'refused without a prompt' : 'why'
  const label = subject === undefined ? verb : `${verb} (${subject})`
  const cause = primary === undefined ? 'unknown' : describeDecider(primary, diagnosis.tool)
  const more = others.length > 0 ? ` (+${others.length} more, /prompt-why)` : ''
  const reason = isInformative(diagnosis.reason) ? ` — ${diagnosis.reason}` : ''
  return clip(`${label}: ${cause}${more}${reason}`, NOTICE_LIMIT)
}

export function modelNote(diagnosis: Diagnosis): string {
  const causes = diagnosis.deciders.map(decider => describeDecider(decider, diagnosis.tool))
  const reason = isInformative(diagnosis.reason) ? ` Claude Code's reason: ${diagnosis.reason}` : ''
  return [
    `prompt-why: this ${diagnosis.tool} call needed permission (${briefOutcome(diagnosis)}).`,
    `Cause: ${causes.join('; ')}.${reason}`,
  ].join(' ')
}

function briefOutcome(diagnosis: Diagnosis): string {
  const answer = diagnosis.requestAnswer
  if (answer !== undefined) return `a PermissionRequest hook answered ${answer.behavior}; no dialog`
  if (diagnosis.isRefused) return 'prompt-why refused it without prompting the user'
  return diagnosis.isPrompted ? 'the user was shown a permission dialog' : 'a permission ask was raised'
}

const isInformative = (reason: string | undefined): reason is string =>
  reason !== undefined && !GENERIC_REASON.test(reason.trim())

export function report(history: readonly Diagnosis[], count: number): string {
  const recent = history.slice(-count).reverse()
  return recent.length === 0
    ? 'No permission asks recorded this session.'
    : recent.map(describeDiagnosis).join('\n\n')
}

function describeDiagnosis(diagnosis: Diagnosis): string {
  const agent = diagnosis.agentId === undefined ? '' : `  (agent ${diagnosis.agentId})`
  return [
    `${clockTime(diagnosis.at)}  ${diagnosis.tool}  ${diagnosis.input}${agent}`,
    `  outcome: ${describeOutcome(diagnosis)}`,
    ...(diagnosis.reason === undefined ? [] : [`  reason: ${diagnosis.reason}`]),
    ...diagnosis.deciders.flatMap(decider => detailLines(decider, diagnosis.tool)),
    ...(diagnosis.isRequeried
      ? ['  (asked again after the prompt appeared; PreToolUse hooks were not consulted)']
      : []),
  ].join('\n')
}

function describeOutcome(diagnosis: Diagnosis): string {
  const answer = diagnosis.requestAnswer
  if (answer !== undefined) {
    return [
      `a PermissionRequest hook answered ${answer.behavior}; no dialog`,
      ...candidateLines(answer.candidates),
    ].join('\n')
  }
  if (diagnosis.isRefused) return "refused by prompt-why (Bash's own check); no dialog"
  if (diagnosis.isPrompted) return `dialog shown (mode: ${diagnosis.permissionMode ?? 'unknown'})`
  return 'no dialog seen (settled by the classifier or a hook above this plugin, or still pending)'
}

function detailLines(decider: Decider, tool: string): string[] {
  const headline = `  • ${describeDecider(decider, tool)}`
  return decider.kind === 'hook' ? [headline, ...candidateLines(decider.candidates)] : [headline]
}

const candidateLines = (candidates: readonly HookCandidate[]): string[] =>
  candidates.map(
    candidate => `      ${candidate.origin} [matcher ${candidate.matcher}]: ${candidate.handler}`,
  )

function describeDecider(decider: Decider, tool: string): string {
  switch (decider.kind) {
    case 'classifier':
      return decider.decision === 'ask'
        ? 'auto-mode classifier gave no verdict'
        : `auto-mode classifier said ${decider.decision}`
    case 'plugin-check':
      return `tool.check hook of plugin ${decider.plugin}`
    case 'hook':
      return `${decider.event} hook ${describeCandidates(decider.candidates)}`
    case 'rule':
      return describeRule(decider.rule, decider.sources)
    case 'setting':
      return `setting ${decider.key}`
    case 'ceiling':
      return `organization ceiling (${decider.ceiling})`
    case 'tool-check':
      return `no rule, hook or setting matched: ${tool}'s own permission check`
    case 'unseen':
      return 'no ask reached prompt-why: decided by a plugin above it, or outside the tool path'
  }
}

function describeCandidates(candidates: readonly HookCandidate[]): string {
  const [only] = candidates
  if (only === undefined) return "(none found in settings or installed plugins' hooks.json)"
  if (candidates.length === 1) return `from ${only.origin}: ${clip(only.handler, HANDLER_LIMIT)}`
  const origins = [...new Set(candidates.map(candidate => candidate.origin))]
  return `from one of ${candidates.length} candidates: ${origins.join(', ')}`
}

function describeRule(rule: string, sources: readonly RuleSource[]): string {
  if (sources.length === 0) {
    return `rule ${rule} (in no settings file: a CLI flag, a rule added this session, or a plugin)`
  }
  const places = sources.map(({ source, list }) => `${list} list of ${SOURCE_LABELS[source]}`)
  return `rule ${rule} in ${places.join('; ')}`
}

const clockTime = (at: number): string => new Date(at).toTimeString().slice(0, 8)

function clip(text: string, limit: number): string {
  const oneLine = text.replace(/\s+/g, ' ').trim()
  return oneLine.length > limit ? `${oneLine.slice(0, limit - 1)}…` : oneLine
}
