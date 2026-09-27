import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import DepartmentDashboard from './pages/DepartmentDashboard';
import PlannerDashboard from './pages/PlannerDashboard';
import TrainPosition from './pages/TrainPosition';
import AvailableWindows from './pages/AvailableWindows';
import DynamicReplanning from './pages/DynamicReplanning';
import WhatIf from './pages/WhatIf';
import Reports from './pages/Reports';
import AdminMaster from './pages/AdminMaster';
import ErrorBoundary from './components/ErrorBoundary';
import { getCurrentUser } from './services/auth';

export default function App() {
  const [currentUser, setCurrentUser] = useState(getCurrentUser());
  const [activeTab, setActiveTab] = useState('planner-dashboard');

  const isDeptRole = (role) => {
    const r = (role || '').toUpperCase();
    return ['TRACK_ENGINEERING', 'SIGNAL_TELECOM', 'TRACTION_DISTRIBUTION', 'DEPARTMENT_USER'].includes(r);
  };

  useEffect(() => {
    if (currentUser) {
      if (isDeptRole(currentUser.role)) {
        setActiveTab('dept-dashboard');
      } else {
        setActiveTab('planner-dashboard');
      }
    } else {
      document.title = 'ABPS — Automatic Block Planning System';
    }
  }, [currentUser]);

  useEffect(() => {
    const titles = {
      'dept-dashboard': 'ABPS — Department Maintenance Portal',
      'planner-dashboard': 'ABPS — Control Room',
      'train-position': 'ABPS — Live Train Position',
      'available-windows': 'ABPS — Available Windows',
      'dynamic-replan': 'ABPS — Dynamic Re-Planning',
      'what-if': 'ABPS — What-If Analysis',
      'reports': 'ABPS — Reports & Audit Trail',
      'admin-master': 'ABPS — Administration & Master Data',
    };
    if (currentUser) {
      document.title = titles[activeTab] || 'ABPS — Automatic Block Planning System';
    } else {
      document.title = 'ABPS — Automatic Block Planning System';
    }
  }, [activeTab, currentUser]);

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    if (isDeptRole(user.role)) {
      setActiveTab('dept-dashboard');
    } else {
      setActiveTab('planner-dashboard');
    }
  };

  const renderActiveScreen = () => {
    switch (activeTab) {
      case 'dept-dashboard':
        return <DepartmentDashboard />;
      case 'planner-dashboard':
        return <PlannerDashboard onTabChange={setActiveTab} />;
      case 'train-position':
        return <TrainPosition />;
      case 'available-windows':
        return <AvailableWindows />;
      case 'dynamic-replan':
        return <DynamicReplanning />;
      case 'what-if':
        return <WhatIf />;
      case 'reports':
        return <Reports />;
      case 'admin-master':
        return <AdminMaster />;
      default:
        return <PlannerDashboard onTabChange={setActiveTab} />;
    }
  };

  if (!currentUser) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className={`flex flex-col bg-[#F4F6F9] ${activeTab === 'planner-dashboard' ? 'h-screen max-h-screen overflow-hidden' : 'min-h-screen'}`}>
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      <main className={`flex-1 ${activeTab === 'planner-dashboard' ? 'overflow-hidden flex flex-col' : 'overflow-y-auto'}`}>
        <ErrorBoundary variant="page">
          {renderActiveScreen()}
        </ErrorBoundary>
      </main>
      {activeTab !== 'planner-dashboard' && (
        <footer className="bg-[#0B2545] text-slate-400 text-[11px] py-2 px-4 border-t border-slate-700 flex flex-wrap justify-between items-center select-none">
          <div className="font-semibold text-slate-300">
            ABPS &mdash; Automatic Block Planning System
          </div>
          <div className="font-mono text-slate-400">
            Railway Maintenance Planning &amp; Decision Support
          </div>
        </footer>
      )}
    </div>
  );
}
