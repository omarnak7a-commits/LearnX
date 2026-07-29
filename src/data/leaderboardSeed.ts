import type { BadgeId, LeaderboardEntry } from '../types/profile'
import { UNIVERSITIES, FACULTIES, DEPARTMENTS, ACADEMIC_YEARS } from './academicCatalog'
import { hashString, pick, randomInt, seededRandom } from '../lib/profile/random'

/**
 * Deterministic seeded cohort of peer students for the Ranking System —
 * same posture as `src/lib/fileVault/seedLibrary.ts` (realistic demo data
 * generated once, not hand-typed one-off fixtures). Every entry resolves
 * real `universityId`/`facultyId`/`departmentId` foreign keys into
 * `academicCatalog.ts`, and real `courseIds` into `coursesMock.ts`, so
 * the leaderboard's filters (University/Faculty/Department/Academic
 * Year/Course) all operate on genuine relational data instead of loose
 * strings.
 *
 * Deterministic via a fixed seed — the same 48 students, XP, streaks and
 * badges are generated every session so the leaderboard doesn't reshuffle
 * on every reload, exactly like the File Vault's seeded demo documents.
 */

const FIRST_NAMES = [
  'Ahmed',
  'Mariam',
  'Youssef',
  'Nour',
  'Omar',
  'Salma',
  'Karim',
  'Layla',
  'Hassan',
  'Farida',
  'Amr',
  'Dina',
  'Mostafa',
  'Habiba',
  'Ziad',
  'Rana',
  'Adam',
  'Jana',
  'Sherif',
  'Malak',
  'Tarek',
  'Yasmin',
  'Khaled',
  'Nada',
  'Ibrahim',
  'Sara',
  'Mahmoud',
  'Aya',
  'Hussein',
  'Reem',
  'Ali',
  'Heba',
  'Marwan',
  'Lina',
  'Fady',
  'Menna',
  'Seif',
  'Rawan',
  'Hesham',
  'Noha',
  'Bassel',
  'Zeina',
  'Yehia',
  'Mona',
  'Wael',
  'Sandra',
  'Ehab',
  'Ola',
]

const LAST_NAMES = [
  'Hassan',
  'Mahmoud',
  'Ibrahim',
  'ElSayed',
  'Fathy',
  'Kamal',
  'Rashad',
  'Abdel Rahman',
  'Nassar',
  'Saleh',
  'Farouk',
  'Gaber',
  'Hosny',
  'Osman',
  'Zaki',
  'ElShamy',
  'Adel',
  'Fahmy',
  'Aziz',
  'Naguib',
  'Younis',
  'Sabry',
  'Nabil',
  'Aboul Fotouh',
  'Sabbagh',
  'Talaat',
  'Riad',
  'Shalaby',
]

const COURSE_IDS = ['cs201', 'math210', 'cs310', 'cs420', 'phys150', 'chem220', 'cs150-legacy']

const ALL_BADGES: BadgeId[] = [
  'top-10-student',
  'top-engineering-student',
  'perfect-quiz',
  '30-day-streak',
  'ai-explorer',
  'fast-learner',
  'course-master',
  'weekly-champion',
  'monthly-champion',
]

const SEED = 424242
const COHORT_SIZE = 48

function buildEntry(index: number): LeaderboardEntry {
  const rng = seededRandom(SEED + index * 7919)

  const university = pick(rng, UNIVERSITIES)
  const universityFaculties = FACULTIES.filter((f) => f.universityId === university.id)
  const faculty =
    universityFaculties.length > 0 ? pick(rng, universityFaculties) : pick(rng, FACULTIES)
  const facultyDepartments = DEPARTMENTS.filter((d) => d.facultyId === faculty.id)
  const department =
    facultyDepartments.length > 0 ? pick(rng, facultyDepartments) : pick(rng, DEPARTMENTS)
  const academicYear = pick(rng, ACADEMIC_YEARS)

  const firstName = pick(rng, FIRST_NAMES)
  const lastName = pick(rng, LAST_NAMES)

  const xp = randomInt(rng, 800, 24000)
  const weeklyXp = randomInt(rng, 40, 2400)
  const monthlyXp = Math.min(xp, weeklyXp * randomInt(rng, 3, 4) + randomInt(rng, 0, 900))
  const studyHours = randomInt(rng, 4, 180)
  const coursesCompleted = randomInt(rng, 0, 15)
  const streakDays = randomInt(rng, 0, 65)

  const courseCount = randomInt(rng, 1, 3)
  const courseIds = Array.from(
    new Set(Array.from({ length: courseCount }, () => pick(rng, COURSE_IDS)))
  )

  const badgeCount = randomInt(rng, 0, 4)
  const badges = Array.from(
    new Set(Array.from({ length: badgeCount }, () => pick(rng, ALL_BADGES)))
  )

  return {
    id: `peer-${index}`,
    isCurrentUser: false,
    fullName: `${firstName} ${lastName}`,
    avatarDataUrl: null,
    universityId: university.id,
    facultyId: faculty.id,
    departmentId: department.id,
    academicYearId: academicYear.id,
    courseIds,
    xp,
    weeklyXp,
    monthlyXp,
    studyHours,
    coursesCompleted,
    streakDays,
    badges,
    isFriend: hashString(`friend-${index}`) % 5 === 0, // ~20% of the cohort are "friends"
  }
}

let cachedCohort: LeaderboardEntry[] | null = null

/** The full seeded peer cohort (excludes the current user — that entry is
 *  merged in by `useProfile()` / the Rankings page from the live profile
 *  state so it always reflects the student's real, current stats). */
export function getSeededCohort(): LeaderboardEntry[] {
  if (!cachedCohort) {
    cachedCohort = Array.from({ length: COHORT_SIZE }, (_, i) => buildEntry(i))
  }
  return cachedCohort
}
