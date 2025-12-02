/**
 * React Application Entry Point
 * 
 * This file is the first JavaScript that runs when the app loads.
 * It renders the root App component into the DOM.
 */

import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
