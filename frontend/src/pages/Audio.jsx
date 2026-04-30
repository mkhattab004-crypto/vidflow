import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Mic, Play, ArrowRight } from 'lucide-react'
import { getProjects, getProject, getVoices, generateAudio, updateProject, previewVoiceUrl } from '../services/api'
import LoadingSpinner from '../components/common/LoadingSpinner'
import useStore from '../store/useStore'
import { useNavigate } from 'react-router-dom'

export default function Audio() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { activeProjectId, setActiveProjectId } = useStore()
  const [selectedVoice, setSelectedVoice] = useState('')
  const [speed, setSpeed] = useState(1.0)
  const [previewText, setPreviewText] = useState('')
  const [previewSrc, setPreviewSrc] = useState('')

  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
  const { data: project } = useQuery({ queryKey: ['project', activeProjectId], queryFn: () => getProject(activeProjectId), enabled: !!activeProjectId })
  const { data: voices = [] } = useQuery({ queryKey: ['voices'], queryFn: () => getVoices() })

  const channelLanguage = project?.language || project?.channel?.language || 'en'
  const isIslamic = project?.is_islamic || project?.channel?.is_islamic || false
  const filteredVoices = voices.filter((v) => !v.language || v.language === channelLanguage || channelLanguage === 'en')

  const genMutation = useMutation({
    mutationFn: () => {
      const scriptText = project.scenes.map((s) => s.script_text || '').join(' ')
      return generateAudio({ project_id: activeProjectId, text: scriptText, voice_id: selectedVoice, speed })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', activeProjectId] }); toast.success('Audio generated!') },
    onError: (e) => toast.error(e.message),
  })

  if (!activeProjectId) {
    return (
      <div>
        <h1 className="page-title">Audio & TTS</h1>
        <p className="page-subtitle">Generate voiceover using Kokoro TTS</p>
        <div className="card"><label className="label">Select Project</label><select className="input max-w-md" onChange={(e) => setActiveProjectId(e.target.value)}><option value="">Choose a project...</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></div>
      </div>
    )
  }

  const RECITER_VOICES = voices.filter((v) => v.type === 'reciter')
  const REGULAR_VOICES = voices.filter((v) => v.type !== 'reciter')

  return (
    <div className="max-w-2xl">
      <h1 className="page-title">Audio — {project?.title}</h1>
      <p className="page-subtitle">Select a voice and generate the narration</p>

      <div className="card mb-4">
        <h3 className="section-title flex items-center gap-2"><Mic size={16} /> Voice Selection</h3>
        {isIslamic && RECITER_VOICES.length > 0 && (
          <div className="mb-4">
            <label className="label">Quran Reciters</label>
            <div className="grid grid-cols-2 gap-2">
              {RECITER_VOICES.map((v) => (
                <button key={v.id} onClick={() => setSelectedVoice(v.id)} className={`p-3 rounded-lg text-sm border text-left transition-all ${selectedVoice === v.id ? 'border-brand-600 bg-brand-900/20 text-brand-300' : 'border-surface-600 text-slate-300 hover:border-surface-500'}`}>
                  <div className="font-medium arabic-text text-base">{v.name}</div>
                </button>
              ))}
            </div>
          </div>
        )}
        <label className="label">Narrator Voices</label>
        <div className="grid grid-cols-2 gap-2">
          {REGULAR_VOICES.map((v) => (
            <button key={v.id} onClick={() => setSelectedVoice(v.id)} className={`p-3 rounded-lg text-sm border text-left transition-all ${selectedVoice === v.id ? 'border-brand-600 bg-brand-900/20 text-brand-300' : 'border-surface-600 text-slate-300 hover:border-surface-500'}`}>
              <div className="font-medium">{v.name}</div>
              <div className="text-xs text-slate-500 mt-0.5">{v.language.toUpperCase()}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="card mb-4">
        <label className="label">Speed: {speed}x</label>
        <input type="range" min="0.5" max="2.0" step="0.1" value={speed} onChange={(e) => setSpeed(parseFloat(e.target.value))} className="w-full accent-brand-500" />
        <div className="flex justify-between text-xs text-slate-500 mt-1"><span>0.5x Slow</span><span>1.0x Normal</span><span>2.0x Fast</span></div>
      </div>

      <div className="card mb-4">
        <label className="label">Preview Text</label>
        <textarea className="input resize-none mb-2" rows={2} placeholder="Type text to preview voice..." value={previewText} onChange={(e) => setPreviewText(e.target.value)} />
        <button
          className="btn-secondary text-sm"
          disabled={!selectedVoice || !previewText}
          onClick={() => setPreviewSrc(previewVoiceUrl(previewText, selectedVoice, speed))}
        >
          <Play size={14} /> Preview Voice
        </button>
        {previewSrc && (
          <audio key={previewSrc} controls autoPlay className="w-full mt-3">
            <source src={previewSrc} type="audio/mpeg" />
          </audio>
        )}
      </div>

      {project?.audio_url && (
        <div className="card mb-4 border-green-700/50 bg-green-900/10">
          <p className="text-sm text-green-300 font-medium">✓ Audio generated successfully</p>
          <p className="text-xs text-slate-400 mt-1">Voice: {project.voice_id} · Speed: {project.audio_speed}x</p>
        </div>
      )}

      <div className="flex gap-3">
        <button className="btn-primary flex-1 py-3" disabled={!selectedVoice || genMutation.isPending} onClick={() => genMutation.mutate()}>
          <Mic size={18} /> {genMutation.isPending ? 'Generating audio...' : 'Generate Full Narration'}
        </button>
        <button className="btn-secondary py-3 px-5" onClick={() => navigate('/templates')}>
          Next <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
