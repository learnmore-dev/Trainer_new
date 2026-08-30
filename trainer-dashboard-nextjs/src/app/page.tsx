'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getStoredUser } from '@/lib/auth';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const user = getStoredUser();
    if (!user) {
      window.location.href = '/login';
    } else if (user.role === 'admin') {
      window.location.href = '/admin/dashboard';
    } else {
      window.location.href = '/trainer/dashboard';
    }
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
      <div className="flex items-center gap-3">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <span className="text-sm font-medium text-slate-400">Loading TrainerPulse...</span>
      </div>
    </div>
  );
}
