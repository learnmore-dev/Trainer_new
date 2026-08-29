from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import get_user_model, logout
from django.db.models import Q, Count
from django.contrib.auth.views import LogoutView
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings as django_settings
from .models import (Batch, WorkSession, Attendance, TrainerAttendance, Leave,
                     OPTIONAL_HOLIDAYS_2026, MANDATORY_HOLIDAYS_2026,
                     OPTIONAL_HOLIDAY_LIMIT_PER_YEAR, CASUAL_LEAVE_LIMIT_PER_MONTH)
import json
import calendar
from datetime import datetime, timedelta, date

from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

# ==================== HOME REDIRECT ====================

@login_required
def home_redirect(request):
    """Redirect superuser to admin dashboard, normal users to trainer dashboard"""
    if request.user.is_superuser:
        return redirect('training:admin_dashboard')
    else:
        return redirect('training:trainer_dashboard')

def get_hours_breakdown(trainer, target_date):
    sessions = WorkSession.objects.filter(
        trainer=trainer,
        session_date=target_date
    ).select_related('batch')
    class_hours = 0.0
    other_hours = 0.0
    for s in sessions:
        if hasattr(s.batch, 'batch_type') and s.batch.batch_type == 'other':
            other_hours += s.hours_taken
        else:
            class_hours += s.hours_taken
    return round(class_hours, 1), round(other_hours, 1)


def get_hours_breakdown_range(trainer, from_date, to_date):
    sessions = WorkSession.objects.filter(
        trainer=trainer,
        session_date__gte=from_date,
        session_date__lte=to_date
    ).select_related('batch')
    class_hours = 0.0
    other_hours = 0.0
    for s in sessions:
        if hasattr(s.batch, 'batch_type') and s.batch.batch_type == 'other':
            other_hours += s.hours_taken
        else:
            class_hours += s.hours_taken
    return round(class_hours, 1), round(other_hours, 1)


# ==================== INCENTIVE CALCULATION ====================

def get_working_days(month, year):
    total_days = calendar.monthrange(year, month)[1]
    working_days = 0
    for day in range(1, total_days + 1):
        if date(year, month, day).weekday() != 6:
            working_days += 1
    return working_days


def get_attendance_percentage(user, month, year):
    working_days = get_working_days(month, year)
    present_days = TrainerAttendance.objects.filter(
        trainer=user,
        date__month=month,
        date__year=year,
        mark_out_time__isnull=False
    ).exclude(date__week_day=1).count()
    return round((present_days / working_days) * 100, 2) if working_days else 0


def get_monthly_new_batches(user, month, year):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return Batch.objects.filter(
        trainer=user,
        start_date__gte=start,
        start_date__lt=end
    ).count()


def calculate_incentive(user, month, year):
    working_days = get_working_days(month, year)
    present_days = TrainerAttendance.objects.filter(
        trainer=user,
        date__month=month,
        date__year=year,
        mark_out_time__isnull=False
    ).exclude(date__week_day=1).count()
    attendance_percent = (present_days / working_days) * 100 if working_days else 0
    is_attendance_eligible = attendance_percent >= 90
    batch_count = get_monthly_new_batches(user, month, year)
    extra_batch = max(0, batch_count - 5)
    batch_bonus = extra_batch * 1000 if is_attendance_eligible else 0
    return {
        "attendance_percent": round(attendance_percent, 2),
        "present_days": present_days,
        "working_days": working_days,
        "is_attendance_eligible": is_attendance_eligible,
        "batch_count": batch_count,
        "extra_batches": extra_batch,
        "batch_bonus": batch_bonus,
        "total_incentive": batch_bonus,
    }


# ==================== TIMEZONE FUNCTIONS ====================

def get_indian_time():
    from pytz import timezone as tz
    try:
        indian_tz = tz('Asia/Kolkata')
        return datetime.now(indian_tz)
    except Exception:
        return timezone.now()


def convert_to_indian_time(utc_time):
    from pytz import timezone as tz
    if utc_time:
        try:
            indian_tz = tz('Asia/Kolkata')
            return utc_time.astimezone(indian_tz)
        except Exception:
            return utc_time
    return None


def convert_string_to_utc(date_time_str):
    try:
        local_dt = datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
        from pytz import timezone as tz
        indian_tz = tz('Asia/Kolkata')
        utc_tz = tz('UTC')
        localized_dt = indian_tz.localize(local_dt)
        return localized_dt.astimezone(utc_tz)
    except Exception as e:
        print(f"Time conversion error: {e}")
        return timezone.now()


# ==================== ATTENDANCE HELPER ====================

def check_today_login(user):
    today = timezone.now().date()
    today_attendances = Attendance.objects.filter(
        user=user,
        login_time__date=today
    ).order_by('-login_time')
    for attendance in today_attendances:
        if attendance.logout_time is None:
            return attendance
    return None


# ==================== LEAVE QUOTA HELPERS ====================

def get_optional_holiday_used(user, year):
    return Leave.objects.filter(
        trainer=user,
        leave_type='optional_holiday',
        leave_date__year=year,
    ).exclude(status='rejected').count()


def get_casual_leave_used_this_month(user, month, year):
    return Leave.objects.filter(
        trainer=user,
        leave_type='casual',
        leave_date__month=month,
        leave_date__year=year,
    ).exclude(status='rejected').count()


# ==================== LEAVE QUOTA API ====================

@login_required
def leave_quota_api(request):
    year  = date.today().year
    month = date.today().month
    used  = get_optional_holiday_used(request.user, year)
    remaining = max(0, OPTIONAL_HOLIDAY_LIMIT_PER_YEAR - used)

    taken_dates = list(
        Leave.objects.filter(
            trainer=request.user,
            leave_type='optional_holiday',
            leave_date__year=year,
        ).exclude(status='rejected').values_list('leave_date', flat=True)
    )
    taken_str = [d.strftime('%Y-%m-%d') for d in taken_dates]

    # Which mandatory holidays already applied
    man_taken = list(
        Leave.objects.filter(
            trainer=request.user,
            leave_type='mandatory_holiday',
            leave_date__year=year,
        ).exclude(status='rejected').values_list('leave_date', flat=True)
    )
    man_taken_str = [d.strftime('%Y-%m-%d') for d in man_taken]

    casual_used = get_casual_leave_used_this_month(request.user, month, year)
    casual_remaining = max(0, CASUAL_LEAVE_LIMIT_PER_MONTH - casual_used)

    return JsonResponse({
        'optional_used':        used,
        'optional_remaining':   remaining,
        'optional_limit':       OPTIONAL_HOLIDAY_LIMIT_PER_YEAR,
        'optional_taken_dates': taken_str,
        'mandatory_taken_dates': man_taken_str,
        'casual_used':          casual_used,
        'casual_remaining':     casual_remaining,
        'casual_limit':         CASUAL_LEAVE_LIMIT_PER_MONTH,
        'optional_holidays':    OPTIONAL_HOLIDAYS_2026,
        'mandatory_holidays':   MANDATORY_HOLIDAYS_2026,
    })


# ==================== LEAVE BALANCE VIEW ====================

@login_required
def leave_balance_view(request):
    """Shows leave balance for all users (admin) or just current user (trainer)"""
    User = get_user_model()
    year = date.today().year
    month = date.today().month

    if request.user.is_superuser:
        users = User.objects.filter(is_active=True, is_superuser=False).order_by('first_name')
    else:
        users = [request.user]

    balance_data = []

    for user in users:
        # ── Optional Holiday balance ──
        opt_used = get_optional_holiday_used(user, year)
        opt_remaining = max(0, OPTIONAL_HOLIDAY_LIMIT_PER_YEAR - opt_used)

        # Which optional holidays taken (approved)
        opt_taken_leaves = Leave.objects.filter(
            trainer=user,
            leave_type='optional_holiday',
            leave_date__year=year,
        ).exclude(status='rejected').order_by('leave_date')

        # Which mandatory holidays taken
        man_taken_leaves = Leave.objects.filter(
            trainer=user,
            leave_type='mandatory_holiday',
            leave_date__year=year,
        ).exclude(status='rejected').order_by('leave_date')

        # ── Casual leave this month ──
        casual_used_month = get_casual_leave_used_this_month(user, month, year)
        casual_remaining_month = max(0, CASUAL_LEAVE_LIMIT_PER_MONTH - casual_used_month)

        # ── Sick leave count this year ──
        sick_used = Leave.objects.filter(
            trainer=user,
            leave_type='sick',
            leave_date__year=year,
        ).exclude(status='rejected').count()

        # ── Emergency leave count this year ──
        emergency_used = Leave.objects.filter(
            trainer=user,
            leave_type='emergency',
            leave_date__year=year,
        ).exclude(status='rejected').count()

        # ── Week off count this year ──
        weekoff_used = Leave.objects.filter(
            trainer=user,
            leave_type='weekoff',
            leave_date__year=year,
        ).exclude(status='rejected').count()

        # ── All leaves this year for history ──
        all_leaves = Leave.objects.filter(
            trainer=user,
            leave_date__year=year,
        ).order_by('-leave_date')

        balance_data.append({
            'user': user,
            'opt_used': opt_used,
            'opt_remaining': opt_remaining,
            'opt_limit': OPTIONAL_HOLIDAY_LIMIT_PER_YEAR,
            'opt_taken_leaves': list(opt_taken_leaves),
            'man_taken_leaves': list(man_taken_leaves),
            'man_total': len(MANDATORY_HOLIDAYS_2026),
            'casual_used_month': casual_used_month,
            'casual_remaining_month': casual_remaining_month,
            'casual_limit': CASUAL_LEAVE_LIMIT_PER_MONTH,
            'sick_used': sick_used,
            'emergency_used': emergency_used,
            'weekoff_used': weekoff_used,
            'all_leaves': list(all_leaves),
        })

    return render(request, 'training/leave_balance.html', {
        'balance_data': balance_data,
        'year': year,
        'month_name': calendar.month_name[month],
        'is_admin': request.user.is_superuser,
        'opt_holidays': OPTIONAL_HOLIDAYS_2026,
        'man_holidays': MANDATORY_HOLIDAYS_2026,
    })


# ==================== LEAVE CREATE ====================

@login_required
def leave_create(request):
    today     = date.today()
    my_leaves = Leave.objects.filter(trainer=request.user).order_by('-leave_date')
    year      = today.year
    month     = today.month

    if request.method == 'POST':
        leave_date_str = request.POST.get('leave_date', '').strip()
        leave_type     = request.POST.get('leave_type', '').strip()
        reason         = request.POST.get('reason', '').strip()
        holiday_name   = request.POST.get('holiday_name', '').strip()

        valid_types = [t[0] for t in Leave.LEAVE_TYPE_CHOICES]
        if not leave_date_str or not leave_type or not reason:
            messages.error(request, 'Please fill all required fields.')
            return _render_leave(request, today, my_leaves)

        if leave_type not in valid_types:
            messages.error(request, 'Invalid leave type selected.')
            return _render_leave(request, today, my_leaves)

        try:
            leave_date = datetime.strptime(leave_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return _render_leave(request, today, my_leaves)

        # Duplicate check
        if Leave.objects.filter(trainer=request.user, leave_date=leave_date).exists():
            messages.error(request, f'You already have a leave application for {leave_date.strftime("%d %b %Y")}.')
            return _render_leave(request, today, my_leaves)

        # Optional Holiday — limit 5 per year + must be from official list
        if leave_type == 'optional_holiday':
            used = get_optional_holiday_used(request.user, leave_date.year)
            if used >= OPTIONAL_HOLIDAY_LIMIT_PER_YEAR:
                messages.error(request,
                    f'❌ You have used all {OPTIONAL_HOLIDAY_LIMIT_PER_YEAR} optional holidays for {leave_date.year}.')
                return _render_leave(request, today, my_leaves)
            # Validate date is in official list
            valid_opt_dates = [h[0] for h in OPTIONAL_HOLIDAYS_2026]
            if leave_date_str not in valid_opt_dates:
                messages.error(request, '❌ Selected date is not in the official Optional Holiday list.')
                return _render_leave(request, today, my_leaves)
            # Auto-fill holiday name from list
            for hdate, hname in OPTIONAL_HOLIDAYS_2026:
                if hdate == leave_date_str:
                    holiday_name = hname
                    break

        # Mandatory Holiday — must be from official list
        if leave_type == 'mandatory_holiday':
            valid_man_dates = [h[0] for h in MANDATORY_HOLIDAYS_2026]
            if leave_date_str not in valid_man_dates:
                messages.error(request, '❌ Selected date is not in the official Mandatory Holiday list.')
                return _render_leave(request, today, my_leaves)
            for hdate, hname in MANDATORY_HOLIDAYS_2026:
                if hdate == leave_date_str:
                    holiday_name = hname
                    break

        # Casual Leave — limit 1 per month
        if leave_type == 'casual':
            casual_used = get_casual_leave_used_this_month(
                request.user, leave_date.month, leave_date.year)
            if casual_used >= CASUAL_LEAVE_LIMIT_PER_MONTH:
                messages.error(request,
                    f'❌ You have already used your Casual Leave for {leave_date.strftime("%B %Y")}. '
                    f'Only {CASUAL_LEAVE_LIMIT_PER_MONTH} casual leave per month allowed.')
                return _render_leave(request, today, my_leaves)

        # Week Off warning
        if leave_type == 'weekoff' and leave_date.weekday() != 6:
            messages.warning(request, '⚠️ Week Off is typically on Sundays. Admin will review.')

        # Save
        leave = Leave.objects.create(
            trainer      = request.user,
            leave_date   = leave_date,
            leave_type   = leave_type,
            holiday_name = holiday_name,
            reason       = reason,
            status       = 'pending'
        )

        # Email admins
        User = get_user_model()
        admin_emails = list(
            User.objects.filter(is_superuser=True, is_active=True)
            .exclude(email='').values_list('email', flat=True)
        )
        trainer_name = request.user.get_full_name() or request.user.username
        type_display = leave.get_leave_type_display()
        if holiday_name:
            type_display += f' ({holiday_name})'

        if admin_emails:
            try:
                send_mail(
                    subject=f'🗓️ Leave Application — {trainer_name} | {leave_date.strftime("%d %b %Y")}',
                    message=f'Trainer: {trainer_name}\nDate: {leave_date.strftime("%d %B %Y")}\nType: {type_display}\nReason: {reason}\nStatus: Pending',
                    from_email=django_settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Email error: {e}")

        messages.success(request,
            f'✅ Leave submitted for {leave_date.strftime("%d %b %Y")} ({type_display}).')
        return redirect('training:leave_create')

    return _render_leave(request, today, my_leaves)


def _render_leave(request, today, my_leaves):
    return render(request, 'training/leave_create.html', {
        'today':     today,
        'my_leaves': my_leaves,
    })


# ==================== ATTENDANCE VIEWS ====================

@login_required
def attendance_home(request):
    today_login = check_today_login(request.user)
    if today_login:
        login_time_indian = convert_to_indian_time(today_login.login_time)
        login_time_str = login_time_indian.strftime('%H:%M:%S') if login_time_indian else None
    else:
        login_time_str = None
    context = {
        'already_logged_in': today_login is not None,
        'login_time': login_time_str,
        'login_address': today_login.login_address if today_login else None,
    }
    return render(request, 'training/attendance.html', context)


@login_required
def login_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lon = data.get('lon')
            address = data.get('address', '')
            dateTime = data.get('dateTime', '')
            today_login = check_today_login(request.user)
            if today_login:
                login_time_indian = convert_to_indian_time(today_login.login_time)
                login_time_str = login_time_indian.strftime('%H:%M:%S') if login_time_indian else None
                return JsonResponse({'status': 'error', 'error': f'Already logged in today at {login_time_str}'})
            if dateTime:
                utc_login_time = convert_string_to_utc(dateTime)
            else:
                utc_login_time = timezone.now()
                dateTime = get_indian_time().strftime('%H:%M:%S')
            attendance = Attendance.objects.create(
                user=request.user, login_time=utc_login_time,
                login_lat=lat, login_lon=lon, login_address=address
            )
            time_part = dateTime.split(' ')[1] if ' ' in dateTime else dateTime
            return JsonResponse({'status': 'success', 'login_time': time_part, 'address': address})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Invalid request'})


@login_required
def logout_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('lat')
            lon = data.get('lon')
            address = data.get('address', '')
            dateTime = data.get('dateTime', '')
            attendance = check_today_login(request.user)
            if attendance:
                if dateTime:
                    utc_logout_time = convert_string_to_utc(dateTime)
                else:
                    utc_logout_time = timezone.now()
                    dateTime = get_indian_time().strftime('%H:%M:%S')
                attendance.logout_time = utc_logout_time
                attendance.logout_lat = lat
                attendance.logout_lon = lon
                attendance.logout_address = address
                if attendance.login_time and attendance.logout_time:
                    from pytz import timezone as tz
                    utc_tz = tz('UTC')
                    if attendance.login_time.tzinfo is None:
                        attendance.login_time = utc_tz.localize(attendance.login_time)
                    if attendance.logout_time.tzinfo is None:
                        attendance.logout_time = utc_tz.localize(attendance.logout_time)
                    attendance.total_time = attendance.logout_time - attendance.login_time
                attendance.save()
                if attendance.total_time:
                    total_seconds = attendance.total_time.total_seconds()
                    total_time_str = f"{int(total_seconds // 3600)}h {int((total_seconds % 3600) // 60)}m"
                else:
                    total_time_str = "0h 0m"
                time_part = dateTime.split(' ')[1] if ' ' in dateTime else dateTime
                return JsonResponse({'status': 'success', 'logout_time': time_part, 'total_time': total_time_str})
            else:
                return JsonResponse({'status': 'error', 'error': 'No active login found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Invalid request'})


# ==================== DASHBOARD VIEWS ====================

@login_required
def trainer_dashboard(request):
    trainer = request.user
    batches = Batch.objects.all() if request.user.is_superuser else Batch.objects.filter(trainer=trainer)
    recent_sessions = WorkSession.objects.filter(trainer=trainer).order_by('-session_date')[:10]
    total_worked_hours = sum(s.hours_taken for s in WorkSession.objects.filter(trainer=trainer))
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    weekly_hours = sum(s.hours_taken for s in WorkSession.objects.filter(
        trainer=trainer, session_date__gte=start_of_week))
    attendance_status = check_today_login(trainer)
    now = timezone.now()
    incentive_data = calculate_incentive(trainer, now.month, now.year)

    # Leave summary for dashboard
    year = today.year
    month = today.month
    recent_leaves = Leave.objects.filter(trainer=trainer).order_by('-leave_date')[:5]
    opt_used = get_optional_holiday_used(trainer, year)
    opt_remaining = max(0, OPTIONAL_HOLIDAY_LIMIT_PER_YEAR - opt_used)
    casual_used = get_casual_leave_used_this_month(trainer, month, year)
    casual_remaining = max(0, CASUAL_LEAVE_LIMIT_PER_MONTH - casual_used)

    context = {
        'batches': batches,
        'sessions': recent_sessions,
        'total_hours': total_worked_hours,
        'hours_week': weekly_hours,
        'attendance_status': attendance_status,
        'incentive': incentive_data,
        'recent_leaves': recent_leaves,
        'opt_used': opt_used,
        'opt_remaining': opt_remaining,
        'opt_limit': OPTIONAL_HOLIDAY_LIMIT_PER_YEAR,
        'casual_used': casual_used,
        'casual_remaining': casual_remaining,
        'casual_limit': CASUAL_LEAVE_LIMIT_PER_MONTH,
    }
    return render(request, 'training/trainer_dashboard.html', context)


@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect('trainer_dashboard')
    User = get_user_model()
    batches = Batch.objects.select_related('trainer').all()
    trainers = User.objects.filter(batches__isnull=False).distinct()
    trainer_filter = request.GET.get('trainer')
    if trainer_filter and trainer_filter != 'all':
        batches = batches.filter(trainer_id=trainer_filter)
    total_sessions = WorkSession.objects.count()
    context = {
        'batches': batches,
        'trainers': trainers,
        'total_sessions': total_sessions,
        'selected_trainer': trainer_filter,
    }
    return render(request, 'training/admin_dashboard.html', context)


# ==================== BATCH VIEWS ====================

@login_required
def batch_list(request):
    batches = Batch.objects.all() if request.user.is_superuser else Batch.objects.filter(trainer=request.user)
    return render(request, 'training/batch_list.html', {'batches': batches})


@login_required
def batch_detail(request, batch_id):
    batch = get_object_or_404(Batch, id=batch_id)
    if not request.user.is_superuser and batch.trainer != request.user:
        return redirect('batch_list')
    sessions = batch.sessions.all().order_by('-session_date')
    used_hours = sum(session.hours_taken for session in sessions)
    remaining_hours = batch.total_hours - used_hours
    context = {
        'batch': batch,
        'sessions': sessions,
        'used_hours': round(used_hours, 2),
        'remaining_hours': round(remaining_hours, 2),
        'delay_hours': abs(remaining_hours) if remaining_hours < 0 else 0,
    }
    return render(request, 'training/batch_detail.html', context)


@login_required
def trainer_batch_list(request):
    batches = Batch.objects.filter(trainer=request.user)
    return render(request, 'training/batch_list.html', {'batches': batches})


# ==================== SESSION VIEWS ====================

@login_required
def session_create(request, batch_id=None):
    batches = Batch.objects.all() if request.user.is_superuser else Batch.objects.filter(trainer=request.user)
    selected_batch = None
    if batch_id:
        selected_batch = get_object_or_404(Batch, id=batch_id)
        if not request.user.is_superuser and selected_batch.trainer != request.user:
            return render(request, 'training/session_form.html', {'error': 'Permission denied', 'batches': batches})

    if request.method == 'POST':
        batch_id_post = request.POST.get('batch')
        session_date = request.POST.get('session_date')
        hours_taken = request.POST.get('hours_taken')
        description = request.POST.get('description', '')
        try:
            batch = get_object_or_404(Batch, id=batch_id_post)
            if not request.user.is_superuser and batch.trainer != request.user:
                return render(request, 'training/session_form.html', {'error': 'Permission denied', 'batches': batches})
            WorkSession.objects.create(
                trainer=request.user,
                batch=batch,
                session_date=datetime.strptime(session_date, '%Y-%m-%d').date(),
                hours_taken=float(hours_taken),
                description=description
            )
            return redirect('training:batch_detail', batch_id=batch.id)
        except Exception as e:
            return render(request, 'training/session_form.html', {'error': str(e), 'batches': batches, 'selected_batch': selected_batch})

    return render(request, 'training/session_form.html', {'batches': batches, 'selected_batch': selected_batch})


def session_form(request, batch_id=None):
    return session_create(request, batch_id)


# ==================== TRAINER ATTENDANCE VIEWS ====================

@login_required
def trainer_attendance_page(request):
    now = timezone.now()
    latest = TrainerAttendance.objects.filter(trainer=request.user).order_by('-date').first()
    if latest:
        context = {'current_month': latest.date.month, 'current_year': latest.date.year}
    else:
        context = {'current_month': now.month, 'current_year': now.year}
    return render(request, "training/attendance_page.html", context)


def trainer_attendance(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=405)
    action   = request.POST.get("attendance")
    photo    = request.FILES.get("photo")
    lat      = request.POST.get("latitude")
    lng      = request.POST.get("longitude")
    accuracy = request.POST.get("accuracy")
    location_name = request.POST.get("location_name", "").strip() or f"{lat}, {lng}"
    if accuracy and float(accuracy) > 500:
        return JsonResponse({"error": "Fake GPS detected"}, status=403)
    if not action or not lat or not lng:
        return JsonResponse({"error": "Missing data"}, status=400)
    user  = request.user
    today = timezone.localdate()
    attendance, created = TrainerAttendance.objects.get_or_create(trainer=user, date=today)
    if action == "mark_in":
        if attendance.mark_in_time:
            return JsonResponse({"error": "Already marked in today"}, status=400)
        attendance.mark_in_time  = timezone.now()
        attendance.photo_in      = photo
        attendance.latitude      = lat
        attendance.longitude     = lng
        attendance.location_name = location_name
        attendance.save()
        return JsonResponse({"status": "Marked In", "time": timezone.localtime(attendance.mark_in_time).strftime("%H:%M:%S"), "location": location_name})
    if action == "mark_out":
        if not attendance.mark_in_time:
            return JsonResponse({"error": "Mark in first"}, status=400)
        if attendance.mark_out_time:
            return JsonResponse({"error": "Already marked out"}, status=400)
        attendance.mark_out_time = timezone.now()
        attendance.photo_out     = photo
        attendance.location_name = location_name
        duration = attendance.mark_out_time - attendance.mark_in_time
        attendance.working_duration = duration
        total_hours = duration.total_seconds() / 3600
        if total_hours < 5:
            attendance.day_status = 'leave'
            status_label = '🔴 Leave (5 hours se kam)'
        elif total_hours < 9:
            attendance.day_status = 'half_day'
            status_label = '🟡 Half Day (5-9 hours)'
        else:
            attendance.day_status = 'present'
            status_label = '🟢 Present (9+ hours)'
        attendance.save()
        hours   = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        return JsonResponse({"status": "Marked Out", "time": timezone.localtime(attendance.mark_out_time).strftime("%H:%M:%S"),
            "working_hours": f"{hours}h {minutes}m", "location": location_name,
            "day_status": attendance.day_status, "day_status_label": status_label})
    return JsonResponse({"error": "Invalid action"}, status=400)


@login_required
def attendance_history(request):
    now = timezone.now()
    month = int(request.GET.get('month', now.month))
    year  = int(request.GET.get('year',  now.year))
    if not (1 <= month <= 12) or not (2020 <= year <= 2030):
        month, year = now.month, now.year
    num_days = calendar.monthrange(year, month)[1]
    days_in_month = [date(year, month, day) for day in range(1, num_days + 1)]
    attendances = TrainerAttendance.objects.filter(trainer=request.user, date__year=year, date__month=month)
    approved_leaves = Leave.objects.filter(
        trainer=request.user, status='approved',
        leave_date__year=year, leave_date__month=month
    ).values('leave_date', 'leave_type', 'holiday_name')
    attendance_dict = {att.date: att for att in attendances}
    leave_dict = {leave['leave_date']: leave for leave in approved_leaves}
    data = []
    today = date.today()
    for day in days_in_month:
        has_record = day in attendance_dict or day in leave_dict
        if has_record or day <= today:
            if day in attendance_dict:
                att = attendance_dict[day]
                status = 'OUT' if att.mark_out_time else 'IN'
                day_status = att.day_status or 'present'
                data.append({
                    "date": day.strftime("%d-%m-%Y"),
                    "mark_in": timezone.localtime(att.mark_in_time).strftime("%H:%M:%S") if att.mark_in_time else "--",
                    "mark_out": timezone.localtime(att.mark_out_time).strftime("%H:%M:%S") if att.mark_out_time else "--",
                    "working_hours": (f"{int(att.working_duration.total_seconds()//3600)}h {int((att.working_duration.total_seconds()%3600)//60)}m" if att.working_duration else "--"),
                    "status": status, "day_status": day_status,
                    "photo_in": att.photo_in.url if att.photo_in else "",
                    "location_name": att.location_name or "--"
                })
            elif day in leave_dict:
                leave = leave_dict[day]
                leave_type_display = dict(Leave.LEAVE_TYPE_CHOICES)[leave['leave_type']]
                data.append({
                    "date": day.strftime("%d-%m-%Y"), "mark_in": "--", "mark_out": "--",
                    "working_hours": "--", "status": "LEAVE", "day_status": leave['leave_type'],
                    "photo_in": "", "location_name": leave_type_display + (f" - {leave['holiday_name']}" if leave['holiday_name'] else "")
                })
            else:
                data.append({
                    "date": day.strftime("%d-%m-%Y"), "mark_in": "--", "mark_out": "--",
                    "working_hours": "--", "status": "ABSENT", "day_status": "absent",
                    "photo_in": "", "location_name": "--"
                })
    return JsonResponse({"data": data, "month": month, "year": year})


@login_required
def monthly_attendance_report(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    now = timezone.now()
    month = int(request.GET.get("month", now.month))
    year  = int(request.GET.get("year",  now.year))
    trainer_id = request.GET.get("trainer", None)
    User = get_user_model()
    all_users = User.objects.filter(is_active=True)
    qs = TrainerAttendance.objects.filter(date__month=month, date__year=year).select_related("trainer")
    if trainer_id:
        qs = qs.filter(trainer_id=trainer_id)
    report = {}
    for r in qs:
        user = r.trainer
        report.setdefault(user.id, {"name": user.get_full_name() or user.username, "records": []})
        duration = "--"
        if r.mark_in_time and r.mark_out_time:
            time_diff = r.mark_out_time - r.mark_in_time
            duration = f"{int(time_diff.total_seconds()//3600)}h {int((time_diff.total_seconds()%3600)//60)}m"
        report[user.id]["records"].append({
            'date': r.date, 'status': 'OUT' if r.mark_out_time else 'IN',
            'day_status': r.day_status,
            'mark_in_time': timezone.localtime(r.mark_in_time).strftime("%I:%M %p") if r.mark_in_time else "--",
            'mark_out_time': timezone.localtime(r.mark_out_time).strftime("%I:%M %p") if r.mark_out_time else "--",
            'duration': duration, 'location_name': r.location_name or "--"
        })
    leave_qs = Leave.objects.filter(leave_date__month=month, leave_date__year=year, status='approved').select_related('trainer')
    if trainer_id:
        leave_qs = leave_qs.filter(trainer_id=trainer_id)
    for leave in leave_qs:
        user = leave.trainer
        report.setdefault(user.id, {"name": user.get_full_name() or user.username, "records": []})
        already_exists = any(r['date'] == leave.leave_date for r in report[user.id]["records"])
        if not already_exists:
            report[user.id]["records"].append({
                'date': leave.leave_date, 'status': 'LEAVE', 'day_status': leave.leave_type,
                'mark_in_time': '--', 'mark_out_time': '--', 'duration': '--',
                'location_name': leave.get_leave_type_display() + (f' ({leave.holiday_name})' if leave.holiday_name else '')
            })
    for uid in report:
        report[uid]["records"].sort(key=lambda x: x['date'], reverse=True)
    for user_id in report:
        user_obj = User.objects.get(id=user_id)
        records  = report[user_id]["records"]
        present_count  = sum(1 for r in records if r.get('day_status') == 'present')
        half_day_count = sum(1 for r in records if r.get('day_status') == 'half_day')
        leave_count    = sum(1 for r in records if r.get('status') == 'LEAVE')
        pending_count  = sum(1 for r in records if r.get('day_status') == 'pending')
        att_qs = TrainerAttendance.objects.filter(trainer=user_obj, date__month=month, date__year=year, working_duration__isnull=False)
        total_seconds = sum(a.working_duration.total_seconds() for a in att_qs if a.working_duration)
        total_hours = round(total_seconds / 3600, 1)
        class_hours, other_hours = get_hours_breakdown_range(user_obj, date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))
        incentive_data = calculate_incentive(user_obj, month, year)
        report[user_id]["summary"] = incentive_data
        attendance_percentage = get_attendance_percentage(user_obj, month, year)
        new_batches   = get_monthly_new_batches(user_obj, month, year)
        extra_batches = max(0, new_batches - 5)
        incentive     = extra_batches * 1000
        eligible      = attendance_percentage >= 90 and extra_batches > 0
        report[user_id].update({
            "attendance_percentage": attendance_percentage,
            "new_batches": new_batches, "extra_batches": extra_batches,
            "incentive": incentive, "eligible": eligible,
            "present_count": present_count, "half_day_count": half_day_count,
            "leave_count": leave_count, "pending_count": pending_count,
            "total_days": len(records), "total_hours": total_hours,
            "class_hours": class_hours, "other_hours": other_hours,
        })
    current_year = now.year
    years = list(range(current_year - 2, current_year + 1))
    return render(request, "training/admin_monthly_report.html", {
        "report": list(report.values()), "month": month, "year": year,
        "trainers": all_users, "selected_trainer": trainer_id,
        "years": years, "month_name": calendar.month_name[month],
    })


# ==================== ADMIN BATCH LIST ====================

@login_required
def admin_batch_list(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    User = get_user_model()
    batches = Batch.objects.select_related('trainer')
    course_query  = request.GET.get('course',  '').strip()
    trainer_query = request.GET.get('trainer', '').strip()
    status_filter = request.GET.get('status',  '').strip()
    active_filter = request.GET.get('active',  '').strip()
    if course_query:
        batches = batches.filter(name__icontains=course_query)
    if trainer_query:
        batches = batches.filter(Q(trainer__username__icontains=trainer_query) | Q(trainer__first_name__icontains=trainer_query) | Q(trainer__last_name__icontains=trainer_query))
    if active_filter == '1':
        batches = batches.filter(is_active=True)
    elif active_filter == '0':
        batches = batches.filter(is_active=False)
    batches = list(batches)
    if status_filter == 'ontime':
        batches = [b for b in batches if not b.is_completed and b.delay_hours == 0]
    elif status_filter == 'delay':
        batches = [b for b in batches if not b.is_completed and b.delay_hours > 0]
    elif status_filter == 'completed':
        batches = [b for b in batches if b.is_completed]
    all_batches = Batch.objects.all()
    return render(request, 'training/admin_batch_list.html', {
        'batches': batches,
        'total_batches': Batch.objects.count(),
        'active_batches': Batch.objects.filter(is_active=True, is_completed=False).count(),
        'completed_batches': Batch.objects.filter(is_completed=True).count(),
        'delayed_batches': len([b for b in all_batches if not b.is_completed and b.delay_hours > 0]),
        'total_trainers': User.objects.filter(is_superuser=False, is_active=True).count(),
    })


# ==================== API VIEWS ====================

@login_required
def get_trainer_batches(request):
    batches = Batch.objects.all() if request.user.is_superuser else Batch.objects.filter(trainer=request.user)
    return JsonResponse({'batches': [{'id': b.id, 'name': b.name} for b in batches]})


# ==================== ADMIN FRONTEND VIEWS ====================

@login_required
def admin_dashboard_view(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    User = get_user_model()
    now   = timezone.now()
    today = timezone.localdate()
    total_batches  = Batch.objects.count()
    total_trainers = User.objects.filter(is_superuser=False, is_active=True).count()
    pending_leaves = Leave.objects.filter(status='pending').count()
    month_sessions = WorkSession.objects.filter(session_date__month=now.month, session_date__year=now.year).count()
    filter_date_str = request.GET.get('filter_date', '')
    filter_trainer  = request.GET.get('filter_trainer', '')
    try:
        filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date() if filter_date_str else today
    except ValueError:
        filter_date = today
    trainers = User.objects.filter(is_superuser=False, is_active=True).order_by('first_name')
    trainers_qs = trainers.filter(id=filter_trainer) if filter_trainer else trainers
    today_data = []
    for trainer in trainers_qs:
        att = TrainerAttendance.objects.filter(trainer=trainer, date=filter_date).first()
        total_mins = int(att.working_duration.total_seconds() // 60) if att and att.working_duration else 0
        class_h, other_h = get_hours_breakdown(trainer, filter_date)
        total_h = round(total_mins / 60, 1)
        if att:
            status = att.day_status if att.mark_out_time else 'active'
        else:
            has_leave = Leave.objects.filter(trainer=trainer, leave_date=filter_date, status='approved').exists()
            status = 'leave' if has_leave else 'absent'
        today_data.append({
            'name': trainer.get_full_name() or trainer.username,
            'username': trainer.username, 'total_hours': total_h,
            'class_hours': class_h, 'other_hours': other_h, 'status': status,
            'mark_in': timezone.localtime(att.mark_in_time).strftime("%I:%M %p") if att and att.mark_in_time else None,
            'mark_out': timezone.localtime(att.mark_out_time).strftime("%I:%M %p") if att and att.mark_out_time else None,
            'location': att.location_name if att else None,
        })
    today_data.sort(key=lambda x: x['total_hours'], reverse=True)
    context = {
        'total_batches': total_batches, 'total_trainers': total_trainers,
        'pending_leaves': pending_leaves, 'month_sessions': month_sessions,
        'pending_leave_list': Leave.objects.filter(status='pending').select_related('trainer').order_by('-applied_at')[:10],
        'today_data': today_data, 'today': today, 'filter_date': filter_date,
        'filter_date_str': filter_date.strftime('%Y-%m-%d'), 'filter_trainer': filter_trainer,
        'all_trainers': trainers, 'is_today': filter_date == today,
    }
    return render(request, 'training/admin_dashboard.html', context)


@login_required
def admin_leave_list(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    User = get_user_model()
    leaves = Leave.objects.select_related('trainer').order_by('-applied_at')
    status  = request.GET.get('status')
    trainer = request.GET.get('trainer')
    month   = request.GET.get('month')
    if status:  leaves = leaves.filter(status=status)
    if trainer: leaves = leaves.filter(trainer_id=trainer)
    if month:   leaves = leaves.filter(leave_date__month=month)
    stats = {
        'pending':  Leave.objects.filter(status='pending').count(),
        'approved': Leave.objects.filter(status='approved').count(),
        'rejected': Leave.objects.filter(status='rejected').count(),
        'total':    Leave.objects.count(),
    }
    months = [{'val': i, 'name': calendar.month_name[i]} for i in range(1, 13)]
    return render(request, 'training/admin_leave_list.html', {
        'leaves': leaves, 'trainers': User.objects.filter(is_active=True),
        'stats': stats, 'months': months,
    })


@login_required
def admin_leave_action(request, leave_id):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    if request.method != 'POST':
        return redirect('training:admin_leave_list')
    leave  = get_object_or_404(Leave, id=leave_id)
    action = request.POST.get('action')
    if action == 'approve':
        leave.status = 'approved'
        leave.save()
        messages.success(request, f'Leave approved for {leave.trainer.get_full_name() or leave.trainer.username}.')
    elif action == 'reject':
        leave.status = 'rejected'
        leave.save()
        messages.error(request, f'Leave rejected.')
    elif action == 'pending':
        leave.status = 'pending'
        leave.save()
        messages.success(request, 'Leave reset to pending.')
    next_url = request.META.get('HTTP_REFERER', '')
    if 'admin-dashboard' in next_url:
        return redirect('training:admin_dashboard')
    return redirect('training:admin_leave_list')


@login_required
def admin_user_list(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    User = get_user_model()
    users = User.objects.annotate(batch_count=Count('batches')).order_by('-date_joined')
    q    = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(employee_id__icontains=q)
        )
    if role == 'admin':   users = users.filter(is_superuser=True)
    elif role == 'trainer': users = users.filter(is_superuser=False)
    return render(request, 'training/admin_user_list.html', {'users': users})


@login_required
def admin_user_create(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    if request.method == 'POST':
        username     = request.POST.get('username', '').strip()
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        email        = request.POST.get('email', '').strip()
        password     = request.POST.get('password', '')
        password2    = request.POST.get('password2', '')
        is_superuser = request.POST.get('is_superuser') == '1'
        if not username or not password:
            messages.error(request, 'Username aur password zaroori hain.')
        elif password != password2:
            messages.error(request, 'Passwords match nahi karte.')
        elif len(password) < 8:
            messages.error(request, 'Password kam se kam 8 characters ka hona chahiye.')
        else:
            User = get_user_model()
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" already exists.')
            else:
                role = 'admin' if is_superuser else 'trainer'
                User.objects.create_user(
                    username=username, first_name=first_name, last_name=last_name,
                    email=email, password=password,
                    is_superuser=is_superuser, is_staff=is_superuser,
                    role=role,
                )
                messages.success(request, f'User "{username}" created!')
                return redirect('training:admin_user_list')
    return render(request, 'training/admin_user_form.html', {'edit_mode': False, 'target_user': {}})


@login_required
def admin_user_edit(request, user_id):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    User = get_user_model()
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        target_user.first_name   = request.POST.get('first_name', '').strip()
        target_user.last_name    = request.POST.get('last_name', '').strip()
        target_user.email        = request.POST.get('email', '').strip()
        target_user.username     = request.POST.get('username', '').strip()
        target_user.is_superuser = request.POST.get('is_superuser') == '1'
        target_user.is_staff     = target_user.is_superuser
        password = request.POST.get('password', '')
        if password:
            if len(password) < 8:
                messages.error(request, 'Password kam se kam 8 characters ka hona chahiye.')
                return render(request, 'training/admin_user_form.html', {'edit_mode': True, 'target_user': target_user})
            target_user.set_password(password)
        target_user.save()
        messages.success(request, f'User "{target_user.username}" updated!')
        return redirect('training:admin_user_list')
    return render(request, 'training/admin_user_form.html', {'edit_mode': True, 'target_user': target_user})


@login_required
def admin_user_toggle(request, user_id):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    if request.method == 'POST':
        User = get_user_model()
        target_user = get_object_or_404(User, id=user_id)
        if target_user == request.user:
            messages.error(request, 'Aap apna account disable nahi kar sakte.')
        else:
            target_user.is_active = not target_user.is_active
            target_user.save()
            messages.success(request, f'User "{target_user.username}" {"enabled" if target_user.is_active else "disabled"}.')
    return redirect('training:admin_user_list')


@login_required
def admin_batch_create(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    User = get_user_model()
    trainers = User.objects.filter(is_superuser=False, is_active=True)
    if request.method == 'POST':
        name           = request.POST.get('name', '').strip()
        start_date_str = request.POST.get('start_date', '')
        total_hours    = request.POST.get('total_hours', 0)
        total_students = request.POST.get('total_students', 0)
        trainer_id     = request.POST.get('trainer')
        is_active      = request.POST.get('is_active') == '1'
        batch_type     = request.POST.get('batch_type', 'training')
        if not name or not start_date_str or not trainer_id:
            messages.error(request, 'Name, start date aur trainer zaroori hain.')
        else:
            try:
                trainer    = get_object_or_404(User, id=trainer_id)
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                Batch.objects.create(name=name, trainer=trainer, start_date=start_date,
                    total_hours=int(total_hours), total_students=int(total_students),
                    is_active=is_active, batch_type=batch_type)
                messages.success(request, f'Batch "{name}" created!')
                return redirect('training:admin_batch_list')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')
    return render(request, 'training/admin_batch_form.html', {'edit_mode': False, 'trainers': trainers, 'batch': {}})


@login_required
def admin_batch_edit(request, batch_id):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    batch    = get_object_or_404(Batch, id=batch_id)
    User     = get_user_model()
    trainers = User.objects.filter(is_superuser=False, is_active=True)
    if request.method == 'POST':
        batch.name           = request.POST.get('name', '').strip()
        batch.total_hours    = int(request.POST.get('total_hours', batch.total_hours))
        batch.total_students = int(request.POST.get('total_students', batch.total_students))
        batch.is_active      = request.POST.get('is_active') == '1'
        batch.batch_type     = request.POST.get('batch_type', 'training')
        trainer_id     = request.POST.get('trainer')
        start_date_str = request.POST.get('start_date', '')
        if trainer_id:
            batch.trainer = get_object_or_404(User, id=trainer_id)
        if start_date_str:
            batch.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        batch.save()
        messages.success(request, f'Batch "{batch.name}" updated!')
        return redirect('training:admin_batch_list')
    return render(request, 'training/admin_batch_form.html', {'edit_mode': True, 'batch': batch, 'trainers': trainers})


@login_required
def admin_batch_complete(request, batch_id):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    if request.method != 'POST':
        return redirect('training:admin_batch_list')
    batch  = get_object_or_404(Batch, id=batch_id)
    action = request.POST.get('action', 'complete')
    if action == 'complete':
        batch.is_completed = True
        batch.completed_at = timezone.now()
        batch.save()
        messages.success(request, f'✅ Batch "{batch.name}" marked as Completed!')
    elif action == 'uncomplete':
        batch.is_completed = False
        batch.completed_at = None
        batch.save()
        messages.success(request, f'↩️ Batch "{batch.name}" marked as Active again.')
    next_url = request.POST.get('next', '')
    if next_url == 'detail':
        return redirect('training:batch_detail', batch_id=batch.id)
    return redirect('training:admin_batch_list')


# ==================== EXCEL EXPORT ====================

# ==================== EXCEL EXPORT ====================

@login_required
def export_attendance_excel(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')

    import io
    import calendar
    from datetime import date
    from django.http import HttpResponse

    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return JsonResponse({"error": "openpyxl not installed."}, status=500)

    now = timezone.now()
    month = int(request.GET.get("month", now.month))
    year  = int(request.GET.get("year", now.year))
    trainer_id = request.GET.get("trainer")

    User = get_user_model()

    trainer_ids_qs = TrainerAttendance.objects.filter(
        date__month=month, date__year=year
    ).values_list("trainer", flat=True).distinct()

    leave_trainer_ids_qs = Leave.objects.filter(
        leave_date__month=month, leave_date__year=year, status='approved'
    ).values_list("trainer", flat=True).distinct()

    trainer_ids = set(trainer_ids_qs) | set(leave_trainer_ids_qs)

    trainers = User.objects.filter(
        id__in=trainer_ids, is_active=True, is_superuser=False
    ).order_by("first_name", "username")

    if trainer_id:
        trainers = trainers.filter(id=trainer_id)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ── Styles ──
    HDR_FILL    = PatternFill("solid", fgColor="1F2937")
    ALT_FILL    = PatternFill("solid", fgColor="F8FAFC")
    WHITE_FILL  = PatternFill("solid", fgColor="FFFFFF")
    PRES_FILL   = PatternFill("solid", fgColor="DCFCE7")
    HALF_FILL   = PatternFill("solid", fgColor="FEF9C3")
    LEAVE_FILL  = PatternFill("solid", fgColor="FEE2E2")
    WEEKOFF_FILL= PatternFill("solid", fgColor="DBEAFE")
    OPT_FILL    = PatternFill("solid", fgColor="F3E8FF")   # purple tint - optional holiday
    MAN_FILL    = PatternFill("solid", fgColor="E0F2FE")   # blue tint - mandatory holiday
    SICK_FILL   = PatternFill("solid", fgColor="FEE2E2")   # red tint - sick
    CASUAL_FILL = PatternFill("solid", fgColor="FEF9C3")   # yellow tint - casual
    EMRG_FILL   = PatternFill("solid", fgColor="FFEDD5")   # orange tint - emergency

    thin   = Side(style='thin', color="CBD5E1")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # ── Leave type display mapping ──
    LEAVE_DISPLAY = {
        'sick':              ('🤒', 'Sick Leave',        SICK_FILL),
        'casual':            ('🏖️', 'Casual Leave',      CASUAL_FILL),
        'emergency':         ('🚨', 'Emergency Leave',   EMRG_FILL),
        'weekoff':           ('📅', 'Week Off',          WEEKOFF_FILL),
        'optional_holiday':  ('🎉', 'Optional Holiday',  OPT_FILL),
        'mandatory_holiday': ('🏛️', 'Mandatory Holiday', MAN_FILL),
        'other':             ('📝', 'Other Leave',       LEAVE_FILL),
    }

    num_days     = calendar.monthrange(year, month)[1]
    days_in_month = [date(year, month, d) for d in range(1, num_days + 1)]

    # ════════════════════════════════════════════
    # SUMMARY SHEET — with leave type breakdown
    # ════════════════════════════════════════════
    ws = wb.create_sheet("Summary")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:N1")
    ws["A1"] = f"Attendance Summary — {calendar.month_name[month]} {year}"
    ws["A1"].font      = Font(bold=True, color="FFFFFF", size=14)
    ws["A1"].fill      = PatternFill("solid", fgColor="2563EB")
    ws["A1"].alignment = Alignment(horizontal="center")

    sum_headers = [
        "Trainer",
        "Total Days", "Present", "Half Day",
        "Sick Leave 🤒", "Casual Leave 🏖️", "Emergency 🚨",
        "Week Off 📅", "Optional Holiday 🎉", "Mandatory Holiday 🏛️",
        "Other Leave 📝",
        "Absent",
        "Total Hours", "Attend %",
    ]
    for c, h in enumerate(sum_headers, 1):
        cell = ws.cell(row=2, column=c, value=h)
        cell.font      = Font(bold=True, color="FFFFFF", size=9)
        cell.fill      = HDR_FILL
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border    = border
    ws.row_dimensions[2].height = 30

    r = 3
    for t in trainers:
        atts = {
            a.date: a for a in TrainerAttendance.objects.filter(
                trainer=t, date__month=month, date__year=year)
        }
        leaves = {
            l.leave_date: l for l in Leave.objects.filter(
                trainer=t, leave_date__month=month, leave_date__year=year, status='approved')
        }

        present_count = half_day_count = absent_count = 0
        leave_counts  = {k: 0 for k in LEAVE_DISPLAY}  # per-type counter
        total_secs    = 0

        for d in days_in_month:
            if d in atts:
                a = atts[d]
                s = a.day_status
                if s == 'present':
                    present_count += 1
                elif s == 'half_day':
                    half_day_count += 1
                elif s == 'leave':
                    # cross-check leave table for exact type
                    if d in leaves:
                        leave_counts[leaves[d].leave_type] = leave_counts.get(leaves[d].leave_type, 0) + 1
                    else:
                        leave_counts['other'] += 1
                else:
                    absent_count += 1
                if a.working_duration:
                    total_secs += a.working_duration.total_seconds()
            elif d in leaves:
                lt = leaves[d].leave_type
                leave_counts[lt] = leave_counts.get(lt, 0) + 1
            else:
                absent_count += 1

        total_hours  = round(total_secs / 3600, 1)
        days_present = present_count + half_day_count
        att_pct      = round((days_present / num_days) * 100, 2) if num_days else 0

        row_data = [
            t.get_full_name() or t.username,
            num_days,
            present_count,
            half_day_count,
            leave_counts.get('sick', 0),
            leave_counts.get('casual', 0),
            leave_counts.get('emergency', 0),
            leave_counts.get('weekoff', 0),
            leave_counts.get('optional_holiday', 0),
            leave_counts.get('mandatory_holiday', 0),
            leave_counts.get('other', 0),
            absent_count,
            f"{total_hours}h",
            f"{att_pct}%",
        ]

        fill = ALT_FILL if r % 2 == 0 else WHITE_FILL
        for c, val in enumerate(row_data, 1):
            cell            = ws.cell(row=r, column=c, value=val)
            cell.alignment  = Alignment(horizontal="center")
            cell.border     = border
            cell.fill       = fill
            # highlight non-zero leave counts with color
            if c == 5  and val: cell.fill = SICK_FILL
            if c == 6  and val: cell.fill = CASUAL_FILL
            if c == 7  and val: cell.fill = EMRG_FILL
            if c == 8  and val: cell.fill = WEEKOFF_FILL
            if c == 9  and val: cell.fill = OPT_FILL
            if c == 10 and val: cell.fill = MAN_FILL
            if c == 11 and val: cell.fill = LEAVE_FILL
        r += 1

    # column widths for summary
    sum_widths = [22, 10, 10, 10, 14, 14, 14, 12, 18, 18, 14, 10, 12, 10]
    for i, w in enumerate(sum_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ════════════════════════════════════════════
    # INDIVIDUAL SHEETS — leave type clearly shown
    # ════════════════════════════════════════════
    for t in trainers:
        sheet_name = (t.get_full_name() or t.username)[:31]
        wst = wb.create_sheet(sheet_name)
        wst.sheet_view.showGridLines = False

        wst.merge_cells("A1:I1")
        wst["A1"] = f"{t.get_full_name() or t.username}  —  {calendar.month_name[month]} {year}"
        wst["A1"].font      = Font(bold=True, color="FFFFFF", size=13)
        wst["A1"].fill      = PatternFill("solid", fgColor="0F766E")
        wst["A1"].alignment = Alignment(horizontal="center")

        ind_headers = ["Date", "Day", "Mark In", "Mark Out", "Duration",
                       "Status", "Leave Type", "Festival / Note", "Hours"]
        for c, h in enumerate(ind_headers, 1):
            cell            = wst.cell(row=3, column=c, value=h)
            cell.font       = Font(bold=True, color="FFFFFF")
            cell.fill       = HDR_FILL
            cell.alignment  = Alignment(horizontal="center")
            cell.border     = border

        atts = {
            a.date: a for a in TrainerAttendance.objects.filter(
                trainer=t, date__month=month, date__year=year)
        }
        leaves = {
            l.leave_date: l for l in Leave.objects.filter(
                trainer=t, leave_date__month=month, leave_date__year=year, status='approved')
        }

        rr = 4
        present_count = half_day_count = absent_count = 0
        leave_counts  = {k: 0 for k in LEAVE_DISPLAY}
        total_secs    = 0

        for d in [date(year, month, x) for x in range(1, num_days + 1)]:

            if d in atts:
                a        = atts[d]
                mark_in  = timezone.localtime(a.mark_in_time).strftime("%I:%M %p")  if a.mark_in_time  else "--"
                mark_out = timezone.localtime(a.mark_out_time).strftime("%I:%M %p") if a.mark_out_time else "--"

                if a.working_duration:
                    h_val     = int(a.working_duration.total_seconds() // 3600)
                    m_val     = int((a.working_duration.total_seconds() % 3600) // 60)
                    dur       = f"{h_val}h {m_val}m"
                    hours_txt = f"{round(a.working_duration.total_seconds()/3600, 1)}h"
                    total_secs += a.working_duration.total_seconds()
                else:
                    dur = hours_txt = "--"

                # ── Determine leave type & fill ──
                if a.day_status == 'present':
                    present_count += 1
                    fill      = PRES_FILL
                    status    = "✅ Present"
                    ltype_str = "--"
                    note_str  = "--"

                elif a.day_status == 'half_day':
                    half_day_count += 1
                    fill      = HALF_FILL
                    status    = "🟡 Half Day"
                    ltype_str = "--"
                    note_str  = "--"

                elif a.day_status == 'leave':
                    # cross-reference leave table
                    if d in leaves:
                        lv        = leaves[d]
                        lt        = lv.leave_type
                        emoji, ltype_str, fill = LEAVE_DISPLAY.get(lt, ('📝', 'Leave', LEAVE_FILL))
                        ltype_str = f"{emoji} {ltype_str}"
                        note_str  = lv.holiday_name or lv.reason[:40] or "--"
                        leave_counts[lt] = leave_counts.get(lt, 0) + 1
                    else:
                        fill      = LEAVE_FILL
                        ltype_str = "📝 Leave"
                        note_str  = "--"
                        leave_counts['other'] += 1
                    status = "🔴 Leave"

                else:
                    fill      = WHITE_FILL
                    status    = "⏳ Pending"
                    ltype_str = "--"
                    note_str  = "--"

                row = [d.strftime("%d-%m-%Y"), d.strftime("%A"),
                       mark_in, mark_out, dur, status, ltype_str, note_str, hours_txt]

            elif d in leaves:
                lv   = leaves[d]
                lt   = lv.leave_type
                emoji, ltype_label, fill = LEAVE_DISPLAY.get(lt, ('📝', 'Leave', LEAVE_FILL))
                leave_counts[lt] = leave_counts.get(lt, 0) + 1
                note = lv.holiday_name or lv.reason[:40] or "--"

                row = [
                    d.strftime("%d-%m-%Y"), d.strftime("%A"),
                    "--", "--", "--",
                    "🗓️ On Leave",
                    f"{emoji} {ltype_label}",
                    note,
                    "--",
                ]

            else:
                absent_count += 1
                fill = WHITE_FILL
                row  = [d.strftime("%d-%m-%Y"), d.strftime("%A"),
                        "--", "--", "--", "❌ Absent", "--", "--", "--"]

            for c, val in enumerate(row, 1):
                cell           = wst.cell(row=rr, column=c, value=val)
                cell.alignment = Alignment(horizontal="center")
                cell.border    = border
                cell.fill      = fill
            rr += 1

        # ── Individual summary block ──
        days_present = present_count + half_day_count
        total_days   = num_days
        att_pct      = round((days_present / total_days) * 100, 2) if total_days else 0
        total_hours  = round(total_secs / 3600, 1)

        srow = rr + 1
        wst.merge_cells(f"A{srow}:I{srow}")
        wst[f"A{srow}"] = "📊 Monthly Summary"
        wst[f"A{srow}"].font      = Font(bold=True, color="FFFFFF", size=11)
        wst[f"A{srow}"].fill      = PatternFill("solid", fgColor="0F766E")
        wst[f"A{srow}"].alignment = Alignment(horizontal="center")
        srow += 1

        summary_items = [
            ("Total Working Days",      total_days),
            ("Days Present",            days_present),
            ("Half Day",                half_day_count),
            ("Sick Leave 🤒",           leave_counts.get('sick', 0)),
            ("Casual Leave 🏖️",         leave_counts.get('casual', 0)),
            ("Emergency Leave 🚨",      leave_counts.get('emergency', 0)),
            ("Week Off 📅",             leave_counts.get('weekoff', 0)),
            ("Optional Holiday 🎉",     leave_counts.get('optional_holiday', 0)),
            ("Mandatory Holiday 🏛️",    leave_counts.get('mandatory_holiday', 0)),
            ("Other Leave 📝",          leave_counts.get('other', 0)),
            ("Absent",                  absent_count),
            ("Total Hours",             f"{total_hours}h"),
            ("Attendance %",            f"{att_pct}%"),
        ]

        # Color map for summary rows
        sum_fill_map = {
            "Sick Leave 🤒":        SICK_FILL,
            "Casual Leave 🏖️":      CASUAL_FILL,
            "Emergency Leave 🚨":   EMRG_FILL,
            "Week Off 📅":          WEEKOFF_FILL,
            "Optional Holiday 🎉":  OPT_FILL,
            "Mandatory Holiday 🏛️": MAN_FILL,
            "Other Leave 📝":       LEAVE_FILL,
        }

        for key, val in summary_items:
            kc = wst.cell(row=srow, column=1, value=key)
            vc = wst.cell(row=srow, column=2, value=val)
            kc.font  = Font(bold=True)
            row_fill = sum_fill_map.get(key, ALT_FILL if srow % 2 else WHITE_FILL)
            kc.fill  = row_fill
            vc.fill  = row_fill
            kc.border = vc.border = border
            srow += 1

        col_widths = [14, 12, 12, 12, 12, 18, 22, 30, 10]
        for i, w in enumerate(col_widths, 1):
            wst.column_dimensions[get_column_letter(i)].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    fname = f"attendance_{calendar.month_name[month]}_{year}.xlsx"
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response

# ==================== TRAINER DATE RANGE REPORT ====================

@login_required
def trainer_range_report(request):
    if not request.user.is_superuser:
        return redirect('training:trainer_dashboard')
    User = get_user_model()
    now  = timezone.now()
    default_from = now.date().replace(day=1)
    default_to   = now.date()
    from_date_str = request.GET.get('from_date', default_from.strftime('%Y-%m-%d'))
    to_date_str   = request.GET.get('to_date',   default_to.strftime('%Y-%m-%d'))
    trainer_id    = request.GET.get('trainer', '')
    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date   = datetime.strptime(to_date_str,   '%Y-%m-%d').date()
    except ValueError:
        from_date = default_from
        to_date   = default_to
    if (to_date - from_date).days > 31:
        to_date = from_date + timedelta(days=30)
    all_trainers = User.objects.filter(is_superuser=False, is_active=True).order_by('first_name')
    selected_trainer = None
    chart_data = []
    summary    = {}
    if trainer_id:
        try:
            selected_trainer = User.objects.get(id=trainer_id)
        except User.DoesNotExist:
            pass
    if selected_trainer:
        delta = (to_date - from_date).days + 1
        total_class = total_other = total_work = present_days = half_day_days = leave_days = absent_days = 0
        for i in range(delta):
            current_date = from_date + timedelta(days=i)
            att = TrainerAttendance.objects.filter(trainer=selected_trainer, date=current_date).first()
            work_mins = int(att.working_duration.total_seconds() // 60) if att and att.working_duration else 0
            class_hf, other_hf = get_hours_breakdown(selected_trainer, current_date)
            work_h = round(work_mins / 60, 1)
            if att:
                status = att.day_status if att.mark_out_time else 'active'
                if status == 'present':    present_days  += 1
                elif status == 'half_day': half_day_days += 1
                elif status == 'leave':    leave_days    += 1
            else:
                has_leave = Leave.objects.filter(trainer=selected_trainer, leave_date=current_date, status='approved').exists()
                status = 'leave' if has_leave else 'absent'
                if status == 'leave': leave_days  += 1
                else:                 absent_days += 1
            total_class += class_hf
            total_other += other_hf
            total_work  += work_h
            chart_data.append({
                'date': current_date.strftime('%d %b'), 'date_full': current_date.strftime('%d %B %Y'),
                'weekday': current_date.strftime('%a'), 'class_hours': class_hf,
                'other_hours': other_hf, 'total_hours': work_h, 'status': status,
                'is_sunday': current_date.weekday() == 6,
            })
        summary = {
            'total_class': round(total_class, 1), 'total_other': round(total_other, 1),
            'total_work': round(total_work, 1), 'present_days': present_days,
            'half_day_days': half_day_days, 'leave_days': leave_days,
            'absent_days': absent_days, 'total_days': delta,
        }
    return render(request, 'training/trainer_range_report.html', {
        'all_trainers': all_trainers, 'selected_trainer': selected_trainer,
        'from_date': from_date, 'to_date': to_date,
        'from_date_str': from_date.strftime('%Y-%m-%d'), 'to_date_str': to_date.strftime('%Y-%m-%d'),
        'chart_data': chart_data, 'summary': summary, 'trainer_id': trainer_id,
    })