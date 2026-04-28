import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Tv2, Lightbulb, FileText, Image, Mic, Layout as LayoutIcon,
  CheckSquare, Download, Archive, ChevronLeft, ChevronRight, Zap, LayoutDashboard
} from 'lucide-react'
import useStore from '../store/useStore'
import clsx from 'clsx'

const NAV = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard',  end: true },
  { to: '/channels',  icon: Tv2,             label: 'Channels'  },
  { to: '/ideas',     icon: Lightbulb,       label: 'Ideas'     },
  { to: '/content',   icon: FileText,        label: 'Content'   },
  { to: '/visuals',   icon: Image,           label: 'Visuals'   },
  { to: '/audio',     icon: Mic,             label: 'Audio'     },
  { to: '/templates', icon: LayoutIcon,      label: 'Templates' },
  { to: '/review',    icon: CheckSquare,     label: 'Review'    },
  { to: '/export',    icon: Download,        label: 'Export'    },
  { to: '/projects',  icon: Archive,         label: 'Projects'  },
]

export default function Layout({ children }) {
  const { sidebarOpen, toggleSidebar } = useStore()

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside
        className={clsx(
          'flex flex-col bg-surface-800 border-r border-surface-700 transition-all duration-200 shrink-0',
          sidebarOpen ? 'w-56' : 'w-16'
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-14 border-b border-surface-700">
          <div className="flex items-center justify-center w-8 h-8 bg-brand-600 rounded-lg shrink-0">
            <Zap size={16} className="text-white" />
          </div>
          {sidebarOpen && (
            <span className="font-bold text-slate-100 text-lg tracking-tight">VidFlow</span>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 overflow-y-auto">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-all mx-2 rounded-lg mb-0.5',
                  isActive
                    ? 'bg-brand-600/20 text-brand-400 border border-brand-600/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-surface-700'
                )
              }
            >
              <item.icon size={18} className="shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Toggle */}
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center h-10 border-t border-surface-700 text-slate-500 hover:text-slate-300 transition-colors"
        >
          {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-surface-900">
        <div className="max-w-7xl mx-auto px-6 py-6">{children}</div>
      </main>
    </div>
  )
}
