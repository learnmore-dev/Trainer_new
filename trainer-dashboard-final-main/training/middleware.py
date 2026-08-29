from django.utils import timezone
from .models import Attendance

class AttendanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check attendance status for authenticated users
        if request.user.is_authenticated:
            today = timezone.now().date()
            today_login = Attendance.objects.filter(
                user=request.user,
                login_time__date=today,
                logout_time__isnull=True
            ).first()
            
            if today_login:
                request.session['attendance_status'] = 'logged_in'
                request.session['attendance_id'] = today_login.id
            else:
                if 'attendance_status' in request.session:
                    del request.session['attendance_status']
                if 'attendance_id' in request.session:
                    del request.session['attendance_id']
        
        response = self.get_response(request)
        return response