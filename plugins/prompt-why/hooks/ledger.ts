import type { ResultOf } from 'claude-code'

import type { Decider, Diagnosis } from '../types'
import { decidersOf } from './deciders'
import { noticeLine, report, summarizeInput } from './describe'
import { findHookCandidates } from './hook-candidates'
import type { CheckVerdict, Session } from './host'
import { createDisplay, type Display } from './display'
import { isRefusedWithoutPrompt } from './policy'

const HISTORY_LIMIT = 50

export type AskedCall = {
  id: string
  tool: string
  input: unknown
  agentId?: string
  verdict: CheckVerdict
}

export type SeenPermissionRequest = {
  tool: string
  input: unknown
  permissionMode?: string
  behavior?: 'allow' | 'deny'
}

type Outcome = Pick<Diagnosis, 'permissionMode' | 'isPrompted' | 'requestAnswer'>

export function createLedger() {
  let session: Session | undefined
  let display: Display | undefined
  const askedIdByInput = new Map<string, string>()

  return {
    bindSession,
    recordAsk,
    recordClassifier,
    recordPermissionRequest,
    report: reportRecent,
  }

  function bindSession(bound: Session): void {
    session = bound
    display = createDisplay(bound.host)
  }

  function showLine(diagnosis: Diagnosis | undefined): void {
    if (diagnosis !== undefined) display?.show(diagnosis.id, noticeLine(diagnosis))
  }

  async function recordAsk(call: AskedCall): Promise<Diagnosis | undefined> {
    if (session === undefined) return undefined
    const deciders = await decidersOf(session, call.verdict, call.tool)
    const isRefused = isRefusedWithoutPrompt(call.tool, deciders)
    if (!isRefused) askedIdByInput.set(inputKey(call.tool, call.input), call.id)
    const diagnosis: Diagnosis = {
      id: call.id,
      at: Date.now(),
      tool: call.tool,
      input: summarizeInput(call.input),
      agentId: call.agentId,
      reason: call.verdict.reason,
      deciders,
      ...(isRefused ? { isRefused: true } : {}),
    }
    await append(session, diagnosis)
    showLine(diagnosis)
    return diagnosis
  }

  async function recordClassifier(id: string, verdict: ResultOf['tool.judge']): Promise<void> {
    if (session === undefined) return
    const classifier: Decider = {
      kind: 'classifier',
      decision: verdict.decision,
      reason: verdict.reason,
    }
    showLine(
      await amend(session, id, diagnosis => ({
        ...diagnosis,
        deciders: [classifier, ...diagnosis.deciders],
      })),
    )
  }

  async function recordPermissionRequest(seen: SeenPermissionRequest): Promise<void> {
    if (session === undefined) return
    const key = inputKey(seen.tool, seen.input)
    const id = askedIdByInput.get(key)
    askedIdByInput.delete(key)
    const outcome = await outcomeOf(session, seen)
    if (id === undefined) {
      display?.showUnattached(noticeLine(await recordUnseen(session, seen, outcome)))
      return
    }
    showLine(await amend(session, id, diagnosis => ({ ...diagnosis, ...outcome })))
  }

  async function reportRecent(count: number): Promise<string> {
    return session === undefined
      ? 'prompt-why has not bound to this session yet.'
      : report(await session.host.readHistory(), count)
  }
}

async function outcomeOf(session: Session, seen: SeenPermissionRequest): Promise<Outcome> {
  if (seen.behavior === undefined) return { permissionMode: seen.permissionMode, isPrompted: true }
  const candidates = await findHookCandidates(session, {
    event: 'PermissionRequest',
    tool: seen.tool,
  })
  return {
    permissionMode: seen.permissionMode,
    requestAnswer: { behavior: seen.behavior, candidates },
  }
}

async function recordUnseen(
  session: Session,
  seen: SeenPermissionRequest,
  outcome: Outcome,
): Promise<Diagnosis> {
  const verdict = await session.host.checkTool(seen.tool, seen.input)
  const isAsk = verdict.decision === 'ask'
  const diagnosis: Diagnosis = {
    id: `unseen-${Date.now()}`,
    at: Date.now(),
    tool: seen.tool,
    input: summarizeInput(seen.input),
    reason: isAsk ? verdict.reason : undefined,
    deciders: isAsk ? await decidersOf(session, verdict, seen.tool) : [{ kind: 'unseen' }],
    ...(isAsk ? { isRequeried: true } : {}),
    ...outcome,
  }
  await append(session, diagnosis)
  return diagnosis
}

async function append(session: Session, diagnosis: Diagnosis): Promise<void> {
  await session.host.updateHistory(entries => [...entries, diagnosis].slice(-HISTORY_LIMIT))
}

async function amend(
  session: Session,
  id: string,
  change: (diagnosis: Diagnosis) => Diagnosis,
): Promise<Diagnosis | undefined> {
  await session.host.updateHistory(entries =>
    entries.map(entry => (entry.id === id ? change(entry) : entry)),
  )
  return (await session.host.readHistory()).find(entry => entry.id === id)
}

const inputKey = (tool: string, input: unknown): string => `${tool}\u0000${JSON.stringify(input)}`
