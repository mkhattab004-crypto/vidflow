import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { CheckSquare, Check, X, Lock, AlertTriangle, ArrowRight, Play } from 'lucide-react'
import { getProjects, getProject, updateProject, renderVideo, getRenderStatus } from '../services/api'
import LoadingSpinner from '../components/common/LoadingSpinner'
import useStore from '../store/useStore'
import { useNavigate } from 'react-router-dom'

function ReviewStep({ number, title, subtitle, approved, onApprove, onReject, locked, notes, isIslamic }) {
  return (
    <div className={`card border ${approved ? 'border-green-600/50 bg-green-900/10' : 'border-surface-600'}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${approved ? 'bg-green-600' : 'bg-surface-600'}`}>{number}</span>
            <h3 className="font-semibold text-slate-100">{title}</h3>
            {isIslamic && <Lock size={14} className="text-yellow-400" title="Mandatory for Islamic content" />}
          </div>
          <p className="text-xs text-slate-400 ml-8">{subtitle}</p>
        </div>
        {approved ? (
          <span className="badge-green">Approved</span>
        ) : locked ? (
          <span className="badge-yellow">Locked</span>
        ) : (
          <div className="flex gap-2">
            <button className="btn-primary py-1.5 text-xs" onClick={onApprove}><Check size={14} /> Approve</button>
            <button className="btn-danger py-1.5 text-xs" onClick={onReject}><X size={14} /> Reject</button>
          </div>
        )}
      </div>
      {notes && <div className="mt-3 p-2.5 bg-surface-700 rounded-lg text-xs text-slate-300">{notes}</div>}
    </div>
  )
}

export default function Review() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { activeProjectId, setActiveProjectId } = useStore()
  const [renderNotes, setRenderNotes] = useState('')
  const [pollInterval, setPollInterval] = useState(null)

  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
  const { data: project } = useQuery({ queryKey: ['project', activeProjectId], queryFn: () => getProject(activeProjectId), enabled: !!activeProjectId })

  const updateMutation = useMutation({
    mutationFn: (data) => updateProject(activeProjectId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project', activeProjectId] }),
  })

  const renderMutation = useMutation({
    mutationFn: () => renderVideo({ project_id: activeProjectId, aspect_ratio: project?.aspect_ratio || '16:9' }),
    onSuccess: () => { toast.success('Rendering started!'); qc.invalidateQueries({ queryKey: ['project', activeProjectId] }) },
    onError: (e) => toast.error(e.message),
  })

  const isIslamic = project?.channel?.is_islamic || false
  const r1 = project?.review1_approved
  const r2 = project?.review2_approved
  const r3 = project?.review3_approved
  const canR2 = r1
  const canR3 = r1 && r2
  const canRender = r1 && r2
  const allApproved = r1 && r2 && r3

  if (!activeProjectId) {
    return (
      <div>
        <h1 className="page-title">Review</h1>
        <p className="page-subtitle">3-level review process before final export</p>
        <div className="card"><label className="label">Select Project</label><select className="input max-w-md" onChange={(e) => setActiveProjectId(e.target.value)}><option value="">Choose a project...</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Review — {project?.title}</h1>
          <p className="page-subtitle">3-level approval process{isIslamic ? ' (mandatory for Islamic content)' : ''}</p>
        </div>
        <button className="btn-secondary text-xs" onClick={() => setActiveProjectId(null)}>Change Project</button>
      </div>

      {isIslamic && (
        <div className="card mb-4 border-yellow-600/50 bg-yellow-900/10">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-yellow-400" />
            <p className="text-sm text-yellow-300 font-medium">Islamic Content — All 3 reviews are mandatory and cannot be skipped</p>
          </div>
        </div>
      )}

      <div className="space-y-3 mb-5">
        <ReviewStep
          number={1}
          title="Review 1 — Script & Translation"
          subtitle="Review the idea, script, Arabic translations, and Sharia references"
          approved={r1}
          locked={false}
          isIslamic={isIslamic}
          onApprove={() => updateMutation.mutate({ review1_approved: true, status: 'review1_done' })}
          onReject={() => { toast.error('Review 1 rejected — please revise the content'); updateMutation.mutate({ review1_approved: false, status: 'content_generated' }) }}
        />
        <ReviewStep
          number={2}
          title="Review 2 — Visuals & Audio"
          subtitle="Check all scene visuals, voice quality, and timing"
          approved={r2}
          locked={!canR2}
          isIslamic={isIslamic}
          onApprove={() => updateMutation.mutate({ review2_approved: true, status: 'review2_done' })}
          onReject={() => { toast.error('Review 2 rejected — please revise visuals/audio'); updateMutation.mutate({ review2_approved: false }) }}
        />
        <ReviewStep
          number={3}
          title="Review 3 — Final Video & Metadata"
          subtitle="Watch the final rendered video and verify all metadata"
          approved={r3}
          locked={!canR3}
          isIslamic={isIslamic}
          onApprove={() => updateMutation.mutate({ review3_approved: true, status: 'done' })}
          onReject={() => { toast.error('Review 3 rejected'); updateMutation.mutate({ review3_approved: false }) }}
        />
      </div>

      {/* Render section */}
      {canRender && !allApproved && (
        <div className="card mb-4">
          <h3 className="section-title flex items-center gap-2"><Play size={16} /> Render Video</h3>
          <p className="text-sm text-slate-400 mb-3">Render the video to complete Review 3. Status: <span className={`font-medium ${project?.status === 'rendering' ? 'text-yellow-300' : project?.status === 'rendered' ? 'text-green-300' : 'text-slate-300'}`}>{project?.status}</span></p>
          <textarea className="input resize-none mb-3" rows={2} placeholder="Review notes (optional)..." value={renderNotes} onChange={(e) => setRenderNotes(e.target.value)} />
          <button className="btn-primary" onClick={() => renderMutation.mutate()} disabled={renderMutation.isPending || project?.status === 'rendering'}>
            <Play size={16} /> {project?.status === 'rendering' ? 'Rendering...' : 'Start Render'}
          </button>
        </div>
      )}

      {allApproved && (
        <div className="card border-green-600/50 bg-green-900/10 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-green-600/20 flex items-center justify-center"><Check size={20} className="text-green-400" /></div>
            <div>
              <p className="font-semibold text-green-300">All reviews approved!</p>
              <p className="text-xs text-slate-400 mt-0.5">The video is ready for export</p>
            </div>
          </div>
        </div>
      )}

      <button className="btn-primary w-full py-3" disabled={!allApproved} onClick={() => navigate('/export')}>
        Go to Export <ArrowRight size={16} />
      </button>
    </div>
  )
}
