# SCG Pilot (demo)

Runnable Flask/SQLite demo for incident reporting and service coordination. **Ова е пилот и не е замена за 112 или официјални упатства. За итни случаи јавете се на 112.**

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # Linux/macOS: cp .env.example .env
flask --app app seed-demo
flask --app app run
pytest
```

Never put real secrets in source control. Set a strong `SECRET_KEY` in `.env`; `DATABASE`, `UPLOAD_FOLDER`, and optional `FIRMS_MAP_KEY` are supported. NASA FIRMS is disabled safely when the key is absent (`python scripts/firms_hotspots.py`).

## Deploy на Render преку GitHub

Во репозиториумот има `render.yaml` Blueprint. На Render избери **New > Blueprint**, поврзи го GitHub repository `burakcek/scg-pilot` и избери branch-от што го содржи овој код. Render автоматски ќе ги инсталира dependencies и ќе стартува:

```text
gunicorn --workers 2 --timeout 120 --bind 0.0.0.0:$PORT app:app
```

По deploy ќе добиеш јавен URL од типот `https://scg-pilot.onrender.com`. `SECRET_KEY` се генерира автоматски. `FIRMS_MAP_KEY` е optional и може да се внесе во Render Environment Variables.

Овој demo користи SQLite и локален upload folder. На бесплатниот Render filesystem е ephemeral, па database/uploads може да се изгубат при redeploy или restart. За вистински pilot користи managed PostgreSQL, object storage за фотографии и persistent disk/backup политика; не внесувај реални чувствителни податоци во demo deployment.

## Roles and access matrix

| Role | Public map/report | Agency dashboard | Operational/contact data | Restricted incidents |
|---|---|---|---|---|
| citizen (public registration) | yes | no | no | no |
| agency | yes | yes | yes | yes |
| police | yes | yes | yes | yes |
| admin | yes | yes | yes | yes |

Public registration can only create `citizen`. Agency, police, and admin accounts must be provisioned by an administrator/CLI. `flask --app app create-admin` creates an admin interactively. Demo seed account: `demo@scg.mk` / `DemoPass123!`.
Use `flask --app app create-account` to provision a non-public `agency` or `police` account and optionally attach its agency ID.

Incidents support requested types, M/ETHANE, coordinates, reporter/contact, image upload (5 MB application limit), lead/supporting agencies, visibility, priority and lifecycle statuses. Audit entries cover login, dashboard access, create and changes. This demo's service authorization is role-based; production must add verified agency scope, SSO/MFA, retention policy, malware scanning and immutable audit storage.

M/ETHANE е задржан како меѓународен оперативен термин, но во формата има македонско објаснување: број на загрозени/повредени, локација, вид на настан, опасности, пристап, потребна помош и број на лица.

## Известувања за службеници

Демо верзијата има in-app notifications: службениците (agency/police/admin) гледаат бројач во навигацијата и страница „Известувања“. Се креира известување за нова пријава, доделен инцидент и промена на статус; достапен е и `/api/notifications` endpoint за Android/WebView polling. За вистински Android push notifications додај Firebase Cloud Messaging credentials, device-token регистрација и server-side push worker; тие secrets намерно не се вклучени во repository.

## Shqip / Албански јазик

Во навигацијата има избор `МК / SQ`. Изборот `SQ` го менува интерфејсот на албански и се зачувува во сесијата: навигација, пријава, типови, статуси, приоритети, агенции, dashboard, известувања и incident detail. Отвори `/language/sq` за албански или `/language/mk` за македонски. Внатрешните database/API кодови остануваат непроменети.

Достапен е и избор `EN` за целосен англиски интерфејс преку `/language/en`.

## Pilot limitations

Leaflet and OpenStreetMap tiles load from CDN; do not rely on availability during an outage. FIRMS is optional and should be rate-limited/cached in production. No real dispatch, geocoding, SMS, encryption-at-rest, or legal incident classification is included. Validate all deployments with the relevant Macedonian authorities.

## Android апликација

Папката `android/` е Android Studio проект кој го прикажува SCG Pilot како native Android app преку безбеден `WebView`. Поддржува login cookies, Android back navigation, offline/error screen, photo upload и GPS permission за incident report формата. Во web формата локацијата може да се избере со GPS, со клик на Leaflet map или со поместување на marker.

Отвори ја папката `android/` во Android Studio. Production URL може да се постави при build:

```bash
gradlew assembleDebug -PscgPilotUrl=https://YOUR-RENDER-URL.onrender.com/
```

APK ќе биде во `android/app/build/outputs/apk/debug/app-debug.apk`. Не оставај placeholder URL во release APK. Android app ги користи истите server-side authorization rules и не е замена за 112.
