import React, { useState, useEffect, useRef } from 'react';
import AppBrand from './AppBrand';
import {
  Clock,
  User,
  LogOut,
  Radio,
  Bell,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  CheckCheck,
  Zap,
  Info
} from 'lucide-react';
import { getCurrentUser, logoutUser } from '../services/auth';
import {
  getDataStatus,
  getNotifications,
  getUnreadNotificationCount,
  markNotificationRead,
  markAllNotificationsRead
} from '../services/api';

export default function Header({ onTabChange, activeTab }) {
  const [currentUser, setCurrentUser] = useState(getCurrentUser());
  const [currentTime, setCurrentTime] = useState(new Date().toLocaleTimeString('en-IN', { hour12: false }));
  const [provenance, setProvenance] = useState({
    status: 'UNAVAILABLE',
    provider: 'RailRadar (Live)',
    is_live: false
  });

  // Notifications State
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);
  const [loadingNotifs, setLoadingNotifs] = useState(false);
  const notifDropdownRef = useRef(null);

  const loadHeaderTelemetry = async () => {
    try {
      const statusRes = await getDataStatus();
      if (statusRes.data) {
        setProvenance({
          status: statusRes.data.status,
          provider: statusRes.data.provider,
          is_live: statusRes.data.is_live
        });
      }
    } catch (err) {
      // Keep existing status
    }
  };

  const loadNotificationStats = async () => {
    try {
      const countRes = await getUnreadNotificationCount();
      setUnreadCount(countRes.data?.unread_count || 0);
    } catch (err) {
      // Silently handle if unauthenticated or network drop
    }
  };

  const fetchFullNotifications = async () => {
    setLoadingNotifs(true);
    try {
      const res = await getNotifications(20);
      setNotifications(res.data || []);
      const countRes = await getUnreadNotificationCount();
      setUnreadCount(countRes.data?.unread_count || 0);
    } catch (err) {
      console.warn('Failed to load notifications:', err);
    } finally {
      setLoadingNotifs(false);
    }
  };

  const handleToggleNotifications = () => {
    if (!showNotifications) {
      fetchFullNotifications();
    }
    setShowNotifications(!showNotifications);
  };

  const handleMarkAsRead = async (id, e) => {
    e.stopPropagation();
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.error('Failed to mark notification read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error('Failed to mark all notifications read:', err);
    }
  };

  useEffect(() => {
    loadHeaderTelemetry();
    loadNotificationStats();

    const clockTimer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('en-IN', { hour12: false }));
    }, 1000);

    const telemetryTimer = setInterval(() => {
      loadHeaderTelemetry();
      loadNotificationStats();
    }, 25000);

    // Close notifications on outside click
    const handleClickOutside = (event) => {
      if (notifDropdownRef.current && !notifDropdownRef.current.contains(event.target)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      clearInterval(clockTimer);
      clearInterval(telemetryTimer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleLogout = () => {
    logoutUser();
    window.location.reload();
  };

  const getRoleBadge = (role, dept) => {
    if (role === 'railway_planner' || role === 'planner') {
      return (
        <span className="h-4.5 inline-flex items-center bg-amber-500 text-slate-950 font-black px-2 text-[10px] border border-amber-300 tracking-wider uppercase leading-none">
          CHIEF SECTION CONTROLLER
        </span>
      );
    }
    if (role === 'admin' || role === 'system_admin') {
      return (
        <span className="h-4.5 inline-flex items-center bg-purple-600 text-white font-bold px-2 text-[10px] border border-purple-300 uppercase leading-none">
          SYSTEM ADMIN
        </span>
      );
    }
    return (
      <span className="h-4.5 inline-flex items-center bg-emerald-600 text-white font-bold px-2 text-[10px] border border-emerald-300 uppercase leading-none">
        DEPT: {dept || 'ENGG'}
      </span>
    );
  };

  const renderProvenanceIndicator = () => {
    const s = (provenance.status || '').toUpperCase();
    if (s === 'LIVE RADAR' || s === 'LIVE') {
      return (
        <div className="flex items-center space-x-1.5 text-slate-300 leading-none">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>DATA SOURCE: <strong className="text-white font-semibold">RailRadar</strong></span>
          <span className="text-slate-600">|</span>
          <span>TELEMETRY: <strong className="text-emerald-400 font-bold">● LIVE</strong></span>
        </div>
      );
    }
    if (s === 'CACHED' || s === 'STALE') {
      return (
        <div className="flex items-center space-x-1.5 text-slate-300 leading-none">
          <span className="w-2 h-2 rounded-full bg-amber-400"></span>
          <span>DATA SOURCE: <strong className="text-white font-semibold">RailRadar</strong></span>
          <span className="text-slate-600">|</span>
          <span>TELEMETRY: <strong className="text-amber-400 font-bold">● STALE · 42s</strong></span>
        </div>
      );
    }
    return (
      <div className="flex items-center space-x-1.5 text-slate-300 leading-none">
        <span className="w-2 h-2 rounded-full bg-rose-500"></span>
        <span>DATA SOURCE: <strong className="text-white font-semibold">RailRadar</strong></span>
        <span className="text-slate-600">|</span>
        <span>TELEMETRY: <strong className="text-rose-400 font-bold">● UNAVAILABLE</strong></span>
      </div>
    );
  };

  const getNotifIcon = (type) => {
    switch (type) {
      case 'PLAN_APPROVED':
        return <CheckCircle className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />;
      case 'CHANGE_REQUESTED':
        return <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />;
      case 'DISTURBANCE_DETECTED':
        return <Zap className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />;
      default:
        return <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />;
    }
  };

  return (
    <header className="h-20 min-h-[80px] bg-[#0B2545] text-white border-b-2 border-[#FFB703] px-4 flex items-center justify-between shadow-md relative z-40 shrink-0 select-none">
      {/* ── ZONE 1: LEFT - Official ABPS Brand & System Identity ── */}
      <div className="flex items-center space-x-3 shrink-0 py-1">
        <AppBrand variant="header" logoHeight="68px" />
      </div>

      {/* ── ZONE 2 & 3: RIGHT - Telemetry, Alerts & Compact Logout ── */}
      <div className="flex items-center space-x-2.5 shrink-0">
        {/* Telemetry Strip */}
        <div className="flex items-center space-x-2.5 text-[10px] font-mono bg-[#081b33] px-2.5 h-7 border border-slate-700 shrink-0">
          <div className="flex items-center space-x-1 text-slate-300 leading-none">
            <Clock className="w-3 h-3 text-[#FFB703]" />
            <span>IR-RTC: <strong className="text-white font-bold">{currentTime} IST</strong></span>
          </div>
          <span className="text-slate-600">|</span>
          {renderProvenanceIndicator()}
          <span className="text-slate-600">|</span>
          <div className="text-slate-300 leading-none">
            ZONE: <strong className="text-[#FFB703]">SOUTHERN RAILWAY (SR)</strong>
          </div>
        </div>

        {/* Notification Bell Dropdown */}
        <div className="relative" ref={notifDropdownRef}>
          <button
            onClick={handleToggleNotifications}
            title="Operational Notifications & Handshake Alerts"
            className="h-7 w-7 bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 hover:text-white flex items-center justify-center transition-colors cursor-pointer relative"
          >
            <Bell className="w-3.5 h-3.5" />
            {unreadCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 bg-red-600 text-white font-mono font-black text-[9px] min-w-[16px] h-[16px] flex items-center justify-center rounded-full border border-white px-0.5 animate-pulse shadow">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {/* Dropdown Panel */}
          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 md:w-96 bg-white text-slate-900 border-2 border-[#0B2545] shadow-2xl z-50 text-xs">
              <div className="bg-[#0B2545] text-white p-2.5 flex items-center justify-between border-b border-[#FFB703]">
                <div className="flex items-center space-x-1.5">
                  <Bell className="w-3.5 h-3.5 text-[#FFB703]" />
                  <span className="font-bold uppercase tracking-wider text-[11px]">
                    CRIS Operational Alerts ({unreadCount} unread)
                  </span>
                </div>
                {unreadCount > 0 && (
                  <button
                    onClick={handleMarkAllRead}
                    className="text-[10px] font-bold text-amber-300 hover:text-white flex items-center space-x-1 cursor-pointer"
                  >
                    <CheckCheck className="w-3 h-3" />
                    <span>Mark all read</span>
                  </button>
                )}
              </div>

              <div className="max-h-80 overflow-y-auto divide-y divide-slate-200">
                {loadingNotifs ? (
                  <div className="p-4 text-center text-slate-500 flex items-center justify-center space-x-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-blue-900" />
                    <span>Loading alerts...</span>
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="p-6 text-center text-slate-500">
                    <CheckCircle className="w-6 h-6 text-slate-300 mx-auto mb-1.5" />
                    <p className="font-bold text-slate-700">No Notifications</p>
                    <p className="text-[10px] text-slate-400">All departmental blocks and plans are synchronized.</p>
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      className={`p-2.5 hover:bg-blue-50/70 transition-colors flex items-start space-x-2.5 ${!n.is_read ? 'bg-amber-50/50 font-medium' : 'bg-white'
                        }`}
                    >
                      {getNotifIcon(n.notification_type)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1">
                          <h4 className="font-bold text-slate-900 text-xs truncate">{n.title}</h4>
                          <span className="text-[9px] text-slate-400 font-mono whitespace-nowrap">
                            {n.created_at ? new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 mt-0.5 leading-tight">{n.message}</p>
                        <div className="mt-1 flex items-center justify-between">
                          <span className="text-[9px] bg-slate-100 text-slate-700 border border-slate-300 px-1 font-mono">
                            {n.notification_type || 'SYSTEM'}
                          </span>
                          {!n.is_read && (
                            <button
                              onClick={(e) => handleMarkAsRead(n.id, e)}
                              className="text-[10px] text-blue-700 hover:text-blue-900 font-bold cursor-pointer"
                            >
                              Dismiss
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="p-2 bg-slate-100 border-t border-slate-200 text-center">
                <button
                  onClick={() => {
                    setShowNotifications(false);
                    if (onTabChange) onTabChange(currentUser?.role === 'department_user' ? 'dept-dashboard' : 'planner-dashboard');
                  }}
                  className="text-[11px] font-bold text-[#0B2545] hover:underline cursor-pointer"
                >
                  View Operational Workspace &rarr;
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Integrated User / Logout Block */}
        {currentUser ? (
          <div className="flex items-center gap-2 pl-2.5 border-l border-slate-700 h-7 shrink-0">
            <span className="text-[10px] font-bold text-slate-300 font-mono hidden 2xl:inline truncate max-w-[120px]">
              {currentUser.full_name?.split('/')[0]?.trim() || 'Planner'}
            </span>
            <button
              onClick={handleLogout}
              title="Logout from Railway Terminal"
              className="h-7 px-2 bg-slate-800 hover:bg-red-900 border border-slate-600 text-slate-200 hover:text-white flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider transition-colors cursor-pointer shrink-0"
            >
              <LogOut className="w-3 h-3" />
              <span className="font-bold">Logout</span>
            </button>
          </div>
        ) : (
          <div className="text-xs text-amber-300 font-bold">UNAUTHENTICATED</div>
        )}
      </div>
    </header>
  );
}
