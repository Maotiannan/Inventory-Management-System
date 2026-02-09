<template>
  <main class="login-page">
    <section class="login-panel">
      <h1>进销存管理系统</h1>
      <p>支持手机与电脑同步协作</p>

      <n-form :model="form" :rules="rules" ref="formRef" size="large">
        <n-form-item path="username" label="用户名">
          <n-input v-model:value="form.username" placeholder="请输入用户名" />
        </n-form-item>
        <n-form-item path="password" label="密码">
          <n-input
            v-model:value="form.password"
            type="password"
            show-password-on="click"
            placeholder="请输入密码"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
      </n-form>

      <label class="remember-line">
        <n-checkbox v-model:checked="rememberMe">记住我</n-checkbox>
      </label>

      <n-button type="primary" block size="large" :loading="authStore.loading" @click="onSubmit">
        登录
      </n-button>
    </section>
  </main>
</template>

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCheckbox, NForm, NFormItem, NInput, useMessage } from "naive-ui";

import { useAuthStore } from "../stores/auth";

const router = useRouter();
const message = useMessage();
const authStore = useAuthStore();
const formRef = ref(null);
const rememberMe = ref(true);

const form = reactive({
  username: "",
  password: "",
});

const rules = {
  username: { required: true, message: "请输入用户名", trigger: "blur" },
  password: { required: true, message: "请输入密码", trigger: "blur" },
};

async function onSubmit() {
  try {
    await formRef.value?.validate();
  } catch (_) {
    return;
  }

  try {
    await authStore.login({
      username: form.username.trim(),
      password: form.password,
      rememberMe: rememberMe.value,
    });
    message.success("登录成功");
    router.replace("/");
  } catch (error) {
    const detail = error?.response?.data?.detail || "登录失败，请检查用户名和密码";
    message.error(detail);
  }
}
</script>
