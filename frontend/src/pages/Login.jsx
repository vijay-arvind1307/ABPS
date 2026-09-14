import React, { useState } from 'react';
import { Shield, Key, User, ArrowRight, CheckCircle2, Train } from 'lucide-react';
import { loginUser } from '../services/auth';

export default function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState('planner');
  const [password, setPassword] = useState('planner123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await loginUser(username, password);
      onLoginSuccess(user);
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid railway credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const setQuickCredentials = (u, p) => {
    setUsername(u);
    setPassword(p);
  };

  return (
    <div className="min-h-[88vh] flex items-center justify-center p-4">
      <div className="bg-white border-2 border-[#0B2545] shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="bg-[#0B2545] text-white p-5 text-center border-b-4 border-[#FFB703]">
          <div className="w-12 h-12 bg-[#FFB703] text-[#0B2545] font-black text-xl flex items-center justify-center mx-auto mb-2 border border-white">
            IR
          </div>
          <h2 className="text-sm font-bold tracking-wide uppercase">INDIAN RAILWAYS</h2>
          <h3 className="text-base font-extrabold tracking-wide uppercase mt-0.5">
            RAILWAY MAINTENANCE BLOCK PLANNING SYSTEM
          </h3>
          <p className="text-xs text-slate-300 mt-0.5">AI-Assisted Maintenance Block Planning & Optimization</p>
          <div className="mt-2 text-[10px] text-amber-300 font-mono uppercase tracking-wider">
            OPERATIONAL CONTROL & PLANNING PORTAL
          </div>
        </div>

        {/* Login Form */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-2 bg-red-100 border border-red-400 text-red-700 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Official User ID:
              </label>
              <div className="flex items-center border border-slate-300 bg-slate-50 focus-within:border-[#134074] focus-within:bg-white">
                <User className="w-4 h-4 text-slate-400 ml-2.5" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs bg-transparent outline-none"
                  placeholder="e.g. planner, engg_user"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                Security Password:
              </label>
              <div className="flex items-center border border-slate-300 bg-slate-50 focus-within:border-[#134074] focus-within:bg-white">
                <Key className="w-4 h-4 text-slate-400 ml-2.5" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs bg-transparent outline-none"
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full cris-btn cris-btn-primary justify-center py-2 text-xs font-bold uppercase tracking-wider"
            >
              {loading ? 'Authenticating Official...' : 'LOGIN TO PLANNING SYSTEM'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Authorized Role Profiles for Quick Login */}
          <div className="mt-6 pt-4 border-t border-slate-200">
            <div className="text-[11px] font-bold text-slate-600 uppercase mb-2">
              Authorized Role Profiles:
            </div>
            <div className="grid grid-cols-2 gap-1.5 text-[11px]">
              <button
                type="button"
                onClick={() => setQuickCredentials('planner', 'planner123')}
                className={`p-1.5 border text-left font-semibold transition-all cursor-pointer ${
                  username === 'planner'
                    ? 'border-[#0B2545] bg-amber-100 text-slate-950 ring-2 ring-[#0B2545]/20 shadow-xs'
                    : 'border-amber-400 bg-amber-50 hover:bg-amber-100 text-slate-900'
                }`}
              >
                ★ Railway Planner
                <span className="block text-[9px] text-slate-500 font-mono font-normal">Chief Controller Authority</span>
              </button>

              <button
                type="button"
                onClick={() => setQuickCredentials('engg_user', 'engg123')}
                className={`p-1.5 border text-left font-semibold transition-all cursor-pointer ${
                  username === 'engg_user'
                    ? 'border-[#0B2545] bg-blue-100 text-slate-950 ring-2 ring-[#0B2545]/20 shadow-xs'
                    : 'border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-800'
                }`}
              >
                Track Engg (Civil)
                <span className="block text-[9px] text-slate-500 font-mono font-normal">Permanent Way Demands</span>
              </button>

              <button
                type="button"
                onClick={() => setQuickCredentials('snt_user', 'snt123')}
                className={`p-1.5 border text-left font-semibold transition-all cursor-pointer ${
                  username === 'snt_user'
                    ? 'border-[#0B2545] bg-blue-100 text-slate-950 ring-2 ring-[#0B2545]/20 shadow-xs'
                    : 'border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-800'
                }`}
              >
                Signal & Telecom
                <span className="block text-[9px] text-slate-500 font-mono font-normal">S&T Point Overhaul</span>
              </button>

              <button
                type="button"
                onClick={() => setQuickCredentials('trd_user', 'trd123')}
                className={`p-1.5 border text-left font-semibold transition-all cursor-pointer ${
                  username === 'trd_user'
                    ? 'border-[#0B2545] bg-blue-100 text-slate-950 ring-2 ring-[#0B2545]/20 shadow-xs'
                    : 'border-slate-300 bg-slate-50 hover:bg-slate-100 text-slate-800'
                }`}
              >
                Traction Distribution
                <span className="block text-[9px] text-slate-500 font-mono font-normal">25kV OHE Power Blocks</span>
              </button>

              <button
                type="button"
                onClick={() => setQuickCredentials('admin', 'admin123')}
                className={`p-1.5 border text-left font-semibold transition-all cursor-pointer col-span-2 ${
                  username === 'admin'
                    ? 'border-[#0B2545] bg-purple-100 text-slate-950 ring-2 ring-[#0B2545]/20 shadow-xs'
                    : 'border-purple-300 bg-purple-50 hover:bg-purple-100 text-slate-800'
                }`}
              >
                ⚙ System Admin
                <span className="block text-[9px] text-slate-500 font-mono font-normal">Network Infrastructure, Stations & Audit Logs</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
