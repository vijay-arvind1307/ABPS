import React from 'react';
import {
  LayoutDashboard,
  CalendarDays,
  Radio,
  Clock,
  Shuffle,
  Cpu,
  FileText,
  Sliders,
  Database,
  Layers,
  Activity
} from 'lucide-react';
import { getCurrentUser } from '../services/auth';

export default function Navbar({ activeTab, onTabChange }) {
  const user = getCurrentUser();
  const rawRole = user ? user.role : 'RAILWAY_PLANNER';
  const role = (rawRole || '').toUpperCase();

  const DEPT_ROLES = ['TRACK_ENGINEERING', 'SIGNAL_TELECOM', 'TRACTION_DISTRIBUTION', 'DEPARTMENT_USER', 'SYSTEM_ADMIN', 'ADMIN'];
  const PLANNER_ROLES = ['RAILWAY_PLANNER', 'PLANNER', 'SYSTEM_ADMIN', 'ADMIN'];
  const ALL_ROLES = ['TRACK_ENGINEERING', 'SIGNAL_TELECOM', 'TRACTION_DISTRIBUTION', 'DEPARTMENT_USER', 'RAILWAY_PLANNER', 'PLANNER', 'SYSTEM_ADMIN', 'ADMIN'];
  const ADMIN_ROLES = ['SYSTEM_ADMIN', 'ADMIN'];

  const navItems = [
    // Department User primary screens
    { id: 'dept-dashboard', label: 'Department Demands & Blocks', icon: LayoutDashboard, roles: DEPT_ROLES },

    // Railway Planner primary screens
    { id: 'planner-dashboard', label: 'Control Room', icon: CalendarDays, roles: PLANNER_ROLES },
    { id: 'train-position', label: 'Live Train Position', icon: Radio, roles: ALL_ROLES },
    { id: 'available-windows', label: 'Available Windows', icon: Clock, roles: PLANNER_ROLES },
    { id: 'dynamic-replan', label: 'Dynamic Re-Planning', icon: Shuffle, roles: PLANNER_ROLES },
    { id: 'what-if', label: 'What-If Analysis', icon: Cpu, roles: PLANNER_ROLES },
    { id: 'reports', label: 'Reports & Audit Trail', icon: FileText, roles: ALL_ROLES },
    { id: 'admin-master', label: 'Administration & Master Data', icon: Database, roles: ADMIN_ROLES }
  ];

  const visibleTabs = navItems.filter((item) => item.roles.includes(role));

  return (
    <nav className="h-10 min-h-[40px] bg-[#134074] border-b border-slate-700 px-4 flex items-stretch space-x-1 overflow-x-auto shadow-inner text-[12px] select-none shrink-0">
      {visibleTabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`h-full px-3.5 flex items-center space-x-2 whitespace-nowrap transition-colors border-b-2 text-xs font-semibold cursor-pointer ${isActive
                ? 'bg-white text-[#0B2545] border-b-[#FFB703] font-bold shadow-xs'
                : 'text-slate-200 hover:bg-[#0B2545]/70 hover:text-white border-b-transparent'
              }`}
          >
            <span className="w-4 h-4 flex items-center justify-center shrink-0">
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#134074]' : 'text-slate-300'}`} />
            </span>
            <span className="leading-none">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
