import type {
  Chapter,
  ChatMessage,
  Flashcard,
  MindMapNode,
  PipelineStage,
  QuizQuestion,
  SilenceSegment,
  SummaryContent,
  TranscriptSegment,
  VideoLecture,
} from '../types/video'

/**
 * Simulated output of the AI Video Intelligence pipeline.
 *
 * In production this data is produced by the pipeline described in
 * `backend/README.md` (Whisper/WhisperX transcription, Silero VAD /
 * pyannote diarization, FFmpeg trimming, embeddings + RAG, etc). Here it is
 * hand-authored so the full frontend experience — upload, processing,
 * chapters, transcript, summaries, flashcards, quiz, mind map, chat, and
 * the silence-removal comparison — can be built and demonstrated without a
 * live inference backend.
 */

export const PIPELINE_STAGE_DEFS: Array<{
  id: PipelineStage['id']
  label: string
  description: string
}> = [
  { id: 'upload', label: 'Video Upload', description: 'Receiving and storing the file' },
  { id: 'virus-scan', label: 'Virus Scan', description: 'Scanning file for threats' },
  { id: 'metadata', label: 'Metadata Extraction', description: 'Reading resolution, codec, duration' },
  { id: 'audio-extraction', label: 'Audio Extraction', description: 'Extracting the audio track' },
  { id: 'speech-detection', label: 'Speech Detection', description: 'Locating spoken segments' },
  { id: 'vad', label: 'Voice Activity Detection', description: 'Silero VAD pass over the waveform' },
  { id: 'diarization', label: 'Speaker Diarization', description: 'Separating speakers' },
  { id: 'silence-detection', label: 'Silence Detection', description: 'Classifying pauses vs. dead air' },
  { id: 'scene-detection', label: 'Scene Detection', description: 'Detecting slide/scene changes' },
  { id: 'ocr', label: 'OCR & Subtitle Detection', description: 'Reading on-screen slide text' },
  { id: 'transcription', label: 'Speech Recognition', description: 'Whisper transcription pass' },
  { id: 'topic-detection', label: 'Topic Detection', description: 'Clustering the transcript by topic' },
  { id: 'chapter-detection', label: 'Chapter Detection', description: 'Building the chapter timeline' },
  { id: 'concept-extraction', label: 'Concept Extraction', description: 'Pulling terms, formulas, definitions' },
  { id: 'summary', label: 'Summary Generation', description: 'Writing multi-level summaries' },
  { id: 'flashcards', label: 'Flashcards', description: 'Generating spaced-repetition cards' },
  { id: 'quiz', label: 'Quiz Generation', description: 'Building practice questions' },
  { id: 'mindmap', label: 'Mind Map', description: 'Mapping concept relationships' },
  { id: 'notes', label: 'Study Notes & Revision Sheet', description: 'Compiling the revision sheet' },
  { id: 'workspace-ready', label: 'AI Workspace', description: 'Finalizing the interactive workspace' },
]

function buildPipeline(doneThrough: number, activeProgress?: number): PipelineStage[] {
  return PIPELINE_STAGE_DEFS.map((def, i) => {
    if (i < doneThrough) return { ...def, status: 'done', durationMs: 800 + i * 130 }
    if (i === doneThrough && activeProgress !== undefined) {
      return { ...def, status: 'active', progress: activeProgress }
    }
    return { ...def, status: 'pending' }
  })
}

/* ─── Lecture 1: fully processed — "Classical Mechanics: Rotational Dynamics" ─── */

const chapters1: Chapter[] = [
  {
    id: 'c1',
    index: 1,
    title: 'Recap & Learning Objectives',
    startSec: 0,
    endSec: 210,
    difficulty: 'easy',
    confidence: 0.97,
    examImportance: 40,
    estimatedStudyMinutes: 6,
    keyConcepts: [{ term: 'Angular velocity', definition: 'Rate of change of angular position, ω = dθ/dt' }],
    formulas: ['ω = dθ/dt'],
    examTips: ['Rarely asked alone — usually combined with torque questions.'],
  },
  {
    id: 'c2',
    index: 2,
    title: 'Torque and Moment of Inertia',
    startSec: 210,
    endSec: 690,
    difficulty: 'medium',
    confidence: 0.94,
    examImportance: 88,
    estimatedStudyMinutes: 18,
    keyConcepts: [
      { term: 'Torque', definition: 'Rotational analogue of force, τ = r × F' },
      { term: 'Moment of inertia', definition: 'Rotational analogue of mass, resistance to angular acceleration' },
    ],
    formulas: ['τ = Iα', 'I = Σ m r²'],
    examTips: ['Expect a numeric problem combining τ = Iα with a compound object.'],
  },
  {
    id: 'c3',
    index: 3,
    title: 'Worked Example: Compound Pulley System',
    startSec: 690,
    endSec: 1080,
    difficulty: 'hard',
    confidence: 0.91,
    examImportance: 95,
    estimatedStudyMinutes: 25,
    keyConcepts: [{ term: 'Parallel axis theorem', definition: 'I = I_cm + Md², relates inertia about any axis to the center-of-mass axis' }],
    formulas: ['I = I_cm + Md²', 'ΣΤ = Iα'],
    examTips: ['This exact worked example appeared (with different numbers) on last year\u2019s midterm.'],
  },
  {
    id: 'c4',
    index: 4,
    title: 'Rotational Kinetic Energy',
    startSec: 1080,
    endSec: 1380,
    difficulty: 'medium',
    confidence: 0.95,
    examImportance: 72,
    estimatedStudyMinutes: 14,
    keyConcepts: [{ term: 'Rotational KE', definition: 'Kinetic energy stored in rotation, KE = ½Iω²' }],
    formulas: ['KE_rot = ½ I ω²'],
    examTips: ['Often paired with energy conservation across an incline.'],
  },
  {
    id: 'c5',
    index: 5,
    title: 'Q&A and Common Mistakes',
    startSec: 1380,
    endSec: 1560,
    difficulty: 'easy',
    confidence: 0.89,
    examImportance: 55,
    estimatedStudyMinutes: 8,
    keyConcepts: [],
    formulas: [],
    examTips: ['Common mistake: forgetting to convert RPM to rad/s before using ω.'],
  },
]

const silence1: SilenceSegment[] = [
  { id: 's1', startSec: 0, endSec: 18, reason: 'setup-time', removed: true, confidence: 0.96 },
  { id: 's2', startSec: 96, endSec: 104, reason: 'meaningful-pause', removed: false, confidence: 0.81 },
  { id: 's3', startSec: 231, endSec: 271, reason: 'dead-air', removed: true, confidence: 0.92 },
  { id: 's4', startSec: 402, endSec: 409, reason: 'meaningful-pause', removed: false, confidence: 0.77 },
  { id: 's5', startSec: 540, endSec: 588, reason: 'waiting', removed: true, confidence: 0.9 },
  { id: 's6', startSec: 715, endSec: 719, reason: 'meaningful-pause', removed: false, confidence: 0.72 },
  { id: 's7', startSec: 940, endSec: 998, reason: 'idle-moment', removed: true, confidence: 0.88 },
  { id: 's8', startSec: 1180, endSec: 1226, reason: 'repeated-pause', removed: true, confidence: 0.85 },
  { id: 's9', startSec: 1400, endSec: 1408, reason: 'meaningful-pause', removed: false, confidence: 0.74 },
  { id: 's10', startSec: 1500, endSec: 1560, reason: 'dead-air', removed: true, confidence: 0.93 },
]

const removedSeconds1 = silence1.filter((s) => s.removed).reduce((sum, s) => sum + (s.endSec - s.startSec), 0)
const originalDuration1 = 1560
const optimizedDuration1 = originalDuration1 - removedSeconds1

const transcript1: TranscriptSegment[] = [
  { id: 't1', startSec: 18, endSec: 45, speaker: 'Dr. Novak', chapterId: 'c1', text: "Alright, let's pick up from last week. We covered linear kinematics — position, velocity, acceleration. Today we make the jump to rotation." },
  { id: 't2', startSec: 45, endSec: 96, speaker: 'Dr. Novak', chapterId: 'c1', text: "Everything you know about linear motion has a rotational twin. Position becomes angular position theta, velocity becomes angular velocity omega, and acceleration becomes angular acceleration alpha." },
  { id: 't3', startSec: 104, endSec: 165, speaker: 'Dr. Novak', chapterId: 'c1', text: "By the end of today you should be able to compute torque for a rigid body, find its moment of inertia, and connect that to rotational kinetic energy. That's the whole roadmap." },
  { id: 't4', startSec: 165, endSec: 210, speaker: 'Dr. Novak', chapterId: 'c1', text: 'Quick show of hands — who remembers the definition of torque from high school physics? Good, most of you. We\u2019ll formalize it properly now.' },
  { id: 't5', startSec: 271, endSec: 330, speaker: 'Dr. Novak', chapterId: 'c2', text: 'Torque is the rotational analogue of force. Mathematically, tau equals r cross F — the position vector from the pivot, crossed with the applied force.' },
  { id: 't6', startSec: 330, endSec: 402, speaker: 'Dr. Novak', chapterId: 'c2', text: "Notice it's a cross product, so direction matters enormously. Push at the very edge of a door and it swings easily. Push near the hinge and almost nothing happens, even with the same force." },
  { id: 't7', startSec: 409, endSec: 470, speaker: 'Dr. Novak', chapterId: 'c2', text: 'Now the second half of the puzzle: moment of inertia, I. It plays the same role mass plays in F equals ma. Newton\u2019s second law becomes tau equals I alpha.' },
  { id: 't8', startSec: 470, endSec: 540, speaker: 'Dr. Novak', chapterId: 'c2', text: 'For a point mass at radius r, I is simply m r squared. For extended objects we sum — or integrate — over every little mass element.' },
  { id: 't9', startSec: 588, endSec: 650, speaker: 'Dr. Novak', chapterId: 'c2', text: 'This is exactly why a figure skater spins faster pulling their arms in — they\u2019re reducing r, which reduces I, and since angular momentum is conserved, omega has to go up.' },
  { id: 't10', startSec: 650, endSec: 690, speaker: 'Dr. Novak', chapterId: 'c2', text: "We'll come back to angular momentum properly next week — for now just remember I depends on how mass is distributed, not just how much mass there is." },
  { id: 't11', startSec: 719, endSec: 790, speaker: 'Dr. Novak', chapterId: 'c3', text: "Let's work a full example. A pulley system: two masses connected over a disk-shaped pulley that actually has mass, so it also resists angular acceleration." },
  { id: 't12', startSec: 790, endSec: 860, speaker: 'Dr. Novak', chapterId: 'c3', text: 'First step — always draw the free body diagram for every rotating and translating piece separately. This is where most students lose points, they skip this.' },
  { id: 't13', startSec: 860, endSec: 940, speaker: 'Dr. Novak', chapterId: 'c3', text: 'For the pulley itself we need its moment of inertia about the axle. Since it\u2019s not rotating about its center of mass in the usual simple sense here, we use the parallel axis theorem: I equals I center of mass plus M d squared.' },
  { id: 't14', startSec: 998, endSec: 1070, speaker: 'Dr. Novak', chapterId: 'c3', text: 'Combining the three equations — Newton\u2019s second law for each hanging mass, and torque equals I alpha for the pulley — gives us three equations, three unknowns. Completely solvable.' },
  { id: 't15', startSec: 1070, endSec: 1080, speaker: 'Dr. Novak', chapterId: 'c3', text: 'This exact setup, just with different numbers, is a very safe bet for your midterm.' },
  { id: 't16', startSec: 1226, endSec: 1290, speaker: 'Dr. Novak', chapterId: 'c4', text: 'Rotational kinetic energy: one half I omega squared. It looks just like the linear version with mass swapped for I and velocity swapped for omega.' },
  { id: 't17', startSec: 1290, endSec: 1380, speaker: 'Dr. Novak', chapterId: 'c4', text: 'For a rolling object — say a solid cylinder rolling down a ramp without slipping — total kinetic energy is translational plus rotational. This is the classic trap: forgetting the rotational term costs you half your energy budget.' },
  { id: 't18', startSec: 1408, endSec: 1470, speaker: 'Dr. Novak', chapterId: 'c5', text: 'Common mistake number one: forgetting to convert RPM to radians per second before plugging into any of today\u2019s formulas. Always convert first.' },
  { id: 't19', startSec: 1470, endSec: 1500, speaker: 'Dr. Novak', chapterId: 'c5', text: 'Common mistake number two: using the wrong moment-of-inertia formula for the shape. Always double-check whether it\u2019s a solid disk, a hoop, or a sphere — the coefficient changes completely.' },
]

const summaries1: SummaryContent[] = [
  { level: 'quick', label: 'Quick Summary', points: [
    'Introduces rotational analogues of linear motion: θ, ω, α.',
    'Defines torque (τ = r × F) and moment of inertia (I).',
    'Works a full pulley example using τ = Iα and the parallel axis theorem.',
    'Covers rotational kinetic energy and rolling-without-slipping.',
  ] },
  { level: 'detailed', label: 'Detailed Summary', points: [
    'Rotational quantities (θ, ω, α) are direct analogues of linear position, velocity, and acceleration.',
    'Torque τ = r × F is the rotational equivalent of force; direction and lever arm both matter.',
    'Moment of inertia I is the rotational equivalent of mass — it depends on how mass is distributed, not just total mass.',
    'Newton\u2019s second law for rotation: τ = Iα.',
    'Worked example: a two-mass pulley system where the pulley itself has mass, requiring the parallel axis theorem I = I_cm + Md² and three simultaneous equations.',
    'Rotational kinetic energy: KE = ½Iω². For rolling objects, total KE = translational + rotational.',
    'Two flagged common mistakes: forgetting to convert RPM→rad/s, and using the wrong I formula for the object\u2019s shape.',
  ] },
  { level: 'bullet', label: 'Bullet Summary', points: [
    'θ, ω, α = rotational analogues of x, v, a',
    'τ = r × F',
    'τ = Iα (rotational Newton\u2019s 2nd law)',
    'I = Σ m r² (point mass), I = I_cm + Md² (parallel axis)',
    'KE_rot = ½Iω²',
    'Rolling KE = translational + rotational',
  ] },
  { level: 'exam', label: 'Exam Summary', points: [
    'High-yield: the pulley worked example (Chapter 3) — very likely to reappear with different numbers.',
    'Know τ = Iα and I = I_cm + Md² cold.',
    'Practice at least one rolling-without-slipping energy problem.',
    'Watch for RPM vs rad/s traps in numeric questions.',
  ] },
  { level: 'revision', label: 'Revision Sheet', points: [
    'ω = dθ/dt, α = dω/dt',
    'τ = r × F = Iα',
    'I (point mass) = mr², I (parallel axis) = I_cm + Md²',
    'KE_rot = ½Iω², KE_rolling = ½mv² + ½Iω²',
    'Common mistakes: RPM→rad/s conversion, wrong I formula for shape',
  ] },
  { level: 'one-minute', label: '1-Minute Summary', points: [
    'Rotation mirrors linear motion: swap force→torque, mass→moment of inertia, and you get the same equations.',
    'The pulley example is the one to actually re-derive before the exam.',
  ] },
]

const flashcards1: Flashcard[] = [
  { id: 'f1', chapterId: 'c2', question: 'What is the formula for torque?', answer: 'τ = r × F — the position vector crossed with the applied force.', difficulty: 'easy', favorite: false, masteredLevel: 3 },
  { id: 'f2', chapterId: 'c2', question: 'What does moment of inertia represent physically?', answer: 'A body\u2019s resistance to angular acceleration — the rotational analogue of mass.', difficulty: 'medium', favorite: true, masteredLevel: 2 },
  { id: 'f3', chapterId: 'c3', question: 'State the parallel axis theorem.', answer: 'I = I_cm + Md², where d is the distance between the two parallel axes.', difficulty: 'hard', favorite: true, masteredLevel: 1 },
  { id: 'f4', chapterId: 'c4', question: 'Formula for rotational kinetic energy?', answer: 'KE_rot = ½Iω²', difficulty: 'easy', favorite: false, masteredLevel: 4 },
  { id: 'f5', chapterId: 'c4', question: 'How do you find total KE of a rolling object?', answer: 'Add translational and rotational KE: ½mv² + ½Iω²', difficulty: 'medium', favorite: false, masteredLevel: 2 },
  { id: 'f6', chapterId: 'c5', question: 'What unit must ω be in before use in these formulas?', answer: 'Radians per second (rad/s) — always convert from RPM first.', difficulty: 'easy', favorite: false, masteredLevel: 3 },
]

const quiz1: QuizQuestion[] = [
  { id: 'q1', chapterId: 'c2', type: 'mcq', prompt: 'Which quantity plays the same role in rotation that mass plays in linear motion?', options: ['Torque', 'Angular velocity', 'Moment of inertia', 'Angular momentum'], correctAnswer: 'Moment of inertia', explanation: 'Moment of inertia I resists angular acceleration the way mass resists linear acceleration — that\u2019s why τ = Iα mirrors F = ma.', difficulty: 'easy' },
  { id: 'q2', chapterId: 'c3', type: 'true-false', prompt: 'The parallel axis theorem can only be used when the object is rotating about its own center of mass.', correctAnswer: 'False', explanation: 'It\u2019s the opposite — the parallel axis theorem lets you find I about any axis parallel to (but offset from) the center-of-mass axis.', difficulty: 'medium' },
  { id: 'q3', chapterId: 'c4', type: 'short-answer', prompt: 'Write the total kinetic energy of a solid cylinder rolling without slipping.', correctAnswer: 'KE = ½mv² + ½Iω²', explanation: 'Rolling without slipping combines translational and rotational kinetic energy — a very common exam trap is forgetting the rotational term.', difficulty: 'hard' },
  { id: 'q4', chapterId: 'c5', type: 'mcq', prompt: 'A motor spins at 300 RPM. What must you do before using ω in τ = Iα?', options: ['Nothing, use 300 directly', 'Convert to rad/s', 'Convert to Hz', 'Divide by π'], correctAnswer: 'Convert to rad/s', explanation: 'ω must be in rad/s. 300 RPM × (2π/60) ≈ 31.4 rad/s.', difficulty: 'easy' },
  { id: 'q5', chapterId: 'c2', type: 'fill-blank', prompt: 'Torque is maximized when the force is applied ___ to the position vector.', correctAnswer: 'perpendicular', explanation: 'τ = rF sin(θ) is maximized at θ = 90°, i.e. when F is perpendicular to r.', difficulty: 'medium' },
]

const mindMap1: MindMapNode = {
  id: 'root',
  label: 'Rotational Dynamics',
  children: [
    {
      id: 'm1',
      label: 'Kinematics',
      children: [
        { id: 'm1a', label: 'θ — angular position', children: [] },
        { id: 'm1b', label: 'ω — angular velocity', children: [] },
        { id: 'm1c', label: 'α — angular acceleration', children: [] },
      ],
    },
    {
      id: 'm2',
      label: 'Torque',
      children: [
        { id: 'm2a', label: 'τ = r × F', children: [] },
        { id: 'm2b', label: 'Lever arm & direction', children: [] },
      ],
    },
    {
      id: 'm3',
      label: 'Moment of Inertia',
      children: [
        { id: 'm3a', label: 'I = Σmr² (point mass)', children: [] },
        { id: 'm3b', label: 'Parallel axis theorem', children: [] },
        { id: 'm3c', label: 'Depends on mass distribution', children: [] },
      ],
    },
    {
      id: 'm4',
      label: 'Rotational Energy',
      children: [
        { id: 'm4a', label: 'KE_rot = ½Iω²', children: [] },
        { id: 'm4b', label: 'Rolling without slipping', children: [] },
      ],
    },
  ],
}

const chat1: ChatMessage[] = [
  {
    id: 'cm1',
    role: 'assistant',
    text: "Hi! I've fully processed this lecture. Ask me to explain any chapter, summarize a section, or pull out the important formulas — I'll always point you to the exact timestamp.",
  },
]

const lecture1: VideoLecture = {
  id: 'lec-1',
  title: 'Rotational Dynamics — Torque & Moment of Inertia',
  course: 'Classical Mechanics · CS-less, Physics 201',
  sourceType: 'lecture',
  uploadedAt: '2 days ago',
  thumbnailGradient: ['#2DD4BF', '#0d9488'],
  state: 'ready',
  currentStageIndex: PIPELINE_STAGE_DEFS.length,
  pipeline: buildPipeline(PIPELINE_STAGE_DEFS.length),
  durationSec: originalDuration1,
  stats: {
    originalDurationSec: originalDuration1,
    optimizedDurationSec: optimizedDuration1,
    minutesSaved: Math.round((removedSeconds1 / 60) * 10) / 10,
    percentRemoved: Math.round((removedSeconds1 / originalDuration1) * 100),
    learningEfficiencyScore: 92,
  },
  silenceSegments: silence1,
  chapters: chapters1,
  transcript: transcript1,
  summaries: summaries1,
  flashcards: flashcards1,
  quiz: quiz1,
  mindMap: mindMap1,
  chat: chat1,
  demoVideoUrl: 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
}

/* ─── Lecture 2: currently processing — "Organic Chemistry: Reaction Mechanisms" ─── */

const lecture2: VideoLecture = {
  id: 'lec-2',
  title: 'SN1 vs SN2 Reaction Mechanisms',
  course: 'Organic Chemistry II',
  sourceType: 'zoom',
  uploadedAt: '3 minutes ago',
  thumbnailGradient: ['#f59e0b', '#ea580c'],
  state: 'processing',
  currentStageIndex: 10,
  pipeline: buildPipeline(10, 62),
  durationSec: 2340,
  stats: {
    originalDurationSec: 2340,
    optimizedDurationSec: 0,
    minutesSaved: 0,
    percentRemoved: 0,
    learningEfficiencyScore: 0,
  },
  silenceSegments: [],
  chapters: [],
  transcript: [],
  summaries: [],
  flashcards: [],
  quiz: [],
  mindMap: { id: 'root', label: 'SN1 vs SN2', children: [] },
  chat: [],
}

/* ─── Lecture 3: queued — "Cell Biology: Mitosis Recording" ─── */

const lecture3: VideoLecture = {
  id: 'lec-3',
  title: 'Mitosis & Cell Division (Teams Recording)',
  course: 'Cell Biology',
  sourceType: 'teams',
  uploadedAt: 'Just now',
  thumbnailGradient: ['#a855f7', '#7e22ce'],
  state: 'queued',
  currentStageIndex: 0,
  pipeline: buildPipeline(0),
  durationSec: 1860,
  stats: { originalDurationSec: 1860, optimizedDurationSec: 0, minutesSaved: 0, percentRemoved: 0, learningEfficiencyScore: 0 },
  silenceSegments: [],
  chapters: [],
  transcript: [],
  summaries: [],
  flashcards: [],
  quiz: [],
  mindMap: { id: 'root', label: 'Mitosis', children: [] },
  chat: [],
}

export const mockLectures: VideoLecture[] = [lecture1, lecture2, lecture3]

export function formatDuration(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = Math.floor(totalSeconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatTimestamp(seconds: number): string {
  return formatDuration(seconds)
}
