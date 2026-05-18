import React, { useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Download, FileText, Subtitles, FileJson, Video, Monitor, Smartphone, Square } from 'lucide-react'
import { getProjects, getProject, renderAllFormats, getVideoDownloadUrl, getTextDownloadUrl } from '../services/api'
import useStore from '../store/useStore'
import api from '../services/api'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function Export() {
  const { activeProjectId, setActiveProjectId, clearProjectUiState } = useStore()
  const qc = useQueryClient()
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: () => getProjects() })
  const { data: project } = useQuery({ queryKey: ['project', activeProjectId], queryFn: () => getProject(activeProjectId), enabled: !!activeProjectId })
  useEffect(() => {
    clearProjectUiState()
    if (activeProjectId) qc.invalidateQueries({ queryKey: ['project', activeProjectId] })
  }, [activeProjectId, clearProjectUiState, qc])
  const shortFormTypes = new Set(['short_form', 'reels', 'tiktok', 'shorts'])
  const isShortFormProject = shortFormTypes.has((project?.video_type || '').toLowerCase())
const renderMutation = useMutation({
  mutationFn: () => renderAllFormats({
    project_id: project?.id,
    formats: isShortFormProject ? ['9:16', '16:9', '1:1'] : ['16:9', '9:16', '1:1'],
  }),
  onSuccess: () => {
    toast.success('Video rendering started! Refresh after a minute.')
    qc.invalidateQueries({ queryKey: ['project', activeProjectId] })
  },
  onError: (e) => toast.error(e.message),
})
  async function handleDownload(type) {
    if (!activeProjectId) return
    try {
      let res, filename
      if (type === 'metadata') {
        res = await api.get(getTextDownloadUrl(activeProjectId, 'metadata'), { responseType: 'blob' })
        filename = `metadata.json`
      } else if (type === 'script') {
        res = await api.get(getTextDownloadUrl(activeProjectId, 'script'), { responseType: 'blob' })
        filename = `script.txt`
      } else if (type === 'subtitles_srt') {
        res = await api.get(getTextDownloadUrl(activeProjectId, 'subtitles_srt'), { responseType: 'blob' })
        filename = `subtitles.srt`
      } else if (type === 'subtitles_txt') {
        res = await api.get(getTextDownloadUrl(activeProjectId, 'subtitles_txt'), { responseType: 'blob' })
        filename = `captions.txt`
      } else if (type.startsWith('video_')) {
        const fmt = type.replace('video_', '').replace('x', ':')
       window.open(getVideoDownloadUrl(activeProjectId, fmt), '_blank')
        return
      }
      if (res) downloadBlob(res.data, filename)
      toast.success('Download started!')
    } catch (e) {
      toast.error('Download failed: ' + e.message)
    }
  }

  if (!activeProjectId) {
    return (
      <div>
        <h1 className="page-title">Export</h1>
        <p className="page-subtitle">Download your finished video and all assets</p>
        <div className="card"><label className="label">Select Project</label><select className="input max-w-md" onChange={(e) => setActiveProjectId(e.target.value)}><option value="">Choose a project...</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></div>
      </div>
    )
  }

  const hasVideo = project?.output_url || project?.output_9_16_url || project?.output_1_1_url
  const allApproved = project?.review1_approved && project?.review2_approved && project?.review3_approved
  return (
    <div className="max-w-2xl">
      <h1 className="page-title">Export — {project?.title}</h1>
      <p className="page-subtitle">Download video files, script, metadata, and subtitles</p>

      {!allApproved && (
        <div className="card mb-4 border-yellow-600/50 bg-yellow-900/10">
          <p className="text-sm text-yellow-300">⚠️ All 3 reviews must be approved before exporting the video. Text files are always available.</p>
        </div>
      )}
<div className="card mb-4">
  <h3 className="section-title flex items-center gap-2">
    <Video size={16} /> Render Video
  </h3>

  <p className="text-sm text-slate-400 mb-3">
    Generate final video files for YouTube, TikTok/Reels, and Instagram.
  </p>

  <button
    className="btn-primary w-full"
    disabled={!allApproved || renderMutation.isPending}
    onClick={() => renderMutation.mutate()}
  >
    {renderMutation.isPending ? 'Rendering video...' : 'Render All Video Formats'}
  </button>

  {!allApproved && (
    <p className="text-xs text-yellow-300 mt-2">
      All reviews must be approved before rendering.
    </p>
  )}
</div>
      {/* Video Downloads */}
      <div className="card mb-4">
        <h3 className="section-title flex items-center gap-2"><Video size={16} /> Video Files (1080p HD)</h3>
        <div className="grid grid-cols-3 gap-3">
          {(isShortFormProject
            ? [
                { icon: Smartphone, label: 'TikTok / Reels', sub: '9:16 · 1080×1920', key: 'video_9x16', has: !!project?.output_9_16_url },
                { icon: Monitor, label: 'YouTube', sub: '16:9 · 1920×1080', key: 'video_16x9', has: !!project?.output_url },
                { icon: Square, label: 'Instagram', sub: '1:1 · 1080×1080', key: 'video_1x1', has: !!project?.output_1_1_url },
              ]
            : [
                { icon: Monitor, label: 'YouTube', sub: '16:9 · 1920×1080', key: 'video_16x9', has: !!project?.output_url },
                { icon: Smartphone, label: 'TikTok / Reels', sub: '9:16 · 1080×1920', key: 'video_9x16', has: !!project?.output_9_16_url },
                { icon: Square, label: 'Instagram', sub: '1:1 · 1080×1080', key: 'video_1x1', has: !!project?.output_1_1_url },
              ]).map(({ icon: Icon, label, sub, key, has }) => (
            <button
              key={key}
              className={`p-4 rounded-xl border text-center transition-all ${has && allApproved ? 'border-green-600/50 bg-green-900/10 hover:bg-green-900/20 cursor-pointer' : 'border-surface-600 opacity-50 cursor-not-allowed'}`}
              disabled={!has || !allApproved}
              onClick={() => handleDownload(key)}
            >
              <Icon size={24} className={`mx-auto mb-2 ${has && allApproved ? 'text-green-400' : 'text-slate-500'}`} />
              <p className="text-sm font-medium text-slate-200">{label}</p>
              <p className="text-xs text-slate-500 mt-0.5">{sub}</p>
              <Download size={14} className="mx-auto mt-2 text-slate-400" />
            </button>
          ))}
        </div>
      </div>

      {/* Text exports */}
      <div className="card">
        <h3 className="section-title">Text & Data Files</h3>
        <div className="space-y-2">
          {[
            { icon: FileJson, label: 'Metadata (JSON)', sub: 'Title, description, tags, pinned comment', key: 'metadata' },
            { icon: FileText, label: 'Script (TXT)', sub: 'Full narration script with scene breakdown', key: 'script' },
            { icon: FileText, label: 'Subtitles (SRT)', sub: 'Subtitle file for YouTube upload', key: 'subtitles_srt' },
            { icon: FileText, label: 'Captions (TXT)', sub: 'Plain text caption file', key: 'subtitles_txt' },
          ].map(({ icon: Icon, label, sub, key }) => (
            <div key={key} className="flex items-center justify-between p-3 bg-surface-700 rounded-lg">
              <div className="flex items-center gap-3">
                <Icon size={18} className="text-slate-400" />
                <div>
                  <p className="text-sm font-medium text-slate-200">{label}</p>
                  <p className="text-xs text-slate-500">{sub}</p>
                </div>
              </div>
              <button className="btn-secondary text-xs py-1.5" onClick={() => handleDownload(key)}>
                <Download size={13} /> Download
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
