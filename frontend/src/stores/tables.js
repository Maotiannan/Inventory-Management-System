import { defineStore } from "pinia";

import http from "../api/http";

const ACTIVE_TABLE_KEY = "znas_active_table_id";

export const useTablesStore = defineStore("tables", {
  state: () => ({
    tables: [],
    activeTableId: localStorage.getItem(ACTIVE_TABLE_KEY) || "",
    loading: false,
  }),

  getters: {
    activeTable(state) {
      return state.tables.find((table) => table.id === state.activeTableId) || null;
    },
  },

  actions: {
    setActiveTable(tableId) {
      this.activeTableId = tableId || "";
      if (this.activeTableId) {
        localStorage.setItem(ACTIVE_TABLE_KEY, this.activeTableId);
      } else {
        localStorage.removeItem(ACTIVE_TABLE_KEY);
      }
    },

    async fetchTables() {
      this.loading = true;
      try {
        const { data } = await http.get("/tables");
        this.tables = data;
        if (!this.activeTableId && data.length > 0) {
          this.setActiveTable(data[0].id);
        }
        if (this.activeTableId && !data.find((x) => x.id === this.activeTableId)) {
          this.setActiveTable(data[0]?.id || "");
        }
      } finally {
        this.loading = false;
      }
    },

    async createTable(payload) {
      const { data } = await http.post("/tables", payload);
      this.tables = [data, ...this.tables];
      this.setActiveTable(data.id);
      return data;
    },

    async updateTable(tableId, payload) {
      const { data } = await http.patch(`/tables/${tableId}`, payload);
      const index = this.tables.findIndex((x) => x.id === tableId);
      if (index >= 0) {
        this.tables[index] = data;
      }
      return data;
    },

    async deleteTable(tableId) {
      await http.delete(`/tables/${tableId}`);
      this.tables = this.tables.filter((x) => x.id !== tableId);
      if (this.activeTableId === tableId) {
        this.setActiveTable(this.tables[0]?.id || "");
      }
    },
  },
});
