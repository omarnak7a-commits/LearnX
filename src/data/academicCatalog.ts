/**
 * Academic reference catalog for the Student Profile / University &
 * Ranking system — Universities → Faculties → Departments, modelled as a
 * relational graph (id + foreign-key references) rather than opaque
 * strings baked into individual components, so every screen (onboarding,
 * profile, leaderboard filters, dashboard widgets) resolves the *same*
 * record from one source of truth. Faculty names intentionally reuse the
 * exact strings already used by the Course Management catalog
 * (`src/data/coursesMock.ts` — "Faculty of Engineering", "Faculty of
 * Science", department subjects like "Computer Science"/"Mathematics")
 * so a student's academic identity lines up with the courses they're
 * enrolled in instead of inventing a disconnected taxonomy.
 *
 * This is frontend-seed data (no live backend exists yet — see
 * `backend/README.md`), but it is shaped exactly the way the `BACKEND`
 * section of the spec describes: `university_id` / `faculty_id` /
 * `department_id` foreign keys, ready to be swapped for real API-fetched
 * rows without touching any UI code (every consumer goes through the
 * lookup helpers at the bottom of this file, never raw array indices).
 */

export interface University {
  id: string
  name: string
  shortName: string
  country: string
  city: string
}

export interface Faculty {
  id: string
  universityId: string
  name: string
  icon: string
}

export interface Department {
  id: string
  facultyId: string
  name: string
}

export interface AcademicYearOption {
  id: string
  label: string
  order: number
}

export interface SemesterOption {
  id: string
  label: string
  order: number
}

export const UNIVERSITIES: University[] = [
  { id: 'cairo-u', name: 'Cairo University', shortName: 'Cairo U', country: 'Egypt', city: 'Giza' },
  {
    id: 'ain-shams-u',
    name: 'Ain Shams University',
    shortName: 'ASU',
    country: 'Egypt',
    city: 'Cairo',
  },
  {
    id: 'alexandria-u',
    name: 'Alexandria University',
    shortName: 'Alex U',
    country: 'Egypt',
    city: 'Alexandria',
  },
  {
    id: 'auc',
    name: 'The American University in Cairo',
    shortName: 'AUC',
    country: 'Egypt',
    city: 'New Cairo',
  },
  {
    id: 'mansoura-u',
    name: 'Mansoura University',
    shortName: 'Mansoura U',
    country: 'Egypt',
    city: 'Mansoura',
  },
  {
    id: 'menoufia-u',
    name: 'Menoufia University',
    shortName: 'Menoufia U',
    country: 'Egypt',
    city: 'Shibin El Kom',
  },
  {
    id: 'imperial-college',
    name: 'Imperial College London',
    shortName: 'Imperial',
    country: 'United Kingdom',
    city: 'London',
  },
  {
    id: 'mit',
    name: 'Massachusetts Institute of Technology',
    shortName: 'MIT',
    country: 'United States',
    city: 'Cambridge',
  },
  {
    id: 'stanford',
    name: 'Stanford University',
    shortName: 'Stanford',
    country: 'United States',
    city: 'Stanford',
  },
  {
    id: 'u-toronto',
    name: 'University of Toronto',
    shortName: 'U of T',
    country: 'Canada',
    city: 'Toronto',
  },
  {
    id: 'nus',
    name: 'National University of Singapore',
    shortName: 'NUS',
    country: 'Singapore',
    city: 'Singapore',
  },
]

/** Faculty templates reused across universities — every university offers
 *  a realistic subset of these, generated below with per-university ids. */
const FACULTY_TEMPLATES: Array<{ key: string; name: string; icon: string; departments: string[] }> =
  [
    {
      key: 'engineering',
      name: 'Faculty of Engineering',
      icon: '⚙️',
      departments: [
        'Computer Engineering',
        'Electrical Engineering',
        'Mechanical Engineering',
        'Civil Engineering',
        'Biomedical Engineering',
      ],
    },
    {
      key: 'science',
      name: 'Faculty of Science',
      icon: '🔬',
      departments: ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'Geology'],
    },
    {
      key: 'computers-ai',
      name: 'Faculty of Computers & Artificial Intelligence',
      icon: '💻',
      departments: [
        'Computer Science',
        'Artificial Intelligence',
        'Information Systems',
        'Software Engineering',
        'Data Science',
      ],
    },
    {
      key: 'medicine',
      name: 'Faculty of Medicine',
      icon: '🩺',
      departments: ['General Medicine', 'Pharmacy', 'Dentistry', 'Nursing'],
    },
    {
      key: 'commerce',
      name: 'Faculty of Commerce & Business',
      icon: '📈',
      departments: ['Accounting', 'Business Administration', 'Economics', 'Finance'],
    },
    {
      key: 'arts',
      name: 'Faculty of Arts & Humanities',
      icon: '🎨',
      departments: ['English Literature', 'Psychology', 'Mass Communication', 'History'],
    },
  ]

/** Which faculty templates each university actually offers — every real
 *  university has a different mix, matching how the example in the spec
 *  ("Cairo University → Faculty of Engineering → Computer Engineering")
 *  behaves in practice. */
const UNIVERSITY_FACULTY_KEYS: Record<string, string[]> = {
  'cairo-u': ['engineering', 'science', 'computers-ai', 'medicine', 'commerce', 'arts'],
  'ain-shams-u': ['engineering', 'science', 'medicine', 'commerce', 'arts'],
  'alexandria-u': ['engineering', 'science', 'computers-ai', 'medicine'],
  auc: ['engineering', 'computers-ai', 'commerce', 'arts'],
  'mansoura-u': ['engineering', 'science', 'medicine'],
  'menoufia-u': ['engineering', 'science', 'computers-ai', 'commerce'],
  'imperial-college': ['engineering', 'science', 'computers-ai', 'medicine'],
  mit: ['engineering', 'science', 'computers-ai'],
  stanford: ['engineering', 'science', 'computers-ai', 'commerce'],
  'u-toronto': ['engineering', 'science', 'computers-ai', 'medicine', 'arts'],
  nus: ['engineering', 'science', 'computers-ai', 'commerce'],
}

export const FACULTIES: Faculty[] = []
export const DEPARTMENTS: Department[] = []

for (const university of UNIVERSITIES) {
  const keys = UNIVERSITY_FACULTY_KEYS[university.id] ?? []
  for (const key of keys) {
    const template = FACULTY_TEMPLATES.find((f) => f.key === key)
    if (!template) continue
    const facultyId = `${university.id}__${key}`
    FACULTIES.push({
      id: facultyId,
      universityId: university.id,
      name: template.name,
      icon: template.icon,
    })
    for (const deptName of template.departments) {
      DEPARTMENTS.push({
        id: `${facultyId}__${deptName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
        facultyId,
        name: deptName,
      })
    }
  }
}

export const ACADEMIC_YEARS: AcademicYearOption[] = [
  { id: 'year-1', label: 'First Year', order: 1 },
  { id: 'year-2', label: 'Second Year', order: 2 },
  { id: 'year-3', label: 'Third Year', order: 3 },
  { id: 'year-4', label: 'Fourth Year', order: 4 },
  { id: 'year-5', label: 'Fifth Year', order: 5 },
  { id: 'graduate', label: 'Graduate / Postgraduate', order: 6 },
]

export const SEMESTERS: SemesterOption[] = [
  { id: 'semester-1', label: 'Semester 1', order: 1 },
  { id: 'semester-2', label: 'Semester 2', order: 2 },
  { id: 'summer', label: 'Summer Term', order: 3 },
]

export const COUNTRIES: string[] = [
  'Egypt',
  'Saudi Arabia',
  'United Arab Emirates',
  'Jordan',
  'Morocco',
  'Tunisia',
  'United Kingdom',
  'United States',
  'Canada',
  'Germany',
  'France',
  'Singapore',
  'India',
  'Other',
]

export interface LanguageOption {
  id: string
  label: string
}

export const LANGUAGES: LanguageOption[] = [
  { id: 'en', label: 'English' },
  { id: 'ar', label: 'Arabic (العربية)' },
  { id: 'fr', label: 'French' },
  { id: 'es', label: 'Spanish' },
  { id: 'de', label: 'German' },
]

export const STUDY_GOAL_OPTIONS: string[] = [
  'Graduate with honors',
  'Master my core courses',
  'Prepare for postgraduate study',
  'Land an internship',
  'Improve my GPA',
  'Build strong study habits',
  'Learn faster with AI tools',
  'Compete on the leaderboard',
]

/* ─── Lookup helpers — every consumer resolves data through these instead
   of touching the arrays directly, so swapping in a real API later only
   means changing these functions. ─── */

export function getUniversity(id: string | null | undefined): University | undefined {
  if (!id) return undefined
  return UNIVERSITIES.find((u) => u.id === id)
}

export function getFaculty(id: string | null | undefined): Faculty | undefined {
  if (!id) return undefined
  return FACULTIES.find((f) => f.id === id)
}

export function getDepartment(id: string | null | undefined): Department | undefined {
  if (!id) return undefined
  return DEPARTMENTS.find((d) => d.id === id)
}

export function getFacultiesForUniversity(universityId: string | null | undefined): Faculty[] {
  if (!universityId) return []
  return FACULTIES.filter((f) => f.universityId === universityId)
}

export function getDepartmentsForFaculty(facultyId: string | null | undefined): Department[] {
  if (!facultyId) return []
  return DEPARTMENTS.filter((d) => d.facultyId === facultyId)
}

export function getAcademicYear(id: string | null | undefined): AcademicYearOption | undefined {
  if (!id) return undefined
  return ACADEMIC_YEARS.find((y) => y.id === id)
}

export function getSemester(id: string | null | undefined): SemesterOption | undefined {
  if (!id) return undefined
  return SEMESTERS.find((s) => s.id === id)
}
