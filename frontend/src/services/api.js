/**
 * API Service Module
 * 
 * This module handles all communication between the React frontend and the
 * FastAPI backend. It provides clean functions for each API endpoint and
 * handles error cases gracefully.
 * 
 * The API_BASE_URL is set via environment variable (VITE_API_URL) so you can
 * easily switch between local development and production backends.
 */

import axios from "axios";

// Get API URL from environment variable, default to localhost for development
const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// Create axios instance with default configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 60000, // 60 second timeout (LLM responses can take a while)
});

// Log errors for debugging
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", {
      url: error.config?.url,
      status: error.response?.status,
      data: error.response?.data,
    });
    return Promise.reject(error);
  }
);

/**
 * Send a bar hopping request and get an optimized route.
 * 
 * This is the main function you'll use. It sends the user's natural language
 * request to the backend, which parses it, optimizes the route, and generates
 * a response using the LLM.
 * 
 * @param {string} message - The user's request (e.g., "hit chimys at 9pm")
 * @param {number} groupSize - Number of people (default: 2)
 * @param {boolean} useLlm - Whether to use LLM for response (default: true)
 * @returns {Promise<Object>} Route response with itinerary and message
 */
export async function optimizeRoute(message, groupSize = 2, useLlm = true) {
  try {
    const response = await api.post("/optimize", {
      message,
      group_size: groupSize,
      use_llm: useLlm,
    });
    return response.data;
  } catch (error) {
    // Provide user-friendly error messages
    if (error.response?.status === 503) {
      throw new Error("Server is warming up. Please try again in a moment.");
    } else if (error.response?.status === 500) {
      throw new Error(error.response?.data?.detail || "Server error. Please try again.");
    } else if (error.code === "ECONNABORTED") {
      throw new Error("Request timed out. The AI model might still be loading.");
    }
    throw new Error(error.response?.data?.detail || "Failed to optimize route");
  }
}

/**
 * Get a list of all available bars.
 * 
 * @returns {Promise<Object>} Object with bars array and count
 */
export async function getAvailableBars() {
  try {
    const response = await api.get("/bars");
    return response.data;
  } catch (error) {
    throw new Error("Failed to fetch bar list");
  }
}

/**
 * Get information about a specific bar.
 * 
 * @param {string} barName - Name of the bar
 * @returns {Promise<Object>} Bar details including hours and capacity
 */
export async function getBarInfo(barName) {
  try {
    const response = await api.get(`/bars/${encodeURIComponent(barName)}`);
    return response.data;
  } catch (error) {
    if (error.response?.status === 404) {
      throw new Error(`Bar '${barName}' not found`);
    }
    throw new Error("Failed to fetch bar info");
  }
}

/**
 * Check the health of the LLM model service.
 * 
 * This is called on app load to show whether AI features are available.
 * 
 * @returns {Promise<Object>} Model health status
 */
export async function checkModelHealth() {
  try {
    const response = await api.get("/model/health");
    return response.data;
  } catch (error) {
    return {
      status: "error",
      model: {
        backend: "unknown",
        available: false,
        message: "Could not connect to API",
      },
      gpu: { available: false, name: null },
    };
  }
}

/**
 * Check if the API is reachable.
 * 
 * @returns {Promise<boolean>} True if API is healthy
 */
export async function checkHealth() {
  try {
    const response = await axios.get(
      API_BASE_URL.replace("/api", "/health"),
      { timeout: 5000 }
    );
    return response.data?.status === "healthy";
  } catch {
    return false;
  }
}

// Export the base URL for debugging
export const getApiUrl = () => API_BASE_URL;
