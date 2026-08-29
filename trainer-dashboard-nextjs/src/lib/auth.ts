import { User } from './types';

export const AUTH_STORAGE_KEY = 'trainer_monitoring_user';

export function getStoredUser(): User | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredUser(user: User): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
  document.cookie = `trainer_user=${encodeURIComponent(JSON.stringify({ id: user.id, role: user.role, name: user.name }))}; path=/; max-age=604800`;
}

export function clearStoredUser(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(AUTH_STORAGE_KEY);
  document.cookie = 'trainer_user=; path=/; max-age=0';
}
