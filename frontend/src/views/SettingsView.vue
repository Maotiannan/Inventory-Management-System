<template>
  <main class="page-shell">
    <n-spin :show="loading">
      <header class="page-top">
        <div>
          <h2>系统设置</h2>
          <p>管理表格、字段、账号、API Key、系统运维与日志</p>
        </div>
        <n-space>
          <n-button @click="goBack">返回列表</n-button>
        </n-space>
      </header>

      <n-space style="margin-bottom: 14px">
        <n-button
          v-for="section in sectionOptions"
          :key="section.value"
          :type="activeSection === section.value ? 'primary' : 'default'"
          @click="activeSection = section.value"
        >
          {{ section.label }}
        </n-button>
      </n-space>

      <template v-if="activeSection === 'table'">
        <n-card title="表格管理" size="small" class="schema-card">
          <n-space vertical>
            <n-space>
              <n-input v-model:value="newTableName" placeholder="新表格名称，例如：进销存表2" />
              <n-button type="primary" @click="createTable">创建表格</n-button>
            </n-space>
            <n-data-table :columns="tableColumns" :data="tablesStore.tables" :row-key="(row) => row.id" size="small" />
          </n-space>
        </n-card>

        <n-card title="表格详情编辑" size="small" class="schema-card">
          <n-space vertical>
            <n-select
              :options="tableOptions"
              :value="editingTableId"
              placeholder="请选择要编辑的表格"
              @update:value="switchEditingTable"
            />

            <template v-if="editingTableId">
              <n-form-item label="表格名称">
                <n-input v-model:value="editingTableName" placeholder="请输入表格名称" />
              </n-form-item>

              <section class="field-list">
                <article v-for="(field, index) in fields" :key="index" class="field-item">
                  <n-grid cols="1 s:4" responsive="screen" :x-gap="12">
                    <n-form-item-gi label="键名 (key)">
                      <n-input v-model:value="field.key" placeholder="例如：size" />
                    </n-form-item-gi>
                    <n-form-item-gi label="标题 (label)">
                      <n-input v-model:value="field.label" placeholder="例如：尺码" />
                    </n-form-item-gi>
                    <n-form-item-gi label="类型">
                      <n-select v-model:value="field.type" :options="typeOptions" />
                    </n-form-item-gi>
                    <n-form-item-gi label="可选值 (仅 select)">
                      <n-input
                        v-model:value="field.options_text"
                        placeholder="支持分隔符：逗号、空格、分号、斜杠、竖线"
                      />
                    </n-form-item-gi>
                  </n-grid>
                  <n-space>
                    <n-button size="small" tertiary @click="removeField(index)">删除字段</n-button>
                  </n-space>
                </article>
              </section>
            </template>

            <n-space>
              <n-button dashed @click="addField" :disabled="!editingTableId">新增字段</n-button>
              <n-button type="primary" :loading="savingSchema" :disabled="!editingTableId" @click="saveTableConfig">
                保存当前表格配置
              </n-button>
            </n-space>
          </n-space>
        </n-card>
      </template>

      <n-card title="账号配置" size="small" class="schema-card" v-if="activeSection === 'account' && isAdmin">
        <n-space vertical>
          <n-space>
            <n-input v-model:value="newAccount.username" placeholder="新账号用户名" />
            <n-input
              v-model:value="newAccount.password"
              type="password"
              show-password-on="click"
              placeholder="新账号密码（至少 6 位）"
            />
            <n-button type="primary" :loading="creatingUser" @click="createUser">新增账号</n-button>
            <n-button @click="loadUsers">刷新账号列表</n-button>
          </n-space>
          <n-text depth="3">新账号默认角色为 operator，拥有除“新增账号”外的全部功能。</n-text>
          <n-data-table :columns="userColumns" :data="users" :row-key="(row) => row.id" size="small" />
        </n-space>
      </n-card>

      <n-card title="账号配置" size="small" class="schema-card" v-else-if="activeSection === 'account'">
        <n-alert type="info" title="当前账号不是管理员">
          你可以使用所有业务功能，但不能新增账号。
        </n-alert>
      </n-card>

      <n-card title="API 设置" size="small" class="schema-card" v-if="activeSection === 'api'">
        <n-space vertical>
          <n-text>API 地址: {{ apiInfo.api_base || "-" }}</n-text>
          <n-text>OpenAPI: {{ apiInfo.openapi_url || "-" }}</n-text>
          <n-text>文档: {{ apiInfo.docs_url || "-" }}</n-text>

          <n-divider />
          <n-h4>API Key</n-h4>
          <n-space>
            <n-input v-model:value="newApiKeyName" placeholder="API Key 名称" />
            <n-button type="primary" @click="createApiKey">生成 API Key</n-button>
            <n-button @click="loadApiKeys">刷新列表</n-button>
          </n-space>
          <n-alert v-if="generatedApiKey" type="success" title="新生成的 API Key（已永久保存）">
            <n-space>
              <n-text>{{ generatedApiKey }}</n-text>
              <n-button size="tiny" @click="copyText(generatedApiKey)">一键复制</n-button>
            </n-space>
          </n-alert>
          <n-data-table :columns="apiKeyColumns" :data="apiKeys" :row-key="(row) => row.id" size="small" />

          <n-divider />
          <n-h4>可调用 API</n-h4>
          <n-code :code="apiReferenceText" language="text" />
        </n-space>
      </n-card>

      <n-card title="系统运维" size="small" class="schema-card" v-if="activeSection === 'system' && isAdmin">
        <n-space vertical>
          <n-alert type="info" title="使用说明">
            先配置仓库地址（REPO_URL）与分支，再执行检查更新、更新和回滚。
          </n-alert>

          <n-h4>仓库配置</n-h4>
          <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
            <n-form-item-gi label="REPO_URL">
              <n-input v-model:value="repoConfig.repo_url" placeholder="https://github.com/your/repo.git" />
            </n-form-item-gi>
            <n-form-item-gi label="分支">
              <n-input v-model:value="repoConfig.branch" placeholder="main" />
            </n-form-item-gi>
          </n-grid>
          <n-space>
            <n-button :loading="savingRepo" @click="saveRepoConfig(false)">仅保存</n-button>
            <n-button type="primary" :loading="savingRepo" @click="saveRepoConfig(true)">保存并初始化仓库</n-button>
            <n-button @click="loadRepoConfig">刷新</n-button>
          </n-space>
          <n-text depth="3">仓库路径: {{ repoConfig.repo_path || "-" }}</n-text>
          <n-text depth="3">已初始化: {{ repoConfig.initialized ? "是" : "否" }}</n-text>

          <n-divider />
          <n-h4>项目更新</n-h4>
          <n-space vertical>
            <n-text>当前分支: {{ updateStatus.current_branch || versionState.branch || "-" }}</n-text>
            <n-text>当前版本: {{ updateStatus.current_commit || versionState.commit || versionState.short_commit || "-" }}</n-text>
            <n-text>远端版本: {{ updateStatus.remote_commit || "-" }}</n-text>
            <n-text>状态: {{ updateStatus.message || "-" }}</n-text>
            <n-text v-if="versionState.message" depth="3">版本状态: {{ versionState.message }}</n-text>
          </n-space>
          <n-space>
            <n-button :loading="checkingUpdate" @click="checkUpdateStatus">检查更新</n-button>
            <n-button type="primary" :loading="applyingUpdate" @click="applyUpdateNow">一键更新并重启</n-button>
          </n-space>

          <n-divider />
          <n-h4>精确回滚</n-h4>
          <n-space>
            <n-input v-model:value="rollbackRef" placeholder="输入 tag/commit，例如 v1.0.0 或 commit SHA" />
            <n-button type="error" :loading="rollingBack" @click="rollbackToRef">执行回滚</n-button>
            <n-button :loading="refreshingVersionMeta" @click="refreshVersionMeta">刷新版本信息</n-button>
          </n-space>

          <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
            <n-card title="标签列表" size="small">
              <n-space vertical>
                <n-button size="small" @click="loadVersionTags">刷新标签</n-button>
                <n-data-table :columns="versionTagColumns" :data="versionTags" :row-key="(row) => row.tag" size="small" />
              </n-space>
            </n-card>
            <n-card title="最近提交" size="small">
              <n-space vertical>
                <n-button size="small" @click="loadVersionHistory">刷新提交</n-button>
                <n-data-table
                  :columns="versionHistoryColumns"
                  :data="versionHistory"
                  :row-key="(row) => row.commit"
                  size="small"
                />
              </n-space>
            </n-card>
          </n-grid>

          <n-divider />
          <n-h4>Tailscale 设置</n-h4>
          <n-grid cols="1 s:2" responsive="screen" :x-gap="12">
            <n-form-item-gi label="Container Name">
              <n-input v-model:value="tailscaleConfig.container_name" placeholder="tailscaled" />
            </n-form-item-gi>
            <n-form-item-gi label="Hostname">
              <n-input v-model:value="tailscaleConfig.hostname" placeholder="znas-server" />
            </n-form-item-gi>
            <n-form-item-gi label="TS_AUTHKEY">
              <n-input v-model:value="tailscaleConfig.auth_key" type="password" show-password-on="click" />
            </n-form-item-gi>
            <n-form-item-gi label="TS_STATE_DIR">
              <n-input v-model:value="tailscaleConfig.state_dir" placeholder="/var/lib/tailscale" />
            </n-form-item-gi>
            <n-form-item-gi label="TS_USERSPACE">
              <n-select :options="boolOptions" v-model:value="tailscaleConfig.userspace" />
            </n-form-item-gi>
            <n-form-item-gi label="TS_ROUTES">
              <n-input v-model:value="tailscaleConfig.routes" placeholder="192.168.1.0/24" />
            </n-form-item-gi>
          </n-grid>
          <n-space>
            <n-button :loading="savingTailscale" @click="saveTailscale(false)">保存配置</n-button>
            <n-button type="primary" :loading="savingTailscale" @click="saveTailscale(true)">
              保存并应用（重启 tailscale）
            </n-button>
          </n-space>
        </n-space>
      </n-card>

      <n-card title="系统运维" size="small" class="schema-card" v-else-if="activeSection === 'system'">
        <n-alert type="info" title="仅管理员可用">
          当前账号没有系统运维权限。
        </n-alert>
      </n-card>

      <n-card title="日志" size="small" v-if="activeSection === 'logs'">
        <div class="logs-scroll-box">
          <n-data-table :columns="logColumns" :data="logs" :row-key="(row) => row.id" size="small" />
        </div>
      </n-card>
    </n-spin>
  </main>
</template>

<script setup>
import { computed, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NAlert,
  NButton,
  NCard,
  NCode,
  NDataTable,
  NDivider,
  NFormItem,
  NFormItemGi,
  NGrid,
  NH4,
  NInput,
  NSelect,
  NSpace,
  NSpin,
  NText,
  useDialog,
  useMessage,
} from "naive-ui";

import http from "../api/http";
import { useAuthStore } from "../stores/auth";
import { useTablesStore } from "../stores/tables";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const authStore = useAuthStore();
const tablesStore = useTablesStore();

const loading = ref(false);
const savingSchema = ref(false);
const creatingUser = ref(false);
const savingTailscale = ref(false);
const checkingUpdate = ref(false);
const applyingUpdate = ref(false);
const savingRepo = ref(false);
const rollingBack = ref(false);
const refreshingVersionMeta = ref(false);

const newTableName = ref("");
const editingTableId = ref("");
const editingTableName = ref("");
const fields = ref([]);

const apiInfo = ref({ api_base: "", openapi_url: "", docs_url: "" });
const apiReference = ref({});
const apiKeys = ref([]);
const newApiKeyName = ref("AI 管理");
const generatedApiKey = ref("");
const logs = ref([]);
const users = ref([]);
const activeSection = ref("table");

const tailscaleConfig = ref({
  container_name: "tailscaled",
  hostname: "znas-server",
  auth_key: "",
  state_dir: "/var/lib/tailscale",
  userspace: false,
  routes: "192.168.1.0/24",
});

const repoConfig = ref({
  repo_url: "",
  branch: "main",
  repo_path: "",
  initialized: false,
});

const updateStatus = ref({
  enabled: true,
  ok: false,
  current_branch: "",
  current_commit: "",
  remote_commit: "",
  has_update: false,
  message: "",
  log_path: "",
});

const versionState = ref({
  repo_url: "",
  branch: "",
  commit: "",
  short_commit: "",
  tag: "",
  checked_at: "",
  message: "",
});

const versionTags = ref([]);
const versionHistory = ref([]);
const rollbackRef = ref("");

const newAccount = ref({ username: "", password: "" });

const isAdmin = computed(() => authStore.user?.role === "admin");
const sectionOptions = [
  { label: "表格设置", value: "table" },
  { label: "账号配置", value: "account" },
  { label: "API 设置", value: "api" },
  { label: "系统运维", value: "system" },
  { label: "日志", value: "logs" },
];

const typeOptions = [
  { label: "文本", value: "text" },
  { label: "数字", value: "number" },
  { label: "下拉选择", value: "select" },
];
const boolOptions = [
  { label: "true", value: true },
  { label: "false", value: false },
];

const tableOptions = computed(() =>
  tablesStore.tables.map((table) => ({ label: table.name, value: table.id }))
);

const apiReferenceText = computed(() => {
  return Object.entries(apiReference.value || {})
    .map(([k, arr]) => `${k}:\n${Array.isArray(arr) ? arr.map((x) => `  - ${x}`).join("\n") : ""}`)
    .join("\n\n");
});

function parseOptions(text) {
  return String(text || "")
    .split(/[\s,，;；/|、]+/g)
    .map((x) => x.trim())
    .filter(Boolean);
}

function normalizeFields(rawFields) {
  if (!Array.isArray(rawFields)) {
    return [];
  }
  return rawFields.map((field) => ({
    key: field.key || "",
    label: field.label || field.key || "",
    type: field.type || "text",
    options_text: Array.isArray(field.options) ? field.options.join(", ") : "",
  }));
}

function serializeFields() {
  return fields.value.map((field) => ({
    key: String(field.key || "").trim(),
    label: String(field.label || field.key || "").trim(),
    type: field.type || "text",
    options: parseOptions(field.options_text),
  }));
}

async function switchEditingTable(tableId) {
  editingTableId.value = tableId;
  const table = tablesStore.tables.find((x) => x.id === tableId);
  editingTableName.value = table?.name || "";
  fields.value = normalizeFields(table?.schema?.fields);
}

async function createTable() {
  const name = newTableName.value.trim();
  if (!name) {
    message.warning("请填写表格名称");
    return;
  }
  try {
    const created = await tablesStore.createTable({ name, schema: { fields: [] } });
    newTableName.value = "";
    await switchEditingTable(created.id);
    message.success("创建表格成功");
  } catch (error) {
    message.error(error?.response?.data?.detail || "创建表格失败");
  }
}

function addField() {
  fields.value.push({ key: "", label: "", type: "text", options_text: "" });
}

function removeField(index) {
  fields.value.splice(index, 1);
}

async function saveTableConfig() {
  if (!editingTableId.value) {
    message.warning("请先选择表格");
    return;
  }
  const nextTableName = editingTableName.value.trim();
  if (!nextTableName) {
    message.warning("表格名称不能为空");
    return;
  }

  const payloadFields = serializeFields();
  const invalid = payloadFields.find((f) => !f.key);
  if (invalid) {
    message.warning("每个字段都必须填写 key");
    return;
  }

  savingSchema.value = true;
  try {
    const updated = await tablesStore.updateTable(editingTableId.value, {
      name: nextTableName,
      schema: { fields: payloadFields },
    });
    await tablesStore.fetchTables();
    await switchEditingTable(updated.id);
    message.success("表格配置保存成功");
  } catch (error) {
    message.error(error?.response?.data?.detail || "保存失败");
  } finally {
    savingSchema.value = false;
  }
}

function removeTable(row) {
  dialog.warning({
    title: "确认删除表格",
    content: `是否删除表格 ${row.name}？`,
    positiveText: "删除",
    negativeText: "取消",
    async onPositiveClick() {
      try {
        await tablesStore.deleteTable(row.id);
        if (editingTableId.value === row.id) {
          await switchEditingTable(tablesStore.activeTableId || "");
        }
        message.success("删除成功");
      } catch (error) {
        const detail = error?.response?.data?.detail;
        if (
          error?.response?.status === 409 &&
          detail &&
          typeof detail === "object" &&
          detail.code === "TABLE_HAS_ITEMS"
        ) {
          dialog.warning({
            title: "表格包含数据",
            content: `${detail.message || "该表下仍有数据"}（${detail.items_count || 0} 条）`,
            positiveText: "同时删除数据",
            negativeText: "取消",
            async onPositiveClick() {
              try {
                await http.delete(`/tables/${row.id}`, { params: { purge_items: true } });
                await tablesStore.fetchTables();
                if (editingTableId.value === row.id) {
                  await switchEditingTable(tablesStore.activeTableId || "");
                }
                message.success("表格和数据已删除");
              } catch (forceError) {
                message.error(forceError?.response?.data?.detail || "删除失败");
              }
            },
          });
          return;
        }
        message.error(detail || "删除失败");
      }
    },
  });
}

async function loadUsers() {
  if (!isAdmin.value) {
    users.value = [];
    return;
  }
  try {
    const { data } = await http.get("/users");
    users.value = data;
  } catch (error) {
    message.error(error?.response?.data?.detail || "加载账号列表失败");
  }
}

async function createUser() {
  const username = String(newAccount.value.username || "").trim();
  const password = String(newAccount.value.password || "");
  if (!username) {
    message.warning("请填写用户名");
    return;
  }
  if (password.length < 6) {
    message.warning("密码至少 6 位");
    return;
  }

  creatingUser.value = true;
  try {
    await http.post("/users", { username, password });
    newAccount.value = { username: "", password: "" };
    await loadUsers();
    message.success("新增账号成功");
  } catch (error) {
    message.error(error?.response?.data?.detail || "新增账号失败");
  } finally {
    creatingUser.value = false;
  }
}

function removeUser(row) {
  if (row.username === authStore.user?.username) {
    message.warning("不能删除当前登录账号");
    return;
  }
  dialog.warning({
    title: "确认删除账号",
    content: `删除账号 ${row.username} 后无法恢复。`,
    positiveText: "删除",
    negativeText: "取消",
    async onPositiveClick() {
      try {
        await http.delete(`/users/${row.id}`);
        await loadUsers();
        message.success("账号已删除");
      } catch (error) {
        message.error(error?.response?.data?.detail || "删除账号失败");
      }
    },
  });
}

async function loadApiInfo() {
  const { data } = await http.get("/integration/api-info");
  apiInfo.value = data;
}

async function loadApiReference() {
  const { data } = await http.get("/integration/api-reference");
  apiReference.value = data;
}

async function loadApiKeys() {
  const { data } = await http.get("/integration/api-keys");
  apiKeys.value = data;
}

async function loadTailscaleConfig() {
  if (!isAdmin.value) {
    return;
  }
  const { data } = await http.get("/system/tailscale/config");
  tailscaleConfig.value = {
    container_name: data.container_name || "tailscaled",
    hostname: data.hostname || "znas-server",
    auth_key: data.auth_key || "",
    state_dir: data.state_dir || "/var/lib/tailscale",
    userspace: Boolean(data.userspace),
    routes: data.routes || "192.168.1.0/24",
  };
}

async function saveTailscale(apply) {
  savingTailscale.value = true;
  try {
    await http.put("/system/tailscale/config", {
      ...tailscaleConfig.value,
      apply,
    });
    message.success(apply ? "已应用 tailscale 配置" : "tailscale 配置已保存");
  } catch (error) {
    message.error(error?.response?.data?.detail || "保存 tailscale 配置失败");
  } finally {
    savingTailscale.value = false;
  }
}

async function loadRepoConfig() {
  if (!isAdmin.value) {
    return;
  }
  try {
    const { data } = await http.get("/system/repo/config");
    repoConfig.value = {
      repo_url: data.repo_url || "",
      branch: data.branch || "main",
      repo_path: data.repo_path || "",
      initialized: Boolean(data.initialized),
    };
  } catch (error) {
    message.error(error?.response?.data?.detail || "加载仓库配置失败");
  }
}

async function saveRepoConfig(initialize) {
  savingRepo.value = true;
  try {
    const payload = {
      repo_url: String(repoConfig.value.repo_url || "").trim(),
      branch: String(repoConfig.value.branch || "main").trim() || "main",
      initialize,
    };
    await http.put("/system/repo/config", payload);
    await loadRepoConfig();
    message.success(initialize ? "仓库配置已保存并初始化" : "仓库配置已保存");
  } catch (error) {
    message.error(error?.response?.data?.detail || "保存仓库配置失败");
  } finally {
    savingRepo.value = false;
  }
}

async function checkUpdateStatus(silent = false) {
  if (!silent) {
    checkingUpdate.value = true;
  }
  try {
    const { data } = await http.get("/system/update/status", { timeout: 20000 });
    updateStatus.value = { ...updateStatus.value, ...data };
    if (!silent) {
      message.info(data.message || "Update status refreshed");
    }
  } catch (error) {
    const detail =
      error?.response?.data?.detail ||
      (error?.code === "ECONNABORTED" ? "请求超时，请稍后重试" : "Update check failed");
    updateStatus.value = {
      ...updateStatus.value,
      ok: false,
      message: detail,
    };
    if (!silent) {
      message.error(detail);
    }
  } finally {
    if (!silent) {
      checkingUpdate.value = false;
    }
  }
}

async function applyUpdateNow() {
  applyingUpdate.value = true;
  try {
    const { data } = await http.post("/system/update/apply");
    updateStatus.value = { ...updateStatus.value, ...data };
    message.success(data?.message || "更新任务已启动");
  } catch (error) {
    message.error(error?.response?.data?.detail || "启动更新失败");
  } finally {
    applyingUpdate.value = false;
  }
}

async function loadVersionState(silent = false) {
  if (!isAdmin.value) {
    return false;
  }
  try {
    const { data } = await http.get("/system/version/state", { timeout: 20000 });
    versionState.value = data;
    const hasVersion = Boolean(data?.commit || data?.short_commit);
    if (!hasVersion && !silent) {
      message.warning(data?.message || "已连接，但暂未获取到版本号");
    }
    return hasVersion;
  } catch (error) {
    if (!silent) {
      message.error(error?.response?.data?.detail || "Failed to load version state");
    }
    return false;
  }
}

async function loadVersionTags(silent = false) {
  if (!isAdmin.value) {
    return false;
  }
  try {
    const { data } = await http.get("/system/version/tags", {
      params: { limit: 100 },
      timeout: 20000,
    });
    versionTags.value = Array.isArray(data?.items) ? data.items.map((tag) => ({ tag })) : [];
    return true;
  } catch (error) {
    if (!silent) {
      message.error(error?.response?.data?.detail || "Failed to load tags");
    }
    return false;
  }
}

async function loadVersionHistory(silent = false) {
  if (!isAdmin.value) {
    return false;
  }
  try {
    const { data } = await http.get("/system/version/history", {
      params: { limit: 50 },
      timeout: 20000,
    });
    versionHistory.value = Array.isArray(data?.items) ? data.items : [];
    return true;
  } catch (error) {
    if (!silent) {
      message.error(error?.response?.data?.detail || "Failed to load commit history");
    }
    return false;
  }
}

async function refreshVersionMeta() {
  refreshingVersionMeta.value = true;
  try {
    const results = await Promise.all([
      loadVersionState(true),
      loadVersionTags(true),
      loadVersionHistory(true),
    ]);
    const okCount = results.filter(Boolean).length;
    const hasVersionIdentity = Boolean(versionState.value?.commit || versionState.value?.short_commit);
    if (okCount === results.length && hasVersionIdentity) {
      message.success("版本信息已刷新");
    } else if (okCount > 0) {
      message.warning(versionState.value?.message || "部分版本信息刷新成功，请稍后重试失败项");
    } else {
      message.error(versionState.value?.message || "刷新版本信息失败，请检查网络或仓库配置");
    }
  } finally {
    refreshingVersionMeta.value = false;
  }
}

function pickRollbackRef(value) {
  rollbackRef.value = value;
}

async function rollbackToRef() {
  const ref = String(rollbackRef.value || "").trim();
  if (!ref) {
    message.warning("请先输入要回滚的版本号或提交号");
    return;
  }

  dialog.error({
    title: "确认执行回滚",
    content: `即将回滚到 ${ref}，请确认当前数据已备份。`,
    positiveText: "确认回滚",
    negativeText: "取消",
    async onPositiveClick() {
      rollingBack.value = true;
      try {
        const { data } = await http.post("/system/version/rollback", { ref });
        message.success(data?.message || "回滚任务已启动");
      } catch (error) {
        message.error(error?.response?.data?.detail || "启动回滚失败");
      } finally {
        rollingBack.value = false;
      }
    },
  });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    message.success("已复制");
  } catch (_) {
    message.error("复制失败，请手动复制");
  }
}

async function createApiKey() {
  try {
    const { data } = await http.post("/integration/api-keys", { name: newApiKeyName.value || "AI 管理" });
    generatedApiKey.value = data.api_key;
    await loadApiKeys();
    message.success("API Key 生成成功");
  } catch (error) {
    message.error(error?.response?.data?.detail || "生成 API Key 失败");
  }
}

function revokeApiKey(row) {
  dialog.warning({
    title: "确认停用",
    content: `确认停用 API Key: ${row.name}`,
    positiveText: "停用",
    negativeText: "取消",
    async onPositiveClick() {
      try {
        await http.delete(`/integration/api-keys/${row.id}`);
        await loadApiKeys();
        message.success("已停用");
      } catch (error) {
        message.error(error?.response?.data?.detail || "停用失败");
      }
    },
  });
}

async function loadLogs() {
  const { data } = await http.get("/integration/logs", { params: { limit: 50 } });
  logs.value = data;
}

const tableColumns = [
  { title: "名称", key: "name" },
  { title: "更新时间", key: "updated_at" },
  {
    title: "操作",
    key: "actions",
    width: 190,
    render(row) {
      return h(NSpace, null, {
        default: () => [
          h(
            NButton,
            { size: "tiny", onClick: () => switchEditingTable(row.id) },
            { default: () => "编辑" }
          ),
          h(
            NButton,
            { size: "tiny", type: "error", secondary: true, onClick: () => removeTable(row) },
            { default: () => "删除" }
          ),
        ],
      });
    },
  },
];

const userColumns = [
  { title: "用户名", key: "username", minWidth: 120 },
  { title: "角色", key: "role", minWidth: 100 },
  { title: "创建时间", key: "created_at", minWidth: 180 },
  {
    title: "操作",
    key: "actions",
    width: 120,
    render(row) {
      return h(
        NButton,
        { size: "tiny", type: "error", secondary: true, onClick: () => removeUser(row) },
        { default: () => "删除" }
      );
    },
  },
];

const apiKeyColumns = [
  { title: "名称", key: "name", minWidth: 120 },
  { title: "前缀", key: "key_prefix", minWidth: 120 },
  { title: "完整Key", key: "api_key", minWidth: 220 },
  { title: "创建时间", key: "created_at", minWidth: 160 },
  { title: "最近调用", key: "last_used_at", minWidth: 160 },
  {
    title: "操作",
    key: "actions",
    width: 160,
    render(row) {
      return h(NSpace, null, {
        default: () => [
          h(
            NButton,
            { size: "tiny", type: "primary", secondary: true, onClick: () => copyText(row.api_key) },
            { default: () => "复制" }
          ),
          h(
            NButton,
            { size: "tiny", type: "error", secondary: true, onClick: () => revokeApiKey(row) },
            { default: () => "停用" }
          ),
        ],
      });
    },
  },
];

const versionTagColumns = [
  { title: "Tag", key: "tag", minWidth: 180 },
  {
    title: "操作",
    key: "actions",
    width: 100,
    render(row) {
      return h(
        NButton,
        { size: "tiny", onClick: () => pickRollbackRef(row.tag) },
        { default: () => "选中" }
      );
    },
  },
];

const versionHistoryColumns = [
  { title: "提交", key: "short_commit", minWidth: 110 },
  { title: "时间", key: "committed_at", minWidth: 180 },
  { title: "说明", key: "subject", minWidth: 220 },
  {
    title: "操作",
    key: "actions",
    width: 100,
    render(row) {
      return h(
        NButton,
        { size: "tiny", onClick: () => pickRollbackRef(row.commit) },
        { default: () => "选中" }
      );
    },
  },
];

const logColumns = [
  { title: "时间", key: "created_at", minWidth: 170 },
  { title: "操作者", key: "operator_username", minWidth: 120 },
  {
    title: "调用来源",
    key: "auth_source",
    minWidth: 150,
    render(row) {
      if (row.auth_source === "api_key") {
        return `API Key: ${row.auth_label || "-"}`;
      }
      if (row.auth_source === "jwt") {
        return `账号登录: ${row.auth_label || row.operator_username || "-"}`;
      }
      return row.auth_label || row.auth_source || "-";
    },
  },
  { title: "动作", key: "action", minWidth: 120 },
  { title: "目标", key: "target", minWidth: 120 },
  { title: "摘要", key: "summary", minWidth: 240 },
];

function goBack() {
  router.push("/");
}

onMounted(async () => {
  loading.value = true;
  try {
    await Promise.all([
      tablesStore.fetchTables(),
      loadApiInfo(),
      loadApiReference(),
      loadApiKeys(),
      loadLogs(),
      loadUsers(),
    ]);

    if (isAdmin.value) {
      await Promise.all([loadRepoConfig(), loadTailscaleConfig()]);
      await Promise.allSettled([
        checkUpdateStatus(true),
        loadVersionState(true),
        loadVersionTags(true),
        loadVersionHistory(true),
      ]);
    }

    await switchEditingTable(tablesStore.activeTableId || tablesStore.tables[0]?.id || "");
  } catch (error) {
    message.error(error?.response?.data?.detail || "Failed to load settings");
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.logs-scroll-box {
  max-height: calc(100vh - 240px);
  min-height: 260px;
  overflow: auto;
}
</style>
