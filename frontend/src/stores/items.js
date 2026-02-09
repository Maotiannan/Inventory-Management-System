import { defineStore } from "pinia";

import http from "../api/http";

function deepCopy(obj) {
  return JSON.parse(JSON.stringify(obj));
}

export const useItemsStore = defineStore("items", {
  state: () => ({
    items: [],
    loading: false,
    filters: {
      table_id: "",
      q: "",
      code: "",
      min_quantity: null,
      max_quantity: null,
    },
    pollingTimer: null,
  }),

  getters: {
    byId: (state) => (id) => state.items.find((item) => item.id === id),
    byCode: (state) => (code) => state.items.find((item) => item.code === code),
  },

  actions: {
    buildParams() {
      const params = {};
      for (const [key, value] of Object.entries(this.filters)) {
        if (value !== null && value !== undefined && value !== "") {
          params[key] = value;
        }
      }
      return params;
    },

    setFilters(payload) {
      this.filters = { ...this.filters, ...payload };
    },

    upsertItem(nextItem) {
      const index = this.items.findIndex((item) => item.id === nextItem.id);
      if (index === -1) {
        this.items = [nextItem, ...this.items];
      } else {
        this.items[index] = nextItem;
      }
    },

    async fetchItems() {
      this.loading = true;
      try {
        const { data } = await http.get("/items", { params: this.buildParams() });
        this.items = data;
      } finally {
        this.loading = false;
      }
    },

    async fetchItem(itemId) {
      const { data } = await http.get(`/items/${itemId}`);
      this.upsertItem(data);
      return data;
    },

    async createItem(payload) {
      const { data } = await http.post("/items", payload);
      this.upsertItem(data);
      return data;
    },

    applyPatchToItem(item, patch) {
      const fields = ["name", "code", "quantity", "image_original", "image_thumb", "notes"];
      for (const field of fields) {
        if (patch[field] !== undefined) {
          item[field] = patch[field];
        }
      }

      let nextProperties = { ...(item.properties || {}) };
      if (patch.properties !== undefined) {
        nextProperties = { ...patch.properties };
      }
      if (patch.properties_patch) {
        nextProperties = { ...nextProperties, ...patch.properties_patch };
      }
      if (Array.isArray(patch.properties_remove)) {
        for (const key of patch.properties_remove) {
          delete nextProperties[key];
        }
      }
      item.properties = nextProperties;
    },

    async updateItemOptimistic(itemId, patch) {
      const index = this.items.findIndex((item) => item.id === itemId);
      if (index === -1) {
        throw new Error("未找到目标物料");
      }

      const backup = deepCopy(this.items[index]);
      this.applyPatchToItem(this.items[index], patch);

      try {
        const { data } = await http.patch(`/items/${itemId}`, patch);
        this.items[index] = data;
        return data;
      } catch (error) {
        this.items[index] = backup;
        throw error;
      }
    },

    async deleteItem(itemId) {
      await http.delete(`/items/${itemId}`);
      this.items = this.items.filter((item) => item.id !== itemId);
    },

    async stockIn(payload) {
      const code = String(payload.code || "").trim();
      const index = this.items.findIndex(
        (item) => item.table_id === payload.table_id && item.code === code
      );
      const backup = index >= 0 ? deepCopy(this.items[index]) : null;
      if (index >= 0) {
        this.items[index].quantity = Number(this.items[index].quantity || 0) + Number(payload.quantity || 0);
      }

      try {
        const { data } = await http.post("/stock/in", payload);
        this.upsertItem(data);
        return data;
      } catch (error) {
        if (index >= 0 && backup) {
          this.items[index] = backup;
        }
        throw error;
      }
    },

    async stockOut(payload) {
      const code = String(payload.code || "").trim();
      const index = this.items.findIndex(
        (item) => item.table_id === payload.table_id && item.code === code
      );
      const backup = index >= 0 ? deepCopy(this.items[index]) : null;
      if (index >= 0) {
        this.items[index].quantity = Math.max(
          0,
          Number(this.items[index].quantity || 0) - Number(payload.quantity || 0)
        );
      }

      try {
        const { data } = await http.post("/stock/out", payload);
        this.upsertItem(data);
        return data;
      } catch (error) {
        if (index >= 0 && backup) {
          this.items[index] = backup;
        }
        throw error;
      }
    },

    async uploadImage(file) {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await http.post("/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      return data;
    },

    startPolling() {
      if (this.pollingTimer) {
        return;
      }
      this.pollingTimer = window.setInterval(() => {
        this.fetchItems().catch(() => {});
      }, 5000);
    },

    stopPolling() {
      if (!this.pollingTimer) {
        return;
      }
      window.clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    },
  },
});
