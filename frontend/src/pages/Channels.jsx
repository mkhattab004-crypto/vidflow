import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Plus, Tv2, Edit2, Trash2, Globe, Hash, Bookmark, MessageSquare } from 'lucide-react'
import { getChannels, getChannel, createChannel, updateChannel, deleteChannel, addHook, deleteHook, addCTA, deleteCTA } from '../services/api'
import LoadingSpinner from '../components/common/LoadingSpinner'
import EmptyState from '../components/common/EmptyState'

const NICHES = ['curiobuzz', 'islamic', 'finance', 'history', 'science', 'motivation', 'technology', 'travel']
const LANGUAGES = [{ id: 'en', label: 'English' }, { id: 'ar', label: 'Arabic / عربي' }, { id: 'tr', label: 'Turkish / Türkçe' }]
const TONES = ['educational', 'dramatic', 'friendly', 'formal', 'inspirational']

const DEFAULT_FORM = {
  name: '', niche: 'curiobuzz', language: 'en', voice_id: '',
  primary_color: '#0ea5e9', secondary_color: '#ffffff',
  script_tone: 'educational', safety_level: 'normal', is_islamic: false, extra_config: {},
}

export default function Channels() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [form, setForm] = useState(DEFAULT_FORM)
  const [hookText, setHookText] = useState('')
  const [ctaText, setCtaText] = useState('')

  const { data: channels = [], isLoading } = useQuery({ queryKey: ['channels'], queryFn: getChannels })
  const { data: selectedChannel } = useQuery({
    queryKey: ['channel', selectedId], queryFn: () => selectedId ? getChannel(selectedId) : null,
    enabled: !!selectedId,
  })

  const saveMutation = useMutation({
    mutationFn: (d) => editingId ? updateChannel(editingId, d) : createChannel(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['channels'] }); setShowForm(false); setEditingId(null); setForm(DEFAULT_FORM); toast.success('Channel saved!') },
    onError: (e) => toast.error(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteChannel,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['channels'] }); if (selectedId === editingId) setSelectedId(null); toast.success('Channel deleted') },
  })

  const addHookMutation = useMutation({
    mutationFn: ({ id, text }) => addHook(id, { text, category: 'general' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['channel', selectedId] }); setHookText('') },
  })

  const addCTAMutation = useMutation({
    mutationFn: ({ id, text }) => addCTA(id, { text, cta_type: 'subscribe' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['channel', selectedId] }); setCtaText('') },
  })

  function openEdit(ch) {
    setEditingId(ch.id)
    setForm({ name: ch.name, niche: ch.niche, language: ch.language, voice_id: ch.voice_id || '', primary_color: ch.primary_color, secondary_color: ch.secondary_color, script_tone: ch.script_tone, safety_level: ch.safety_level, is_islamic: ch.is_islamic, extra_config: ch.extra_config || {} })
    setShowForm(true)
  }

  if (isLoading) return <LoadingSpinner text="Loading channels..." />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="page-title">Channel Management</h1>
          <p className="page-subtitle">Configure your YouTube channels and their settings</p>
        </div>
        <button className="btn-primary" onClick={() => { setEditingId(null); setForm(DEFAULT_FORM); setShowForm(true) }}>
          <Plus size={16} /> New Channel
        </button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Channel list */}
        <div className="col-span-4">
          {channels.length === 0 ? (
            <EmptyState icon={Tv2} title="No channels yet" description="Create your first channel to start producing videos." />
          ) : (
            <div className="space-y-2">
              {channels.map((ch) => (
                <div
                  key={ch.id}
                  onClick={() => setSelectedId(ch.id)}
                  className={`card cursor-pointer transition-all ${selectedId === ch.id ? 'border-brand-600 bg-brand-900/10' : 'hover:border-surface-500'}`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-semibold text-slate-100">{ch.name}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{ch.niche} · {ch.language.toUpperCase()}</p>
                    </div>
                    <div className="flex gap-1">
                      <button onClick={(e) => { e.stopPropagation(); openEdit(ch) }} className="btn-ghost p-1.5 rounded"><Edit2 size={14} /></button>
                      <button onClick={(e) => { e.stopPropagation(); if (confirm('Delete channel?')) deleteMutation.mutate(ch.id) }} className="btn-ghost p-1.5 rounded text-red-400 hover:text-red-300"><Trash2 size={14} /></button>
                    </div>
                  </div>
                  {ch.is_islamic && <span className="badge-purple mt-2">Islamic</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Channel detail */}
        <div className="col-span-8">
          {selectedId && selectedChannel ? (
            <div className="space-y-4">
              <div className="card">
                <h3 className="section-title flex items-center gap-2"><Globe size={16} /> Channel Info</h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-slate-400">Name:</span> <span className="text-slate-200 ml-1">{selectedChannel.name}</span></div>
                  <div><span className="text-slate-400">Niche:</span> <span className="text-slate-200 ml-1">{selectedChannel.niche}</span></div>
                  <div><span className="text-slate-400">Language:</span> <span className="text-slate-200 ml-1">{selectedChannel.language.toUpperCase()}</span></div>
                  <div><span className="text-slate-400">Tone:</span> <span className="text-slate-200 ml-1">{selectedChannel.script_tone}</span></div>
                  <div><span className="text-slate-400">Safety:</span> <span className="text-slate-200 ml-1">{selectedChannel.safety_level}</span></div>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400">Primary:</span>
                    <div className="w-4 h-4 rounded" style={{ background: selectedChannel.primary_color }} />
                    <span className="text-slate-200">{selectedChannel.primary_color}</span>
                  </div>
                </div>
              </div>

              {/* Hooks */}
              <div className="card">
                <h3 className="section-title flex items-center gap-2"><Bookmark size={16} /> Hooks Library</h3>
                <div className="flex gap-2 mb-3">
                  <input className="input flex-1" placeholder="Add a hook..." value={hookText} onChange={(e) => setHookText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && hookText && addHookMutation.mutate({ id: selectedId, text: hookText })} />
                  <button className="btn-secondary" onClick={() => hookText && addHookMutation.mutate({ id: selectedId, text: hookText })}>Add</button>
                </div>
                <div className="space-y-1.5">
                  {(selectedChannel.hooks || []).map((h) => (
                    <div key={h.id} className="flex items-center justify-between bg-surface-700 rounded-lg px-3 py-2 text-sm">
                      <span className="text-slate-300">{h.text}</span>
                      <button onClick={() => deleteHook(selectedId, h.id).then(() => qc.invalidateQueries({ queryKey: ['channel', selectedId] }))} className="text-slate-500 hover:text-red-400 transition-colors"><Trash2 size={13} /></button>
                    </div>
                  ))}
                  {!(selectedChannel.hooks?.length) && <p className="text-xs text-slate-500">No hooks yet</p>}
                </div>
              </div>

              {/* CTAs */}
              <div className="card">
                <h3 className="section-title flex items-center gap-2"><MessageSquare size={16} /> CTA Library</h3>
                <div className="flex gap-2 mb-3">
                  <input className="input flex-1" placeholder="Add a CTA..." value={ctaText} onChange={(e) => setCtaText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && ctaText && addCTAMutation.mutate({ id: selectedId, text: ctaText })} />
                  <button className="btn-secondary" onClick={() => ctaText && addCTAMutation.mutate({ id: selectedId, text: ctaText })}>Add</button>
                </div>
                <div className="space-y-1.5">
                  {(selectedChannel.ctas || []).map((c) => (
                    <div key={c.id} className="flex items-center justify-between bg-surface-700 rounded-lg px-3 py-2 text-sm">
                      <span className="text-slate-300">{c.text}</span>
                      <button onClick={() => deleteCTA(selectedId, c.id).then(() => qc.invalidateQueries({ queryKey: ['channel', selectedId] }))} className="text-slate-500 hover:text-red-400 transition-colors"><Trash2 size={13} /></button>
                    </div>
                  ))}
                  {!(selectedChannel.ctas?.length) && <p className="text-xs text-slate-500">No CTAs yet</p>}
                </div>
              </div>
            </div>
          ) : (
            <div className="card flex items-center justify-center h-64">
              <p className="text-slate-500">Select a channel to view details</p>
            </div>
          )}
        </div>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-800 border border-surface-700 rounded-xl w-full max-w-lg p-6 overflow-y-auto max-h-[90vh]">
            <h2 className="text-lg font-semibold mb-5">{editingId ? 'Edit Channel' : 'New Channel'}</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Channel Name</label>
                <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="CurioBuzz" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Niche</label>
                  <select className="input" value={form.niche} onChange={(e) => setForm({ ...form, niche: e.target.value, is_islamic: e.target.value === 'islamic' })}>
                    {NICHES.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Language</label>
                  <select className="input" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
                    {LANGUAGES.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Script Tone</label>
                  <select className="input" value={form.script_tone} onChange={(e) => setForm({ ...form, script_tone: e.target.value })}>
                    {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="label">Safety Level</label>
                  <select className="input" value={form.safety_level} onChange={(e) => setForm({ ...form, safety_level: e.target.value })}>
                    <option value="normal">Normal</option>
                    <option value="strict">Strict (Islamic)</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Primary Color</label>
                  <div className="flex gap-2"><input type="color" className="h-9 w-12 rounded cursor-pointer bg-transparent border-0" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} /><input className="input flex-1" value={form.primary_color} onChange={(e) => setForm({ ...form, primary_color: e.target.value })} /></div>
                </div>
                <div>
                  <label className="label">Secondary Color</label>
                  <div className="flex gap-2"><input type="color" className="h-9 w-12 rounded cursor-pointer bg-transparent border-0" value={form.secondary_color} onChange={(e) => setForm({ ...form, secondary_color: e.target.value })} /><input className="input flex-1" value={form.secondary_color} onChange={(e) => setForm({ ...form, secondary_color: e.target.value })} /></div>
                </div>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="rounded" checked={form.is_islamic} onChange={(e) => setForm({ ...form, is_islamic: e.target.checked })} />
                <span className="text-sm text-slate-300">Islamic Content Channel</span>
              </label>
            </div>
            <div className="flex gap-3 mt-6">
              <button className="btn-primary flex-1" disabled={!form.name || saveMutation.isPending} onClick={() => saveMutation.mutate(form)}>
                {saveMutation.isPending ? 'Saving...' : 'Save Channel'}
              </button>
              <button className="btn-secondary" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
