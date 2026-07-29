export type BadgeToneMap<K extends string> = Record<
  K,
  'primary' | 'accent' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'
>
