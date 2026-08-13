# LearnX — دليل النشر الكامل (Deployment Runbook)

> **الحالة:** Full-stack implementation مكتملة على `arena/019fba3f-learnx`:
> باك إند حقيقي (Google OAuth + Resend + Supabase Storage S3 + Courses/Roster +
> File Vault + Calendar + Notifications) وواجهة مربوطة بالـ APIs عبر
> `src/lib/*/apiClient.ts` (بدون mocks).
>
> **النشر الأساسي: كل حاجة على Vercel (بدون فيزا/كارت).** الباك إند بيشتغل
> كـ Python Serverless Functions (`api/index.py` — ASGI)، والفرونت SPA على نفس
> الدومين (same-origin → مفيش CORS). البديل (Render) موثق في آخر الملف لمن
> عنده كارت.

---

## 1) البنية الحالية (Full Stack)

| الطبقة | التقنية | ملفات النشر |
|---|---|---|
| Frontend (SPA) | React 19 + Vite 8 + Tailwind v4 | `vercel.json`, `dist/` |
| Backend (API) | FastAPI ASGI على Vercel Functions | `api/index.py`, `requirements.txt` (جذر) |
| قاعدة البيانات | Supabase Postgres (pooler) | migrations في `backend/alembic/` |
| الملفات/الفيديو | Supabase Storage (S3) | `STORAGE_*` env vars |
| الإيميلات | Resend | `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS` |
| الدخول | Google OAuth 2.0 (Code Flow + JWKS) | `GOOGLE_*` env vars |

### التوجيه في `vercel.json`:
```jsonc
"rewrites": [
  { "source": "/api/v1/(.*)", "destination": "/api/index.py" },  // FastAPI
  { "source": "/health",        "destination": "/api/index.py" },
  { "source": "/docs",          "destination": "/api/index.py" },
  { "source": "/openapi.json",  "destination": "/api/index.py" },
  { "source": "/api/migrate",   "destination": "/api/migrate.py" }, // migrations مرة واحدة
  { "source": "/(.*)",          "destination": "/index.html" }      // SPA fallback
]
```
- `functions.api/index.py` → runtime `python3.11`, `includeFiles: backend/**`
  (بيضمن إن package الـ backend + ملفات alembic داخل حزمة الـ function).
- الـ Python deps بيتثبتوا تلقائيًا من `requirements.txt` اللي في جذر المشروع.

## 2) الأسرار (Secrets)

- ملف الأسرار الحقيقي: `.env.deployment.secrets.md` — **gitignored**.
- نسخة الباك إند: `backend/.env` — **gitignored** (للتشغيل المحلي فقط).
- نموذج بدون قيم: `.env.example` (committed).

> ⚠️ ممنوع commit أي ملف فيه أسرار. `vercel.json` متعمد **مفيش فيه env** — المتغيرات
> كلها بتتحط في Vercel Dashboard مباشرة (القسم التالي).

## 3) النشر الكامل على Vercel (بدون فيزا) — الخطوات

### 3.1 اربط المشروع
- GitHub → Vercel → **Add New Project** → استورد `omarnak7a-commits/LearnX`.
  أو من CLI: `npx vercel login && npx vercel link --project learn-x-ofvm`.
- Vercel هياخد البناء من `vercel.json`: `pnpm install && pnpm build` (الفرونت)
  + Python function (الباك).

### 3.2 حط المتغيرات في Vercel Dashboard
Project → **Settings → Environment Variables** → أضف (Production) — القيم الحقيقية من
`.env.deployment.secrets.md` عندك (مش مكتوبة هنا عشان الملف ده committed):

| المتغير | القيمة (من ملف الأسرار) |
|---|---|
| `ENVIRONMENT` | `production` |
| `API_PREFIX` | `/api/v1` |
| `CORS_ORIGINS` | `["https://learn-x-ofvm.vercel.app"]` |
| `DATABASE_URL` | رابط Supabase pooler (فيه `%23`) |
| `JWT_SECRET` | الـ hex الطويل |
| `STORAGE_ENDPOINT_URL` | `https://nmhqleagwizfyigxakqn.storage.supabase.co/storage/v1/s3` |
| `STORAGE_REGION` | `us-east-1` |
| `STORAGE_BUCKET` | `learnx-uploads` |
| `STORAGE_ACCESS_KEY` | access key |
| `STORAGE_SECRET_KEY` | secret key |
| `SIGNED_URL_TTL_SECONDS` | `900` |
| `GEMINI_API_KEY` | مفتاح Google Gemini (backend only) |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `GROQ_API_KEY` | مفتاح Groq (backend only) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| `AI_PROVIDER` | `gemini` |
| `AI_FALLBACK_PROVIDER` | `groq` |
| `RESEND_API_KEY` | مفتاح Resend |
| `EMAIL_FROM_ADDRESS` | `LearnX <onboarding@resend.dev>` |
| `GOOGLE_CLIENT_ID` | client id |
| `GOOGLE_CLIENT_SECRET` | client secret |
| `GOOGLE_REDIRECT_URI` | `https://learn-x-ofvm.vercel.app/auth/callback/google` |
| `APP_BASE_URL` | `https://learn-x-ofvm.vercel.app` |
| `COOKIE_SECURE` | `true` |
| `REQUIRE_EMAIL_VERIFICATION` | `true` |
| `MIGRATION_KEY` | (اختياري) أي نص عشوائي — لتفعيل endpoint الـ migrations |

> `VITE_API_BASE_URL` **متسببهاش** (same-origin — الفرونت والـ API على نفس الدومين).
> إضافة متغير build بيشتغل برضه لو حبيت، بنفس قيمة `APP_BASE_URL`.

### 3.3 انشر
- `npx vercel --prod` أو ادفع على الـ branch المرتبط بـ Vercel.
- لأول مرة في عمر قاعدة البيانات، شغّل الـ migrations **مرة واحدة**:
  ```bash
  curl -X POST https://learn-x-ofvm.vercel.app/api/migrate \
    -H "x-migration-key: <MIGRATION_KEY اللي حطيته في الـ Dashboard>"
  # {"ok": true, "target": "head"}
  ```
  (لو `MIGRATION_KEY` مش متظبط → 503؛ مفتاح غلط → 403؛ الـ endpoint بيعمل
  `alembic upgrade head` بس — من غير مفتاح مش شغال أصلًا.)

### 3.4 فحص بعد النشر
```bash
curl -s https://learn-x-ofvm.vercel.app/health
# {"status":"ok","environment":"production"}

curl -s https://learn-x-ofvm.vercel.app/api/v1/auth/me          # 401 (مطلوب token — تمام)
curl -sI https://learn-x-ofvm.vercel.app | head -1              # 200 (الفرونت)

# تسجيل حساب حقيقي (بييجي إيميل تفعيل من Resend)
curl -s -X POST https://learn-x-ofvm.vercel.app/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@university.edu","password":"password123","full_name":"Alex Chen"}'
```

### 3.5 حدود Vercel لازم تعرفها
- **WebSockets غير مدعومة على Serverless Functions** — route الـ `/ws/...` موجود
  في الكود بس مش مستخدم من الفرونت حاليًا؛ مش بيأثر على أي حاجة.
- **maxDuration = 60s** على خطة Hobby — كفاية لكل الـ endpoints (كلها DB/API calls سريعة).
- **DB connection pooling**: Vercel functions cold start بيفتح اتصال جديد — طبيعي
  وسريع مع Supabase pooler.

---

## 4) البديل: الباك إند على Render (لو في كارت)

```bash
npm i -g @renderinc/cli
render blueprint launch --blueprint backend/render.yaml
```
- Build: `pip install -r requirements-web.txt` • Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Pre-deploy: `alembic upgrade head` (بيشغّل migrations تلقائيًا)
- وبعدها `VITE_API_BASE_URL` في Vercel = رابط Render.

## 5) قاعدة البيانات (Supabase Postgres)

- سلسلتان migrations (`alembic upgrade head`):
  1. `fa94e7c3c032` — initial (users, universities, video_lectures, ...)
  2. `b7c9d1e2f3a4` — full-stack: auth state columns, courses/roster tables,
     vault_files, student_notes, file_bookmarks, calendar_events, notifications,
     email/password-reset tokens
- توليد SQL يدوي للتحقق: `cd backend && alembic upgrade head --sql`

## 6) ملاحظات معمارية

- **OAuth:** `backend/app/services/google_oauth.py` — بيـverify الـ ID token بـ
  `google.oauth2.id_token.verify_oauth2_token` (JWKS + audience)، والـ state محمي بـ HTTP-only cookie.
- **التخزين:** كل object باسم namespace `users/{user_id}/...`، والقراءة بس عبر presigned URLs قصيرة الأجل.
- **File Vault:** الرفع الكبير بيمر مباشرة client → Supabase Storage (presigned PUT). تحليل PDF
  يمر عبر FastAPI بعد التحقق من ملكية صف `VaultFile` واسم storage المعزول للمستخدم؛ لا يُرسل
  storage key أو signed URL من المتصفح إلى مزود AI.
- **Online AI:** كل الطلبات تمر `Frontend → FastAPI → AIService`. يتم استدعاء
  `gemini-2.5-flash` أولًا، ثم Groq تلقائيًا عند timeout/rate limit/provider failure. مفاتيح
  المزودين backend-only ولا يوجد أي متغير `VITE_GEMINI_*` أو `VITE_GROQ_*`.
- **Courses:** شجرة Course → Module → Lesson، enrollment + lesson completion بيحسب
  progress % للطالب و completion rate للكورس، و`/roster/students` بيرجّع سجل طلاب الدكتور.

