// src/api/axiosInstance.js

import axios from "axios";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
const apiSecretKey = import.meta.env.VITE_API_KEY;

if (!apiBaseUrl && import.meta.env.PROD) {
  console.warn(
    "CRITICAL WARNING: VITE_API_BASE_URL environment variable is NOT SET for production build. API calls will likely fail."
  );
}

if (!apiSecretKey) {
  console.warn(
    "CRITICAL WARNING: VITE_API_KEY environment variable is NOT SET. API calls will be unauthenticated and will likely fail."
  );
}

const apiClient = axios.create({
  baseURL: apiBaseUrl || "",

  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
    "X-API-KEY": apiSecretKey || "",
  },
});

export default apiClient;
