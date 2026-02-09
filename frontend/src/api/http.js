import axios from "axios";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 15000,
});

let unauthorizedHandler = null;

export function setAuthToken(token) {
  if (token) {
    http.defaults.headers.common.Authorization = `Bearer ${token}`;
    return;
  }
  delete http.defaults.headers.common.Authorization;
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof unauthorizedHandler === "function") {
      unauthorizedHandler();
    }
    return Promise.reject(error);
  }
);

export default http;
