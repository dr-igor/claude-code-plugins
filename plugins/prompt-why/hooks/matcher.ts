const PLAIN_NAMES = /^[\w|-]+$/

export function matcherCovers(matcher: string | undefined, tool: string): boolean {
  if (matcher === undefined || matcher === '' || matcher === '*') return true
  if (PLAIN_NAMES.test(matcher)) return matcher.split('|').includes(tool)
  return patternCovers(matcher, tool)
}

function patternCovers(pattern: string, tool: string): boolean {
  try {
    return new RegExp(`^(?:${pattern})$`).test(tool)
  } catch {
    return false
  }
}
