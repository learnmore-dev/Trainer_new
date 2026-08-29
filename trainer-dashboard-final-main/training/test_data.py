"""
Complete Test Data Script
Run: python manage.py shell < test_data.py
Ya shell mein paste karo
"""

import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trainer_monitoring.settings')

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta, datetime, time
import calendar, random

User = get_user_model()

# ─────────────── COLORS ───────────────
G = "\033[92m"  # green
Y = "\033[93m"  # yellow
R = "\033[91m"  # red
B = "\033[94m"  # blue
E = "\033[0m"   # reset

def ok(msg):  print(f"{G}  ✅ {msg}{E}")
def info(msg): print(f"{B}  ℹ️  {msg}{E}")
def warn(msg): print(f"{Y}  ⚠️  {msg}{E}")

print(f"\n{B}{'='*55}")
print("  TRAINER MONITORING — TEST DATA GENERATOR")
print(f"{'='*55}{E}\n")

# ─────────────── 1. USERS ───────────────
print(f"{Y}[1] Creating Users...{E}")

from training.models import Batch, WorkSession, TrainerAttendance, Leave

trainers_data = [
    {"username": "rahul_trainer",  "first_name": "Rahul",  "last_name": "Sharma",  "email": "rahul@test.com",  "password": "test@1234"},
    {"username": "priya_trainer",  "first_name": "Priya",  "last_name": "Gupta",   "email": "priya@test.com",  "password": "test@1234"},
    {"username": "amit_trainer",   "first_name": "Amit",   "last_name": "Verma",   "email": "amit@test.com",   "password": "test@1234"},
]

trainers = []
for td in trainers_data:
    u, created = User.objects.get_or_create(
        username=td["username"],
        defaults={
            "first_name": td["first_name"],
            "last_name":  td["last_name"],
            "email":      td["email"],
            "is_superuser": False,
            "is_staff":     False,
            "is_active":    True,
        }
    )
    if created:
        u.set_password(td["password"])
        u.save()
        ok(f"Trainer created: {u.get_full_name()} (@{u.username}) | Password: {td['password']}")
    else:
        warn(f"Already exists: @{u.username}")
    trainers.append(u)

# ─────────────── 2. BATCHES ───────────────
print(f"\n{Y}[2] Creating Batches...{E}")

batches_data = [
    {"name": "Python Full Stack — Batch 1", "trainer": trainers[0], "start_date": date(2026, 1, 5),  "total_hours": 120, "total_students": 22},
    {"name": "Django REST API — Batch 2",   "trainer": trainers[0], "start_date": date(2026, 2, 1),  "total_hours": 80,  "total_students": 18},
    {"name": "React & Node.js — Batch 1",   "trainer": trainers[1], "start_date": date(2026, 1, 10), "total_hours": 100, "total_students": 25},
    {"name": "Data Science — Batch 3",      "trainer": trainers[1], "start_date": date(2026, 2, 15), "total_hours": 90,  "total_students": 20},
    {"name": "Java Spring Boot — Batch 1",  "trainer": trainers[2], "start_date": date(2026, 1, 20), "total_hours": 110, "total_students": 15},
    {"name": "Flutter Mobile Dev — Batch 2","trainer": trainers[2], "start_date": date(2026, 3, 1),  "total_hours": 70,  "total_students": 12},
    {"name": "AWS Cloud — Batch 1",         "trainer": trainers[0], "start_date": date(2026, 3, 5),  "total_hours": 60,  "total_students": 10},
]

batches = []
for bd in batches_data:
    b, created = Batch.objects.get_or_create(
        name=bd["name"],
        trainer=bd["trainer"],
        defaults={
            "start_date":     bd["start_date"],
            "total_hours":    bd["total_hours"],
            "total_students": bd["total_students"],
            "is_active":      True,
        }
    )
    batches.append(b)
    if created:
        ok(f"Batch: '{b.name}' → {b.trainer.get_full_name()} ({b.total_hours}h, {b.total_students} students)")
    else:
        warn(f"Already exists: '{b.name}'")

# ─────────────── 3. WORK SESSIONS ───────────────
print(f"\n{Y}[3] Creating Work Sessions...{E}")

sessions_data = [
    # Batch 1 - Python
    {"batch": batches[0], "trainer": trainers[0], "days_ago": 45, "hours": 4, "desc": "Python basics — variables, loops, functions"},
    {"batch": batches[0], "trainer": trainers[0], "days_ago": 42, "hours": 5, "desc": "OOP concepts — classes, inheritance"},
    {"batch": batches[0], "trainer": trainers[0], "days_ago": 38, "hours": 6, "desc": "Django intro — models, views, templates"},
    {"batch": batches[0], "trainer": trainers[0], "days_ago": 35, "hours": 4, "desc": "REST API with Django REST Framework"},
    {"batch": batches[0], "trainer": trainers[0], "days_ago": 30, "hours": 8, "desc": "Project: E-commerce backend"},

    # Batch 2 - Django REST
    {"batch": batches[1], "trainer": trainers[0], "days_ago": 25, "hours": 5, "desc": "DRF serializers and viewsets"},
    {"batch": batches[1], "trainer": trainers[0], "days_ago": 20, "hours": 6, "desc": "Authentication — JWT tokens"},

    # Batch 3 - React
    {"batch": batches[2], "trainer": trainers[1], "days_ago": 40, "hours": 5, "desc": "React fundamentals — components, state"},
    {"batch": batches[2], "trainer": trainers[1], "days_ago": 36, "hours": 6, "desc": "Hooks — useState, useEffect, useContext"},
    {"batch": batches[2], "trainer": trainers[1], "days_ago": 30, "hours": 7, "desc": "Redux Toolkit state management"},
    {"batch": batches[2], "trainer": trainers[1], "days_ago": 25, "hours": 5, "desc": "Node.js + Express API integration"},

    # Batch 4 - Data Science
    {"batch": batches[3], "trainer": trainers[1], "days_ago": 20, "hours": 4, "desc": "Numpy & Pandas basics"},
    {"batch": batches[3], "trainer": trainers[1], "days_ago": 15, "hours": 5, "desc": "Data visualization — Matplotlib"},

    # Batch 5 - Java
    {"batch": batches[4], "trainer": trainers[2], "days_ago": 35, "hours": 6, "desc": "Spring Boot introduction"},
    {"batch": batches[4], "trainer": trainers[2], "days_ago": 28, "hours": 5, "desc": "JPA & Hibernate ORM"},
    {"batch": batches[4], "trainer": trainers[2], "days_ago": 20, "hours": 7, "desc": "Microservices architecture"},

    # Batch 6 - Flutter
    {"batch": batches[5], "trainer": trainers[2], "days_ago": 10, "hours": 4, "desc": "Flutter widgets & layouts"},
    {"batch": batches[5], "trainer": trainers[2], "days_ago": 5,  "hours": 5, "desc": "State management — Provider"},
]

for sd in sessions_data:
    sess_date = date.today() - timedelta(days=sd["days_ago"])
    ws, created = WorkSession.objects.get_or_create(
        batch=sd["batch"],
        trainer=sd["trainer"],
        session_date=sess_date,
        defaults={"hours_taken": sd["hours"], "description": sd["desc"]}
    )
    if created:
        ok(f"Session: {sd['batch'].name[:30]} | {sess_date} | {sd['hours']}h")

# ─────────────── 4. TRAINER ATTENDANCE ───────────────
print(f"\n{Y}[4] Creating Attendance Records (March 2026)...{E}")

def make_aware_time(d, h, m=0):
    from pytz import timezone as tz
    ist = tz('Asia/Kolkata')
    dt  = datetime.combine(d, time(h, m, 0))
    return ist.localize(dt)

today     = date.today()
month     = today.month
year      = today.year
num_days  = calendar.monthrange(year, month)[1]

attendance_patterns = {
    # trainer: list of (day, in_hour, out_hour)
    # out_hour < in_hour+5 = Leave, <9 = Half Day, >=9 = Present
    trainers[0]: [
        # Present days (9+ hours)
        (1,9,19),(2,9,18),(3,9,19),(4,9,18),(5,9,19),
        (6,9,18),(7,9,19),(8,9,18),(10,9,19),(11,9,18),
        (12,9,19),(13,9,18),(14,9,19),(15,9,18),(17,9,19),
        (18,9,18),
        # Half day (5-9 hours)
        (9,10,15),(16,9,14),
        # Leave (< 5 hours)
        (19,9,11),
    ],
    trainers[1]: [
        # Present
        (1,9,18),(2,9,19),(3,9,18),(4,9,19),(5,9,18),
        (7,9,19),(8,9,18),(10,9,19),(11,9,18),(12,9,19),
        (13,9,18),(14,9,19),(15,9,18),(17,9,19),(18,9,18),
        (19,9,18),
        # Half day
        (6,10,15),(9,9,14),
    ],
    trainers[2]: [
        # Present
        (1,9,18),(2,9,19),(3,9,18),(4,9,19),(5,9,18),
        (6,9,19),(7,9,18),(8,9,19),(10,9,18),(11,9,19),
        (12,9,18),(13,9,19),(14,9,18),(15,9,19),
        # Half day
        (16,10,15),(17,9,14),
        # Leave
        (18,9,12),
        (19,9,18),
    ],
}

for trainer, days in attendance_patterns.items():
    for (day, in_h, out_h) in days:
        try:
            att_date = date(year, month, day)
            if att_date > today:
                continue

            mark_in  = make_aware_time(att_date, in_h)
            mark_out = make_aware_time(att_date, out_h)
            duration = mark_out - mark_in
            total_h  = duration.total_seconds() / 3600

            if total_h < 5:
                day_status = 'leave'
            elif total_h < 9:
                day_status = 'half_day'
            else:
                day_status = 'present'

            att, created = TrainerAttendance.objects.get_or_create(
                trainer=trainer,
                date=att_date,
                defaults={
                    "mark_in_time":    mark_in,
                    "mark_out_time":   mark_out,
                    "working_duration": duration,
                    "latitude":  "18.5204",
                    "longitude": "73.8567",
                    "location_name": "Hinjewadi, Pune, Maharashtra",
                    "day_status": day_status,
                }
            )
            if created:
                ok(f"{trainer.username} | {att_date} | {in_h}:00–{out_h}:00 ({total_h:.0f}h) → {day_status}")
        except Exception as e:
            warn(f"Attendance skip: {trainer.username} day={day} — {e}")

# ─────────────── 5. LEAVE APPLICATIONS ───────────────
print(f"\n{Y}[5] Creating Leave Applications...{E}")

leaves_data = [
    # (trainer, days_from_today, type, reason, status)
    (trainers[0], 3,   "sick",      "Fever aur sardi hai, doctor ne rest lene kaha.",                 "pending"),
    (trainers[0], -5,  "casual",    "Family function tha ghar mein, isliye chutti li.",               "approved"),
    (trainers[1], 7,   "emergency", "Ghar pe emergency thi, immediate jana pada.",                    "approved"),
    (trainers[1], -10, "sick",      "Migraine ki problem thi, kaam nahi ho raha tha.",                "rejected"),
    (trainers[1], 2,   "casual",    "Personal kaam ke liye chutti chahiye.",                          "pending"),
    (trainers[2], -3,  "sick",      "Viral fever tha, 2 din rest kiya.",                              "approved"),
    (trainers[2], 5,   "other",     "Government kaam ke liye office jana hai.",                       "pending"),
]

for (trainer, days_offset, ltype, reason, status) in leaves_data:
    leave_date = today + timedelta(days=days_offset)
    l, created = Leave.objects.get_or_create(
        trainer=trainer,
        leave_date=leave_date,
        defaults={
            "leave_type": ltype,
            "reason":     reason,
            "status":     status,
        }
    )
    if created:
        ok(f"Leave: {trainer.username} | {leave_date} | {ltype} | {status}")
    else:
        warn(f"Leave already exists: {trainer.username} on {leave_date}")

# ─────────────── SUMMARY ───────────────
print(f"\n{B}{'='*55}")
print("  TEST DATA SUMMARY")
print(f"{'='*55}{E}")

print(f"""
{G}Trainers created:{E}
  • rahul_trainer  (Rahul Sharma)  — password: test@1234
  • priya_trainer  (Priya Gupta)   — password: test@1234
  • amit_trainer   (Amit Verma)    — password: test@1234

{G}Batches:{E}     {Batch.objects.count()} total
{G}Sessions:{E}    {WorkSession.objects.count()} total
{G}Attendance:{E}  {TrainerAttendance.objects.count()} records
{G}Leaves:{E}      {Leave.objects.count()} applications
  • Pending:  {Leave.objects.filter(status='pending').count()}
  • Approved: {Leave.objects.filter(status='approved').count()}
  • Rejected: {Leave.objects.filter(status='rejected').count()}

{Y}Test karne ke liye:{E}
  • Login: http://localhost:8000/login/
  • Admin: http://localhost:8000/admin/
  • Admin Dashboard: http://localhost:8000/training/admin-dashboard/
  • Leave List:      http://localhost:8000/training/admin/leaves/
  • User List:       http://localhost:8000/training/admin/users/
  • Batch List:      http://localhost:8000/training/admin/batches/
  • Monthly Report:  http://localhost:8000/training/monthly-attendance-report/

{G}Attendance Status check:{E}
  • < 5 hours  → 🔴 Leave
  • 5-9 hours  → 🟡 Half Day
  • 9+ hours   → 🟢 Present
""")

print(f"{G}✅ All test data created successfully!{E}\n")