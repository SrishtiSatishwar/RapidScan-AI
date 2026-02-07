import React, { useState, useEffect } from 'react';
import { ChevronRight, AlertCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { API_BASE_URL } from '../config';

export default function Dashboard() {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchQueue = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/queue?facility_id=1`);
      const data = await response.json();
      setScans(data.scans || []);
      setLoading(false);
    } catch (err) { console.error("Sync error:", err); }
  };

  useEffect(() => {
    fetchQueue();
    const interval = setInterval(fetchQueue, 5000); // 5s Polling
    return () => clearInterval(interval);
  }, []);

  const getUrgencyColor = (rank) => {
    if (rank >= 9) return "bg-red-600 text-white";
    if (rank >= 7) return "bg-orange-500 text-white";
    if (rank >= 5) return "bg-yellow-400 text-slate-900";
    return "bg-green-500 text-white";
  };

  if (loading) return <div className="p-20 text-center font-black text-slate-300 animate-pulse tracking-widest uppercase">Synchronizing Worklist...</div>;

  return (
    <div className="max-w-6xl mx-auto mt-8 font-sans">
      <div className="flex justify-between items-end mb-8">
        <h1 className="text-3xl font-black text-slate-900 tracking-tight uppercase">Triage Queue</h1>
        <div className="text-xs font-black text-blue-600 animate-pulse">LIVE UPDATING</div>
      </div>

      <div className="bg-white rounded-[2rem] shadow-sm border border-slate-200 overflow-hidden">
        <div className="divide-y divide-slate-100">
          {scans.map((scan) => (
            <Link to={`/scan/${scan.scan_id}`} key={scan.scan_id} className="grid grid-cols-5 items-center px-8 py-6 hover:bg-slate-50 transition group">
              <div>
                <span className="text-[10px] font-black text-slate-400 uppercase block mb-1">Patient ID</span>
                <span className="font-bold text-slate-800">{scan.patient_id || 'Unknown'}</span>
              </div>
              <div className="col-span-2">
                <span className="text-[10px] font-black text-slate-400 uppercase block mb-1">AI Detection</span>
                <span className="font-bold text-slate-800">{scan.conditions_detected.join(', ') || 'Normal'}</span>
              </div>
              <div className="text-center">
                <span className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-black uppercase ${getUrgencyColor(scan.urgency_ranking)}`}>
                  {scan.urgency_ranking >= 9 && <AlertCircle size={14}/>}
                  Level {scan.urgency_ranking}
                </span>
              </div>
              <div className="flex justify-end gap-6 items-center">
                <span className="text-xs font-bold text-slate-500">{new Date(scan.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                <ChevronRight className="text-slate-300 group-hover:text-blue-500 transition" size={24} />
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}