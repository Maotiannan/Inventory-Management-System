<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN">
    <n-dialog-provider>
      <n-message-provider>
        <router-view />
        <footer class="app-footer">
          <span>ZNAS {{ appVersion }}</span>
        </footer>
      </n-message-provider>
    </n-dialog-provider>
  </n-config-provider>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { NConfigProvider, NDialogProvider, NMessageProvider, dateZhCN, zhCN } from "naive-ui";
import http from "./api/http";

const appVersion = ref("");

onMounted(async () => {
  try {
    const { data } = await http.get("/version");
    appVersion.value = data.version || "";
  } catch (_) {
    appVersion.value = "";
  }
});
</script>

<style>
.app-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  text-align: center;
  padding: 6px 0;
  font-size: 12px;
  color: #999;
  pointer-events: none;
  z-index: 0;
}
</style>
