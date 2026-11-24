import { expect, mock, test } from 'claude-code/testing'
import type { On, Settings } from 'claude-code'

type Verdict = { decision: 'allow' | 'ask' | 'deny'; reason?: string; rule?: string; hook?: string }

type World = {
  verdict: Verdict
  settings?: Partial<Record<'user' | 'project' | 'local' | 'flag' | 'policy' | 'merged', Settings>>
  files?: Readonly<Record<string, string>>
  permissionRequestBehavior?: 'allow' | 'deny'
}

type Screen = { notices: string[]; toasts: string[]; transcript: string[]; checkedIds: string[] }

const SHELL_GUARD_HOOKS = JSON.stringify({
  hooks: {
    PreToolUse: [{ matcher: 'Bash', hooks: [{ type: 'command', command: 'shell-guard' }] }],
    PermissionRequest: [
      { matcher: 'Bash', hooks: [{ type: 'command', command: 'shell-guard permission-request' }] },
    ],
  },
})

const INSTALLED_PLUGINS = JSON.stringify({
  version: 2,
  plugins: { 'shell-guard@market': [{ scope: 'user', installPath: '/plugins/shell-guard' }] },
})

function buildWorld(on: On, world: World): string[] {
  return buildScreen(on, world).notices
}

function buildScreen(on: On, world: World): Screen {
  const screen: Screen = { notices: [], toasts: [], transcript: [], checkedIds: [] }
  mock.env(on, { HOME: '/home/tester' })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('command.register', () => ({ value: { command: 'prompt-why' } }))
  on('settings.read', (_, e) => ({ value: world.settings?.[e.source ?? 'merged'] ?? {} }))
  on('fs.read', (_, e) => {
    const text = world.files?.[e.path]
    return text === undefined ? { deny: `no such file: ${e.path}` } : { value: text }
  })
  on('ui.notice', (_, e) => {
    if (e.text !== undefined) screen.notices.push(e.text)
    return { value: undefined }
  })
  on('ui.toast', (_, e) => {
    screen.toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.log', (_, e) => {
    if (e.to === 'transcript') screen.transcript.push(e.text)
    return { value: undefined }
  })
  on('tool.check', (_, e) => {
    if (e.tool_use_id !== undefined) screen.checkedIds.push(e.tool_use_id)
    return world.verdict
  })
  on('classic.PermissionRequest', () =>
    world.permissionRequestBehavior === undefined
      ? {}
      : { decision: { behavior: world.permissionRequestBehavior } },
  )
  on('tool.call', () => ({ result: {} }))
  return screen
}

const PRESENTATION = { isFullscreen: false, columns: 120 } as const

test('an ask rule is traced to the settings file that holds it', async ($, on) => {
  const notices = buildWorld(on, {
    verdict: { decision: 'ask', rule: 'Bash(git push:*)', reason: 'Permission rule' },
    settings: { project: { permissions: { ask: ['Bash(git push:*)'] } } },
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Bash', command: 'git push origin main' })
  const { text } = await $.command.run({
    command: 'prompt-why',
    args: '',
    origin: { kind: 'composer' },
    presentation: PRESENTATION,
  })

  expect(notices.at(-1)).toBe(
    'why: rule Bash(git push:*) in ask list of project settings (.claude/settings.json) — Permission rule',
  )
  expect(text).toContain('Bash  git push origin main')
  expect(text).toContain('outcome: dialog shown')
})

test("a hook's ask lists the plugin hooks whose matcher covers the tool", async ($, on) => {
  const notices = buildWorld(on, {
    verdict: { decision: 'ask', hook: 'PreToolUse', reason: 'too complex to review' },
    settings: { merged: { enabledPlugins: { 'shell-guard@market': true } } },
    files: {
      '/home/tester/.claude/plugins/installed_plugins.json': INSTALLED_PLUGINS,
      '/plugins/shell-guard/hooks/hooks.json': SHELL_GUARD_HOOKS,
    },
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Bash', command: 'echo $(date)' })

  expect(notices.at(-1)).toBe(
    'why: PreToolUse hook from plugin shell-guard@market: shell-guard — too complex to review',
  )
})

test("an ask from Bash's own check alone is refused without a prompt", async ($, on) => {
  const notices = buildWorld(on, {
    verdict: { decision: 'ask', reason: 'unclassifiable' },
    permissionRequestBehavior: 'allow',
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const outcome = await $.tool.call({ tool: 'Bash', command: 'tr "a=b" x f' })
  const { text } = await $.command.run({
    command: 'prompt-why',
    args: '1',
    origin: { kind: 'composer' },
    presentation: PRESENTATION,
  })

  expect(outcome.deny ?? outcome.text).toContain("tripped Claude's builtin auto-allow refusal")
  expect(outcome.context ?? []).toEqual([
    'prompt-why: this Bash call needed permission (prompt-why refused it without prompting the user). ' +
      "Cause: no rule, hook or setting matched: Bash's own permission check. Claude Code's reason: unclassifiable",
  ])
  expect(notices.at(-1)).toBe(
    "refused without a prompt: no rule, hook or setting matched: Bash's own permission check — unclassifiable",
  )
  expect(text).toContain("outcome: refused by prompt-why (Bash's own check); no dialog")
})

test("an ask from another tool's own check still prompts", async ($, on) => {
  buildWorld(on, {
    verdict: { decision: 'ask', reason: 'outside the working directories' },
    permissionRequestBehavior: 'allow',
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const outcome = await $.tool.call({ tool: 'Read', file_path: '/etc/hosts' })

  expect(outcome.deny).toBeUndefined()
})

test('the explanation is toasted, since standard permission dialogs draw no plugin line', async ($, on) => {
  const screen = buildScreen(on, {
    verdict: { decision: 'ask', reason: 'outside the working directories' },
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Read', file_path: '/etc/hosts' })

  expect(new Set(screen.toasts)).toEqual(
    new Set([
      "why: no rule, hook or setting matched: Read's own permission check — outside the working directories",
    ]),
  )
})

const READ_ROW = { tool: 'Read', isRunning: false, isErrored: false, isInterrupted: false }

test("a prompted call's row carries the why line in the warning color", async ($, on) => {
  const screen = buildScreen(on, {
    verdict: { decision: 'ask', reason: 'outside the working directories' },
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Read', file_path: '/etc/hosts' })
  const [id = ''] = screen.checkedIds
  const row = await $.ui.mount({
    plugin: 'prompt-why',
    surface: 'terminal',
    component: 'ToolUse',
    requestId: id,
    props: { ...READ_ROW, tool_use_id: id, input: { file_path: '/etc/hosts' } },
  })
  const line = await row.find({ type: 'Text', text: /^why/ })

  expect({ text: line?.text, color: line?.props.color }).toEqual({
    text: "why: no rule, hook or setting matched: Read's own permission check — outside the working directories",
    color: 'warning',
  })
  expect(screen.transcript).toEqual([])
  await row.unmount()
})

test('a folded group lists a why line for each prompted call in it', async ($, on) => {
  const screen = buildScreen(on, {
    verdict: { decision: 'ask', reason: 'outside the working directories' },
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Read', file_path: '/etc/hosts' })
  await $.tool.call({ tool: 'Read', file_path: '/etc/shells' })
  const [hosts = '', shells = ''] = screen.checkedIds
  const group = await $.ui.mount({
    plugin: 'prompt-why',
    surface: 'terminal',
    component: 'ToolGroup',
    props: {
      isActive: false,
      isExpanded: false,
      calls: [
        { ...READ_ROW, tool_use_id: hosts, input: { file_path: '/etc/hosts' } },
        { ...READ_ROW, tool_use_id: 'unprompted', input: { file_path: 'README.md' } },
        { ...READ_ROW, tool_use_id: shells, input: { file_path: '/etc/shells' } },
      ],
    },
  })
  const lines = await group.findAll({ type: 'Text', text: /^why/ })

  expect(lines.map(line => line.text)).toEqual([
    "why (/etc/hosts): no rule, hook or setting matched: Read's own permission check — outside the working directories",
    "why (/etc/shells): no rule, hook or setting matched: Read's own permission check — outside the working directories",
  ])
  await group.unmount()
})

test('a row of a call that did not prompt is drawn as Claude Code draws it', async ($, on) => {
  buildScreen(on, { verdict: { decision: 'allow' } })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Read', file_path: 'README.md' })
  const row = await $.ui.mount({
    plugin: 'prompt-why',
    surface: 'terminal',
    component: 'ToolUse',
    props: { ...READ_ROW, tool_use_id: 'quiet', input: { file_path: 'README.md' } },
  })

  expect(await row.find({ text: /^why/ })).toBeUndefined()
  await row.unmount()
})

test("core's generic reason is left out of the line and kept in the report", async ($, on) => {
  const generic = "Claude requested permissions to use Bash, but you haven't granted it yet."
  const screen = buildScreen(on, {
    verdict: { decision: 'ask', rule: 'Bash(uname:*)', reason: generic },
    settings: { local: { permissions: { ask: ['Bash(uname:*)'] } } },
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Bash', command: 'uname -a' })
  const { text } = await $.command.run({
    command: 'prompt-why',
    args: '1',
    origin: { kind: 'composer' },
    presentation: PRESENTATION,
  })

  expect(screen.toasts.at(-1)).toBe(
    'why: rule Bash(uname:*) in ask list of local settings (.claude/settings.local.json)',
  )
  expect(text).toContain(`reason: ${generic}`)
})

test('a PermissionRequest hook that answers is reported as answering in place of a dialog', async ($, on) => {
  buildWorld(on, {
    verdict: { decision: 'ask', hook: 'PreToolUse', reason: 'too complex to review' },
    settings: { merged: { enabledPlugins: { 'shell-guard@market': true } } },
    files: {
      '/home/tester/.claude/plugins/installed_plugins.json': INSTALLED_PLUGINS,
      '/plugins/shell-guard/hooks/hooks.json': SHELL_GUARD_HOOKS,
    },
    permissionRequestBehavior: 'deny',
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Bash', command: 'echo $(date)' })
  const { text } = await $.command.run({
    command: 'prompt-why',
    args: '1',
    origin: { kind: 'composer' },
    presentation: PRESENTATION,
  })

  expect(text).toContain('a PermissionRequest hook answered deny; no dialog')
  expect(text).toContain('plugin shell-guard@market [matcher Bash]: shell-guard permission-request')
})

test("the model reads why the call needed permission after the call's result", async ($, on) => {
  const longReason = `/etc/hosts is outside. ${'Only files in the working directories. '.repeat(8)}`
  buildWorld(on, {
    verdict: { decision: 'ask', reason: longReason },
    permissionRequestBehavior: 'allow',
  })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const outcome = await $.tool.call({ tool: 'Read', file_path: '/etc/hosts' })

  expect(outcome.context).toEqual([
    'prompt-why: this Read call needed permission (a PermissionRequest hook answered allow; no dialog). ' +
      `Cause: no rule, hook or setting matched: Read's own permission check. Claude Code's reason: ${longReason}`,
  ])
})

test('a call that needed no permission carries no note for the model', async ($, on) => {
  buildWorld(on, { verdict: { decision: 'allow' } })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const outcome = await $.tool.call({ tool: 'Bash', command: 'ls' })

  expect(outcome.context).toBeUndefined()
})

test('an allowed call leaves no record', async ($, on) => {
  const notices = buildWorld(on, { verdict: { decision: 'allow' } })

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.tool.call({ tool: 'Bash', command: 'ls' })
  const { text } = await $.command.run({
    command: 'prompt-why',
    args: '',
    origin: { kind: 'composer' },
    presentation: PRESENTATION,
  })

  expect(notices).toEqual([])
  expect(text).toBe('No permission asks recorded this session.')
})
