import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Channels from './pages/Channels'
import Ideas from './pages/Ideas'
import Content from './pages/Content'
import Visuals from './pages/Visuals'
import Audio from './pages/Audio'
import Templates from './pages/Templates'
import Review from './pages/Review'
import Export from './pages/Export'
import Projects from './pages/Projects'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/channels" element={<Channels />} />
          <Route path="/ideas" element={<Ideas />} />
          <Route path="/content" element={<Content />} />
          <Route path="/visuals" element={<Visuals />} />
          <Route path="/audio" element={<Audio />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/review" element={<Review />} />
          <Route path="/export" element={<Export />} />
          <Route path="/projects" element={<Projects />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
