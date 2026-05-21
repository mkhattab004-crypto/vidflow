import axios from 'axios'

// VITE_API_URL can be set as a Railway build-time env var to call the backend
// directly (e.g. https://vidflow-production-727a.up.railway.app/api).
// Falls back to /api which is handled by the nginx proxy.
export const API_BASE_URL = 'https://vidflow-production-727a.up.railway.app/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 180000, // 3 minutes — Gemini script generation can take 60-120s
})

// ── Interceptors ─────────────────────────────────────────────────────────────

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const detail = err.response?.data?.detail
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(', ')
      : detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

// Ensure API response is always an array (guards against HTML fallback pages, null, etc.)
const toArr = (r) => (Array.isArray(r.data) ? r.data : [])

// Helper: trigger a file download from a blob response
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── Channels ─────────────────────────────────────────────────────────────────

export const getChannels     = ()        => api.get('/channels').then(toArr)
export const getChannel      = (id)      => api.get(`/channels/${id}`).then(r => r.data)
export const createChannel   = (data)    => api.post('/channels', data).then(r => r.data)
export const updateChannel   = (id, d)   => api.put(`/channels/${id}`, d).then(r => r.data)
export const deleteChannel   = (id)      => api.delete(`/channels/${id}`)
export const uploadLogo      = (id, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post(`/channels/${id}/logo`, fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
}
export const addHook    = (cid, data) => api.post(`/channels/${cid}/hooks`, data).then(r => r.data)
export const deleteHook = (cid, hid)  => api.delete(`/channels/${cid}/hooks/${hid}`)
export const addCTA     = (cid, data) => api.post(`/channels/${cid}/ctas`, data).then(r => r.data)
export const deleteCTA  = (cid, ctid) => api.delete(`/channels/${cid}/ctas/${ctid}`)

// ── Ideas ─────────────────────────────────────────────────────────────────────

export const suggestIdeas    = (data)  => api.post('/ideas/suggest', data).then(toArr)
export const quickGenerate   = (data)  => api.post('/projects/quick-generate', data).then(r => r.data)
export const checkDuplicate  = (data)  => api.post('/ideas/check-duplicate', data).then(r => r.data)
export const getVideoTypes   = ()      => api.get('/ideas/video-types').then(toArr)

// ── Projects ─────────────────────────────────────────────────────────────────

export const getProjects      = (params)         => api.get('/projects', { params }).then(toArr)
export const getProject       = (id)             => api.get(`/projects/${id}`).then(r => r.data)
export const createProject    = (data)           => api.post('/projects', data).then(r => r.data)
export const updateProject    = (id, data)       => api.put(`/projects/${id}`, data).then(r => r.data)
export const deleteProject    = (id)             => api.delete(`/projects/${id}`)
export const generateContent  = (id)             => api.post(`/projects/${id}/generate-content`).then(r => r.data)
export const updateScene      = (pid, sid, data) => api.put(`/projects/${pid}/scenes/${sid}`, data).then(r => r.data)
export const copyProject      = (id)             => api.post(`/projects/${id}/copy`).then(r => r.data)
export const optimizeSEO      = (id)             => api.post(`/projects/${id}/optimize-seo`).then(r => r.data)
export const getExportBundle  = (id)             => api.get(`/projects/${id}/export-bundle`).then(r => r.data)

// ── Visuals ───────────────────────────────────────────────────────────────────

export const searchVisuals  = (params)          => api.get('/visuals/search', { params }).then(r => r.data)
export const assignVisual   = (params)          => api.post('/visuals/assign', null, { params }).then(r => r.data)
export const autoFillVisuals = (pid, niche, forceRefresh = true)     => api.post(`/visuals/auto-fill/${pid}`, null, { params: { niche, force_refresh: forceRefresh } }).then(r => r.data)
export const getVisualGaps  = (pid)             => api.get(`/visuals/gap-analysis/${pid}`).then(r => r.data)

// ── Audio ─────────────────────────────────────────────────────────────────────

export const getVoices         = ()           => api.get('/audio/voices').then(r => r.data)
export const getVoicesByLang   = ()           => api.get('/audio/voices/by-language').then(r => r.data)
export const generateAudio     = (data)       => api.post('/audio/generate', data).then(r => r.data)
export const getTtsProvider    = (language)   => api.get('/audio/provider', { params: { language } }).then(r => r.data)
export const generateSceneAudio = (data)      => api.post('/audio/generate-scene', data).then(r => r.data)
export const getAudioStatus    = (id)         => api.get(`/audio/status/${id}`).then(r => r.data)
export const getSceneTimings   = (id, voice, speed) =>
  api.get(`/audio/timings/${id}`, { params: { voice_id: voice, speed } }).then(r => r.data)
export const previewVoiceUrl   = (text, voice, speed, provider = 'edge_tts', language = 'en') =>
  `/api/audio/preview?text=${encodeURIComponent(text)}&voice_id=${voice}&speed=${speed}&provider=${encodeURIComponent(provider)}&language=${encodeURIComponent(language)}`

// ── Video ─────────────────────────────────────────────────────────────────────

export const renderVideo       = (data)       => api.post('/video/render', data).then(r => r.data)
export const renderAllFormats  = (data)       => api.post('/video/render-all-formats', data).then(r => r.data)
export const getRenderStatus   = (id)         => api.get(`/video/status/${id}`).then(r => r.data)
export const getVideoDownloadUrl = (projectId, format) =>
  `${API_BASE_URL}/video/download/${projectId}?format=${encodeURIComponent(format)}`
export const videoDownloadUrl  = getVideoDownloadUrl

// ── Thumbnails ────────────────────────────────────────────────────────────────

export const generateThumbnail  = (data)  => api.post('/thumbnails/generate', data).then(r => r.data)
export const thumbnailDownloadUrl = (id)  => `/api/thumbnails/download/${id}`

// ── Export ────────────────────────────────────────────────────────────────────

export async function downloadMetadata(id) {
  const r = await api.get(`/export/${id}/metadata`, { responseType: 'blob' })
  downloadBlob(r.data, `${id}_metadata.json`)
}
export async function downloadScript(id) {
  const r = await api.get(`/export/${id}/script`, { responseType: 'blob' })
  downloadBlob(r.data, `${id}_script.txt`)
}
export async function downloadSubtitles(id, format = 'srt', useAudioTiming = false) {
  const r = await api.get(`/export/${id}/subtitles`, {
    params: { format, use_audio_timing: useAudioTiming },
    responseType: 'blob',
  })
  downloadBlob(r.data, `${id}_subtitles.${format}`)
}
export const getFullBundle = (id) => api.get(`/export/${id}/full-bundle`).then(r => r.data)
export const getTextDownloadUrl = (projectId, type) => {
  if (type === 'metadata') return `${API_BASE_URL}/export/${projectId}/metadata`
  if (type === 'script') return `${API_BASE_URL}/export/${projectId}/script`
  if (type === 'subtitles_srt') return `${API_BASE_URL}/export/${projectId}/subtitles?format=srt`
  if (type === 'subtitles_txt') return `${API_BASE_URL}/export/${projectId}/subtitles?format=txt`
  return null
}

// ── Islamic ───────────────────────────────────────────────────────────────────

export const getQuranVerse        = (s, a, lang) => api.get(`/islamic/quran/verse/${s}/${a}`, { params: { lang } }).then(r => r.data)
export const getVerseWithTafsir   = (s, a, lang) => api.get(`/islamic/quran/verse-with-tafsir/${s}/${a}`, { params: { lang } }).then(r => r.data)
export const searchQuran          = (q, size)    => api.get('/islamic/quran/search', { params: { q, size } }).then(r => r.data)
export const getDailyVerse        = (lang)       => api.get('/islamic/quran/daily', { params: { lang } }).then(r => r.data)
export const getHadithCollections = ()           => api.get('/islamic/hadith/collections').then(r => r.data)
export const getRandomHadith      = (col)        => api.get(`/islamic/hadith/random/${col}`).then(r => r.data)
export const getHadithExplained   = (col, lang)  => api.get(`/islamic/hadith/random-with-explanation/${col}`, { params: { lang } }).then(r => r.data)
export const getAsmaAlHusna       = (num)        => api.get('/islamic/asma-al-husna', { params: num ? { number: num } : {} }).then(r => r.data)
export const getAdhkar            = (time)       => api.get(`/islamic/adhkar/${time}`).then(r => r.data)
export const getSurahVirtues      = (surah)      => api.get('/islamic/surah-virtues', { params: surah ? { surah } : {} }).then(r => r.data)
export const getIslamicLibrary    = ()           => api.get('/islamic/library').then(r => r.data)
export const getIslamicContentTypes = ()         => api.get('/islamic/content-types').then(r => r.data)
export const getImageSafetyRules  = ()           => api.get('/islamic/image-safety-rules').then(r => r.data)

// ── Automation ────────────────────────────────────────────────────────────────

export const getDashboardStats  = ()     => api.get('/automation/stats/dashboard').then(r => r.data)
export const getWeeklyStats     = ()     => api.get('/automation/stats/weekly').then(r => r.data)
export const scheduleChannel    = (data) => api.post('/automation/schedule', data).then(r => r.data)

export default api
