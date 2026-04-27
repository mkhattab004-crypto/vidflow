import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Layout, Monitor, Smartphone, Square, ArrowRight } from 'lucide-react'
import { getProjects, getProject, updateProject } from '../services/api'
import useStore from '../store/useStore'
import { useNavigate } from 'react-router-dom'

const SUBTITLE_POSITIONS = ['bottom', 'top', 'center']
const TRANSITIONS = ['fade', 'zoom_in', 'zoom_out', 'slide_left', 'slide_right', 'wipe']
const EFFECTS = ['text_typing', 'zoom', 'fade', 'slide', 'title_reveal', 'ken_burns']
const ASPECT_RATIOS = [
  { id: '16:9', label: 'YouTube', icon: Monitor, dim: '1920×1080' },
  { id: '9:16', label: 'TikTok / Reels', icon: Smartphone, dim: '1080×1920' },
  { id: '1:1', label: 'Instagram', icon: Square, dim: '1080×1080' },
]

export default function Templates() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { activeProjectId, setActiveProjectId } = useStore()
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
  const { data: project } = useQuery({ queryKey: ['project', activeProjectId], queryFn: () => getProject(activeProjectId), enabled: !!activeProjectId })

  const [config, setConfig] = useState({
    aspect_ratio: '16:9',
    subtitle_position: 'bottom',
    subtitle_size: 'large',
    subtitle_color: '#ffffff',
    logo_position: 'top-right',
    default_transition: 'fade',
    default_effects: ['fade'],
  })

  const saveMutation = useMutation({
    mutationFn: () => updateProject(activeProjectId, { aspect_ratio: config.aspect_ratio, template_config: config }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', activeProjectId] }); toast.success('Template saved!') },
  })

  if (!activeProjectId) {
    return (
      <div>
        <h1 className="page-title">Templates</h1>
        <p className="page-subtitle">Configure video format, subtitles, and effects</p>
        <div className="card"><label className="label">Select Project</label><select className="input max-w-md" onChange={(e) => setActiveProjectId(e.target.value)}><option value="">Choose a project...</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl">
      <h1 className="page-title">Templates — {project?.title}</h1>
      <p className="page-subtitle">Video format, subtitles, logo, and Remotion effects</p>

      <div className="card mb-4">
        <h3 className="section-title">Aspect Ratio</h3>
        <div className="grid grid-cols-3 gap-3">
          {ASPECT_RATIOS.map(({ id, label, icon: Icon, dim }) => (
            <button key={id} onClick={() => setConfig({ ...config, aspect_ratio: id })} className={`p-4 rounded-xl border text-center transition-all ${config.aspect_ratio === id ? 'border-brand-600 bg-brand-900/20' : 'border-surface-600 hover:border-surface-500'}`}>
              <Icon size={28} className={`mx-auto mb-2 ${config.aspect_ratio === id ? 'text-brand-400' : 'text-slate-400'}`} />
              <p className="text-sm font-medium text-slate-200">{label}</p>
              <p className="text-xs text-slate-500">{dim}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="card mb-4">
        <h3 className="section-title">Subtitle Style</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Position</label>
            <select className="input" value={config.subtitle_position} onChange={(e) => setConfig({ ...config, subtitle_position: e.target.value })}>
              {SUBTITLE_POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Size</label>
            <select className="input" value={config.subtitle_size} onChange={(e) => setConfig({ ...config, subtitle_size: e.target.value })}>
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
            </select>
          </div>
          <div>
            <label className="label">Text Color</label>
            <div className="flex gap-2">
              <input type="color" className="h-9 w-12 rounded bg-transparent border-0 cursor-pointer" value={config.subtitle_color} onChange={(e) => setConfig({ ...config, subtitle_color: e.target.value })} />
              <input className="input flex-1" value={config.subtitle_color} onChange={(e) => setConfig({ ...config, subtitle_color: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Logo Position</label>
            <select className="input" value={config.logo_position} onChange={(e) => setConfig({ ...config, logo_position: e.target.value })}>
              <option value="top-right">Top Right</option>
              <option value="top-left">Top Left</option>
              <option value="bottom-right">Bottom Right</option>
              <option value="bottom-left">Bottom Left</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card mb-4">
        <h3 className="section-title">Default Transition</h3>
        <div className="flex flex-wrap gap-2">
          {TRANSITIONS.map((t) => (
            <button key={t} onClick={() => setConfig({ ...config, default_transition: t })} className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${config.default_transition === t ? 'border-brand-600 bg-brand-900/20 text-brand-300' : 'border-surface-600 text-slate-400 hover:border-surface-500'}`}>{t}</button>
          ))}
        </div>
      </div>

      <div className="card mb-6">
        <h3 className="section-title">Remotion Effects</h3>
        <div className="flex flex-wrap gap-2">
          {EFFECTS.map((e) => {
            const active = config.default_effects?.includes(e)
            return (
              <button key={e} onClick={() => setConfig({ ...config, default_effects: active ? config.default_effects.filter((x) => x !== e) : [...(config.default_effects || []), e] })} className={`px-3 py-1.5 rounded-lg text-sm border transition-all ${active ? 'border-brand-600 bg-brand-900/20 text-brand-300' : 'border-surface-600 text-slate-400 hover:border-surface-500'}`}>{e}</button>
            )
          })}
        </div>
      </div>

      <div className="flex gap-3">
        <button className="btn-primary flex-1 py-3" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          <Layout size={16} /> {saveMutation.isPending ? 'Saving...' : 'Save Template'}
        </button>
        <button className="btn-secondary py-3 px-5" onClick={() => { saveMutation.mutate(); navigate('/review') }}>
          Go to Review <ArrowRight size={16} />
        </button>
      </div>
    </div>
  )
}
