import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

// Channels
export const getChannels = () => api.get('/channels').then((r) => r.data)
export const getChannel = (id) => api.get(`/channels/${id}`).then((r) => r.data)
export const createChannel = (data) => api.post('/channels', data).then((r) => r.data)
export const updateChannel = (id, data) => api.put(`/channels/${id}`, data).then((r) => r.data)
export const deleteChannel = (id) => api.delete(`/channels/${id}`)
export const addHook = (channelId, data) => api.post(`/channels/${channelId}/hooks`, data).then((r) => r.data)
export const deleteHook = (channelId, hookId) => api.delete(`/channels/${channelId}/hooks/${hookId}`)
export const addCTA = (channelId, data) => api.post(`/channels/${channelId}/ctas`, data).then((r) => r.data)
export const deleteCTA = (channelId, ctaId) => api.delete(`/channels/${channelId}/ctas/${ctaId}`)

// Ideas
export const suggestIdeas = (data) => api.post('/ideas/suggest', data).then((r) => r.data)
export const checkDuplicate = (data) => api.post('/ideas/check-duplicate', data).then((r) => r.data)
export const getVideoTypes = () => api.get('/ideas/video-types').then((r) => r.data)

// Projects
export const getProjects = (params) => api.get('/projects', { params }).then((r) => r.data)
export const getProject = (id) => api.get(`/projects/${id}`).then((r) => r.data)
export const createProject = (data) => api.post('/projects', data).then((r) => r.data)
export const updateProject = (id, data) => api.put(`/projects/${id}`, data).then((r) => r.data)
export const deleteProject = (id) => api.delete(`/projects/${id}`)
export const generateContent = (id) => api.post(`/projects/${id}/generate-content`).then((r) => r.data)
export const updateScene = (projectId, sceneId, data) => api.put(`/projects/${projectId}/scenes/${sceneId}`, data).then((r) => r.data)
export const copyProject = (id) => api.post(`/projects/${id}/copy`).then((r) => r.data)

// Visuals
export const searchVisuals = (params) => api.get('/visuals/search', { params }).then((r) => r.data)
export const assignVisual = (data) => api.post('/visuals/assign', null, { params: data }).then((r) => r.data)
export const autoFillVisuals = (projectId, niche) => api.post(`/visuals/auto-fill/${projectId}`, null, { params: { niche } }).then((r) => r.data)
export const getVisualGaps = (projectId) => api.get(`/visuals/gap-analysis/${projectId}`).then((r) => r.data)

// Audio
export const getVoices = (language) => api.get('/audio/voices', { params: language ? { language } : {} }).then((r) => r.data)
export const generateAudio = (data) => api.post('/audio/generate', data).then((r) => r.data)

// Video
export const renderVideo = (data) => api.post('/video/render', data).then((r) => r.data)
export const getRenderStatus = (id) => api.get(`/video/status/${id}`).then((r) => r.data)

// Export
export const exportMetadata = (id) => api.get(`/export/${id}/metadata`, { responseType: 'blob' })
export const exportScript = (id) => api.get(`/export/${id}/script`, { responseType: 'blob' })
export const exportSubtitles = (id, format) => api.get(`/export/${id}/subtitles`, { params: { format }, responseType: 'blob' })

// Islamic
export const getQuranVerse = (surah, ayah, lang) => api.get(`/islamic/quran/verse/${surah}/${ayah}`, { params: { lang } }).then((r) => r.data)
export const searchQuran = (q) => api.get('/islamic/quran/search', { params: { q } }).then((r) => r.data)
export const getDailyVerse = (lang) => api.get('/islamic/quran/daily', { params: { lang } }).then((r) => r.data)
export const getHadithCollections = () => api.get('/islamic/hadith/collections').then((r) => r.data)
export const getRandomHadith = (collection) => api.get(`/islamic/hadith/random/${collection}`).then((r) => r.data)
export const getIslamicLibrary = () => api.get('/islamic/library').then((r) => r.data)
export const getIslamicContentTypes = () => api.get('/islamic/content-types').then((r) => r.data)

export default api
