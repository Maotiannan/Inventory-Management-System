import { createApp } from "vue";
import { createPinia } from "pinia";
import { createDiscreteApi } from "naive-ui";

import App from "./App.vue";
import router from "./router";
import { setUnauthorizedHandler } from "./api/http";
import { useAuthStore } from "./stores/auth";
import "./styles.css";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);

const authStore = useAuthStore(pinia);
const { message } = createDiscreteApi(["message"]);

setUnauthorizedHandler(() => {
  authStore.clearSession();
  message.warning("登录已过期，请重新登录");
  if (router.currentRoute.value.path !== "/login") {
    router.replace("/login");
  }
});

async function bootstrap() {
  await authStore.initialize();
  app.use(router);
  app.mount("#app");
}

bootstrap();
