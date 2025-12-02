/**
 * Chat Interface Component
 * 
 * This component provides the conversational UI where users type their bar
 * hopping requests. It displays the message history and handles input.
 */

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Beer, User } from "lucide-react";
import "./ChatInterface.css";

function ChatInterface({ messages, onSendMessage, isLoading }) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input after loading
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus();
    }
  }, [isLoading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput("");
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <Beer size={24} />
        <span>Bar Hopping Assistant</span>
      </div>

      <div className="messages-container">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.type}`}>
            <div className="message-avatar">
              {msg.type === "assistant" ? <Beer size={20} /> : <User size={20} />}
            </div>
            <div className="message-bubble">
              <div className="message-content">{msg.content}</div>
              {msg.type === "assistant" && msg.llmUsed && (
                <div className="llm-badge">🤖 AI Generated</div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="message assistant">
            <div className="message-avatar"><Beer size={20} /></div>
            <div className="message-bubble">
              <div className="message-content loading">
                <Loader2 className="spinner" size={18} />
                <span>Finding the best route...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="chat-input-form">
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g., Let's hit Chimy's and Cricket's at 9pm..."
          disabled={isLoading}
          className="chat-input"
        />
        <button type="submit" disabled={isLoading || !input.trim()} className="send-button">
          {isLoading ? <Loader2 className="spinner" size={20} /> : <Send size={20} />}
        </button>
      </form>

      <div className="quick-suggestions">
        <span className="suggestions-label">Try:</span>
        {["Chimy's at 9pm", "Cricket's and Bier Haus", "Game day route"].map((suggestion, i) => (
          <button
            key={i}
            className="suggestion-chip"
            onClick={() => { setInput(suggestion); inputRef.current?.focus(); }}
            disabled={isLoading}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

export default ChatInterface;
