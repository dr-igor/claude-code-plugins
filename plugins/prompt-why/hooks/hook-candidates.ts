import type { HookCandidate } from '../types'
import type { Host, Session } from './host'
import { matcherCovers } from './matcher'
import { pluginHooksConfigs } from './plugin-hooks'
import { SETTINGS_SOURCES, SOURCE_LABELS } from './settings-sources'
import { isRecord, recordsIn, stringAt, type HooksConfig, type JsonRecord } from './shapes'

export type HookQuery = { event: string; tool: string }

export async function findHookCandidates(
  session: Session,
  query: HookQuery,
): Promise<HookCandidate[]> {
  const [fromSettings, fromPlugins] = await Promise.all([
    settingsHooksConfigs(session.host),
    pluginHooksConfigs(session),
  ])
  return [...fromSettings, ...fromPlugins].flatMap(config => candidatesIn(config, query))
}

async function settingsHooksConfigs(host: Host): Promise<HooksConfig[]> {
  return Promise.all(
    SETTINGS_SOURCES.map(async source => ({
      origin: SOURCE_LABELS[source],
      hooks: (await host.readSettings(source))['hooks'],
    })),
  )
}

function candidatesIn({ origin, hooks }: HooksConfig, { event, tool }: HookQuery): HookCandidate[] {
  if (!isRecord(hooks)) return []
  return recordsIn(hooks[event])
    .filter(group => matcherCovers(stringAt(group, 'matcher'), tool))
    .flatMap(group =>
      recordsIn(group['hooks']).map(handler => ({
        origin,
        matcher: stringAt(group, 'matcher') || '*',
        handler: describeHandler(handler),
      })),
    )
}

function describeHandler(handler: JsonRecord): string {
  const type = stringAt(handler, 'type')
  switch (type) {
    case 'command':
      return stringAt(handler, 'command') ?? 'command'
    case 'http':
      return stringAt(handler, 'url') ?? 'http'
    case 'prompt':
    case 'agent':
      return `${type}: ${stringAt(handler, 'prompt') ?? ''}`
    case 'mcp_tool':
      return `mcp_tool ${stringAt(handler, 'server')}/${stringAt(handler, 'tool')}`
    default:
      return JSON.stringify(handler)
  }
}
