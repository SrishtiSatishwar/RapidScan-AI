// API Configuration - reads from .env file
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001';


export const config = {
  apiUrl: API_BASE_URL,
  
  endpoints: {
    health: `${API_BASE_URL}/health`,
    upload: `${API_BASE_URL}/upload`,
    queue: `${API_BASE_URL}/queue`,
    scan: (id) => `${API_BASE_URL}/scan/${id}`,
    facilities: `${API_BASE_URL}/facilities`,
    stats: `${API_BASE_URL}/stats`,
  },
};

// Helper for image URLs
export const getImageUrl = (imageUrl) => {
  if (!imageUrl) return null;
  if (imageUrl.startsWith('http')) return imageUrl;
  return `${API_BASE_URL}${imageUrl}`;
};

export default config;
