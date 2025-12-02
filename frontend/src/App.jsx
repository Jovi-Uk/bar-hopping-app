/**
 * Main Application Component
 * 
 * This is the root component of the React application. It manages the global
 * application state including chat messages, the current route, and model status.
 */

import { useState, useEffect } from "react";
import ChatInterface from "./components/ChatInterface";
import RouteDisplay from "./components/RouteDisplay";
import BarList from "./components/BarList";
import { optimizeRoute, checkModelHealth } from "./services/api";
import "./App.css";

function App() {
  // Chat messages - starts with welcome message
  const [messages, setMessages] = useState([
    {
      type: "assistant",
      content: 
        "Hey! 👋 I'm your bar hopping assistant for Lubbock. " +
        "Tell me which bars you want to hit and when, and I'll optimize " +
        "your route to minimize wait times. Try: \"Let's hit Chimy's and Cricket's at 9pm\"",
      llmUsed: false
    },
  ]);
  
  // Current optimized route
  const [currentRoute, setCurrentRoute] = useState(null);
  
  // Loading state
  const [isLoading, setIsLoading] = useState(false);
  
  // Show bar list panel
  const [showBars, setShowBars] = useState(false);
  
  // Model health status
  const [modelStatus, setModelStatus] = useState({
    checked: false,
    available: false,
    backend: "unknown",
    gpu: null
  });

  // Check model health on mount
  useEffect(() => {
    async function checkModel() {
      try {
        const health = await checkModelHealth();
        setModelStatus({
          checked: true,
          available: health.model?.available || false,
          backend: health.model?.backend || "unknown",
          gpu: health.gpu?.name || null
        });
      } catch (error) {
        setModelStatus({
          checked: true,
          available: false,
          backend: "error",
          gpu: null
        });
      }
    }
    checkModel();
  }, []);

  // Handle user message submission
  const handleUserMessage = async (userMessage) => {
    setMessages((prev) => [...prev, { type: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await optimizeRoute(userMessage, 2, modelStatus.available);

      setMessages((prev) => [
        ...prev,
        { 
          type: "assistant", 
          content: response.message,
          llmUsed: response.llm_used || false
        },
      ]);

      if (response.status === "success" && response.itinerary.length > 0) {
        setCurrentRoute(response);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          type: "assistant",
          content: error.message || "Oops! Something went wrong. Please try again.",
          llmUsed: false
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Clear current route
  const handleClearRoute = () => {
    setCurrentRoute(null);
    setMessages([{
      type: "assistant",
      content: "Route cleared! What would you like to plan next?",
      llmUsed: false
    }]);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <h1>🍺 Lubbock Bar Hopping Optimizer</h1>
          <p>Plan your perfect night out with AI-optimized routes</p>
        </div>
        <div className="header-actions">
          {/* Model status indicator */}
          <div className={`model-status ${modelStatus.available ? 'online' : 'offline'}`}>
            <span className="status-dot"></span>
            <span className="status-text">
              {modelStatus.available ? 'AI Active' : 'AI Offline'}
            </span>
            {modelStatus.gpu && (
              <span className="gpu-badge">GPU</span>
            )}
          </div>
          
          <button className="header-btn" onClick={() => setShowBars(!showBars)}>
            {showBars ? "Hide Bars" : "Show Bars"}
          </button>
          
          {currentRoute && (
            <button className="header-btn secondary" onClick={handleClearRoute}>
              Clear Route
            </button>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="app-main">
        <div className="chat-section">
          <ChatInterface
            messages={messages}
            onSendMessage={handleUserMessage}
            isLoading={isLoading}
          />
        </div>

        <div className="route-section">
          {showBars ? <BarList /> : <RouteDisplay route={currentRoute} />}
        </div>
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p>
          Built with React + FastAPI + Fine-tuned Phi-3.5 | 
          Backend: {modelStatus.backend}
        </p>
      </footer>
    </div>
  );
}

export default App;
