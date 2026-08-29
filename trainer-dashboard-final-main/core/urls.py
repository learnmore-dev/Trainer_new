from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from training import views as training_views  # ← add karo

urlpatterns = [
    path('', training_views.home_redirect, name='home'),  # ← root pe home_redirect
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_user, name='logout'),
    # signup agar chahiye toh:
    # path('signup/', views.signup, name='signup'),
    
]