"""
Eduvaris: APAAR ID-based Student Data Management and Verification Platform
for AICTE-approved institutions (Smart India Hackathon 2026, Problem Statement 26263).

The whole backend in one file.

HOW TO RUN (in the terminal, from the backend folder):
    .\\.venv\\Scripts\\python.exe portal.py seed   -> creates the database + demo data (run once)
    .\\.venv\\Scripts\\python.exe portal.py        -> starts the API at http://localhost:8000
    API documentation (try every endpoint):          http://localhost:8000/docs

WHO USES IT
    AICTE admin   : adds institutions, sees every institution's data, dashboards and flagged problems.
    Institution   : adds programs (with approved intake), submits student data by
                    form, Excel/CSV upload, or API (for their own software), and fixes flagged problems.
    Public        : can check whether an APAAR ID is enrolled at an AICTE-approved institution.

SECTIONS
    1. Settings
    2. Database tables
    3. Validation rules (APAAR ID, student data, automatic problem detection)
    4. Login & security (passwords, JWT tokens, API keys)
    5. API: login
    6. API: AICTE admin
    7. API: institution (programs, students, form, file upload, API key)
    8. API: public verification
    9. Demo data
   10. Start-up
"""

import csv
import enum
import io
import json
import random
import re
import secrets
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import bcrypt
import jwt
import openpyxl
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator
from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint,
    create_engine, func, select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


# =============================================================================
# 1. SETTINGS
# =============================================================================
APP_NAME = "Eduvaris"
BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = f"sqlite:///{(BASE_DIR / 'eduvaris.db').as_posix()}"  # one file next to portal.py

# AICTE admin account (created by "portal.py seed")
ADMIN_NAME = "AICTE Admin"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "kana143"

# Password for the demo institution accounts (institution1@example.com ... institution4@example.com)
DEMO_INSTITUTION_PASSWORD = "Institute@123"

# Secret used to sign login tokens. Change it before putting the portal online.
JWT_SECRET = "eduvaris-change-this-secret-before-going-live-7f3c9a1e"
JWT_ALGORITHM = "HS256"
TOKEN_HOURS = 8

FRONTEND_URLS = ["http://localhost:3000", "http://127.0.0.1:3000"]
MAX_UPLOAD_MB = 5
MAX_UPLOAD_ROWS = 5000


# =============================================================================
# 2. DATABASE TABLES
# =============================================================================
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_api_key() -> str:
    return "edv_" + secrets.token_urlsafe(24)


class Role(str, enum.Enum):
    aicte_admin = "aicte_admin"
    institution = "institution"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    aicte_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=new_api_key)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="institution")
    programs: Mapped[list["Program"]] = relationship(back_populates="institution", cascade="all, delete-orphan")
    students: Mapped[list["Student"]] = relationship(back_populates="institution", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20))
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    institution: Mapped[Institution | None] = relationship(back_populates="users")


class Program(Base):
    """A course an institution runs in one academic year, with its AICTE-approved intake."""

    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("institution_id", "name", "academic_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    level: Mapped[str] = mapped_column(String(20))  # UG, PG, Diploma
    academic_year: Mapped[str] = mapped_column(String(7))  # e.g. 2025-26
    approved_intake: Mapped[int] = mapped_column(Integer)
    supernumerary_seats: Mapped[int] = mapped_column(Integer, default=0)

    institution: Mapped[Institution] = relationship(back_populates="programs")
    students: Mapped[list["Student"]] = relationship(back_populates="program")


class Student(Base):
    __tablename__ = "students"
    # The same APAAR ID can't appear twice in one institution. It CAN appear at two
    # institutions, so that the platform can detect and flag duplicate enrolment.
    __table_args__ = (UniqueConstraint("institution_id", "apaar_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), index=True)
    apaar_id: Mapped[str] = mapped_column(String(12), index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    gender: Mapped[str] = mapped_column(String(10))
    date_of_birth: Mapped[date] = mapped_column(Date)
    year_of_study: Mapped[int] = mapped_column(Integer)
    admission_category: Mapped[str] = mapped_column(String(10))  # General, OBC, SC, ST, EWS
    seat_type: Mapped[str] = mapped_column(String(15))  # Regular or Supernumerary
    is_nri: Mapped[bool] = mapped_column(Boolean, default=False)
    is_oci: Mapped[bool] = mapped_column(Boolean, default=False)
    is_foreign_national: Mapped[bool] = mapped_column(Boolean, default=False)
    nationality: Mapped[str] = mapped_column(String(60), default="Indian")
    email: Mapped[str | None] = mapped_column(String(255))
    mobile: Mapped[str | None] = mapped_column(String(15))
    source: Mapped[str] = mapped_column(String(10), default="form")  # form, file or api
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    institution: Mapped[Institution] = relationship(back_populates="students")
    program: Mapped[Program] = relationship(back_populates="students")


class UploadLog(Base):
    """One row per Excel/CSV upload, including the rows that were rejected and why."""

    __tablename__ = "upload_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total_rows: Mapped[int] = mapped_column(Integer)
    created: Mapped[int] = mapped_column(Integer)
    updated: Mapped[int] = mapped_column(Integer)
    failed: Mapped[int] = mapped_column(Integer)
    errors_json: Mapped[str] = mapped_column(Text, default="[]")


Base.metadata.create_all(bind=engine)


# =============================================================================
# 3. VALIDATION RULES
# =============================================================================
APAAR_RE = re.compile(r"^\d{12}$")
CATEGORIES = {"general": "General", "obc": "OBC", "sc": "SC", "st": "ST", "ews": "EWS"}
YES_VALUES = {"yes", "y", "true", "1"}
NO_VALUES = {"no", "n", "false", "0", ""}

ISSUE_LABELS = {
    "intake_exceeded": "Admissions exceed approved intake",
    "supernumerary_exceeded": "Supernumerary seats exceeded",
    "cross_institution_duplicate": "Duplicate enrolment across institutions",
    "identity_mismatch": "Same APAAR ID, different identity",
    "inconsistent_data": "Inconsistent student data",
}


def clean_apaar(value) -> str:
    """Removes spaces and dashes, so '1234 5678 9012' becomes '123456789012'."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():  # Excel can store long numbers as floats
        value = int(value)
    return re.sub(r"[\s-]", "", str(value))


def mask_name(full_name: str) -> str:
    return " ".join(p[0] + "*" * (len(p) - 1) for p in full_name.split())


def age_on(dob: date, day: date) -> int:
    return day.year - dob.year - ((day.month, day.day) < (dob.month, dob.day))


class StudentIn(BaseModel):
    """Student data sent by the form or the API. Uploaded files are converted into this too."""

    model_config = ConfigDict(str_strip_whitespace=True)

    apaar_id: str
    full_name: str = Field(min_length=2, max_length=150)
    gender: Literal["Male", "Female", "Other"]
    date_of_birth: date
    program_id: int
    year_of_study: int = Field(ge=1, le=6)
    admission_category: Literal["General", "OBC", "SC", "ST", "EWS"]
    seat_type: Literal["Regular", "Supernumerary"] = "Regular"
    is_nri: bool = False
    is_oci: bool = False
    is_foreign_national: bool = False
    nationality: str = Field(default="Indian", min_length=2, max_length=60)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, pattern=r"^[6-9]\d{9}$")

    @field_validator("apaar_id", mode="before")
    @classmethod
    def check_apaar(cls, v):
        v = clean_apaar(v)
        if not v:
            raise ValueError("APAAR ID is missing")
        if not APAAR_RE.fullmatch(v):
            raise ValueError("APAAR ID must be exactly 12 digits")
        return v

    @field_validator("gender", "seat_type", mode="before")
    @classmethod
    def capitalise(cls, v):
        return v.strip().capitalize() if isinstance(v, str) else v

    @field_validator("admission_category", mode="before")
    @classmethod
    def normalise_category(cls, v):
        return CATEGORIES.get(v.strip().lower(), v) if isinstance(v, str) else v

    @field_validator("email", "mobile", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return None if v is None or str(v).strip() == "" else v

    @field_validator("date_of_birth")
    @classmethod
    def dob_in_past(cls, v: date) -> date:
        if v >= date.today():
            raise ValueError("Date of birth must be in the past")
        return v


def student_inconsistencies(s: Student) -> list[str]:
    """Data that is allowed in, but doesn't add up. Shown as warnings to the institution and AICTE."""
    problems = []
    nationality = (s.nationality or "").strip().lower()
    if s.is_foreign_national and nationality == "indian":
        problems.append("Marked Foreign National but nationality is Indian")
    if not s.is_foreign_national and not s.is_oci and nationality not in ("", "indian"):
        problems.append(f"Nationality is {s.nationality} but not marked Foreign National or OCI")
    if s.is_nri and s.is_foreign_national:
        problems.append("Marked both NRI and Foreign National (NRIs are Indian citizens)")
    if s.is_nri and s.is_oci:
        problems.append("Marked both NRI and OCI (OCI holders are foreign citizens)")
    age = age_on(s.date_of_birth, date.today())
    if age < 15:
        problems.append(f"Age is {age}, too young for higher education")
    if age > 60:
        problems.append(f"Age is {age}, please check date of birth")
    return problems


def compute_issues(db: Session, institution_id: int | None = None) -> list[dict]:
    """Automatic validation: finds every problem in the data.

    institution_id=None -> all institutions (AICTE view, shows other institutions' names)
    institution_id=N    -> only that institution's problems (other institutions stay anonymous)
    """
    names = {i.id: i.name for i in db.scalars(select(Institution))}
    issues: list[dict] = []

    def add(kind, severity, inst_id, message, program=None, student=None):
        issues.append({
            "type": kind,
            "label": ISSUE_LABELS[kind],
            "severity": severity,
            "institution_id": inst_id,
            "institution_name": names.get(inst_id),
            "program": program or (f"{student.program.name} ({student.program.academic_year})" if student else None),
            "student_id": student.id if student else None,
            "apaar_id": student.apaar_id if student else None,
            "student_name": student.full_name if student else None,
            "message": message,
        })

    # 1. Admissions exceeding approved intake / supernumerary seats
    seat_counts = defaultdict(Counter)
    for program_id, seat_type, count in db.execute(
        select(Student.program_id, Student.seat_type, func.count()).group_by(Student.program_id, Student.seat_type)
    ):
        seat_counts[program_id][seat_type] = count
    program_stmt = select(Program)
    if institution_id:
        program_stmt = program_stmt.where(Program.institution_id == institution_id)
    for p in db.scalars(program_stmt):
        label = f"{p.name} ({p.academic_year})"
        regular, supernumerary = seat_counts[p.id]["Regular"], seat_counts[p.id]["Supernumerary"]
        if regular > p.approved_intake:
            add("intake_exceeded", "high", p.institution_id,
                f"{regular} regular admissions against approved intake of {p.approved_intake} "
                f"({regular - p.approved_intake} over)", program=label)
        if supernumerary > p.supernumerary_seats:
            add("supernumerary_exceeded", "high", p.institution_id,
                f"{supernumerary} supernumerary admissions against {p.supernumerary_seats} seats "
                f"({supernumerary - p.supernumerary_seats} over)", program=label)

    # 2. Same APAAR ID enrolled at more than one institution
    duplicate_ids = db.scalars(
        select(Student.apaar_id).group_by(Student.apaar_id).having(func.count(func.distinct(Student.institution_id)) > 1)
    ).all()
    if duplicate_ids:
        groups = defaultdict(list)
        for s in db.scalars(select(Student).where(Student.apaar_id.in_(duplicate_ids))):
            groups[s.apaar_id].append(s)
        for records in groups.values():
            different_identity = (
                len({r.full_name.strip().lower() for r in records}) > 1 or len({r.date_of_birth for r in records}) > 1
            )
            for r in records:
                if institution_id and r.institution_id != institution_id:
                    continue
                others = [names[o.institution_id] for o in records if o.id != r.id]
                where = ", ".join(others) if institution_id is None else f"{len(others)} other institution(s)"
                add("cross_institution_duplicate", "high", r.institution_id,
                    f"Same APAAR ID is also enrolled at {where}", student=r)
                if different_identity:
                    add("identity_mismatch", "high", r.institution_id,
                        "Same APAAR ID is registered with a different name or date of birth elsewhere", student=r)

    # 3. Inconsistent data within a record
    student_stmt = select(Student)
    if institution_id:
        student_stmt = student_stmt.where(Student.institution_id == institution_id)
    for s in db.scalars(student_stmt):
        for message in student_inconsistencies(s):
            add("inconsistent_data", "medium", s.institution_id, message, student=s)

    return issues


def student_warnings(db: Session, s: Student) -> list[str]:
    """Instant feedback after saving one student (form or API)."""
    warnings = student_inconsistencies(s)
    elsewhere = db.scalar(
        select(func.count()).select_from(Student)
        .where(Student.apaar_id == s.apaar_id, Student.institution_id != s.institution_id)
    )
    if elsewhere:
        warnings.append("This APAAR ID is also enrolled at another institution. AICTE will see it as a possible duplicate enrolment")
    p = s.program
    taken = db.scalar(
        select(func.count()).select_from(Student).where(Student.program_id == p.id, Student.seat_type == s.seat_type)
    )
    limit = p.approved_intake if s.seat_type == "Regular" else p.supernumerary_seats
    if taken > limit:
        warnings.append(f"{p.name}: {taken} {s.seat_type.lower()} admissions exceed the limit of {limit}")
    return warnings


# =============================================================================
# 4. LOGIN & SECURITY
# =============================================================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "role": user.role.value, "iat": now, "exp": now + timedelta(hours=TOKEN_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def user_from_token(token: str | None, db: Session) -> User:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in again", headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise error
    try:
        user_id = int(jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error
    user = db.get(User, user_id)
    if user is None:
        raise error
    return user


def current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return user_from_token(token, db)


def aicte_admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.aicte_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the AICTE admin can do this")
    return user


def current_institution(
    x_api_key: str | None = Header(default=None, description="Institution API key, for institution software (ERP)"),
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Institution:
    """An institution is identified EITHER by a logged-in institution user (the website)
    OR by its API key in the X-API-Key header (the institution's own software)."""
    if x_api_key:
        institution = db.scalar(select(Institution).where(Institution.api_key == x_api_key))
        if institution is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
        return institution
    user = user_from_token(token, db)
    if user.role != Role.institution or user.institution is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only institution accounts can do this")
    return user.institution


# =============================================================================
# 5. API: LOGIN
# =============================================================================
app = FastAPI(
    title=f"{APP_NAME} API",
    description="APAAR ID-based student data management and verification for AICTE-approved institutions. "
                "Institution software can call the /api/programs and /api/students endpoints with an X-API-Key header.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_URLS, allow_methods=["*"], allow_headers=["*"])


@app.post("/api/auth/token", tags=["login"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Log in with email (as `username`) and password. Returns a JWT token."""
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if user is None or not check_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer", "role": user.role.value}


@app.get("/api/auth/me", tags=["login"])
def me(user: User = Depends(current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "institution": institution_dict(user.institution) if user.institution else None,
    }


# =============================================================================
# 6. API: AICTE ADMIN
# =============================================================================
class InstitutionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=255)
    aicte_id: str = Field(min_length=3, max_length=50)
    state: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    login_email: EmailStr
    login_password: str = Field(min_length=6, max_length=72)


def institution_dict(i: Institution) -> dict:
    return {"id": i.id, "name": i.name, "aicte_id": i.aicte_id, "state": i.state, "city": i.city}


def build_overview(db: Session, institution_id: int | None = None) -> dict:
    """Numbers for the dashboards. Whole country for AICTE, one institution for an institution."""
    s_filter = [Student.institution_id == institution_id] if institution_id else []
    p_filter = [Program.institution_id == institution_id] if institution_id else []

    def count_students(*extra):
        return db.scalar(select(func.count()).select_from(Student).where(*s_filter, *extra))

    issues = compute_issues(db, institution_id)
    logs = db.scalars(select(UploadLog).where(*([UploadLog.institution_id == institution_id] if institution_id else []))).all()
    rejected = [e for log in logs for e in json.loads(log.errors_json)]

    overview = {
        "totals": {
            "institutions": 1 if institution_id else db.scalar(select(func.count()).select_from(Institution)),
            "programs": db.scalar(select(func.count()).select_from(Program).where(*p_filter)),
            "approved_intake": db.scalar(select(func.coalesce(func.sum(Program.approved_intake), 0)).where(*p_filter)),
            "supernumerary_seats": db.scalar(select(func.coalesce(func.sum(Program.supernumerary_seats), 0)).where(*p_filter)),
            "enrolled": count_students(),
            "enrolled_supernumerary": count_students(Student.seat_type == "Supernumerary"),
            "nri": count_students(Student.is_nri.is_(True)),
            "oci": count_students(Student.is_oci.is_(True)),
            "foreign_nationals": count_students(Student.is_foreign_national.is_(True)),
            "issues": len(issues),
            "rows_rejected": len(rejected),
            "rows_rejected_apaar": sum(
                1 for e in rejected if any("APAAR ID is missing" in m or "APAAR ID must be" in m for m in e["errors"])
            ),
        },
        "issues_by_type": [{"label": k, "count": v} for k, v in Counter(i["label"] for i in issues).most_common()],
        "by_category": [
            {"label": c, "count": n}
            for c, n in db.execute(
                select(Student.admission_category, func.count()).where(*s_filter).group_by(Student.admission_category)
            )
        ],
    }

    if institution_id is None:
        intake = dict(db.execute(select(Program.institution_id, func.sum(Program.approved_intake)).group_by(Program.institution_id)).all())
        enrolled = dict(db.execute(select(Student.institution_id, func.count()).group_by(Student.institution_id)).all())
        issue_count = Counter(i["institution_id"] for i in issues)
        overview["rows"] = [
            {**institution_dict(i), "approved_intake": intake.get(i.id, 0), "enrolled": enrolled.get(i.id, 0),
             "issues": issue_count[i.id]}
            for i in db.scalars(select(Institution).order_by(Institution.name))
        ]
    else:
        seats = defaultdict(Counter)
        for pid, seat_type, n in db.execute(
            select(Student.program_id, Student.seat_type, func.count()).where(*s_filter)
            .group_by(Student.program_id, Student.seat_type)
        ):
            seats[pid][seat_type] = n
        issue_count = Counter(i["program"] for i in issues)
        overview["rows"] = [
            {**program_dict(p), "enrolled": seats[p.id]["Regular"] + seats[p.id]["Supernumerary"],
             "enrolled_regular": seats[p.id]["Regular"], "enrolled_supernumerary": seats[p.id]["Supernumerary"],
             "issues": issue_count[f"{p.name} ({p.academic_year})"]}
            for p in db.scalars(select(Program).where(*p_filter).order_by(Program.academic_year.desc(), Program.name))
        ]
    return overview


@app.get("/api/admin/overview", tags=["AICTE admin"])
def admin_overview(db: Session = Depends(get_db), _: User = Depends(aicte_admin)):
    return build_overview(db)


@app.get("/api/admin/issues", tags=["AICTE admin"])
def admin_issues(db: Session = Depends(get_db), _: User = Depends(aicte_admin)):
    return compute_issues(db)


@app.get("/api/admin/institutions", tags=["AICTE admin"])
def list_institutions(db: Session = Depends(get_db), _: User = Depends(aicte_admin)):
    result = []
    for i in db.scalars(select(Institution).order_by(Institution.name)):
        result.append({**institution_dict(i), "login_email": i.users[0].email if i.users else None})
    return result


@app.post("/api/admin/institutions", status_code=status.HTTP_201_CREATED, tags=["AICTE admin"])
def add_institution(data: InstitutionIn, db: Session = Depends(get_db), _: User = Depends(aicte_admin)):
    """Adds an AICTE-approved institution and creates its login."""
    if db.scalar(select(Institution).where(Institution.aicte_id == data.aicte_id)):
        raise HTTPException(400, "An institution with this AICTE ID already exists")
    email = data.login_email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "This login email is already used")
    institution = Institution(name=data.name, aicte_id=data.aicte_id, state=data.state, city=data.city)
    db.add(institution)
    db.flush()
    db.add(User(email=email, hashed_password=hash_password(data.login_password), full_name=data.name,
                role=Role.institution, institution_id=institution.id))
    db.commit()
    return institution_dict(institution)


@app.get("/api/admin/students", tags=["AICTE admin"])
def admin_search_students(
    search: str = Query(default="", max_length=100), db: Session = Depends(get_db), _: User = Depends(aicte_admin)
):
    """Search all institutions by APAAR ID or name."""
    stmt = select(Student).order_by(Student.full_name).limit(200)
    if search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(Student.apaar_id.like(like) | Student.full_name.ilike(like))
    return [student_dict(s, with_institution=True) for s in db.scalars(stmt)]


# =============================================================================
# 7. API: INSTITUTION
# =============================================================================
class ProgramIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=150)
    level: Literal["UG", "PG", "Diploma"]
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2025-26"])
    approved_intake: int = Field(ge=1, le=5000)
    supernumerary_seats: int = Field(default=0, ge=0, le=1000)


def program_dict(p: Program) -> dict:
    return {"id": p.id, "name": p.name, "level": p.level, "academic_year": p.academic_year,
            "approved_intake": p.approved_intake, "supernumerary_seats": p.supernumerary_seats}


def student_dict(s: Student, with_institution: bool = False) -> dict:
    d = {
        "id": s.id, "apaar_id": s.apaar_id, "full_name": s.full_name, "gender": s.gender,
        "date_of_birth": s.date_of_birth, "program_id": s.program_id,
        "program": f"{s.program.name} ({s.program.academic_year})", "year_of_study": s.year_of_study,
        "admission_category": s.admission_category, "seat_type": s.seat_type, "is_nri": s.is_nri,
        "is_oci": s.is_oci, "is_foreign_national": s.is_foreign_national, "nationality": s.nationality,
        "email": s.email, "mobile": s.mobile, "source": s.source, "updated_at": s.updated_at,
    }
    if with_institution:
        d["institution"] = s.institution.name
    return d


@app.get("/api/institution/overview", tags=["institution"])
def institution_overview(db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    return build_overview(db, inst.id)


@app.get("/api/institution/issues", tags=["institution"])
def institution_issues(db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    return compute_issues(db, inst.id)


@app.get("/api/institution/api-key", tags=["institution"])
def get_api_key(inst: Institution = Depends(current_institution)):
    """The key the institution's own software (ERP) sends in the X-API-Key header."""
    return {"api_key": inst.api_key}


@app.post("/api/institution/api-key", tags=["institution"])
def regenerate_api_key(db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    """Makes a new key; the old one stops working immediately."""
    inst.api_key = new_api_key()
    db.commit()
    return {"api_key": inst.api_key}


# ---------- Programs (with approved intake) ----------
@app.get("/api/programs", tags=["institution"])
def list_programs(db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    stmt = select(Program).where(Program.institution_id == inst.id).order_by(Program.academic_year.desc(), Program.name)
    return [program_dict(p) for p in db.scalars(stmt)]


@app.post("/api/programs", status_code=status.HTTP_201_CREATED, tags=["institution"])
def add_program(data: ProgramIn, db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    exists = db.scalar(select(Program).where(
        Program.institution_id == inst.id, Program.name == data.name, Program.academic_year == data.academic_year))
    if exists:
        raise HTTPException(400, "This program already exists for that academic year")
    program = Program(institution_id=inst.id, **data.model_dump())
    db.add(program)
    db.commit()
    return program_dict(program)


@app.put("/api/programs/{program_id}", tags=["institution"])
def update_program(program_id: int, data: ProgramIn, db: Session = Depends(get_db),
                   inst: Institution = Depends(current_institution)):
    program = db.get(Program, program_id)
    if program is None or program.institution_id != inst.id:
        raise HTTPException(404, "Program not found")
    clash = db.scalar(select(Program).where(
        Program.institution_id == inst.id, Program.name == data.name,
        Program.academic_year == data.academic_year, Program.id != program_id))
    if clash:
        raise HTTPException(400, "Another program already has this name and academic year")
    for key, value in data.model_dump().items():
        setattr(program, key, value)
    db.commit()
    return program_dict(program)


@app.delete("/api/programs/{program_id}", tags=["institution"])
def delete_program(program_id: int, db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    program = db.get(Program, program_id)
    if program is None or program.institution_id != inst.id:
        raise HTTPException(404, "Program not found")
    if program.students:
        raise HTTPException(400, "Remove or move this program's students first")
    db.delete(program)
    db.commit()
    return {"deleted": True}


# ---------- Students: list, form/API add, edit, delete ----------
def own_program(db: Session, inst: Institution, program_id: int) -> Program:
    program = db.get(Program, program_id)
    if program is None or program.institution_id != inst.id:
        raise HTTPException(400, "Choose one of your own programs")
    return program


@app.get("/api/students", tags=["institution"])
def list_students(
    search: str = Query(default="", max_length=100),
    program_id: int | None = None,
    db: Session = Depends(get_db),
    inst: Institution = Depends(current_institution),
):
    stmt = select(Student).where(Student.institution_id == inst.id).order_by(Student.full_name).limit(1000)
    if program_id:
        stmt = stmt.where(Student.program_id == program_id)
    if search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(Student.apaar_id.like(like) | Student.full_name.ilike(like))
    return [student_dict(s) for s in db.scalars(stmt)]


@app.post("/api/students", status_code=status.HTTP_201_CREATED, tags=["institution"])
def add_student(
    data: StudentIn,
    x_api_key: str | None = Header(default=None, include_in_schema=False),
    db: Session = Depends(get_db),
    inst: Institution = Depends(current_institution),
):
    """Add one student (website form, or institution software using the API key)."""
    own_program(db, inst, data.program_id)
    if db.scalar(select(Student).where(Student.institution_id == inst.id, Student.apaar_id == data.apaar_id)):
        raise HTTPException(400, "A student with this APAAR ID already exists in your institution. Edit that record instead")
    student = Student(institution_id=inst.id, source="api" if x_api_key else "form", **data.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return {"student": student_dict(student), "warnings": student_warnings(db, student)}


@app.put("/api/students/{student_id}", tags=["institution"])
def update_student(student_id: int, data: StudentIn, db: Session = Depends(get_db),
                   inst: Institution = Depends(current_institution)):
    student = db.get(Student, student_id)
    if student is None or student.institution_id != inst.id:
        raise HTTPException(404, "Student not found")
    own_program(db, inst, data.program_id)
    clash = db.scalar(select(Student).where(
        Student.institution_id == inst.id, Student.apaar_id == data.apaar_id, Student.id != student_id))
    if clash:
        raise HTTPException(400, "Another student in your institution already has this APAAR ID")
    for key, value in data.model_dump().items():
        setattr(student, key, value)
    db.commit()
    db.refresh(student)
    return {"student": student_dict(student), "warnings": student_warnings(db, student)}


@app.delete("/api/students/{student_id}", tags=["institution"])
def delete_student(student_id: int, db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    student = db.get(Student, student_id)
    if student is None or student.institution_id != inst.id:
        raise HTTPException(404, "Student not found")
    db.delete(student)
    db.commit()
    return {"deleted": True}


# ---------- Students: Excel / CSV upload ----------
TEMPLATE_COLUMNS = [
    "apaar_id", "full_name", "gender", "date_of_birth", "program_name", "academic_year", "year_of_study",
    "admission_category", "seat_type", "nri", "oci", "foreign_national", "nationality", "email", "mobile",
]
TEMPLATE_EXAMPLE = [
    "123456789012", "Priya Sharma", "Female", "2005-08-21", "B.Tech Computer Science", "2025-26", "1",
    "General", "Regular", "No", "No", "No", "Indian", "priya@example.com", "9876543210",
]


@app.get("/api/students/template.csv", tags=["institution"])
def download_template():
    """Empty spreadsheet with the right columns and one example row. Opens in Excel."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(TEMPLATE_COLUMNS)
    writer.writerow(TEMPLATE_EXAMPLE)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="eduvaris_student_template.csv"'},
    )


def _header(value) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_spreadsheet(filename: str, content: bytes) -> list[dict]:
    name = filename.lower()
    if name.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        rows = []
        for raw in csv.DictReader(io.StringIO(text)):
            row = {_header(k): (v or "").strip() for k, v in raw.items() if k and isinstance(v, (str, type(None)))}
            if any(row.values()):
                rows.append(row)
        return rows
    if name.endswith(".xlsx"):
        try:
            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:
            raise HTTPException(400, "Could not read this Excel file")
        sheet_rows = workbook.active.iter_rows(values_only=True)
        headers = [_header(h) if h is not None else "" for h in next(sheet_rows, ())]
        rows = []
        for values in sheet_rows:
            row = {h: _cell(v) for h, v in zip(headers, values) if h}
            if any(row.values()):
                rows.append(row)
        workbook.close()
        return rows
    raise HTTPException(400, "Please upload a .xlsx (Excel) or .csv file")


def parse_date(text: str) -> date:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError


@app.post("/api/students/upload", tags=["institution"])
async def upload_students(
    file: UploadFile = File(..., description="Excel (.xlsx) or CSV file in the template format"),
    db: Session = Depends(get_db),
    inst: Institution = Depends(current_institution),
):
    """Bulk add/update students. Each row is checked; good rows are saved, bad rows are reported with reasons.
    A row whose APAAR ID already exists in your institution UPDATES that student."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"File is larger than {MAX_UPLOAD_MB} MB")
    rows = read_spreadsheet(file.filename or "", content)
    if not rows:
        raise HTTPException(400, "The file has no student rows")
    if len(rows) > MAX_UPLOAD_ROWS:
        raise HTTPException(400, f"Please upload at most {MAX_UPLOAD_ROWS} rows at a time")
    missing_columns = [c for c in ("apaar_id", "full_name", "program_name", "academic_year") if c not in rows[0]]
    if missing_columns:
        raise HTTPException(400, f"Missing columns: {', '.join(missing_columns)}. Download the template to see the format")

    programs = {(p.name.strip().lower(), p.academic_year): p for p in inst.programs}
    existing = {s.apaar_id: s for s in inst.students}
    first_seen: dict[str, int] = {}
    created = updated = 0
    failures = []

    for row_number, raw in enumerate(rows, start=2):  # row 1 is the header
        errors = []
        apaar = clean_apaar(raw.get("apaar_id"))
        if apaar and apaar in first_seen:
            errors.append(f"Duplicate APAAR ID in this file (also on row {first_seen[apaar]})")
        elif apaar:
            first_seen[apaar] = row_number

        program = programs.get(((raw.get("program_name") or "").strip().lower(), (raw.get("academic_year") or "").strip()))
        if program is None:
            errors.append(f"Program '{raw.get('program_name', '')}' for '{raw.get('academic_year', '')}' "
                          "not found. Add it under Programs first")

        dob = None
        try:
            dob = parse_date(raw.get("date_of_birth") or "")
        except ValueError:
            errors.append("date_of_birth must look like 2005-08-21 or 21-08-2005")

        flags = {}
        for column, field in (("nri", "is_nri"), ("oci", "is_oci"), ("foreign_national", "is_foreign_national")):
            value = (raw.get(column) or "").strip().lower()
            if value in YES_VALUES:
                flags[field] = True
            elif value in NO_VALUES:
                flags[field] = False
            else:
                errors.append(f"{column} must be Yes or No")

        data = {
            "apaar_id": raw.get("apaar_id"), "full_name": raw.get("full_name") or "",
            "gender": raw.get("gender") or "", "date_of_birth": dob, "program_id": program.id if program else 0,
            "year_of_study": raw.get("year_of_study") or None, "admission_category": raw.get("admission_category") or "",
            "seat_type": raw.get("seat_type") or "Regular", "nationality": raw.get("nationality") or "Indian",
            "email": raw.get("email"), "mobile": raw.get("mobile"), **flags,
        }
        student_in = None
        try:
            student_in = StudentIn.model_validate(data)
        except ValidationError as exc:
            for e in exc.errors():
                field = str(e["loc"][0]) if e["loc"] else ""
                if (field == "date_of_birth" and dob is None) or (field == "program_id" and program is None) or field in flags:
                    continue  # already reported above in plainer words
                errors.append(f"{field}: {e['msg'].removeprefix('Value error, ')}")

        if errors or student_in is None:
            failures.append({"row": row_number, "apaar_id": apaar or "(missing)", "errors": errors or ["Invalid row"]})
            continue

        values = student_in.model_dump()
        if student_in.apaar_id in existing:
            student = existing[student_in.apaar_id]
            for key, value in values.items():
                setattr(student, key, value)
            student.source = "file"
            updated += 1
        else:
            student = Student(institution_id=inst.id, source="file", **values)
            db.add(student)
            existing[student.apaar_id] = student
            created += 1

    db.add(UploadLog(institution_id=inst.id, filename=(file.filename or "upload")[:255], total_rows=len(rows),
                     created=created, updated=updated, failed=len(failures), errors_json=json.dumps(failures)))
    db.commit()
    return {
        "filename": file.filename, "total_rows": len(rows), "created": created, "updated": updated,
        "failed": len(failures), "errors": failures[:300], "issues_now": len(compute_issues(db, inst.id)),
    }


@app.get("/api/students/uploads", tags=["institution"])
def upload_history(db: Session = Depends(get_db), inst: Institution = Depends(current_institution)):
    logs = db.scalars(select(UploadLog).where(UploadLog.institution_id == inst.id)
                      .order_by(UploadLog.uploaded_at.desc()).limit(20))
    return [{"id": l.id, "filename": l.filename, "uploaded_at": l.uploaded_at, "total_rows": l.total_rows,
             "created": l.created, "updated": l.updated, "failed": l.failed} for l in logs]


# =============================================================================
# 8. API: PUBLIC VERIFICATION
# =============================================================================
@app.get("/api/verify/{apaar_id}", tags=["public"])
def verify_apaar(apaar_id: str, db: Session = Depends(get_db)):
    """Real-time check: is this APAAR ID enrolled at an AICTE-approved institution? Shows only a masked name."""
    apaar = clean_apaar(apaar_id)
    if not APAAR_RE.fullmatch(apaar):
        raise HTTPException(400, "APAAR ID must be exactly 12 digits")
    records = db.scalars(select(Student).where(Student.apaar_id == apaar)).all()
    if not records:
        raise HTTPException(404, "No enrolment found for this APAAR ID")
    return {
        "apaar_id": apaar,
        "student_name_masked": mask_name(records[0].full_name),
        "enrolments": [
            {"institution": r.institution.name, "aicte_id": r.institution.aicte_id, "program": r.program.name,
             "academic_year": r.program.academic_year, "year_of_study": r.year_of_study}
            for r in records
        ],
        "multiple_institutions": len({r.institution_id for r in records}) > 1,
    }


@app.get("/api/health", tags=["public"])
def health():
    return {"status": "ok", "app": APP_NAME}


# =============================================================================
# 9. DEMO DATA (all names and IDs are made up)
# =============================================================================
DEMO_INSTITUTIONS = [
    ("Sunrise Institute of Technology", "1-DEMO-1001", "Maharashtra", "Pune",
     [("B.Tech Computer Science", "UG", 12, 2), ("B.Tech Mechanical", "UG", 10, 1), ("MCA", "PG", 8, 1)]),
    ("Coastal College of Engineering", "1-DEMO-1002", "Karnataka", "Mangaluru",
     [("B.Tech Computer Science", "UG", 10, 2), ("B.Tech Civil", "UG", 8, 1)]),
    ("Northern Institute of Management", "1-DEMO-1003", "Delhi", "New Delhi",
     [("MBA", "PG", 15, 3), ("PGDM", "PG", 10, 2)]),
    ("Riverside Polytechnic", "1-DEMO-1004", "Tamil Nadu", "Coimbatore",
     [("Diploma Electrical", "Diploma", 10, 1), ("Diploma Civil", "Diploma", 8, 1)]),
]
FIRST_NAMES = ["Aarav", "Diya", "Kabir", "Ananya", "Rohan", "Isha", "Vivaan", "Meera", "Arjun", "Sara",
               "Aditya", "Kavya", "Reyansh", "Nisha", "Yash", "Pooja", "Om", "Tanvi", "Siddharth", "Riya"]
LAST_NAMES = ["Sharma", "Patil", "Iyer", "Khan", "Reddy", "Das", "Gupta", "Nair", "Joshi", "Singh", "Menon", "Kulkarni"]
FOREIGN = [("Nepalese", "Bikash Thapa"), ("Bangladeshi", "Farhan Rahman"), ("Kenyan", "Wanjiru Kamau"),
           ("Sri Lankan", "Nimal Perera")]
OCI = [("American", "Rahul Mehta"), ("British", "Anjali Shah")]
ACADEMIC_YEAR = "2025-26"


def seed() -> None:
    """Creates the AICTE admin and, if the database is empty, demo institutions with students.
    Some problems are added ON PURPOSE so the automatic checks have something to find."""
    rng = random.Random(2026)
    with SessionLocal() as db:
        if not db.scalar(select(User).where(User.email == ADMIN_EMAIL.lower())):
            db.add(User(email=ADMIN_EMAIL.lower(), hashed_password=hash_password(ADMIN_PASSWORD),
                        full_name=ADMIN_NAME, role=Role.aicte_admin))
            db.commit()

        if db.scalar(select(func.count()).select_from(Institution)):
            print("Demo data already exists, skipping it.")
        else:
            next_apaar = iter(range(700000000001, 800000000000))
            institutions = []
            for n, (name, aicte_id, state, city, programs) in enumerate(DEMO_INSTITUTIONS, start=1):
                inst = Institution(name=name, aicte_id=aicte_id, state=state, city=city)
                db.add(inst)
                db.flush()
                db.add(User(email=f"institution{n}@example.com", hashed_password=hash_password(DEMO_INSTITUTION_PASSWORD),
                            full_name=name, role=Role.institution, institution_id=inst.id))
                institutions.append(inst)
                for prog_name, level, intake, extra in programs:
                    prog = Program(institution_id=inst.id, name=prog_name, level=level, academic_year=ACADEMIC_YEAR,
                                   approved_intake=intake, supernumerary_seats=extra)
                    db.add(prog)
                    db.flush()
                    # Fill 70-100% of regular seats. Sunrise B.Tech CS gets 2 MORE than allowed (problem on purpose).
                    regular = intake + 2 if (n == 1 and prog_name == "B.Tech Computer Science") else rng.randint(intake * 7 // 10, intake)
                    for _ in range(regular):
                        db.add(_demo_student(rng, inst, prog, next(next_apaar)))
                    if extra:  # one supernumerary seat used: a foreign national or OCI student
                        nationality, full_name = rng.choice(FOREIGN + OCI)
                        is_oci = (nationality, full_name) in OCI
                        db.add(_demo_student(rng, inst, prog, next(next_apaar), seat_type="Supernumerary",
                                             full_name=full_name, nationality=nationality,
                                             is_oci=is_oci, is_foreign_national=not is_oci))
            db.flush()

            sunrise, coastal = institutions[0], institutions[1]
            coastal_cs = next(p for p in coastal.programs if p.name == "B.Tech Computer Science")
            sunrise_students = [s for s in sunrise.students if s.seat_type == "Regular"]
            # Problem on purpose: same student enrolled at two institutions.
            same = sunrise_students[0]
            db.add(_demo_student(rng, coastal, coastal_cs, int(same.apaar_id), full_name=same.full_name, dob=same.date_of_birth))
            # Problem on purpose: an APAAR ID reused with a different name and date of birth.
            db.add(_demo_student(rng, coastal, coastal_cs, int(sunrise_students[1].apaar_id), full_name="Vikram Rao"))
            # Problems on purpose: inconsistent data.
            sunrise_students[2].is_foreign_national = True  # foreign national, but nationality says Indian
            sunrise_students[3].is_nri = True
            sunrise_students[3].is_foreign_national = True
            sunrise_students[3].nationality = "Canadian"  # NRI and foreign national together
            db.commit()
            print("Demo data created.")

    print(f"\n{APP_NAME} is ready. Logins:")
    print(f"  AICTE admin : {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  Institution : institution1@example.com (to institution4@example.com) / {DEMO_INSTITUTION_PASSWORD}")


def _demo_student(rng, inst, prog, apaar, seat_type="Regular", full_name=None, dob=None,
                  nationality="Indian", is_oci=False, is_foreign_national=False) -> Student:
    return Student(
        institution_id=inst.id, program_id=prog.id, apaar_id=str(apaar),
        full_name=full_name or f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
        gender=rng.choice(["Male", "Female"]),
        date_of_birth=dob or date(2003, 1, 1) + timedelta(days=rng.randint(0, 1800)),
        year_of_study=1, admission_category=rng.choices(["General", "OBC", "SC", "ST", "EWS"], [45, 27, 13, 7, 8])[0],
        seat_type=seat_type, is_nri=False, is_oci=is_oci, is_foreign_national=is_foreign_national,
        nationality=nationality, source="file",
    )


# =============================================================================
# 10. START-UP
# =============================================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        seed()
    else:
        import uvicorn

        uvicorn.run("portal:app", app_dir=str(BASE_DIR), host="127.0.0.1", port=8000, reload=True)
