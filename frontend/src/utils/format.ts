export function formatResourceType(type: string): string {
  if (!type) return 'Unknown';
  // e.g. AWS::EC2::SecurityGroup -> SecurityGroup or AWS::S3::Bucket -> S3 Bucket
  const parts = type.split('::');
  if (parts.length >= 3) {
    return `${parts[1]} ${parts[2]}`;
  }
  return type;
}

export function truncateMiddle(str: string, maxLength: number = 32): string {
  if (!str || str.length <= maxLength) return str;
  const half = Math.floor((maxLength - 3) / 2);
  return `${str.slice(0, half)}...${str.slice(-half)}`;
}

export function formatPercent(val: number | null | undefined): string {
  if (val === null || val === undefined) return '—';
  return `${Math.round(val)}%`;
}
