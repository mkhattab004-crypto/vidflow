import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Image, Search, Zap, CheckCircle, AlertTriangle, ArrowRight, ExternalLink } from 'lucide-react'
import { getProjects, getProject, searchVisuals, assignVisual, autoFillVisuals, getVisualGaps } from '../services/api'
import LoadingSpinner from '../components/common/LoadingSpinner'
import useStore from '../store/useStore'
import { useNavigate } from 'react-router-dom'

const GAP_COLORS = { ok: 'badge-green', missing: 'badge-red', needs_ai: 'badge-purple', suggested: 'badge-yellow' }

export default function Visuals() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { activeProjectId, setActiveProjectId } = useStore()
  const [selectedScene, setSelectedScene] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [mediaType, setMediaType] = useState('video')
  const [searchResults, setSearchResults] = useState([])

  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
  const { data: project } = useQuery({ queryKey: ['project', activeProjectId], queryFn: () => getProject(activeProjectId), enabled: !!activeProjectId })
  const { data: gapAnalysis } = useQuery({ queryKey: ['gaps', activeProjectId], queryFn: () => getVisualGaps(activeProjectId), enabled: !!activeProjectId })

  const searchMutation = useMutation({
    mutationFn: () => searchVisuals({ query: searchQuery, media_type: mediaType, limit: 12 }),
    onSuccess: (data) => setSearchResults(data.results || []),
    onError: (e) => toast.error(e.message),
  })

  const autoFillMutation = useMutation({
    mutationFn: () => autoFillVisuals(activeProjectId),
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ['gaps', activeProjectId] }); toast.success(`Auto-filled ${data.filled} scenes`) },
    onError: (e) => toast.error(e.message),
  })

  const assignMutation = useMutation({
    mutationFn: ({ sceneId, url, source }) => assignVisual({ scene_id: sceneId, visual_url: url, visual_source: source }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['gaps', activeProjectId] }); toast.success('Visual assigned!') },
  })

  if (!activeProjectId) {
    return (
      <div>
        <h1 className="page-title">Visuals</h1>
        <p className="page-subtitle">Find and assign visual assets for each scene</p>
        <div className="card">
          <label className="label">Select Project</label>
          <select className="input max-w-md" onChange={(e) => setActiveProjectId(e.target.value)}>
            <option value="">Choose a project...</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select>
        </div>
      </div>
    )
  }

  const gaps = gapAnalysis?.scenes || []
  const totalFilled = gaps.filter((g) => g.visual_url).length

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Visuals — {project?.title}</h1>
          <p className="page-subtitle">{totalFilled}/{gaps.length} scenes filled</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setActiveProjectId(null)}>Change Project</button>
          <button className="btn-primary" onClick={() => autoFillMutation.mutate()} disabled={autoFillMutation.isPending}>
            <Zap size={16} /> {autoFillMutation.isPending ? 'Filling...' : 'Auto-Fill All'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-5">
        {/* Scene list */}
        <div className="col-span-4">
          <div className="card">
            <h3 className="section-title">Scene Status</h3>
            <div className="space-y-2 max-h-[65vh] overflow-y-auto">
              {gaps.map((g) => (
                <div
                  key={g.scene_id}
                  onClick={() => { setSelectedScene(g); setSearchQuery(g.visual_query || '') }}
                  className={`p-3 rounded-lg cursor-pointer transition-all border ${selectedScene?.scene_id === g.scene_id ? 'border-brand-600 bg-brand-900/20' : 'border-surface-600 hover:border-surface-500 bg-surface-700'}`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-slate-300">Scene {g.order}</span>
                    <span className={GAP_COLORS[g.gap_type] || 'badge-gray'}>{g.gap_type}</span>
                  </div>
                  <p className="text-xs text-slate-400 truncate">{g.visual_query}</p>
                  {g.visual_url && (
                    <div className="mt-2 flex items-center gap-1 text-xs text-green-400">
                      <CheckCircle size={11} /> {g.visual_source}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Search + results */}
        <div className="col-span-8">
          <div className="card mb-4">
            <div className="flex gap-2 mb-3">
              <input
                className="input flex-1"
                placeholder="Search visuals..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && searchMutation.mutate()}
              />
              <select className="input w-28" value={mediaType} onChange={(e) => setMediaType(e.target.value)}>
                <option value="video">Video</option>
                <option value="photo">Photo</option>
              </select>
              <button className="btn-primary" onClick={() => searchMutation.mutate()} disabled={searchMutation.isPending}>
                <Search size={16} /> {searchMutation.isPending ? '...' : 'Search'}
              </button>
            </div>
            <div className="text-xs text-slate-500">Sources: Pexels · Pixabay · Wikimedia</div>
          </div>

          {selectedScene && (
            <div className="mb-3 p-3 bg-surface-700 rounded-lg text-sm">
              <span className="text-slate-400">Assigning to:</span> <span className="text-brand-300 font-medium">Scene {selectedScene.order}</span>
              {selectedScene.visual_query && <span className="text-slate-400"> — "{selectedScene.visual_query}"</span>}
            </div>
          )}

          {searchResults.length > 0 ? (
            <div className="grid grid-cols-3 gap-3">
              {searchResults.map((r) => (
                <div key={r.id} className="bg-surface-700 rounded-lg overflow-hidden group relative">
                  {r.thumb ? (
                    <img src={r.thumb} alt="" className="w-full h-28 object-cover" />
                  ) : (
                    <div className="w-full h-28 bg-surface-600 flex items-center justify-center"><Image size={24} className="text-slate-500" /></div>
                  )}
                  <div className="p-2">
                    <div className="flex items-center justify-between">
                      <span className="badge-gray text-xs">{r.source}</span>
                      {r.duration && <span className="text-xs text-slate-400">{r.duration}s</span>}
                    </div>
                  </div>
                  {selectedScene && (
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                      <button className="btn-primary text-xs py-1.5" onClick={() => assignMutation.mutate({ sceneId: selectedScene.scene_id, url: r.url, source: r.source })}>
                        <CheckCircle size={13} /> Use This
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="card flex items-center justify-center h-48">
              <div className="text-center">
                <Image size={32} className="text-slate-600 mx-auto mb-2" />
                <p className="text-slate-400 text-sm">Search for visuals above</p>
                <p className="text-slate-500 text-xs mt-1">Select a scene on the left, then search</p>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 flex justify-end">
        <button className="btn-primary" onClick={() => navigate('/audio')}>
          Go to Audio <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
