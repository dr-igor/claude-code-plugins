import type { Decider } from '../types'
import { findHookCandidates } from './hook-candidates'
import type { CheckVerdict, Session } from './host'
import { findRuleSources } from './rule-sources'

export async function decidersOf(
  session: Session,
  verdict: CheckVerdict,
  tool: string,
): Promise<Decider[]> {
  const found = await Promise.all([
    pluginCheckDecider(verdict),
    hookDecider(session, verdict, tool),
    ruleDecider(session, verdict),
    settingDecider(verdict),
    ceilingDecider(verdict),
  ])
  const deciders = found.filter((decider): decider is Decider => decider !== undefined)
  return deciders.length > 0 ? deciders : [{ kind: 'tool-check' }]
}

const pluginCheckDecider = (verdict: CheckVerdict): Decider | undefined =>
  verdict.plugin === undefined ? undefined : { kind: 'plugin-check', plugin: verdict.plugin }

async function hookDecider(
  session: Session,
  verdict: CheckVerdict,
  tool: string,
): Promise<Decider | undefined> {
  if (verdict.hook === undefined) return undefined
  const candidates = await findHookCandidates(session, { event: verdict.hook, tool })
  return { kind: 'hook', event: verdict.hook, candidates }
}

async function ruleDecider(
  session: Session,
  verdict: CheckVerdict,
): Promise<Decider | undefined> {
  if (verdict.rule === undefined) return undefined
  return {
    kind: 'rule',
    rule: verdict.rule,
    sources: await findRuleSources(session.host, verdict.rule),
  }
}

const settingDecider = (verdict: CheckVerdict): Decider | undefined =>
  verdict.setting === undefined ? undefined : { kind: 'setting', key: verdict.setting }

const ceilingDecider = (verdict: CheckVerdict): Decider | undefined =>
  verdict.ceiling === 'ask' ? { kind: 'ceiling', ceiling: verdict.ceiling } : undefined
