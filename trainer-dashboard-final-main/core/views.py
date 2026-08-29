from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse
from .forms import SignUpForm


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')

            user = authenticate(username=username, password=raw_password)

            if user is not None:
                login(request, user)

            return redirect('login')
    else:
        form = SignUpForm()

    return render(request, 'signup.html', {'form': form})


# ✅ FIX: Git merge conflict resolved — only ONE logout_user function kept
@require_POST
@login_required
def logout_user(request):
    logout(request)
    return JsonResponse({
        "status": "success",
        "redirect_url": "/login/"
    })