import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "../stores/auth";
import ItemDetailView from "../views/ItemDetailView.vue";
import ListView from "../views/ListView.vue";
import LoginView from "../views/LoginView.vue";
import SettingsView from "../views/SettingsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/", name: "list", component: ListView, meta: { requiresAuth: true } },
    { path: "/items/new", name: "item-new", component: ItemDetailView, meta: { requiresAuth: true } },
    {
      path: "/items/:id",
      name: "item-detail",
      component: ItemDetailView,
      meta: { requiresAuth: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: SettingsView,
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach((to) => {
  const authStore = useAuthStore();
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { path: "/login" };
  }
  if (to.path === "/login" && authStore.isAuthenticated) {
    return { path: "/" };
  }
  return true;
});

export default router;
