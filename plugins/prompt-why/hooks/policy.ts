import type { Decider } from '../types'

export const BUILTIN_REFUSAL =
  "This tool call tripped Claude's builtin auto-allow refusal; the user will not be prompted; your intent can probably be achieved by different call that will not trip this check - feel free to try again."

const REFUSED_TOOLS: ReadonlySet<string> = new Set(['Bash'])

export const isRefusedWithoutPrompt = (tool: string, deciders: readonly Decider[]): boolean =>
  REFUSED_TOOLS.has(tool) && deciders.every(decider => decider.kind === 'tool-check')
