# trainer_monitoring/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    # ✅ FIX: GET bhi allow karo logout ke liye
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('training/', include('training.urls')),
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)