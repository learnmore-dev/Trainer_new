# views.py
from django.shortcuts import render, redirect
from .models import Batch, WorkSession  # assuming WorkSession model hai
from django.contrib.auth.decorators import login_required

@login_required
def log_work_session(request):
    # 1️⃣ Fetch all batches
    batches = Batch.objects.all()

    if request.method == 'POST':
        batch_id = request.POST.get('batch')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        description = request.POST.get('description')

        # 2️⃣ Get batch object
        try:
            batch = Batch.objects.get(id=batch_id)
        except Batch.DoesNotExist:
            # handle invalid batch
            return render(request, 'log_work_session.html', {
                'batches': batches,
                'error': 'Invalid batch selected'
            })

        # 3️⃣ Save WorkSession
        WorkSession.objects.create(
            batch=batch,
            trainer=request.user,
            start_time=start_time,
            end_time=end_time,
            description=description
        )
        return redirect('trainer_dashboard')

    # 4️⃣ Render template with batches
    return render(request, 'log_work_session.html', {'batches': batches})
