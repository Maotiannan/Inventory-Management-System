<template>
  <main class="page-shell">
    <n-spin :show="pageLoading">
      <header class="page-top">
        <div>
          <h2>{{ isNew ? "新建物料" : "编辑物料" }}</h2>
          <p>当前表格: {{ tableLabel }}</p>
        </div>
        <n-space>
          <n-button @click="backToList">返回列表</n-button>
          <n-button v-if="!isNew" type="error" secondary :loading="deleting" @click="deleteItem">删除</n-button>
          <n-button type="primary" :loading="saving" @click="saveItem">保存</n-button>
        </n-space>
      </header>

      <section class="detail-grid">
        <n-card title="基础信息" size="small">
          <n-form label-placement="top">
            <n-grid cols="1 s:2" responsive="screen" :x-gap="16">
              <n-form-item-gi label="名称">
                <n-input v-model:value="form.name" placeholder="请输入名称" />
              </n-form-item-gi>
              <n-form-item-gi label="编码">
                <n-input v-model:value="form.code" placeholder="请输入唯一编码" />
              </n-form-item-gi>
              <n-form-item-gi label="库存数量">
                <n-input-number v-model:value="form.quantity" :min="0" style="width: 100%" />
              </n-form-item-gi>
              <n-form-item-gi label="备注">
                <n-input v-model:value="form.notes" type="textarea" :rows="4" placeholder="可选备注" />
              </n-form-item-gi>
            </n-grid>
          </n-form>
        </n-card>

        <n-card title="图片" size="small">
          <n-space vertical>
            <n-upload :custom-request="uploadImage" :show-file-list="false" accept="image/*">
              <n-button>上传图片并生成缩略图</n-button>
            </n-upload>
            <img v-if="thumbPreview" :src="thumbPreview" class="preview-thumb" alt="缩略图" />
            <n-text depth="3">原图路径: {{ form.image_original || "未上传" }}</n-text>
            <n-text depth="3">缩略图路径: {{ form.image_thumb || "未上传" }}</n-text>
          </n-space>
        </n-card>
      </section>

      <n-card title="动态字段 (JSONB)" size="small" class="schema-card">
        <n-empty v-if="schemaFields.length === 0" description="该表格暂未配置动态字段" />
        <n-form v-else label-placement="top">
          <n-grid cols="1 s:2" responsive="screen" :x-gap="16">
            <n-form-item-gi v-for="field in schemaFields" :key="field.key" :label="field.label || field.key">
              <n-input
                v-if="field.type === 'text' || !field.type"
                v-model:value="form.properties[field.key]"
                :placeholder="`请输入 ${field.label || field.key}`"
              />
              <n-input-number
                v-else-if="field.type === 'number'"
                v-model:value="form.properties[field.key]"
                style="width: 100%"
              />
              <n-select
                v-else-if="field.type === 'select'"
                v-model:value="form.properties[field.key]"
                :options="selectOptions(field.options)"
                placeholder="请选择"
              />
              <n-input v-else v-model:value="form.properties[field.key]" />
            </n-form-item-gi>
          </n-grid>
        </n-form>
      </n-card>
    </n-spin>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NEmpty,
  NForm,
  NFormItemGi,
  NGrid,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSpin,
  NText,
  NUpload,
  useDialog,
  useMessage,
} from "naive-ui";

import http from "../api/http";
import { useItemsStore } from "../stores/items";
import { useTablesStore } from "../stores/tables";
import { mediaUrl } from "../utils/media";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const itemsStore = useItemsStore();
const tablesStore = useTablesStore();

const isNew = route.path.endsWith("/new");
const itemId = route.params.id;
const saving = ref(false);
const deleting = ref(false);
const pageLoading = ref(false);
const schemaFields = ref([]);
const currentTableId = ref("");

const form = reactive({
  name: "",
  code: "",
  quantity: 0,
  image_original: "",
  image_thumb: "",
  notes: "",
  properties: {},
});

const thumbPreview = ref("");
const tableLabel = computed(() => {
  const table = tablesStore.tables.find((x) => x.id === currentTableId.value);
  return table?.name || "未选择";
});

function selectOptions(options) {
  if (!Array.isArray(options)) {
    return [];
  }
  return options.map((opt) => ({ label: String(opt), value: String(opt) }));
}

async function loadSchema(tableId) {
  const { data } = await http.get("/config/schema", { params: { table_id: tableId } });
  const fields = data?.schema?.fields;
  schemaFields.value = Array.isArray(fields) ? fields : [];
}

async function loadItem() {
  if (isNew) {
    currentTableId.value = String(route.query.table_id || tablesStore.activeTableId || "");
    if (!currentTableId.value) {
      message.warning("请先在列表页选择表格");
      router.replace("/");
      return;
    }
    await loadSchema(currentTableId.value);
    return;
  }

  const item = await itemsStore.fetchItem(itemId);
  currentTableId.value = item.table_id;
  await loadSchema(currentTableId.value);

  form.name = item.name;
  form.code = item.code;
  form.quantity = item.quantity;
  form.image_original = item.image_original || "";
  form.image_thumb = item.image_thumb || "";
  form.notes = item.notes || "";
  form.properties = { ...(item.properties || {}) };
  thumbPreview.value = mediaUrl(form.image_thumb);
}

async function uploadImage({ file, onFinish, onError }) {
  try {
    const resp = await itemsStore.uploadImage(file.file);
    form.image_original = resp.original_path;
    form.image_thumb = resp.thumb_path;
    thumbPreview.value = resp.thumb_url || mediaUrl(resp.thumb_path);
    message.success("图片上传成功");
    onFinish();
  } catch (error) {
    message.error(error?.response?.data?.detail || "图片上传失败");
    onError();
  }
}

function buildPayload() {
  return {
    table_id: currentTableId.value,
    name: form.name.trim(),
    code: form.code.trim(),
    quantity: Number(form.quantity || 0),
    image_original: form.image_original || null,
    image_thumb: form.image_thumb || null,
    notes: form.notes || null,
    properties: { ...(form.properties || {}) },
  };
}

async function saveItem() {
  if (!currentTableId.value) {
    message.warning("未选择表格");
    return;
  }
  if (!form.name.trim() || !form.code.trim()) {
    message.warning("名称和编码必填");
    return;
  }

  saving.value = true;
  try {
    if (isNew) {
      const created = await itemsStore.createItem(buildPayload());
      message.success("创建成功");
      router.replace(`/items/${created.id}`);
    } else {
      await itemsStore.updateItemOptimistic(itemId, buildPayload());
      message.success("保存成功");
    }
  } catch (error) {
    message.error(error?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

function deleteItem() {
  dialog.error({
    title: "确认删除",
    content: "删除后不可恢复，是否继续？",
    positiveText: "删除",
    negativeText: "取消",
    async onPositiveClick() {
      deleting.value = true;
      try {
        await itemsStore.deleteItem(itemId);
        message.success("已删除");
        router.replace("/");
      } catch (error) {
        message.error(error?.response?.data?.detail || "删除失败");
      } finally {
        deleting.value = false;
      }
    },
  });
}

function backToList() {
  router.push("/");
}

onMounted(async () => {
  pageLoading.value = true;
  try {
    if (tablesStore.tables.length === 0) {
      await tablesStore.fetchTables();
    }
    await loadItem();
  } catch (error) {
    message.error(error?.response?.data?.detail || "页面加载失败");
  } finally {
    pageLoading.value = false;
  }
});
</script>
