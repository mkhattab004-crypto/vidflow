import React from 'react'

export default function LoadingSpinner({ size = 'md', text = '' }) {
  const sz = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' }[size]
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <div className={`${sz} border-2 border-brand-600 border-t-transparent rounded-full animate-spin`} />
      {text && <p className="text-sm text-slate-400">{text}</p>}
    </div>
  )
}
