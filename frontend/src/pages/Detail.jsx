import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { 
  ChevronLeft, Layers, ShieldCheck, Activity, 
  User, Droplets, Calendar, FileText, AlertCircle, Clock 
} from 'lucide-react';
import { API_BASE_URL } from '../config';

export default function Detail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [scan, setScan] = useState(null);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [isPatching, setIsPatching] = useState(false);

  // Fetch the full scan details from the backend
  useEffect(() => {
    fetch(`${API_BASE_URL}/scan/${id}`)
      .then(res => res.json())
      .then(data => setScan(data))
      .catch(err => console.error("Error fetching scan details:", err));
  }, [id]);

  // Handle the "Confirm Review" button (PATCH request)
  const markReviewed = async () => {
    setIsPatching(true);
    try {
      const res = await fetch(`${API_BASE_URL}/scan/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'reviewed' })
      });
      if (res.ok) {
        navigate('/dashboard');
      }
    } catch (err) {
      console.error("Error updating status:", err);
    } finally {
      setIsPatching(false);
    }
  };

  if (!scan) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center space-y-4">
        <Activity className="text-blue-500 animate-spin" size={48} />
        <p className="text-slate-400 font-black uppercase tracking-[0.3em]">Decoding Medical Data...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-20 font-sans">
      
      {/* TOP NAVIGATION BAR */}
      <div className="flex justify-between items-center bg-white p-4 rounded-2xl border shadow-sm">
        <Link to="/dashboard" className="flex items-center text-slate-500 font-bold hover:text-blue-600 transition">
          <ChevronLeft size={20} /> Back to Triage Queue
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-[10px] font-bold text-slate-400 uppercase hidden md:block">
            Final Clinical Confirmation
          </span>
          <button 
            onClick={markReviewed}
            disabled={isPatching}
            className="bg-slate-900 text-white px-8 py-3 rounded-xl font-black text-sm flex items-center gap-2 hover:bg-black transition shadow-lg disabled:opacity-50"
          >
            <ShieldCheck size={18} /> 
            {isPatching ? "UPDATING..." : "CONFIRM REVIEW"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* LEFT COLUMN: PATIENT BIO-PROFILE */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white p-8 rounded-[2.5rem] border shadow-sm h-full flex flex-col">
            <h2 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-6">Physician View: Bio-Data</h2>
            
            <div className="space-y-6 flex-grow">
              {/* Name & ID Header */}
              <div className="flex items-center gap-4 border-b pb-6">
                <div className="bg-blue-50 p-4 rounded-2xl text-blue-600">
                  <User size={32} />
                </div>
                <div>
                  <h3 className="text-2xl font-black text-slate-800 tracking-tighter leading-none">
                    {scan.patient_name || "Unknown Patient"}
                  </h3>
                  <p className="text-slate-400 font-bold text-xs mt-1">MRN: {scan.patient_id}</p>
                </div>
              </div>

              {/* Age & Blood Type Grid */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                  <div className="flex items-center gap-2 text-slate-400 mb-1 font-bold text-[10px] uppercase">
                    <Calendar size={12}/> Patient Age
                  </div>
                  <span className="font-black text-slate-700 text-lg">{scan.patient_age} Years</span>
                </div>
                <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                  <div className="flex items-center gap-2 text-red-400 mb-1 font-bold text-[10px] uppercase">
                    <Droplets size={12}/> Blood Type
                  </div>
                  <span className="font-black text-slate-700 text-lg">{scan.patient_blood_type}</span>
                </div>
              </div>

              {/* Medical File / RAG Context */}
              <div className="p-6 bg-slate-50 rounded-3xl border border-slate-100">
                <div className="flex items-center gap-2 text-slate-500 mb-3 font-black text-[10px] uppercase tracking-widest">
                  <FileText size={14}/> Electronic Medical File
                </div>
                <p className="text-xs text-slate-600 font-bold leading-relaxed overflow-y-auto max-h-48 scrollbar-hide">
                  {scan.patient_medical_file || "No historical records found for this patient ID."}
                </p>
              </div>
            </div>

            {/* Urgency Badge at bottom of sidebar */}
            <div className={`mt-8 p-6 rounded-2xl flex items-center justify-between shadow-inner ${
              scan.urgency_ranking >= 9 ? 'bg-red-600 text-white' : 'bg-slate-900 text-white'
            }`}>
               <div>
                 <span className="text-[10px] font-black uppercase tracking-widest block opacity-70 mb-1">Triage Priority</span>
                 <span className="text-3xl font-black italic tracking-tighter uppercase">Level {scan.urgency_ranking}/10</span>
               </div>
               {scan.urgency_ranking >= 9 && <AlertCircle size={32} className="animate-pulse" />}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: SCAN & AI FINDINGS */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* Main X-Ray Viewer */}
          <div className="relative bg-black rounded-[3rem] overflow-hidden aspect-video shadow-2xl border-4 border-white group">
            <img 
              src={`${API_BASE_URL}${scan.image_url}`} 
              className={`w-full h-full object-cover transition-all duration-1000 ${
                showHeatmap ? 'opacity-40 brightness-50 contrast-125 scale-105 blur-[1px]' : 'opacity-100'
              }`} 
              alt="Radiology Scan"
            />
            
            {/* Heatmap Glow Effect */}
            {showHeatmap && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-1/2 h-1/2 bg-red-600 rounded-full blur-[110px] opacity-70 animate-pulse" />
                <div className="absolute top-1/4 left-1/3 w-32 h-32 bg-yellow-400 rounded-full blur-[60px] opacity-30 animate-pulse delay-150" />
              </div>
            )}

            {/* Overlay UI elements */}
            <div className="absolute top-8 left-8 flex flex-col gap-2">
               <div className="bg-black/40 backdrop-blur-md border border-white/20 text-white text-[10px] px-4 py-1.5 rounded-full font-mono font-bold">
                 SCAN_ID: {scan.scan_id}
               </div>
               <div className="bg-blue-600 text-white text-[10px] px-4 py-1.5 rounded-full font-black uppercase tracking-[0.2em] shadow-lg">
                 AI Triage Mode
               </div>
            </div>

            <button 
              onClick={() => setShowHeatmap(!showHeatmap)} 
              className={`absolute bottom-8 right-8 px-10 py-5 rounded-2xl font-black shadow-2xl flex items-center gap-3 transition-all transform active:scale-95 ${
                showHeatmap ? 'bg-red-600 text-white' : 'bg-white text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Layers size={24} /> {showHeatmap ? "HIDE AI HEATMAP" : "VIEW AI HEATMAP"}
            </button>
          </div>

          {/* AI Diagnostic Panel */}
          <div className="bg-white p-10 rounded-[2.5rem] border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <Activity className="text-blue-600" size={24} />
                <h2 className="text-xs font-black text-slate-400 uppercase tracking-[0.2em]">Clinical Reasoning (Gemini LLM)</h2>
              </div>
              <div className="flex items-center gap-2 text-slate-400">
                <Clock size={14} />
                <span className="text-[10px] font-bold uppercase">{new Date(scan.timestamp).toLocaleString()}</span>
              </div>
            </div>

            <p className="text-slate-800 font-bold leading-relaxed bg-slate-50 p-8 rounded-[2rem] border text-xl italic mb-10 shadow-inner">
              "{scan.gemini_reasoning}"
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
              {/* Conditions List */}
              <div className="space-y-3">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">AI Pathological Findings</span>
                <div className="flex flex-wrap gap-2">
                  {scan.conditions_detected && scan.conditions_detected.length > 0 ? (
                    scan.conditions_detected.map((condition, idx) => (
                      <span key={idx} className="px-4 py-2 bg-slate-900 text-white text-[11px] font-black rounded-xl uppercase tracking-wider shadow-sm">
                        {condition}
                      </span>
                    ))
                  ) : (
                    <span className="text-slate-400 italic">No pathologies detected</span>
                  )}
                </div>
              </div>

              {/* Confidence Meter */}
              <div className="text-right space-y-3">
                 <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block">AI Confidence Level</span>
                 <div className="flex items-center justify-end gap-4">
                    <span className="font-black text-red-600 text-4xl tracking-tighter">{scan.confidence_score}%</span>
                    <div className="w-40 bg-slate-100 h-4 rounded-full overflow-hidden shadow-inner border border-slate-50">
                      <div 
                        className="bg-red-500 h-full transition-all duration-[2000ms] ease-out shadow-[0_0_10px_rgba(239,68,68,0.5)]" 
                        style={{ width: `${scan.confidence_score}%` }}
                      ></div>
                    </div>
                 </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}