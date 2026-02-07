import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
// Changed Activity to Stethoscope
import { Stethoscope, LayoutDashboard, Upload as UploadIcon, LogOut, ShieldCheck } from 'lucide-react';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import { jwtDecode } from "jwt-decode";

import UploadPage from './pages/Upload';
import DashboardPage from './pages/Dashboard';
import DetailPage from './pages/Detail';

// --- UPDATED LOGIN PAGE ---
const LoginPage = ({ onLoginSuccess }) => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4 font-sans">
      <div className="max-w-md w-full bg-white p-10 rounded-[3rem] shadow-2xl border border-slate-200 text-center">
        <div className="mb-8">
          <div className="bg-blue-100 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4">
            {/* Using Stethoscope here too for branding consistency */}
            <Stethoscope className="text-blue-600" size={40} />
          </div>
          <h1 className="text-4xl font-black text-slate-800 tracking-tighter leading-none">RapidScan</h1>
          <p className="text-slate-400 font-bold text-[10px] uppercase tracking-[0.3em] mt-2">Clinical Decision Support</p>
        </div>

        <div className="space-y-6">
          <div className="p-6 bg-slate-50 rounded-2xl border border-slate-100 mb-6">
            <p className="text-sm text-slate-500 font-medium leading-relaxed">
              Secure Physician Portal. Please authenticate with your Google account to access patient triage data.
            </p>
          </div>

          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={(credentialResponse) => {
                const decoded = jwtDecode(credentialResponse.credential);
                onLoginSuccess(decoded);
              }}
              onError={() => alert("Authentication Failed.")}
              useOneTap
              shape="pill"
              theme="filled_black"
              size="large"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [user, setUser] = useState(null);
  const GOOGLE_CLIENT_ID = "680190226804-ic6ov3kahls2prjqaauen1galb598n28.apps.googleusercontent.com";

  if (!user) {
    return (
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <LoginPage onLoginSuccess={(userData) => setUser(userData)} />
      </GoogleOAuthProvider>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
        
        {/* NAVIGATION BAR */}
        <nav className="bg-slate-900 text-white px-8 py-5 flex justify-between items-center shadow-2xl z-10">
          <div className="flex items-center gap-3">
            <div className="bg-blue-600 p-2 rounded-xl shadow-lg">
              {/* Heartbeat icon changed to Stethoscope */}
              <Stethoscope className="text-white" size={20} />
            </div>
            <div>
              <span className="font-black tracking-tight text-2xl leading-none block">RapidScan</span>
            </div>
          </div>

          <div className="flex gap-10 items-center">
            <Link to="/" className="flex items-center gap-2 hover:text-blue-400 font-bold text-xs uppercase tracking-widest transition">
              <UploadIcon size={18}/> Upload
            </Link>
            <Link to="/dashboard" className="flex items-center gap-2 hover:text-blue-400 font-bold text-xs uppercase tracking-widest transition">
              <LayoutDashboard size={18}/> Queue
            </Link>
            
            <div className="h-6 w-[1px] bg-slate-700 mx-2"></div>

            <div className="flex items-center gap-4">
               <img src={user.picture} alt="Profile" className="w-8 h-8 rounded-full border border-slate-600 shadow-sm" />
               <button 
                onClick={() => setUser(null)} 
                className="text-slate-400 hover:text-red-500 transition"
                title="Logout"
              >
                <LogOut size={20} />
              </button>
            </div>
          </div>
        </nav>

        <main className="flex-grow container mx-auto p-8">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/scan/:id" element={<DetailPage />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>

        <footer className="p-6 text-center text-slate-400 text-[9px] font-black uppercase tracking-[0.2em]">
          RapidScan TERMINAL • {new Date().toLocaleDateString()}
        </footer>
      </div>
    </Router>
  );
}