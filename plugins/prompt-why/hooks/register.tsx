import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import { modelNote, noticeLine } from './describe'
import { createLedger } from './ledger'
import { BUILTIN_REFUSAL } from './policy'

const DEFAULT_REPORT_COUNT = 5
const WHY_COLOR = 'warning'

const history = atom({ plugin: 'prompt-why', key: 'history' } as const, [], {
  shape: 'history-1',
})

export const register: Register = on => {
  const ledger = createLedger()

  on('session.start', async ($, e, next) => {
    const [configDir, home] = await Promise.all([
      $.env.get('CLAUDE_CONFIG_DIR'),
      $.env.get('HOME'),
    ])
    ledger.bindSession({
      cwd: e.cwd,
      claudeDir: configDir ?? (home === undefined ? undefined : `${home}/.claude`),
      host: {
        readSettings: source => $.settings.read({ source }),
        readFile: path => $.fs.read(path),
        checkTool: (tool, input) => $.tool.check({ tool, input }),
        readHistory: () => read($, history),
        updateHistory: async change => void (await update($, history, change)),
        notice: (id, text) => $.ui.notice(id, text),
        toast: (text, timeoutMs) => $.ui.toast(text, { timeoutMs }),
        log: text => $.ui.log(text),
        debug: text => $.ui.log(text, { to: 'debug' }),
      },
    })
    await $.command.register({
      name: 'prompt-why',
      description: 'Explain why recent permission prompts appeared',
      argumentHint: '[count]',
      immediate: true,
    })
    return next(e)
  })

  on('command.run', { command: 'prompt-why' }, async (_$, e) => ({
    text: await ledger.report(reportCount(e.args)),
  }))

  on('tool.check', async (_$, e, next) => {
    const verdict = await next(e)
    if (verdict.decision !== 'ask' || e.tool_use_id === undefined) return verdict
    const diagnosis = await ledger.recordAsk({
      id: e.tool_use_id,
      tool: e.tool,
      input: e.input,
      agentId: e.agentId,
      verdict,
    })
    return diagnosis?.isRefused ? { decision: 'deny', reason: BUILTIN_REFUSAL } : verdict
  }).catch((_$, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    const outcome = await next(e)
    if (outcome.deny !== undefined || e.tool_use_id === undefined) return outcome
    const diagnosis = (await read($, history)).find(entry => entry.id === e.tool_use_id)
    return diagnosis === undefined
      ? outcome
      : { ...outcome, context: [...(outcome.context ?? []), modelNote(diagnosis)] }
  }).catch((_$, e, next) => next(e))

  on('tool.judge', async (_$, e, next) => {
    const verdict = await next(e)
    await ledger.recordClassifier(e.tool_use_id, verdict)
    return verdict
  }).catch((_$, e, next) => next(e))

  on('classic.PermissionRequest', async (_$, e, next) => {
    const answer = await next(e)
    await ledger.recordPermissionRequest({
      tool: e.tool_name,
      input: e.tool_input,
      permissionMode: e.permission_mode,
      behavior: answer.decision?.behavior,
    })
    return answer
  }).catch((_$, e, next) => next(e))

  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    const diagnosis = (await read($, history)).find(entry => entry.id === e.props.tool_use_id)
    if (diagnosis === undefined) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="column">
        {await next(e)}
        <Text color={WHY_COLOR}>{noticeLine(diagnosis)}</Text>
      </Box>
    )
  }).catch((_$, e, next) => next(e))

  on('ui.render', { component: 'ToolGroup' }, async ($, e, next) => {
    if (e.props.isExpanded) return next(e)
    const ids = new Set(e.props.calls.flatMap(call => call.tool_use_id ?? []))
    const asked = (await read($, history)).filter(entry => ids.has(entry.id))
    if (asked.length === 0) return next(e)
    const { Box, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="column">
        {await next(e)}
        {asked.map(diagnosis => (
          <Text color={WHY_COLOR}>{noticeLine(diagnosis, { subject: diagnosis.input })}</Text>
        ))}
      </Box>
    )
  }).catch((_$, e, next) => next(e))
}

function reportCount(args: string): number {
  const requested = Number.parseInt(args.trim(), 10)
  return Number.isInteger(requested) && requested > 0 ? requested : DEFAULT_REPORT_COUNT
}
