export type JsonRecord = Readonly<Record<string, unknown>>

export type HooksConfig = { origin: string; hooks: unknown }

export const isRecord = (value: unknown): value is JsonRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

export const stringsIn = (value: unknown): readonly string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []

export const recordsIn = (value: unknown): readonly JsonRecord[] =>
  Array.isArray(value) ? value.filter(isRecord) : []

export const stringAt = (record: JsonRecord, key: string): string | undefined => {
  const value = record[key]
  return typeof value === 'string' ? value : undefined
}
