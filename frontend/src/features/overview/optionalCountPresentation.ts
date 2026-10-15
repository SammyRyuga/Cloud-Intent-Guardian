export function getOptionalCountPresentation(count: number | null, enabled?: boolean) {
  if (count !== null) return { label: String(count), showLink: true };
  if (enabled) return { label: 'Unavailable', showLink: true };
  return { label: 'Not enabled', showLink: false };
}
