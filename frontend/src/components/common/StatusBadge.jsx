import React from 'react'

const STATUS_MAP = {
  idea: { label: 'Idea', cls: 'badge-gray' },
  content_generated: { label: 'Content Ready', cls: 'badge-blue' },
  visuals_pending: { label: 'Visuals Pending', cls: 'badge-yellow' },
  audio_ready: { label: 'Audio Ready', cls: 'badge-blue' },
  review_pending: { label: 'Under Review', cls: 'badge-yellow' },
  rendering: { label: 'Rendering...', cls: 'badge-purple' },
  rendered: { label: 'Rendered', cls: 'badge-green' },
  done: { label: 'Done', cls: 'badge-green' },
}

export default function StatusBadge({ status }) {
  const s = STATUS_MAP[status] || { label: status, cls: 'badge-gray' }
  return <span className={s.cls}>{s.label}</span>
}
