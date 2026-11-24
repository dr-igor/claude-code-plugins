import type { RuleSource, Verdict } from '../types'
import type { Host } from './host'
import { SETTINGS_SOURCES } from './settings-sources'
import { isRecord, stringsIn } from './shapes'

const RULE_LISTS: readonly Verdict[] = ['ask', 'deny', 'allow']

export async function findRuleSources(host: Host, rule: string): Promise<RuleSource[]> {
  const perSource = await Promise.all(
    SETTINGS_SOURCES.map(async source =>
      listsHolding(rule, (await host.readSettings(source))['permissions']).map(list => ({
        source,
        list,
      })),
    ),
  )
  return perSource.flat()
}

const listsHolding = (rule: string, permissions: unknown): Verdict[] =>
  isRecord(permissions)
    ? RULE_LISTS.filter(list => stringsIn(permissions[list]).includes(rule))
    : []
