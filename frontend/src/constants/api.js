export const API_URL = import.meta.env.VITE_API_URL || (
  import.meta.env.PROD
    ? "https://hikeup.onrender.com"
    : "http://localhost:5000"
);
