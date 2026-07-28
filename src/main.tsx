import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import logoLockupLightInk from './assets/brand/logo-lockup-light-ink.png'

// Preload the official LearnX logo used by the cinematic intro so it's
// already in the browser cache the instant IntroAnimation mounts —
// prevents any flicker/delayed render of the brand mark on first paint.
const introLogoPreload = document.createElement('link')
introLogoPreload.rel = 'preload'
introLogoPreload.as = 'image'
introLogoPreload.href = logoLockupLightInk
document.head.appendChild(introLogoPreload)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
