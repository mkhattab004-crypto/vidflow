import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Lightbulb, Sparkles, AlertTriangle, Check, ArrowRight } from 'lucide-react'
import { getChannels, suggestIdeas, checkDuplicate, getVideoTypes, createProject } from '../services/api'
import LoadingSpinner from '../components/common/LoadingSpinner'
import useStore from '../store/useStore'

export default function Ideas() {
  const navigate = useNavigate()
  const { setActiveProjectId } = useStore()
  const [channelId, setChannelId] = useState('')
  const [idea, setIdea] = useState('')
  const [videoType, setVideoType] = useState('explainer')
  const [suggestions, setSuggestions] = useState([])
  const [dupResult, setDupResult] = useState(null)

  const { data: channels = [] } = useQuery({ queryKey: ['channels'], queryFn: getChannels })
  const { data: videoTypes = [] } = useQuery({ queryKey: ['videoTypes'], queryFn: getVideoTypes })

  const suggestMutation = useMutation({
    mutationFn: () => suggestIdeas({ channel_id: channelId, count: 5 }),
    onSuccess: (data) => setSuggestions(data),
    onError: (e) => toast.error(e.message),
  })

  const dupMutation = useMutation({
    mutationFn: () => checkDuplicate({ channel_id: channelId, idea }),
    onSuccess: (data) => setDupResult(data),
    onError: (e) => toast.error(e.message),
  })

  const createMutation = useMutation({
    mutationFn: () => createProject({ channel_id: channelId, title: idea, idea, video_type: videoType }),
    onSuccess: (project) => {
      setActiveProjectId(project.id)
      toast.success('Project created!')
      navigate('/content')
    },
    onError: (e) => toast.error(e.message),
  })

  const canProceed = channelId && idea

  return (
    <div className="max-w-3xl">
      <h1 className="page-title">Ideas</h1>
      <p className="page-subtitle">Generate and validate video ideas for your channels</p>

      <div className="card mb-4">
        <label className="label">Select Channel</label>
        <select className="input" value={channelId} onChange={(e) => setChannelId(e.target.value)}>
          <option value="">Choose a channel...</option>
          {channels.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.niche})</option>)}
        </select>
      </div>

      <div className="card mb-4">
        <div className="flex items-start justify-between mb-3">
          <label className="label mb-0">Video Idea</label>
          <button
            className="btn-secondary text-xs py-1"
            disabled={!channelId || suggestMutation.isPending}
            onClick={() => suggestMutation.mutate()}
          >
            <Sparkles size={13} />
            {suggestMutation.isPending ? 'Generating...' : 'Suggest 5 Ideas'}
          </button>
        </div>
        <textarea
          className="input resize-none"
          rows={3}
          placeholder="Describe your video idea..."
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
        />
        {idea && channelId && (
          <button
            className="btn-ghost text-xs mt-2"
            onClick={() => dupMutation.mutate()}
            disabled={dupMutation.isPending}
          >
            {dupMutation.isPending ? 'Checking...' : 'Check for duplicates'}
          </button>
        )}
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
                onClick={() => { setIdea(s.title); setVideoType(s.video_type) }}
              >
                <Lightbulb size={16} className="text-yellow-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-200">{s.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{s.angle}</p>
                  <span className="badge-blue mt-1">{s.video_type}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Duplicate check result */}
      {dupResult && (
        <div className={`card mb-4 border ${dupResult.is_duplicate ? 'border-yellow-600/50 bg-yellow-900/10' : 'border-green-600/50 bg-green-900/10'}`}>
          <div className="flex items-start gap-3">
            {dupResult.is_duplicate
              ? <AlertTriangle size={20} className="text-yellow-400 shrink-0 mt-0.5" />
              : <Check size={20} className="text-green-400 shrink-0 mt-0.5" />}
            <div>
              {dupResult.is_duplicate ? (
                <>
                  <p className="text-sm font-medium text-yellow-300">Similar content detected ({Math.round(dupResult.similarity * 100)}% match)</p>
                  {dupResult.similar_project_title && <p className="text-xs text-slate-400 mt-1">Similar to: "{dupResult.similar_project_title}"</p>}
                  {dupResult.suggested_angle && <p className="text-xs text-brand-400 mt-1">Suggested angle: {dupResult.suggested_angle}</p>}
                </>
              ) : (
                <p className="text-sm font-medium text-green-300">No duplicates found — this is a fresh idea!</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Video type */}
      <div className="card mb-6">
        <label className="label">Video Type</label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {videoTypes.map((t) => (
            <button
              key={t.id}
              onClick={() => setVideoType(t.id)}
              className={`p-2.5 rounded-lg text-sm font-medium border transition-all text-left ${videoType === t.id ? 'border-brand-600 bg-brand-900/20 text-brand-300' : 'border-surface-600 text-slate-400 hover:border-surface-500 hover:text-slate-300'}`}
            >
              <div className="font-medium">{t.label}</div>
              <div className="text-xs opacity-70">{t.label_ar}</div>
            </button>
          ))}
        </div>
      </div>

      <button
        className="btn-primary w-full text-base py-3"
        disabled={!canProceed || createMutation.isPending}
        onClick={() => createMutation.mutate()}
      >
        {createMutation.isPending ? 'Creating...' : 'Create Project & Generate Content'}
        <ArrowRight size={18} />
      </button>
    </div>
  )
}
