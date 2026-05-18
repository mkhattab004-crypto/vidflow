import { create } from 'zustand'

const useStore = create((set, get) => ({
  // Active channel
  activeChannelId: null,
  setActiveChannelId: (id) => set({ activeChannelId: id }),

  // Active project
  activeProjectId: null,
  projectUiState: { previewSrc: '', audioUrl: '', downloadUrl: '' },
  setActiveProjectId: (id) => set({ activeProjectId: id, projectUiState: { previewSrc: '', audioUrl: '', downloadUrl: '' } }),
  clearProjectUiState: () => set({ projectUiState: { previewSrc: '', audioUrl: '', downloadUrl: '' } }),

  // Workflow step (for project wizard)
  workflowStep: 'idea',
  setWorkflowStep: (step) => set({ workflowStep: step }),

  // Sidebar
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}))

export default useStore
