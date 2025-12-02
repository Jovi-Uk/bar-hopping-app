/**
 * Bar List Component
 * 
 * Displays all available bars with their information.
 * Helps users see what options are available for their bar hopping plans.
 */

import { useState, useEffect } from "react";
import { Users, Clock, Star, Loader2 } from "lucide-react";
import { getAvailableBars } from "../services/api";
import "./BarList.css";

function BarList() {
  const [bars, setBars] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchBars() {
      try {
        setLoading(true);
        const response = await getAvailableBars();
        setBars(response.bars || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchBars();
  }, []);

  if (loading) {
    return (
      <div className="bar-list loading-state">
        <Loader2 className="spinner" size={32} />
        <p>Loading bars...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bar-list error-state">
        <p>Failed to load bars: {error}</p>
      </div>
    );
  }

  // Render star rating
  const renderStars = (popularity) => {
    return Array.from({ length: 5 }, (_, i) => (
      <Star key={i} size={14} className={i < popularity ? "star filled" : "star"} />
    ));
  };

  return (
    <div className="bar-list">
      <div className="bar-list-header">
        <h2>Available Bars</h2>
        <p>{bars.length} bars in Lubbock</p>
      </div>

      <div className="bars-grid">
        {bars.map((bar, index) => (
          <div key={index} className="bar-card">
            <div className="bar-card-header">
              <h3>{bar.name}</h3>
              <div className="popularity-stars">{renderStars(bar.popularity)}</div>
            </div>
            <div className="bar-card-stats">
              <div className="stat">
                <Users size={14} />
                <span>Capacity: {bar.capacity}</span>
              </div>
              <div className="stat">
                <Clock size={14} />
                <span>Base wait: ~{bar.base_wait} min</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bar-list-footer">
        <p>💡 Just mention bar names in your request - I handle typos!</p>
      </div>
    </div>
  );
}

export default BarList;
