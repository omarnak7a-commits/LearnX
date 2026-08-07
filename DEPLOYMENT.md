# LearnX — دليل النشر الكامل (Deployment Runbook)

> **الحالة:** Full-stack implementation مكتملة على `arena/019fba3f-learnx`:
> باك إند حقيقي (Google OAuth + Resend + Supabase Storage S3 + Courses/Roster +
> File Vault + Calendar + Notifications) وواجهة مربوطة بالـ APIs عبر
> `src/lib/*/apiClient.ts` (بدون mocks). النشر الفعلي على Vercel/Render بيتعمل
> من جهاز فيه وصول للإنترنت الكامل — الـ sandbox اللي اتبنى فيه الكود عندها
> network allowlist (Supabase/Vercel/Render/Resend مش متوصلة منها).

---

## 1) البنية الحالية (Full Stack)

| الطبقة | التقنية | ملفات النشر |
|---|---|---|
| Frontend (SPA) | React 19 + Vite 8 + Tailwind v4 | `vercel.json`, `VITE_API_BASE_URL` |
| Backend (API) | FastAPI + SQLAlchemy + Alembic | `backend/render.yaml` |
| قاعدة البيانات | Supabase Postgres (pooler) | migrations في `backend/alembic/` |
| الملفات/الفيديو | Supabase Storage (S3) | `STORAGE_*` env vars |
| الإيميلات | Resend | `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS` |
| الدخول | Google OAuth 2.0 (Code Flow + JWKS) | `GOOGLE_*` env vars |

### API المتاح (47 route):
- `POST /api/v1/auth/register` — إنشاء حساب + إيميل تفعيل
- `POST /api/v1/auth/login` — دخول إيميل/كلمة مرور → JWT
- `GET  /api/v1/auth/google` + `GET /api/v1/auth/google/callback` — OAuth حقيقي
- `POST /api/v1/auth/verify-email` • `POST /api/v1/auth/forgot-password` • `POST /api/v1/auth/reset-password` • `GET /api/v1/auth/me`
- `GET|POST /api/v1/courses` + module/lesson/enroll/save/complete endpoints + `GET /api/v1/courses/roster/students`
- `GET|POST /api/v1/file-vault` (رفع عبر presigned PUT لـ Supabase Storage) + notes + bookmarks
- `GET|POST /api/v1/calendar` • `GET /api/v1/notifications`

## 2) الأسرار (Secrets)

- ملف الأسرار الحقيقي: `.env.deployment.secrets.md` — **gitignored**.
- نسخة الباك إند: `backend/.env` — **gitignored**.
- نموذج بدون قيم: `.env.example` (committed).

> ⚠️ ممنوع commit أي ملف فيه أسرار. لو اتضافت بالغلط: `git rm --cached` فورًا
> وغيّر الأسرار المتسربة.

## 3) نشر الـ Frontend على Vercel (learn-x-ofvm)

```bash
npx vercel login
npx vercel link --project learn-x-ofvm
npx vercel env add VITE_API_BASE_URL production   # https://learnx-api.onrender.com
npx vercel --prod
```

- Build command في `vercel.json`: `pnpm install && pnpm build` (output: `dist`).
- **مهم:** `VITE_API_BASE_URL` لازم يكون رابط Render بعد أول deploy للباك إند.
- SPA routes (`/auth/callback/google`) بتتخدم عادي لأن Vercel بيدي fallback لـ `index.html`.

## 4) نشر الـ Backend على Render

```bash
npm i -g @renderinc/cli
render blueprint launch --blueprint backend/render.yaml
```

أو يدويًا (Web Service):
- Root Directory: `backend`
- Build: `pip install -r requirements-web.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Pre-deploy: `alembic upgrade head` (بيشغّل migrations على Supabase قبل كل نشر)
- Health check: `/health`

ثم حط الأسرار من `.env.deployment.secrets.md` في Render dashboard:
`DATABASE_URL, JWT_SECRET, STORAGE_ENDPOINT_URL, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY,
STORAGE_REGION, STORAGE_BUCKET, RESEND_API_KEY, EMAIL_FROM_ADDRESS, GOOGLE_CLIENT_ID,
GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, APP_BASE_URL, CORS_ORIGINS, COOKIE_SECURE,
REQUIRE_EMAIL_VERIFICATION`.

بعد أول deploy:
1. خد رابط الـ service الجديد (مثل `https://learnx-api.onrender.com`).
2. حدّث `VITE_API_BASE_URL` في Vercel بـه وأعد deploy الفرونت.
3. لو `GOOGLE_REDIRECT_URI` بتشاور على `https://learn-x-ofvm.vercel.app/auth/callback/google`،
   تأكد إن الفرونت منشور على نفس الدومين قبل ما تجرب الدخول بجوجل.

## 5) قاعدة البيانات (Supabase Postgres)

- سلسلتان من migrations (`alembic upgrade head`):
  1. `fa94e7c3c032` — initial (users, universities, video_lectures, ...)
  2. `b7c9d1e2f3a4` — full-stack: auth state columns, courses/roster tables,
     vault_files, student_notes, file_bookmarks, calendar_events, notifications,
     email/password-reset tokens
- توليد SQL يدوي للتحقق: `cd backend && alembic upgrade head --sql`

## 6) فحص سريع بعد النشر

```bash
curl -s https://learnx-api.onrender.com/health
# {"status":"ok","environment":"production"}

curl -sI https://learn-x-ofvm.vercel.app | head -1    # 200

# تسجيل حساب حقيقي (بييجي إيميل تفعيل من Resend)
curl -s -X POST https://learnx-api.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@university.edu","password":"password123","full_name":"Alex Chen"}'
```

## 7) ملاحظات معمارية

- **OAuth:** `backend/app/services/google_oauth.py` — بيـverify الـ ID token بـ
  `google.oauth2.id_token.verify_oauth2_token` (JWKS + audience)، والـ state محمي بـ HTTP-only cookie.
- **التخزين:** كل object باسم namespace `users/{user_id}/...`، والقراءة بس عبر presigned URLs قصيرة الأجل.
- **File Vault:** الرفع الكبير بيمر مباشرة client → Supabase Storage (presigned PUT)،
  والتحليل (PDF extraction, summaries, flashcards) شغال client-side حقيقي ومتزامن مع الـ API.
- **Courses:** شجرة Course → Module → Lesson، enrollment + lesson completion بيحسب
  progress % للطالب و completion rate للكورس، و`/roster/students` بيرجّع سجل طلاب الدكتور.
