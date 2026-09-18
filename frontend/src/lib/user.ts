export function initials(nameOrEmail: string | undefined | null): string {
  if (!nameOrEmail) return '?'
  const namePart = nameOrEmail.includes('@') ? nameOrEmail.split('@')[0] : nameOrEmail
  const words = namePart.replace(/[._-]+/g, ' ').trim().split(/\s+/)
  const chars = words.length > 1 ? [words[0][0], words[1][0]] : [namePart[0], namePart[1] ?? '']
  return chars.join('').toUpperCase()
}

export function firstName(nameOrEmail: string | undefined | null): string {
  if (!nameOrEmail) return ''
  const namePart = nameOrEmail.includes('@') ? nameOrEmail.split('@')[0] : nameOrEmail
  const first = namePart.replace(/[._-]+/g, ' ').trim().split(/\s+/)[0] ?? ''
  return first.charAt(0).toUpperCase() + first.slice(1)
}
