"""SCG Pilot demo application."""
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from scripts.firms_hotspots import fetch_hotspots

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AGENCIES = [
    ("Министерство за внатрешни работи / Полиција", "MVR / Police", "national"),
    ("Армија", "Army", "national"),
    ("Шумска полиција", "Forest Police", "national"),
    ("Противпожарна бригада", "Firefighting Brigade", "municipality"),
    ("Јавно претпријатие Национални шуми / Шумочувари", "Public Forestry / Forest Guards", "region"),
    ("Центар за управување со кризи", "Crisis Management Center", "national"),
    ("Итна медицинска помош / Здравство", "Emergency Medical / Healthcare", "municipality"),
    ("Дирекција за заштита и спасување", "Protection and Rescue Directorate", "national"),
    ("Црвен крст", "Red Cross", "region"),
    ("Специјални единици", "Special Units", "restricted"),
    ("Општина", "Municipality", "municipality"),
    ("Државен инспекторат (екологија/шуми/градежништво)", "Environmental/Forestry/Construction Inspection", "national"),
    ("Јавни патишта", "Public Roads", "national"),
    ("Оператори вода/електрична енергија/телекомуникации", "Water/Electricity/Telecom Operators", "region"),
    ("Планинска спасувачка служба", "Mountain Rescue", "region"),
    ("Волонтерска спасувачка служба", "Volunteer Rescue", "region"),
]
INCIDENT_TYPES = ["forest_fire", "smoke", "illegal_logging", "house_theft", "illegal_transport",
                  "illegal_border_crossing", "illegal_construction", "flood", "rescue", "medical_emergency"]
STATUSES = ["reported", "triaged", "acknowledged", "verified", "assigned", "in_progress",
             "contained", "resolved", "closed", "reopened", "false_report", "duplicate"]
PRIORITIES = ["low", "normal", "high", "critical"]
VISIBILITIES = ["public", "internal", "restricted", "service_only"]
ROLES = ["citizen", "agency", "admin", "police"]
TYPE_LABELS = {
    "forest_fire": "Шумски пожар", "smoke": "Дим", "illegal_logging": "Нелегална сеч",
    "house_theft": "Кражба во дом", "illegal_transport": "Нелегален транспорт",
    "illegal_border_crossing": "Нелегално преминување граница",
    "illegal_construction": "Нелегална градба", "flood": "Поплава",
    "rescue": "Спасување", "medical_emergency": "Медицинска итност",
}
STATUS_LABELS = {
    "reported": "Пријавен", "triaged": "Сортиран", "acknowledged": "Потврден прием",
    "verified": "Проверен", "assigned": "Доделен", "in_progress": "Во тек",
    "contained": "Ставена под контрола", "resolved": "Решен", "closed": "Затворен",
    "reopened": "Повторно отворен", "false_report": "Лажна пријава", "duplicate": "Дупликат",
}
PRIORITY_LABELS = {"low": "Низок", "normal": "Нормален", "high": "Висок", "critical": "Критичен"}
VISIBILITY_LABELS = {"public": "Јавен", "internal": "Внатрешен", "restricted": "Ограничен", "service_only": "Само за надлежната служба"}

login_manager = LoginManager()
login_manager.login_view = "login"

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.getenv("DATABASE", os.path.join(app.instance_path, "scg.sqlite")),
        UPLOAD_FOLDER=os.getenv("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads")),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    login_manager.init_app(app)

    @app.teardown_appcontext
    def close_db(_exception=None):
        db = g.pop("db", None)
        if db:
            db.close()

    with app.app_context():
        init_db()

    @app.context_processor
    def inject_globals():
        return {"incident_types": INCIDENT_TYPES, "statuses": STATUSES, "priorities": PRIORITIES,
                "type_labels": TYPE_LABELS, "status_labels": STATUS_LABELS,
                "priority_labels": PRIORITY_LABELS, "visibility_labels": VISIBILITY_LABELS}

    register_routes(app)
    return app

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.app.config["DATABASE"] if hasattr(g, "app") else current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db

# Flask's app context proxy is not a regular g attribute; import lazily to retain a small module API.
from flask import current_app
def db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db
get_db = db

def init_db():
    database = db()
    database.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
      name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('citizen','agency','admin','police')),
      agency_id INTEGER, municipality TEXT, region TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS agencies (
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_en TEXT NOT NULL,
      scope TEXT NOT NULL, municipality TEXT, region TEXT
    );
    CREATE TABLE IF NOT EXISTS incidents (
      id INTEGER PRIMARY KEY, public_id TEXT UNIQUE NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL,
      description TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL,
      priority TEXT NOT NULL, status TEXT NOT NULL, visibility TEXT NOT NULL,
      lead_agency_id INTEGER, supporting_agencies TEXT, m_ethane TEXT, reporter_name TEXT,
      contact TEXT, photo_filename TEXT, municipality TEXT, region TEXT, created_by INTEGER,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY, actor_id INTEGER, action TEXT NOT NULL, incident_id INTEGER,
      details TEXT, created_at TEXT NOT NULL
    );
    """)
    for column in ("municipality", "region"):
        try:
            database.execute(f"ALTER TABLE incidents ADD COLUMN {column} TEXT")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
    if database.execute("SELECT COUNT(*) FROM agencies").fetchone()[0] == 0:
        database.executemany("INSERT INTO agencies(name,name_en,scope,municipality,region) VALUES (?,?,?,?,?)",
                             [(a, en, scope, "Центар" if scope == "municipality" else None, "Скопски" if scope == "region" else None) for a,en,scope in AGENCIES])
    database.commit()

class User(UserMixin):
    def __init__(self, row): self.__dict__.update(dict(row))

@login_manager.user_loader
def load_user(user_id):
    row = db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return User(row) if row else None

def now(): return datetime.now(timezone.utc).isoformat()
def audit(action, incident_id=None, details=""):
    db().execute("INSERT INTO audit_log(actor_id,action,incident_id,details,created_at) VALUES (?,?,?,?,?)",
                 (current_user.id if current_user.is_authenticated else None, action, incident_id, details, now()))
    db().commit()
def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles: abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
def can_view(incident):
    if incident["visibility"] == "public": return True
    if not current_user.is_authenticated: return False
    if current_user.role in ("admin", "police"): return True
    if current_user.role != "agency" or incident["visibility"] == "restricted":
        return False
    if incident["visibility"] == "service_only":
        return incident["lead_agency_id"] == current_user.agency_id
    assigned = str(current_user.agency_id or "")
    return incident["visibility"] in ("internal", "service_only") and (
        incident["lead_agency_id"] == current_user.agency_id or assigned in (incident["supporting_agencies"] or "").split(",")
    )

def can_manage(incident):
    if not current_user.is_authenticated or current_user.role in ("admin", "police"):
        return current_user.is_authenticated
    return current_user.role == "agency" and (
        incident["lead_agency_id"] == current_user.agency_id or
        str(current_user.agency_id or "") in (incident["supporting_agencies"] or "").split(",")
    )

def register_routes(app):
    @app.route("/")
    def index():
        rows = db().execute("SELECT id,public_id,type,title,latitude,longitude,priority,status,created_at FROM incidents WHERE visibility='public' ORDER BY id DESC").fetchall()
        return render_template("index.html", incidents=rows)

    @app.route("/register", methods=("GET", "POST"))
    def register():
        if request.method == "POST":
            email, name, password = request.form.get("email","").strip().lower(), request.form.get("name","").strip(), request.form.get("password","")
            if not email or not name or len(password) < 8: flash("Внесете име, валиден email и лозинка од најмалку 8 знаци.", "error")
            else:
                try:
                    cur = db().execute("INSERT INTO users(email,password_hash,name,role,created_at) VALUES (?,?,?,?,?)",
                        (email, generate_password_hash(password), name, "citizen", now())); db().commit()
                    login_user(load_user(cur.lastrowid)); return redirect(url_for("index"))
                except sqlite3.IntegrityError: flash("Email веќе постои.", "error")
        return render_template("auth.html", register=True)

    @app.route("/login", methods=("GET","POST"))
    def login():
        if request.method == "POST":
            user = db().execute("SELECT * FROM users WHERE email=?", (request.form.get("email","").strip().lower(),)).fetchone()
            if user and check_password_hash(user["password_hash"], request.form.get("password","")):
                login_user(User(user)); audit("login"); return redirect(request.args.get("next") or url_for("dashboard"))
            flash("Неточен email или лозинка.", "error")
        return render_template("auth.html", register=False)
    @app.route("/logout")
    @login_required
    def logout(): logout_user(); return redirect(url_for("index"))

    @app.route("/report", methods=("GET","POST"))
    def report():
        if request.method == "POST":
            try:
                lat, lon = float(request.form["latitude"]), float(request.form["longitude"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError
            except (KeyError, ValueError): flash("Невалидни координати.", "error"); return render_template("report.html")
            photo = request.files.get("photo"); filename = None
            if photo and photo.filename:
                if not photo.mimetype.startswith("image/"): flash("Фото мора да биде слика.", "error"); return render_template("report.html")
                filename = f"{uuid.uuid4().hex}_{secure_filename(photo.filename)}"; photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            incident_type = request.form.get("type", INCIDENT_TYPES[0])
            if incident_type not in INCIDENT_TYPES:
                incident_type = INCIDENT_TYPES[0]
            visibility = "public" if not current_user.is_authenticated or current_user.role == "citizen" else request.form.get("visibility", "internal")
            if visibility not in VISIBILITIES:
                visibility = "internal"
            anonymous = request.form.get("anonymous") == "on"
            reporter_name = "" if anonymous else request.form.get("reporter_name", "")[:120]
            contact = "" if anonymous else request.form.get("contact", "")[:120]
            values = (uuid.uuid4().hex[:12], incident_type, request.form.get("title","")[:160], request.form.get("description","")[:5000], lat, lon, request.form.get("priority","normal") if request.form.get("priority") in PRIORITIES else "normal", "reported", visibility, None, request.form.get("supporting_agencies",""), request.form.get("m_ethane","")[:2000], reporter_name, contact, filename, current_user.id if current_user.is_authenticated and not anonymous else None, now(), now())
            cur = db().execute("""INSERT INTO incidents(public_id,type,title,description,latitude,longitude,priority,status,visibility,lead_agency_id,supporting_agencies,m_ethane,reporter_name,contact,photo_filename,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values); db().commit(); audit("incident_created", cur.lastrowid); flash("Пријавата е зачувана.", "success"); return redirect(url_for("incident_detail", incident_id=cur.lastrowid))
        return render_template("report.html")

    @app.route("/incidents/<int:incident_id>", methods=("GET","POST"))
    def incident_detail(incident_id):
        incident = db().execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        if not incident: abort(404)
        if not can_view(incident): abort(403)
        if request.method == "POST":
            if not can_manage(incident): abort(403)
            updates = {"status": request.form.get("status"), "priority": request.form.get("priority"), "visibility": request.form.get("visibility")}
            sets, params = [], []
            for key, value in updates.items():
                if value in (STATUSES if key=="status" else PRIORITIES if key=="priority" else VISIBILITIES):
                    sets.append(key+"=?"); params.append(value)
            if request.form.get("lead_agency_id"): sets.append("lead_agency_id=?"); params.append(int(request.form["lead_agency_id"]))
            if sets:
                params += [now(), incident_id]; db().execute("UPDATE incidents SET "+",".join(sets)+",updated_at=? WHERE id=?", params); db().commit(); audit("incident_changed", incident_id, ",".join(sets))
                if "status=?" in sets: audit("status_transition", incident_id, request.form.get("status"))
                if "lead_agency_id=?" in sets: audit("assignment", incident_id, request.form.get("lead_agency_id"))
                if "visibility=?" in sets and request.form.get("visibility") == "public": audit("redaction", incident_id, "operational fields hidden from public view")
            return redirect(url_for("incident_detail", incident_id=incident_id))
        agencies = db().execute("SELECT * FROM agencies ORDER BY name").fetchall()
        return render_template("incident.html", incident=incident, agencies=agencies, safe=not current_user.is_authenticated or current_user.role=="citizen")

    @app.route("/dashboard")
    @roles_required("agency","admin","police")
    def dashboard():
        where, params = ["1=1"], []
        if request.args.get("status") in STATUSES: where.append("status=?"); params.append(request.args["status"])
        if request.args.get("priority") in PRIORITIES: where.append("priority=?"); params.append(request.args["priority"])
        if current_user.role == "agency":
            agency_id = str(current_user.agency_id or "")
            where.append("(visibility='public' OR (visibility IN ('internal','service_only') AND (lead_agency_id=? OR ',' || supporting_agencies || ',' LIKE '%,' || ? || ',%')))")
            params.extend([current_user.agency_id, agency_id])
        elif current_user.role not in ("admin", "police"):
            abort(403)
        rows = db().execute("SELECT * FROM incidents WHERE "+" AND ".join(where)+" ORDER BY id DESC", params).fetchall()
        audit("dashboard_access", details=request.query_string.decode())
        return render_template("dashboard.html", incidents=rows)

    @app.route("/agencies")
    def agencies():
        return render_template("agencies.html", agencies=db().execute("SELECT * FROM agencies ORDER BY scope,name").fetchall())
    @app.route("/api/incidents")
    def api_incidents():
        return jsonify([dict(r) for r in db().execute("SELECT id,public_id,type,title,latitude,longitude,priority,status FROM incidents WHERE visibility='public'").fetchall()])

    @app.route("/api/hotspots")
    def api_hotspots():
        """Return FIRMS data only when explicitly configured; otherwise return [] safely."""
        return jsonify(fetch_hotspots())

    @app.cli.command("create-admin")
    def create_admin():
        email = input("Admin email: ").strip().lower(); password = input("Password (8+): ")
        if len(password) < 8: raise SystemExit("Password too short")
        db().execute("INSERT INTO users(email,password_hash,name,role,created_at) VALUES (?,?,?,?,?)", (email, generate_password_hash(password), "Administrator", "admin", now())); db().commit(); print("Admin created")
    @app.cli.command("create-account")
    def create_account():
        """Provision agency/police accounts (never exposed as public registration)."""
        email = input("Email: ").strip().lower(); name = input("Name: ").strip()
        role = input("Role (agency/police): ").strip().lower(); password = input("Password (8+): ")
        if role not in ("agency", "police") or len(password) < 8: raise SystemExit("Role or password invalid")
        agency_id = None
        if role == "agency":
            agency_id = input("Agency ID (optional): ").strip() or None
        db().execute("INSERT INTO users(email,password_hash,name,role,agency_id,created_at) VALUES (?,?,?,?,?,?)",
                     (email, generate_password_hash(password), name, role, agency_id, now())); db().commit(); print("Account created")
    @app.cli.command("seed-demo")
    def seed_demo():
        if not db().execute("SELECT 1 FROM users WHERE email='demo@scg.mk'").fetchone():
            db().execute("INSERT INTO users(email,password_hash,name,role,created_at) VALUES (?,?,?,?,?)", ("demo@scg.mk",generate_password_hash("DemoPass123!"),"Demo Citizen","citizen",now())); db().commit()
        print("Demo seed ready (demo@scg.mk / DemoPass123!)")

app = create_app()
if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
