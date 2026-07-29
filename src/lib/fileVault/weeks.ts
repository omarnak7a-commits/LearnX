/**
 * ISO-week helpers used to automatically group uploaded files into the
 * "Week 1 / Week 2 / ..." timeline the spec requires. Weeks are computed
 * from real upload timestamps, not hardcoded — uploading a file today
 * groups it into the current week immediately. The specific "Week N"
 * *number* each calendar week is assigned depends on the full set of
 * weeks present in the library (earliest = Week 1), so that lives in
 * `deriveWeekGroups` in `context/FileVaultContext.tsx` rather than here;
 * this module only provides the calendar-week key/date-range primitives.
 */

function startOfWeek(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay() // 0 = Sunday
  const diff = (day + 6) % 7 // days since Monday
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - diff)
  return d
}

export function weekKeyFor(date: Date): string {
  const start = startOfWeek(date)
  return start.toISOString().slice(0, 10)
}

const WEEKDAY_MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/** Human date-range label for a calendar week key, e.g. "Jul 21 – Jul 27". */
export function weekLabelFor(date: Date): string {
  const start = startOfWeek(date)
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  const startLabel = `${WEEKDAY_MONTHS[start.getMonth()]} ${start.getDate()}`
  const endLabel = `${WEEKDAY_MONTHS[end.getMonth()]} ${end.getDate()}`
  return `${startLabel} – ${endLabel}`
}

export function isCurrentCalendarWeek(weekKey: string): boolean {
  return weekKey === weekKeyFor(new Date())
}

/** Sort key: most recent week first. */
export function weekSortKey(weekKey: string): number {
  return -new Date(weekKey).getTime()
}
