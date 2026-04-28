import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Tv2, Archive, CheckSquare, Video, Zap, ArrowRight, BookOpen, Mic } from 'lucide-react'
import { getDashboardStats, getChannels, getProjects } from '../services/api'
import LoadingSpinner from '../components/common/LoadingSpinner'
import StatusBadge from '../components/common/StatusBadge'

function StatCard({ icon: Icon, label, value, color = 'text-brand-400' }) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center bg-surface-700`}>
        <Icon size={22} className={color} />
      </div>
      <div>
        <p className="text-2xl font-bold text-slate-100">{value ?? '—'}</p>
        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: stats } = useQuery({ queryKey: ['dashboard'], queryFn: getDashboardStats, refetchInterval: 30000 })
  const { data: channels = [] } = useQuery({ queryKey: ['channels'], queryFn: getChannels })
  const { data: recentProjects = [] } = useQuery({
    queryKey: ['projects', 'recent'],
    queryFn: () => getProjects({ limit: 5 }),
  })

  const byStatus = stats?.by_status || {}

  return (
    <div>
      <div className="mb-6">
        <h1 className="page-title flex items-center gap-2">
          <Zap size={24} className="text-brand-400" /> VidFlow Dashboard
        </h1>
        <p className="page-subtitle">Internal video production platform overview</p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard icon={Archive}    label="Total Projects"  value={stats?.total_projects}  color="text-brand-400" />
        <StatCard icon={Tv2}        label="Channels"        value={stats?.total_channels}  color="text-purple-400" />
        <StatCard icon={Video}      label="Rendered"        value={byStatus.rendered}      color="text-green-400" />
        <StatCard icon={CheckSquare} label="Done"           value={byStatus.done}          color="text-emerald-400" />
      </div>

      <div className="grid grid-cols-12 gap-5">
        {/* Quick actions */}
        <div className="col-span-4">
          <div className="card">
            <h3 className="section-title">Quick Actions</h3>
            <div className="space-y-2">
              {[
                { icon: Zap, label: 'New Video Idea', sub: 'Start a new project', to: '/ideas', color: 'text-yellow-400' },
                { icon: Tv2, label: 'Manage Channels', sub: `${channels.length} channels configured`, to: '/channels', color: 'text-brand-400' },
                { icon: Archive, label: 'All Projects', sub: `${stats?.total_projects ?? 0} total`, to: '/projects', color: 'text-purple-400' },
                { icon: BookOpen, label: 'Islamic Library', sub: 'Quran, Hadith, Adhkar', to: '/content', color: 'text-green-400' },
              ].map(({ icon: Icon, label, sub, to, color }) => (
                <button
                  key={to}
                  onClick={() => navigate(to)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg bg-surface-700 hover:bg-surface-600 transition-colors text-left"
                >
                  <Icon size={18} className={color} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-200">{label}</p>
                    <p className="text-xs text-slate-400">{sub}</p>
                  </div>
                  <ArrowRight size={14} className="text-slate-500" />
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Pipeline status */}
        <div className="col-span-4">
          <div className="card">
            <h3 className="section-title">Pipeline Status</h3>
            <div className="space-y-2">
              {[
                { label: 'Idea', key: 'idea' },
                { label: 'Content Generated', key: 'content_generated' },
                { label: 'Rendering', key: 'rendering' },
                { label: 'Rendered', key: 'rendered' },
                { label: 'Done', key: 'done' },
              ].map(({ label, key }) => {
                const count = byStatus[key] || 0
                const total = stats?.total_projects || 1
                const pct = Math.round((count / total) * 100)
                return (
                  <div key={key}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">{label}</span>
                      <span className="text-slate-300 font-medium">{count}</span>
                    </div>
                    <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
                      <div className="h-full bg-brand-600 rounded-full transition-all" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Channels */}
        <div className="col-span-4">
          <div className="card">
            <h3 className="section-title flex items-center justify-between">
              Channels
              <button onClick={() => navigate('/channels')} className="text-xs text-brand-400 hover:text-brand-300 font-normal">Manage →</button>
            </h3>
            <div className="space-y-2">
              {channels.length === 0 ? (
                <p className="text-slate-500 text-sm">No channels yet</p>
              ) : (
                channels.map((ch) => (
                  <div key={ch.id} className="flex items-center gap-2.5 p-2.5 rounded-lg bg-surface-700">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ background: '#0ea5e9' }} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-200 truncate">{ch.name}</p>
                      <p className="text-xs text-slate-500">{ch.niche} · {ch.language.toUpperCase()}</p>
                    </div>
                    {ch.is_islamic && <span className="badge-purple text-xs">Islamic</span>}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Recent projects */}
        <div className="col-span-12">
          <div className="card">
            <h3 className="section-title flex items-center justify-between">
              Recent Projects
              <button onClick={() => navigate('/projects')} className="text-xs text-brand-400 hover:text-brand-300 font-normal">View all →</button>
            </h3>
            {recentProjects.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-500 text-sm">No projects yet.</p>
                <button onClick={() => navigate('/ideas')} className="btn-primary mt-3 text-sm">Start your first video →</button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-500 border-b border-surface-700">
                      <th className="text-left py-2 font-medium">Title</th>
                      <th className="text-left py-2 font-medium">Type</th>
                      <th className="text-left py-2 font-medium">Status</th>
                      <th className="text-left py-2 font-medium">Created</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-700/50">
                    {recentProjects.slice(0, 8).map((p) => (
                      <tr key={p.id} className="hover:bg-surface-700/30 transition-colors">
                        <td className="py-2.5 pr-4 font-medium text-slate-200 max-w-xs truncate">{p.title}</td>
                        <td className="py-2.5 pr-4"><span className="badge-gray">{p.video_type}</span></td>
                        <td className="py-2.5 pr-4"><StatusBadge status={p.status} /></td>
                        <td className="py-2.5 pr-4 text-slate-400">{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                        <td className="py-2.5">
                          <button onClick={() => navigate('/content')} className="text-xs text-brand-400 hover:text-brand-300">Open →</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
