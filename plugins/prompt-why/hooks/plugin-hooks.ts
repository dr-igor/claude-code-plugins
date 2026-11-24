import type { Host, Session } from './host'
import { isRecord, recordsIn, stringAt, type HooksConfig, type JsonRecord } from './shapes'

export async function pluginHooksConfigs({ host, cwd, claudeDir }: Session): Promise<HooksConfig[]> {
  const [enabled, installs] = await Promise.all([
    enabledPluginIds(host),
    installedPlugins(host, claudeDir),
  ])
  const configs = await Promise.all(
    enabled.map(async id => {
      const installPath = installPathFor(installs[id], cwd)
      return installPath === undefined
        ? undefined
        : { origin: `plugin ${id}`, hooks: await readPluginHooks(host, installPath) }
    }),
  )
  return configs.filter((config): config is HooksConfig => config !== undefined)
}

async function enabledPluginIds(host: Host): Promise<string[]> {
  const enabledPlugins = (await host.readSettings())['enabledPlugins']
  return isRecord(enabledPlugins)
    ? Object.entries(enabledPlugins)
        .filter(([, isEnabled]) => isEnabled === true)
        .map(([id]) => id)
    : []
}

async function installedPlugins(host: Host, claudeDir: string | undefined): Promise<JsonRecord> {
  const registry =
    claudeDir === undefined
      ? undefined
      : await readJson(host, `${claudeDir}/plugins/installed_plugins.json`)
  return isRecord(registry) && isRecord(registry['plugins']) ? registry['plugins'] : {}
}

function installPathFor(installs: unknown, cwd: string): string | undefined {
  const entries = recordsIn(installs)
  const chosen =
    entries.find(entry => entry['projectPath'] === cwd) ??
    entries.find(entry => entry['projectPath'] === undefined) ??
    entries[0]
  return chosen === undefined ? undefined : stringAt(chosen, 'installPath')
}

async function readPluginHooks(host: Host, installPath: string): Promise<unknown> {
  const file = await readJson(host, `${installPath}/hooks/hooks.json`)
  return isRecord(file) ? file['hooks'] : undefined
}

async function readJson(host: Host, path: string): Promise<unknown> {
  try {
    return JSON.parse(await host.readFile(path))
  } catch {
    return undefined
  }
}
