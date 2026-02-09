import { defineStore } from "pinia";

import http, { setAuthToken } from "../api/http";

const TOKEN_KEY = "znas_access_token";
const SESSION_TOKEN_KEY = "znas_access_token_session";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: "",
    user: null,
    loading: false,
    initialized: false,
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
  },

  actions: {
    persistToken(token, rememberMe) {
      if (rememberMe) {
        localStorage.setItem(TOKEN_KEY, token);
        sessionStorage.removeItem(SESSION_TOKEN_KEY);
      } else {
        sessionStorage.setItem(SESSION_TOKEN_KEY, token);
        localStorage.removeItem(TOKEN_KEY);
      }
    },

    clearSession() {
      this.token = "";
      this.user = null;
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(SESSION_TOKEN_KEY);
      setAuthToken("");
    },

    async initialize() {
      const localToken = localStorage.getItem(TOKEN_KEY);
      const sessionToken = sessionStorage.getItem(SESSION_TOKEN_KEY);
      this.token = localToken || sessionToken || "";

      if (!this.token) {
        this.initialized = true;
        return;
      }

      setAuthToken(this.token);
      try {
        const { data } = await http.get("/auth/validate", { timeout: 5000 });
        this.user = data;
      } catch (_) {
        this.clearSession();
      } finally {
        this.initialized = true;
      }
    },

    async login({ username, password, rememberMe }) {
      this.loading = true;
      try {
        const { data } = await http.post("/auth/login", { username, password });
        this.token = data.access_token;
        this.user = data.user;
        this.persistToken(this.token, rememberMe);
        setAuthToken(this.token);
      } finally {
        this.loading = false;
      }
    },

    logout() {
      this.clearSession();
    },
  },
});
