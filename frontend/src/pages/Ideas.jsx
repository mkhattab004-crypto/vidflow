import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Lightbulb, Sparkles, ArrowRight, Loader2 } from 'lucide-react'
import { suggestIdeas, quickGenerate, getVideoTypes } from '../services/api'
import useStore from '../store/useStore'

const NICHES = [
  { id: 'educational', label: 'Educational' },
  { id: 'islamic',     label: 'Islamic' },
  { id: 'news',        label: 'News' },
  { id: 'story',       label: 'Story' },
  { id: 'science',     label: 'Science' },
  { id: 'history',     label: 'History' },
  { id: 'finance',     label: 'Finance' },
  { id: 'motivation',  label: 'Motivation' },
]

const LANGUAGES = [
  { id: 'en', label: 'English' },
  { id: 'ar', label: 'Arabic' },
  { id: 'tr', label: 'Turkish' },
]

const TONE_BY_NICHE = {
  islamic:    'respectful',
  news:       'informative',
  story:      'narrative',
  finance:    'professional',
  motivation: 'inspirational',
}

export default function Ideas() {
  const navigate = useNavigate()
  const { setActiveProjectId } = useStore()

  const [title, setTitle]       = useState('')
  const [niche, setNiche]       = useState('educational')
  const [language, setLanguage] = useState('en')
  const [videoType, setVideoType] = useState('explainer')
  const [suggestions, setSuggestions] = useState([])

  const { data: videoTypes = [] } = useQuery({ queryKey: ['videoTypes'], queryFn: getVideoTypes })

  const tone = TONE_BY_NICHE[niche] || 'educational'
  const isIslamic = niche === 'islamic'

  const suggestMutation = useMutation({
    mutationFn: () => suggestIdeas({ niche, language, tone, count: 5 }),
    onSuccess: (data) => setSuggestions(data),
    onError: (e) => toast.error(e.message),
  })

  const generateMutation = useMutation({
  mutationFn: async () => {
    const project = await quickGenerate({
      title: title.trim(),
      niche,
      language,
      tone,
      is_islamic: isIslamic,
      video_type: videoType,
      aspect_ratio: '9:16',
    })

    return project
  },
  onSuccess: (project) => {
    console.log('quickGenerate project:', project)

    if (!project?.id) {
      toast.error('Project was created but no ID was returned')
      return
    }

    setActiveProjectId(project.id)
    toast.success('Script generated!')
    navigate('/content')
  },
  onError: (e) => toast.error(e.message),
})

  return (
    <div className="max-w-3xl">
      <h1 className="page-title">New Video</h1>
      <p className="page-subtitle">Enter a topic, pick a niche and language, then generate your script</p>

      {/* Topic */}
      <div className="card mb-4">
        <div className="flex items-start justify-between mb-3">
          <label className="label mb-0">Topic / Title</label>
          <button
            className="btn-secondary text-xs py-1"
            disabled={suggestMutation.isPending}
            onClick={() => suggestMutation.mutate()}
          >
            <Sparkles size={13} />
            {suggestMutation.isPending ? 'Generating...' : 'Suggest Ideas'}
          </button>
        </div>
        <textarea
          className="input resize-none"
          rows={3}
          placeholder="What is your video about? e.g. 'The miracles of Surah Al-Kahf'"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>

      {/* AI Suggestions */}
      {suggestions.length > 0 && (
        <div className="card mb-4">
          <h3 className="section-title flex items-center gap-2"><Sparkles size={16} /> AI Suggestions</h3>
          <div className="space-y-2">
            {suggestions.map((s, i) => (
              <div
                key={i}
                className="flex items-start gap-3 bg-surface-700 rounded-lg p-3 cursor-pointer hover:bg-surface-600 transition-colors"
                onClick={() => { setTitle(s.title); setVideoType(s.video_type) }}
              >
                <Lightbulb size={16} className="text-yellow-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-200">{s.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{s.angle}</p>
                  <span className="badge-blue mt-1 inline-block">{s.video_type}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Niche + Language */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="card">
          <label className="label">Niche</label>
          <div className="grid grid-cols-2 gap-1.5">
            {NICHES.map((n) => (
              <button
                key={n.id}
                onClick={() => setNiche(n.id)}
                className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all text-left ${
                  niche === n.id
                    ? 'border-brand-600 bg-brand-900/20 text-brand-300'
                    : 'border-surface-600 text-slate-400 hover:border-surface-500 hover:text-slate-300'
                }`}
              >
                {n.label}
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <label className="label">Language</label>
          <div className="space-y-1.5">
            {LANGUAGES.map((l) => (
              <button
                key={l.id}
                onClick={() => setLanguage(l.id)}
                className={`w-full px-3 py-2.5 rounded-lg text-sm font-medium border transition-all text-left ${
                  language === l.id
                    ? 'border-brand-600 bg-brand-900/20 text-brand-300'
                    : 'border-surface-600 text-slate-400 hover:border-surface-500 hover:text-slate-300'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Video Type */}
      <div className="card mb-6">
        <label className="label">Video Type</label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {videoTypes.map((t) => (
            <button
              key={t.id}
              onClick={() => setVideoType(t.id)}
              className={`p-2.5 rounded-lg text-sm font-medium border transition-all text-left ${
                videoType === t.id
                  ? 'border-brand-600 bg-brand-900/20 text-brand-300'
                  : 'border-surface-600 text-slate-400 hover:border-surface-500 hover:text-slate-300'
              }`}
            >
              <div className="font-medium">{t.label}</div>
              <div className="text-xs opacity-70">{t.label_ar}</div>
            </button>
          ))}
        </div>
      </div>

      <button
        className="btn-primary w-full text-base py-3"
        disabled={!title.trim() || generateMutation.isPending}
        onClick={() => generateMutation.mutate()}
      >
        {generateMutation.isPending
          ? <><Loader2 size={18} className="animate-spin" /> Generating Script...</>
          : <><ArrowRight size={18} /> Generate Script</>}
      </button>
    </div>
  )
}
