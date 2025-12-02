/**
 * Route Display Component
 * 
 * Shows the optimized bar hopping itinerary as a visual timeline.
 * Displays arrival times, departure times, and wait estimates for each stop.
 */

import { MapPin, Clock, CheckCircle } from "lucide-react";
import "./RouteDisplay.css";

function RouteDisplay({ route }) {
  // Show empty state if no route
  if (!route || !route.itinerary || route.itinerary.length === 0) {
    return (
      <div className="route-display empty-state">
        <div className="empty-content">
          <MapPin size={48} className="empty-icon" />
          <h2>No Route Yet</h2>
          <p>Tell me which bars you want to visit and I'll optimize your route!</p>
          <div className="empty-hints">
            <h3>Example requests:</h3>
            <ul>
              <li>"Let's hit Chimy's and Cricket's at 9pm"</li>
              <li>"Plan a route for Bier Haus and Atomic"</li>
              <li>"Me and 5 friends want to bar hop on game day"</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  // Convert 24h time to 12h format
  const formatTime12h = (time24) => {
    const [hours, minutes] = time24.split(':').map(Number);
    const period = hours >= 12 ? 'PM' : 'AM';
    const hours12 = hours % 12 || 12;
    return `${hours12}:${minutes.toString().padStart(2, '0')} ${period}`;
  };

  // Get color class based on wait time
  const getWaitClass = (wait) => {
    if (wait <= 10) return "wait-short";
    if (wait <= 20) return "wait-medium";
    return "wait-long";
  };

  return (
    <div className="route-display">
      <div className="route-header">
        <h2>Your Optimized Route</h2>
        <div className="route-summary">
          <div className="summary-stat">
            <MapPin size={16} />
            <span>{route.itinerary.length} stops</span>
          </div>
          <div className="summary-stat">
            <Clock size={16} />
            <span>{route.total_wait_time} min total wait</span>
          </div>
        </div>
      </div>

      <div className="route-message success">
        <CheckCircle size={20} />
        <span>{route.message}</span>
      </div>

      <div className="route-timeline">
        {route.itinerary.map((stop, index) => (
          <div key={index} className="timeline-item">
            <div className="timeline-marker">
              <div className="marker-number">{index + 1}</div>
              {index < route.itinerary.length - 1 && <div className="marker-line" />}
            </div>
            
            <div className="timeline-card">
              <div className="card-header">
                <h3 className="venue-name">{stop.venue_name}</h3>
                <span className={`wait-badge ${getWaitClass(stop.expected_wait)}`}>
                  ~{stop.expected_wait} min wait
                </span>
              </div>
              
              <div className="card-times">
                <div className="time-block">
                  <span className="time-label">Arrive</span>
                  <span className="time-value">{formatTime12h(stop.arrival_time)}</span>
                </div>
                <span className="time-arrow">→</span>
                <div className="time-block">
                  <span className="time-label">Leave</span>
                  <span className="time-value">{formatTime12h(stop.departure_time)}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="route-footer">
        <p>💡 Wait times are estimates and may vary based on actual conditions.</p>
      </div>
    </div>
  );
}

export default RouteDisplay;
