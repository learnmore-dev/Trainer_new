from django.contrib.auth.views import LogoutView
from django.urls import path
from . import views

app_name = "training"

urlpatterns = [
    path('', views.home_redirect, name='home_redirect'),    

    # ================= AUTH =================
    path('django-logout/', LogoutView.as_view(next_page='login'), name='django_logout'),

    # ================= DASHBOARDS =================
    path('admin-dashboard/',  views.admin_dashboard_view, name='admin_dashboard'),
    path('trainer/dashboard/', views.trainer_dashboard,   name='trainer_dashboard'),

    # ================= ADMIN — USER MANAGEMENT =================
    path('admin/users/',               views.admin_user_list,   name='admin_user_list'),
    path('admin/users/create/',        views.admin_user_create, name='admin_user_create'),
    path('admin/users/<int:user_id>/edit/',   views.admin_user_edit,   name='admin_user_edit'),
    path('admin/users/<int:user_id>/toggle/', views.admin_user_toggle, name='admin_user_toggle'),

    # ================= ADMIN — BATCH MANAGEMENT =================
    path('admin/batches/',                    views.admin_batch_list,   name='admin_batch_list'),
    path('admin/batches/create/',             views.admin_batch_create, name='admin_batch_create'),
    path('admin/batches/<int:batch_id>/edit/', views.admin_batch_edit,  name='admin_batch_edit'),
    path('admin/batches/<int:batch_id>/complete/', views.admin_batch_complete, name='admin_batch_complete'),

    # ================= ADMIN — LEAVE MANAGEMENT =================
    path('admin/leaves/',                          views.admin_leave_list,   name='admin_leave_list'),
    path('admin/leaves/<int:leave_id>/action/',    views.admin_leave_action, name='admin_leave_action'),

    # ================= API =================
    path('api/trainer-batches/', views.get_trainer_batches, name='get_trainer_batches'),

    # ================= BATCH =================
    path('batches/',               views.batch_list,   name='batch_list'),
    path('batch/<int:batch_id>/', views.batch_detail, name='batch_detail'),

    # ================= SESSION =================
    path('session/add/<int:batch_id>/', views.session_form,          name='session_create'),
    path('session/add/',                views.session_form,          name='session_create_standalone'),

    # ================= USER ATTENDANCE =================
    path('attendance/',         views.attendance_home, name='attendance'),
    path('attendance/login/',   views.login_view,      name='attendance_login'),
    path('attendance/logout/',  views.logout_view,     name='attendance_logout'),

    # ================= TRAINER ATTENDANCE =================
    path('trainer-attendance/',          views.trainer_attendance_page, name='trainer_attendance_page'),
    path('trainer-attendance/api/',      views.trainer_attendance,      name='trainer_attendance_api'),
    path('trainer-attendance/history/',  views.attendance_history,      name='trainer_attendance_history'),

    # ================= REPORTS =================
    path('monthly-attendance-report/', views.monthly_attendance_report, name='monthly_attendance_report'),
    path('export-attendance-excel/', views.export_attendance_excel, name='export_attendance_excel'),
    path('trainer-range-report/', views.trainer_range_report, name='trainer_range_report'),

    # ================= LEAVE =================
    path('leave/create/', views.leave_create, name='leave_create'),
    path('leave/quota/', views.leave_quota_api, name='leave_quota'),
    path('leave/quota/',   views.leave_quota_api,   name='leave_quota_api'),
    path('leave/balance/', views.leave_balance_view, name='leave_balance'),
    

]