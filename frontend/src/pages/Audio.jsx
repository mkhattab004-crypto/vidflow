import React, { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Mic, Play, ArrowRight } from 'lucide-react'
import { getProjects, getProject, getVoices, generateAudio, previewVoiceUrl } from '../services/api'
import useStore from '../store/useStore'
import { useNavigate } from 'react-router-dom'

const EDGE_DEFAULTS = { ar: 'ar-EG-ShakirNeural', en: 'en-US-GuyNeural', tr: 'tr-TR-AhmetNeural' }

export default function Audio() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { activeProjectId, setActiveProjectId, clearProjectUiState } = useStore()
  const [selectedVoice, setSelectedVoice] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('edge_tts')
  const [showAllLanguages, setShowAllLanguages] = useState(false)
  const [speed, setSpeed] = useState(1.0)
  const [previewText, setPreviewText] = useState('')
  const [previewSrc, setPreviewSrc] = useState('')

  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
  const { data: project } = useQuery({ queryKey: ['project', activeProjectId], queryFn: () => getProject(activeProjectId), enabled: !!activeProjectId })
  const channelLanguage = (project?.language || project?.channel?.language || 'en').toLowerCase()
  const { data: voiceData } = useQuery({ queryKey: ['voices'], queryFn: () => getVoices() })

  const edgeVoiceMap = voiceData?.providers?.edge_tts || { ar: [], en: [], tr: [] }
  const gttsVoiceMap = voiceData?.providers?.gtts || { ar: [], en: [], tr: [] }

  const edgeVisibleVoices = useMemo(() => {
    if (showAllLanguages) return [...edgeVoiceMap.ar, ...edgeVoiceMap.en, ...edgeVoiceMap.tr]
    return edgeVoiceMap[channelLanguage] || edgeVoiceMap.en || []
  }, [edgeVoiceMap, channelLanguage, showAllLanguages])

  const gttsVisibleVoices = gttsVoiceMap[channelLanguage] || gttsVoiceMap.en || []
  const visibleVoices = selectedProvider === 'gtts' ? gttsVisibleVoices : edgeVisibleVoices

  useEffect(() => {
    setPreviewSrc('')
    clearProjectUiState()
    if (activeProjectId) qc.invalidateQueries({ queryKey: ['project', activeProjectId] })
  }, [activeProjectId, clearProjectUiState, qc])

  useEffect(() => {
    if (!selectedVoice) {
      setSelectedVoice(selectedProvider === 'edge_tts' ? (EDGE_DEFAULTS[channelLanguage] || EDGE_DEFAULTS.en) : `gtts-${channelLanguage}`)
    }
  }, [channelLanguage, selectedProvider, selectedVoice])

  const genMutation = useMutation({
    mutationFn: () => generateAudio({ project_id: project?.id, voice_id: selectedVoice, speed, tts_provider: selectedProvider }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', activeProjectId] }); toast.success('Audio generated!') },
    onError: (e) => toast.error(e.message),
  })

  if (!activeProjectId) return <div><h1 className="page-title">Audio & TTS</h1><div className="card"><label className="label">Select Project</label><select className="input max-w-md" onChange={(e) => setActiveProjectId(e.target.value)}><option value="">Choose a project...</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></div></div>

  return (
    <div className="max-w-2xl">
      <h1 className="page-title">Audio — {project?.title}</h1>
      <p className="page-subtitle">Select a voice and generate the narration</p>
      <div className="card mb-4">
        <h3 className="section-title flex items-center gap-2"><Mic size={16} /> Voice Selection</h3>
        <label className="label">Provider</label>
        <select className="input mb-3" value={selectedProvider} onChange={(e) => { setSelectedProvider(e.target.value); setSelectedVoice('') }}>
          <option value="edge_tts">Edge TTS</option>
          <option value="gtts">gTTS Free</option>
        </select>
        {selectedProvider === 'gtts' && <p className="text-xs text-slate-400 mb-3">gTTS is free but does not support named voices or gender selection.</p>}
        {selectedProvider === 'edge_tts' && (
          <label className="flex items-center gap-2 text-sm text-slate-300 mb-3">
            <input type="checkbox" checked={showAllLanguages} onChange={(e) => setShowAllLanguages(e.target.checked)} />
            Show all languages
          </label>
        )}
        <div className="grid grid-cols-2 gap-2">
          {visibleVoices.map((v) => (
            <button key={v.name} onClick={() => setSelectedVoice(v.name)} className={`p-3 rounded-lg text-sm border text-left transition-all ${selectedVoice === v.name ? 'border-brand-600 bg-brand-900/20 text-brand-300' : 'border-surface-600 text-slate-300 hover:border-surface-500'}`}>
              <div className="font-medium">{v.display_name}</div>
              <div className="text-xs text-slate-500 mt-0.5">{v.locale} · {v.gender}</div>
            </button>
          ))}
        </div>
      </div>

      <div className="card mb-4">
        <label className="label">Preview Text</label>
        <textarea className="input resize-none mb-2" rows={2} placeholder="Type text to preview voice..." value={previewText} onChange={(e) => setPreviewText(e.target.value)} />
        <button className="btn-secondary text-sm" disabled={!selectedVoice || !previewText} onClick={() => setPreviewSrc(previewVoiceUrl(previewText, selectedVoice, speed, selectedProvider, channelLanguage))}>
          <Play size={14} /> Preview Voice
        </button>
        {previewSrc && <audio key={previewSrc} controls autoPlay className="w-full mt-3"><source src={previewSrc} type="audio/mpeg" /></audio>}
      </div>

      <div className="flex gap-3">
        <button className="btn-primary flex-1 py-3" disabled={!selectedVoice || genMutation.isPending} onClick={() => genMutation.mutate()}><Mic size={18} /> {genMutation.isPending ? 'Generating audio...' : 'Generate Full Narration'}</button>
        <button className="btn-secondary py-3 px-5" onClick={() => navigate('/templates')}>Next <ArrowRight size={16} /></button>
      </div>
    </div>
  )
}
