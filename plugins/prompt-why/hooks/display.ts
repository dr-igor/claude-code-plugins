import type { Host } from './host'

export const TOAST_MS = 15_000

export type Display = ReturnType<typeof createDisplay>

export function createDisplay(host: Host) {
  return { show, showUnattached }

  function show(id: string, text: string): void {
    attempt(`notice for ${id}`, () => host.notice(id, text))
    toast(text)
  }

  function showUnattached(text: string): void {
    toast(text)
    attempt('transcript line', () => host.log(text))
  }

  function toast(text: string): void {
    attempt('toast', () => host.toast(text, TOAST_MS))
  }

  function attempt(what: string, act: () => void): void {
    try {
      act()
    } catch (error) {
      host.debug(`${what} refused: ${String(error)}`)
    }
  }
}
