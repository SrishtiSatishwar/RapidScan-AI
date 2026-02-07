import React, { useState } from 'react';
import { Upload as UploadIcon, CheckCircle, Activity, User, Calendar, Droplets } from 'lucide-react';
import { Link } from 'react-router-dom';
import { API_BASE_URL } from '../config';

export default function Upload() {
  const [file, setFile] = useState(null);
  const [patientId, setPatientId] = useState('');
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [bloodType, setBloodType] = useState('A+');
  const [status, setStatus] = useState('idle');
  const [analysis, setAnalysis] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setStatus('uploading');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('patient_id', patientId);
    formData.append('patient_name', name);
    formData.append('patient_age', age);
    formData.append('patient_blood_type', bloodType);
    formData.append('facility_id', '1');
    formData.append('use_rag', 'true');

    try {
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (response.ok) {
        setAnalysis(data);
        setStatus('success');
      }
    } catch (err) {
      console.error(err);
      setStatus('idle');
    }
  };

  if (status === 'success' && analysis) {
    return (
      <div className="max-w-2xl mx-auto mt-10">
        <div className="bg-white p-10 rounded-[2.5rem] shadow-2xl border-4 border-blue-600 animate-in zoom-in duration-300">
          <div className="flex items-center gap-4 mb-8">
            <CheckCircle className="text-green-500" size={40} />
            <h2 className="text-3xl font-black text-slate-800 tracking-tighter uppercase">Triage Confirmed</h2>
          </div>
          
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 text-center">
              <span className="text-[10px] font-black text-slate-400 uppercase block mb-1">Patient</span>
              <span className="font-bold text-slate-700">{name}</span>
            </div>
            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 text-center">
              <span className="text-[10px] font-black text-slate-400 uppercase block mb-1">Age</span>
              <span className="font-bold text-slate-700">{age}y</span>
            </div>
            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 text-center">
              <span className="text-[10px] font-black text-slate-400 uppercase block mb-1">Urgency</span>
              <span className={`font-black ${analysis.urgency_ranking >= 8 ? 'text-red-600' : 'text-blue-600'}`}>{analysis.urgency_ranking}/10</span>
            </div>
          </div>

          <div className="bg-slate-900 p-6 rounded-2xl text-white mb-8">
            <h3 className="text-xs font-black text-blue-400 uppercase mb-2 tracking-widest">Initial AI Reasoning</h3>
            <p className="text-sm font-medium leading-relaxed italic opacity-90">"{analysis.gemini_reasoning}"</p>
          </div>

          <Link to="/dashboard" className="w-full py-5 bg-blue-600 text-white rounded-2xl font-black flex items-center justify-center gap-3 hover:bg-blue-700 transition shadow-xl uppercase tracking-widest">
            Entry Patient into Queue
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto mt-10 bg-white p-10 rounded-[2.5rem] shadow-sm border border-slate-200">
      <h1 className="text-2xl font-black text-slate-800 mb-8 uppercase tracking-tight">New Radiology Intake</h1>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-xs font-black text-slate-400 uppercase ml-1">Full Name</label>
            <div className="relative">
              <User className="absolute left-4 top-4 text-slate-300" size={18} />
              <input required type="text" value={name} onChange={(e) => setName(e.target.value)} className="w-full pl-12 p-4 bg-slate-50 border rounded-2xl outline-none font-bold" placeholder="Patient Name" />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-black text-slate-400 uppercase ml-1">Patient ID</label>
            <input required type="text" value={patientId} onChange={(e) => setPatientId(e.target.value)} className="w-full p-4 bg-slate-50 border rounded-2xl outline-none font-bold" placeholder="MRN / ID" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-xs font-black text-slate-400 uppercase ml-1">Age</label>
            <div className="relative">
              <Calendar className="absolute left-4 top-4 text-slate-300" size={18} />
              <input required type="number" value={age} onChange={(e) => setAge(e.target.value)} className="w-full pl-12 p-4 bg-slate-50 border rounded-2xl outline-none font-bold" placeholder="Years" />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-black text-slate-400 uppercase ml-1">Blood Type</label>
            <div className="relative">
              <Droplets className="absolute left-4 top-4 text-red-300" size={18} />
              <select value={bloodType} onChange={(e) => setBloodType(e.target.value)} className="w-full pl-12 p-4 bg-slate-50 border rounded-2xl outline-none font-bold appearance-none">
                {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div className="border-2 border-dashed border-slate-200 rounded-[2rem] p-12 text-center bg-slate-50 relative group">
          <input type="file" onChange={(e) => setFile(e.target.files[0])} className="absolute inset-0 opacity-0 cursor-pointer" accept="image/*" />
          <UploadIcon className="mx-auto text-slate-300 group-hover:text-blue-500 mb-4 transition" size={48} />
          <p className="font-black text-slate-600 uppercase tracking-tighter">{file ? file.name : "SELECT CHEST X-RAY SCAN"}</p>
        </div>

        <button type="submit" disabled={!file || status === 'uploading'} className="w-full py-5 rounded-2xl font-black text-lg shadow-lg bg-blue-600 text-white hover:bg-blue-700 transition flex justify-center gap-2 uppercase tracking-widest">
          {status === 'uploading' ? <Activity className="animate-spin"/> : 'PROCESS AI TRIAGE'}
        </button>
      </form>
    </div>
  );
}