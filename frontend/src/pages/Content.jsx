import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Sparkles, FileText, Tags, BookOpen, ArrowRight, Edit3, Save } from 'lucide-react'
import { getProjects, getProject, generateContent, updateProject, updateScene } from '../services/api'
import LoadingSpinner from '../components/common/LoadingSpinner'
import useStore from '../store/useStore'
import { useNavigate } from 'react-router-dom'

export default function Content() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { activeProjectId, setActiveProjectId } = useStore()
  const [editingScene, setEditingScene] = useState(null)
  const [sceneText, setSceneText] = useState('')
  const [editingMeta, setEditingMeta] = useState(false)
  const [metaForm, setMetaForm] = useState({})

  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
  const { data: project, isLoading } = useQuery({
    queryKey: ['project', activeProjectId],
    queryFn: () => getProject(activeProjectId),
    enabled: !!activeProjectId,
  })

  const genMutation = useMutation({
    mutationFn: () => generateContent(activeProjectId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', activeProjectId] }); toast.success('Content generated!') },
    onError: (e) => toast.error(e.message),
  })

  const updateMutation = useMutation({
    mutationFn: (data) => updateProject(activeProjectId, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', activeProjectId] }); setEditingMeta(false); toast.success('Saved') },
  })

  const saveSceneMutation = useMutation({
    mutationFn: ({ sceneId, text }) => updateScene(activeProjectId, sceneId, { script_text: text }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['project', activeProjectId] }); setEditingScene(null); toast.success('Scene updated') },
  })

  if (!activeProjectId) {
    return (
      <div>
        <h1 className="page-title">Content Generation</h1>
        <p className="page-subtitle">Select a project to generate its content</p>
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

  if (isLoading) return <LoadingSpinner text="Loading project..." />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">{project?.title || 'Content Generation'}</h1>
          <p className="page-subtitle">Script, metadata, and scene breakdown</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setActiveProjectId(null)}>Change Project</button>
          <button className="btn-primary" onClick={() => genMutation.mutate()} disabled={genMutation.isPending}>
            <Sparkles size={16} />
            {genMutation.isPending ? 'Generating...' : 'Generate with AI'}
          </button>
        </div>
      </div>

      {genMutation.isPending && <LoadingSpinner text="Generating script with Gemini AI..." />}

      {project && (
        <div className="grid grid-cols-12 gap-5">
          {/* Metadata panel */}
          <div className="col-span-5 space-y-4">
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h3 className="section-title mb-0 flex items-center gap-2"><Tags size={16} /> Metadata</h3>
                <button className="btn-ghost p-1.5 rounded" onClick={() => { setEditingMeta(!editingMeta); setMetaForm({ title: project.title, description: project.description, pinned_comment: project.pinned_comment, thumbnail_prompt: project.thumbnail_prompt }) }}>
                  {editingMeta ? <Save size={15} /> : <Edit3 size={15} />}
                </button>
              </div>
              {editingMeta ? (
                <div className="space-y-3">
                  <div><label className="label">Title</label><input className="input" value={metaForm.title || ''} onChange={(e) => setMetaForm({ ...metaForm, title: e.target.value })} /></div>
                  <div><label className="label">Description</label><textarea className="input resize-none" rows={4} value={metaForm.description || ''} onChange={(e) => setMetaForm({ ...metaForm, description: e.target.value })} /></div>
                  <div><label className="label">Pinned Comment</label><input className="input" value={metaForm.pinned_comment || ''} onChange={(e) => setMetaForm({ ...metaForm, pinned_comment: e.target.value })} /></div>
                  <div><label className="label">Thumbnail Prompt</label><textarea className="input resize-none" rows={2} value={metaForm.thumbnail_prompt || ''} onChange={(e) => setMetaForm({ ...metaForm, thumbnail_prompt: e.target.value })} /></div>
                  <div className="flex gap-2">
                    <button className="btn-primary flex-1 text-xs" onClick={() => updateMutation.mutate(metaForm)}>Save</button>
                    <button className="btn-secondary text-xs" onClick={() => setEditingMeta(false)}>Cancel</button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  <div><p className="text-slate-400 text-xs mb-1">Title</p><p className="text-slate-200 font-medium">{project.title}</p></div>
                  {project.description && <div><p className="text-slate-400 text-xs mb-1">Description</p><p className="text-slate-300 text-xs leading-relaxed line-clamp-4">{project.description}</p></div>}
                  {project.pinned_comment && <div><p className="text-slate-400 text-xs mb-1">Pinned Comment</p><p className="text-slate-300 text-xs">{project.pinned_comment}</p></div>}
                  {project.thumbnail_prompt && <div><p className="text-slate-400 text-xs mb-1">Thumbnail Prompt</p><p className="text-slate-300 text-xs italic">{project.thumbnail_prompt}</p></div>}
                  {project.metadata_tags?.length > 0 && (
                    <div><p className="text-slate-400 text-xs mb-1">Tags</p><div className="flex flex-wrap gap-1">{project.metadata_tags.slice(0, 8).map((t, i) => <span key={i} className="badge-gray">#{t}</span>)}</div></div>
                  )}
                  {project.sharia_reference && (
                    <div className="border-t border-surface-700 pt-3">
                      <p className="text-slate-400 text-xs mb-1">Sharia Reference</p>
                      <p className="text-green-300 text-xs">{project.sharia_reference}</p>
                      {project.trust_level && <span className={`badge mt-1 ${project.trust_level === 'verified' ? 'badge-green' : project.trust_level === 'probable' ? 'badge-yellow' : 'badge-red'}`}>{project.trust_level}</span>}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Scenes */}
          <div className="col-span-7">
            <div className="card">
              <h3 className="section-title flex items-center gap-2"><FileText size={16} /> Script Scenes ({project.scenes?.length || 0})</h3>
              {!project.scenes?.length ? (
                <p className="text-slate-500 text-sm text-center py-8">No scenes yet. Click "Generate with AI" to create the script.</p>
              ) : (
                <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
                  {project.scenes.map((scene) => (
                    <div key={scene.id} className="bg-surface-700 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-brand-400 bg-brand-900/30 px-2 py-0.5 rounded">Scene {scene.order}</span>
                          <span className="text-xs text-slate-500">{scene.duration}s · {scene.transition}</span>
                        </div>
                        <button className="btn-ghost p-1 rounded text-xs" onClick={() => { setEditingScene(scene.id); setSceneText(scene.script_text || '') }}>
                          <Edit3 size={12} />
                        </button>
                      </div>
                      {editingScene === scene.id ? (
                        <div>
                          <textarea className="input resize-none text-xs" rows={3} value={sceneText} onChange={(e) => setSceneText(e.target.value)} />
                          <div className="flex gap-2 mt-2">
                            <button className="btn-primary text-xs py-1" onClick={() => saveSceneMutation.mutate({ sceneId: scene.id, text: sceneText })}>Save</button>
                            <button className="btn-ghost text-xs py-1" onClick={() => setEditingScene(null)}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <p className="text-sm text-slate-200 leading-relaxed">{scene.script_text}</p>
                          {scene.script_ar && <p className="text-xs text-slate-400 mt-1 arabic-text">{scene.script_ar}</p>}
                          {scene.visual_query && <p className="text-xs text-slate-500 mt-1.5">🎬 {scene.visual_query}</p>}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {project?.scenes?.length > 0 && (
        <div className="mt-6 flex justify-end">
          <button className="btn-primary" onClick={async () => { await updateProject(activeProjectId, { review1_approved: true }); navigate('/visuals') }}>
            Approve & Go to Visuals <ArrowRight size={16} />
          </button>
        </div>
      )}
    </div>
  )
}
