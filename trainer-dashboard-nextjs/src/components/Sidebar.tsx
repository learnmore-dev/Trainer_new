'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Users,
  BookOpen,
  Camera,
  Clock,
  FileBarChart2,
  CalendarDays,
  Calendar,
  MessageSquare,
  Radio,
  Settings,
  ChevronDown
} from 'lucide-react';

export default function Sidebar() {
  const pathname = usePathname();

  const links = [
    { href: '/admin/dashboard', label: 'Overview', icon: LayoutDashboard },
    { href: '/admin/batches', label: 'Batches', icon: BookOpen },
    { href: '/admin/trainers', label: 'Trainers', icon: Users },
    { href: '/admin/attendance', label: 'Attendance', icon: Camera },
    { href: '/admin/monitoring', label: 'Login Monitor', icon: Clock },
    { href: '/admin/reports', label: 'Reports', icon: FileBarChart2 },
    { href: '/admin/leaves', label: 'Leaves', icon: CalendarDays },
    { href: '/admin/holidays', label: 'Holidays', icon: Calendar },
    { href: '/admin/whatsapp', label: 'WhatsApp Hub', icon: MessageSquare },
    { href: '/admin/live-monitor', label: 'Radar', icon: Radio },
    { href: '/admin/settings', label: 'Institute Settings', icon: Settings },
  ];

  return (
    <aside className="w-60 shrink-0 hidden lg:flex flex-col bg-white border-r border-slate-200/80 min-h-screen p-4 justify-between">
      <div>
        {/* Brand Header */}
        <div className="flex items-center gap-2.5 px-2 py-3 mb-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-600 text-white font-black text-xs shadow-md">
            LT
          </div>
          <div className="font-extrabold text-sm text-slate-900 tracking-tight leading-tight">
            Learnmore <br />
            <span className="text-blue-600 font-bold text-xs">Technologies</span>
          </div>
        </div>

        {/* Sidebar Nav Links */}
        <nav className="space-y-1">
          {links.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-600/20'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-white' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* User Profile at Bottom */}
      <div className="pt-4 border-t border-slate-100 space-y-2">
        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-200/60">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-full bg-slate-900 text-white font-black text-xs flex items-center justify-center">
              N
            </div>
            <div>
              <div className="font-extrabold text-xs text-slate-900">Nimisha</div>
              <div className="text-[10px] text-slate-500 font-semibold">Super Admin</div>
            </div>
          </div>
          <ChevronDown className="h-4 w-4 text-slate-400" />
        </div>

        <div className="py-1 px-3 rounded-lg bg-blue-50 text-blue-700 font-bold text-[11px] text-center border border-blue-100">
          11:45 AM • 22 May 2025
        </div>
      </div>
    </aside>
  );
}

