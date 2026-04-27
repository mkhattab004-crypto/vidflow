import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Archive, Search, Filter, Copy, Trash2, Edit2, ExternalLink } from 'lucide-react'
import { getProjects, getChannels, deleteProject, copyProject } from '../services/api'
import StatusBadge from '../components/common/StatusBadge'
import LoadingSpinner from '../components/common/LoadingSpinner'
import EmptyState from '../components/common/EmptyState'
import useStore from '../store/useStore'

export default function Projects() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { setActiveProjectId } = useStore()
  const [search, setSearch] = useState('')
  const [filterChannel, setFilterChannel] = useState('')
  const [filterStatus, setFilterStatus] = useState('')

  const { data: channels = [] } = useQuery({ queryKey: ['channels'], queryFn: getChannels })
  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects', filterChannel, filterStatus],
    queryFn: () => getProjects({ channel_id: filterChannel || undefined, status: filterStatus || undefined }),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project deleted') },
  })

  const copyMutation = useMutation({
    mutationFn: copyProject,
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project copied!'); setActiveProjectId(data.new_project_id); navigate('/content') },
  })

  const filtered = projects.filter((p) => !search || p.title.toLowerCase().includes(search.toLowerCase()))

  const STATUSES = ['idea', 'content_generated', 'review1_done', 'review2_done', 'rendering', 'rendered', 'done']

  if (isLoading) return <LoadingSpinner text="Loading projects..." />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Project History</h1>
          <p className="page-subtitle">{projects.length} projects across all channels</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <div className="relative flex-1 max-w-xs">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9" placeholder="Search projects..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select className="input w-48" value={filterChannel} onChange={(e) => setFilterChannel(e.target.value)}>
          <option value="">All Channels</option>
          {channels.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select className="input w-48" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
          <option value="">All Status</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={Archive}
          title="No projects found"
          description="Create a new video from the Ideas page to get started"
          action={<button className="btn-primary mt-2" onClick={() => navigate('/ideas')}>Go to Ideas</button>}
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((p) => {
            const channel = channels.find((c) => c.id === p.channel_id)
            return (
              <div key={p.id} className="card flex items-center gap-4 hover:border-surface-500 transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="font-medium text-slate-100 truncate">{p.title}</p>
                    <StatusBadge status={p.status} />
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-400">
                    {channel && <span>{channel.name}</span>}
                    <span className="badge-gray">{p.video_type}</span>
                    <span>{new Date(p.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    className="btn-ghost p-2 rounded-lg text-xs"
                    title="Continue editing"
                    onClick={() => { setActiveProjectId(p.id); navigate('/content') }}
                  >
                    <Edit2 size={15} />
                  </button>
                  <button
                    className="btn-ghost p-2 rounded-lg text-xs"
                    title="Copy project"
                    onClick={() => copyMutation.mutate(p.id)}
                  >
                    <Copy size={15} />
                  </button>
                  <button
                    className="btn-ghost p-2 rounded-lg text-xs text-red-400 hover:text-red-300"
                    title="Delete"
                    onClick={() => { if (confirm(`Delete "${p.title}"?`)) deleteMutation.mutate(p.id) }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
