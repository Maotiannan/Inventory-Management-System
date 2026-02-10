<template>
  <main class="page-shell">
    <input
      ref="quickUploadInput"
      type="file"
      accept="image/*"
      style="display: none"
      @change="onQuickUploadChange"
    />
    <header class="page-top">
      <div>
        <h2>进销存列表</h2>
        <p>当前已启用 5 秒自动同步，不同表格字段互相独立</p>
      </div>
      <n-space>
        <n-select
          class="table-select"
          :options="tableOptions"
          :value="tablesStore.activeTableId"
          placeholder="请选择表格"
          @update:value="onSwitchTable"
        />
        <n-button type="primary" @click="openStockModal('in')">入库</n-button>
        <n-button type="warning" @click="openStockModal('out')">出库</n-button>
        <n-button type="info" @click="openScannerModal">扫码出入库</n-button>
        <n-button @click="goSettings">设置</n-button>
        <n-button tertiary @click="logout">退出登录</n-button>
      </n-space>
    </header>

    <section class="toolbar">
      <n-input
        v-model:value="keyword"
        clearable
        placeholder="按名称或编码搜索"
        @keyup.enter="applyFilters"
      />
      <n-button type="primary" @click="applyFilters">搜索</n-button>
      <n-button @click="resetFilters">重置</n-button>
      <n-button tertiary @click="refresh">刷新</n-button>
    </section>

    <n-spin :show="itemsStore.loading || tablesStore.loading">
      <n-empty v-if="!tablesStore.activeTableId" description="请先在设置页创建一个表格" />

      <section v-else-if="isMobile" class="mobile-cards">
        <article v-for="item in itemsStore.items" :key="item.id" class="item-card">
          <div class="item-card-head">
            <img
              v-if="item.image_thumb"
              :src="mediaUrl(item.image_thumb)"
              class="list-thumb"
              alt="缩略图"
              title="点击更换缩略图"
              style="cursor: pointer"
              @click="openQuickUpload(item)"
            />
            <n-button v-else size="small" tertiary @click="openQuickUpload(item)">上传缩略图</n-button>
            <div class="item-meta">
              <h3>{{ item.name }}</h3>
              <p>编码: {{ item.code }}</p>
            </div>
          </div>
          <div class="item-card-fields">
            <n-text v-for="field in activeSchemaFields" :key="field.key" depth="3">
              {{ field.label || field.key }}: {{ item.properties?.[field.key] ?? "-" }}
            </n-text>
          </div>
          <div class="item-card-foot">
            <n-tag type="info">库存 {{ item.quantity }}</n-tag>
            <n-space>
              <n-button size="small" type="primary" @click="openStockModal('in', item)">入库</n-button>
              <n-button size="small" type="warning" @click="openStockModal('out', item)">出库</n-button>
              <n-button size="small" secondary @click="goDetail(item.id)">编辑</n-button>
            </n-space>
          </div>
        </article>
      </section>

      <n-data-table
        v-else-if="tablesStore.activeTableId"
        :columns="columns"
        :data="itemsStore.items"
        :row-key="(row) => row.id"
        striped
        size="small"
      />
    </n-spin>

    <n-modal v-model:show="stockModal.show" preset="card" :title="stockModal.title" style="width: 560px">
      <n-form label-placement="top">
        <n-form-item label="编码">
          <n-input v-model:value="stockModal.form.code" placeholder="请输入物料编码" />
        </n-form-item>
        <n-form-item label="名称 (仅新物料入库必填)">
          <n-input v-model:value="stockModal.form.name" placeholder="入库新物料时请输入名称" />
        </n-form-item>
        <n-form-item label="数量">
          <n-input-number v-model:value="stockModal.form.quantity" :min="1" style="width: 100%" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="stockModal.show = false">取消</n-button>
          <n-button
            :type="stockModal.type === 'in' ? 'primary' : 'warning'"
            :loading="stockModal.submitting"
            @click="submitStock"
          >
            {{ stockModal.type === "in" ? "确认入库" : "确认出库" }}
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <n-modal v-model:show="scanner.show" preset="card" title="扫码出入库" style="width: min(980px, 96vw)">
      <n-space vertical>
        <n-alert type="info" title="扫码说明">
          请选择“表格 + 入/出库”，扫码枪每扫一次通常会自动回车换行，系统将按每行 1 个编码自动处理数量 1。
        </n-alert>

        <n-grid cols="1 s:3" responsive="screen" :x-gap="12">
          <n-form-item-gi label="库存表格">
            <n-select
              :options="tableOptions"
              :value="scanner.tableId"
              placeholder="请选择库存表格"
              @update:value="(v) => (scanner.tableId = v || '')"
            />
          </n-form-item-gi>
          <n-form-item-gi label="动作类型">
            <n-select
              :options="scanModeOptions"
              :value="scanner.mode"
              @update:value="(v) => (scanner.mode = v || 'in')"
            />
          </n-form-item-gi>
          <n-form-item-gi label="记录操作">
            <n-button @click="clearScanRecords">清空记录</n-button>
          </n-form-item-gi>
        </n-grid>

        <n-form-item label="扫码输入区（每行一个编码）">
          <n-input
            :value="scanner.scanText"
            type="textarea"
            :autosize="{ minRows: 6, maxRows: 12 }"
            placeholder="将光标放在这里开始扫码；每次换行会自动触发一次入/出库"
            @update:value="onScannerTextChange"
          />
        </n-form-item>

        <n-divider />
        <n-h4>处理记录</n-h4>

        <n-empty v-if="scanner.records.length === 0" description="暂无扫码记录" />
        <section v-else class="field-list">
          <article v-for="row in scanner.records" :key="row.id" class="field-item">
            <n-space justify="space-between">
              <n-text>{{ row.created_at }} | {{ row.code }}</n-text>
              <n-tag :type="row.status === '成功' ? 'success' : row.status === '待补名称' ? 'warning' : 'error'">
                {{ row.status }}
              </n-tag>
            </n-space>

            <n-space style="margin-top: 8px">
              <n-text>产品名: {{ row.name || "-" }}</n-text>
              <n-text>动作: {{ row.action_label }}</n-text>
              <n-text>数量: 1</n-text>
              <n-text>库存: {{ row.stock_after ?? "-" }}</n-text>
              <n-button size="small" tertiary :loading="row.undoing" @click="undoScan(row)">撤回</n-button>
            </n-space>

            <n-space v-if="row.editable_name" style="margin-top: 8px">
              <n-input v-model:value="row.draft_name" placeholder="请输入该编码的产品名" />
              <n-button size="small" type="primary" :loading="row.saving" @click="saveScannedNewItem(row)">
                保存品名
              </n-button>
            </n-space>

            <n-text v-if="row.message" depth="3" style="display: block; margin-top: 8px">
              {{ row.message }}
            </n-text>
          </article>
        </section>
      </n-space>
    </n-modal>
  </main>
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NAlert,
  NButton,
  NDataTable,
  NDivider,
  NEmpty,
  NForm,
  NFormItem,
  NFormItemGi,
  NGrid,
  NH4,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  NSpin,
  NTag,
  NText,
  useMessage,
} from "naive-ui";

import http from "../api/http";
import { useAuthStore } from "../stores/auth";
import { useItemsStore } from "../stores/items";
import { useTablesStore } from "../stores/tables";
import { mediaUrl } from "../utils/media";

const router = useRouter();
const message = useMessage();
const authStore = useAuthStore();
const itemsStore = useItemsStore();
const tablesStore = useTablesStore();

const keyword = ref(itemsStore.filters.q || "");
const isMobile = ref(window.innerWidth < 960);

const stockModal = reactive({
  show: false,
  submitting: false,
  type: "in",
  title: "入库",
  form: {
    code: "",
    name: "",
    quantity: 1,
  },
});

const scanner = reactive({
  show: false,
  tableId: "",
  mode: "in",
  scanText: "",
  seenLines: 0,
  processing: false,
  queue: [],
  records: [],
});
const quickUploadInput = ref(null);
const quickUploadTargetItemId = ref("");

const scanModeOptions = [
  { label: "扫码入库", value: "in" },
  { label: "扫码出库", value: "out" },
];

const tableOptions = computed(() =>
  tablesStore.tables.map((table) => ({ label: table.name, value: table.id }))
);

const activeSchemaFields = computed(() => {
  const fields = tablesStore.activeTable?.schema?.fields;
  return Array.isArray(fields) ? fields : [];
});

function onResize() {
  isMobile.value = window.innerWidth < 960;
}

async function refresh() {
  if (!tablesStore.activeTableId) {
    itemsStore.items = [];
    return;
  }
  itemsStore.setFilters({ table_id: tablesStore.activeTableId });
  try {
    await itemsStore.fetchItems();
  } catch (error) {
    message.error(error?.response?.data?.detail || "刷新失败");
  }
}

async function applyFilters() {
  itemsStore.setFilters({
    table_id: tablesStore.activeTableId,
    q: keyword.value.trim(),
  });
  await refresh();
}

async function resetFilters() {
  keyword.value = "";
  itemsStore.setFilters({
    table_id: tablesStore.activeTableId,
    q: "",
    code: "",
    min_quantity: null,
    max_quantity: null,
  });
  await refresh();
}

async function onSwitchTable(tableId) {
  tablesStore.setActiveTable(tableId);
  await refresh();
}

function openStockModal(type, item = null) {
  stockModal.type = type;
  stockModal.title = type === "in" ? "入库" : "出库";
  stockModal.form.code = item?.code || "";
  stockModal.form.name = item?.name || "";
  stockModal.form.quantity = 1;
  stockModal.show = true;
}

async function submitStock() {
  if (!tablesStore.activeTableId) {
    message.warning("请先选择表格");
    return;
  }

  const code = String(stockModal.form.code || "").trim();
  const quantity = Number(stockModal.form.quantity || 0);
  if (!code) {
    message.warning("请填写编码");
    return;
  }
  if (quantity <= 0) {
    message.warning("数量必须大于 0");
    return;
  }

  stockModal.submitting = true;
  try {
    if (stockModal.type === "in") {
      await itemsStore.stockIn({
        table_id: tablesStore.activeTableId,
        code,
        name: stockModal.form.name?.trim() || null,
        quantity,
      });
      message.success("入库成功");
    } else {
      await itemsStore.stockOut({
        table_id: tablesStore.activeTableId,
        code,
        quantity,
      });
      message.success("出库成功");
    }
    stockModal.show = false;
  } catch (error) {
    message.error(error?.response?.data?.detail || "操作失败");
  } finally {
    stockModal.submitting = false;
  }
}

function openScannerModal() {
  scanner.show = true;
  scanner.tableId = scanner.tableId || tablesStore.activeTableId || tablesStore.tables[0]?.id || "";
  scanner.mode = "in";
  scanner.scanText = "";
  scanner.seenLines = 0;
  scanner.queue = [];
}

function clearScanRecords() {
  scanner.records = [];
}

function createScanRecord(payload) {
  return {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    created_at: new Date().toLocaleString(),
    code: payload.code,
    name: payload.name || "",
    action_label: payload.action_label,
    status: payload.status,
    stock_after: payload.stock_after ?? null,
    message: payload.message || "",
    item_id: payload.item_id || "",
    created_new: Boolean(payload.created_new),
    source_line_index: Number.isInteger(payload.source_line_index) ? payload.source_line_index : null,
    editable_name: Boolean(payload.editable_name),
    draft_name: payload.draft_name || "",
    saving: false,
    undoing: false,
    table_id: payload.table_id,
  };
}

async function findItemInTable(tableId, code) {
  const { data } = await http.get("/items", { params: { table_id: tableId, code } });
  if (Array.isArray(data) && data.length > 0) {
    return data[0];
  }
  return null;
}

function upsertListWhenActiveTable(updatedItem) {
  if (updatedItem?.table_id === tablesStore.activeTableId) {
    itemsStore.upsertItem(updatedItem);
  }
}

async function handleScanCode(task) {
  const code = String(task?.code || "").trim();
  const sourceLineIndex = Number.isInteger(task?.source_line_index) ? task.source_line_index : null;
  if (!code) {
    return;
  }

  if (!scanner.tableId) {
    scanner.records.unshift(
      createScanRecord({
        code,
        source_line_index: sourceLineIndex,
        table_id: scanner.tableId,
        action_label: scanner.mode === "in" ? "入库" : "出库",
        status: "失败",
        message: "请先选择库存表格",
      })
    );
    return;
  }

  const actionLabel = scanner.mode === "in" ? "入库" : "出库";

  if (scanner.mode === "in") {
    try {
      // BUG-12: 直接调用 stock/in，后端已处理"不存在则创建"，无需额外查询
      const { data } = await http.post("/stock/in", {
        table_id: scanner.tableId,
        code,
        quantity: 1,
      });
      upsertListWhenActiveTable(data);

      const isNewItem = data.quantity === 1;
      scanner.records.unshift(
        createScanRecord({
          code,
          name: data.name,
          item_id: data.id,
          created_new: isNewItem,
          source_line_index: sourceLineIndex,
          table_id: scanner.tableId,
          action_label: actionLabel,
          status: "成功",
          stock_after: data.quantity,
          message: isNewItem ? "新条目已按默认品名 NUM 入库，可在此处直接改名" : "自动入库完成",
          editable_name: isNewItem,
          draft_name: isNewItem ? (data.name || "") : "",
        })
      );
    } catch (error) {
      scanner.records.unshift(
        createScanRecord({
          code,
          source_line_index: sourceLineIndex,
          table_id: scanner.tableId,
          action_label: actionLabel,
          status: "失败",
          message: error?.response?.data?.detail || "入库失败",
        })
      );
    }
    return;
  }

  try {
    const { data } = await http.post("/stock/out", {
      table_id: scanner.tableId,
      code,
      quantity: 1,
    });
    upsertListWhenActiveTable(data);

    scanner.records.unshift(
      createScanRecord({
        code,
        name: data.name,
        item_id: data.id,
        created_new: false,
        source_line_index: sourceLineIndex,
        table_id: scanner.tableId,
        action_label: actionLabel,
        status: "成功",
        stock_after: data.quantity,
        message: "自动出库完成",
      })
    );
  } catch (error) {
    scanner.records.unshift(
      createScanRecord({
        code,
        source_line_index: sourceLineIndex,
        table_id: scanner.tableId,
        action_label: actionLabel,
        status: "失败",
        message: error?.response?.data?.detail || "出库失败",
      })
    );
  }
}

async function processScannerQueue() {
  if (scanner.processing) {
    return;
  }
  scanner.processing = true;

  try {
    while (scanner.queue.length > 0) {
      const task = scanner.queue.shift();
      if (!task) {
        continue;
      }
      await handleScanCode(task);
    }
  } finally {
    scanner.processing = false;
  }
}

function onScannerTextChange(nextValue) {
  const text = String(nextValue || "");
  scanner.scanText = text;

  const lines = text.split(/\r?\n/);
  const hasTrailingNewline = /\r?\n$/.test(text);
  let completeLines = lines.length - (hasTrailingNewline ? 0 : 1);
  if (completeLines < 0) {
    completeLines = 0;
  }

  if (completeLines < scanner.seenLines) {
    scanner.seenLines = completeLines;
    return;
  }

  for (let i = scanner.seenLines; i < completeLines; i += 1) {
    const code = String(lines[i] || "").trim();
    if (code) {
      scanner.queue.push({ code, source_line_index: i });
    }
  }

  scanner.seenLines = completeLines;
  processScannerQueue().catch(() => {});
}

function removeScanLineForRecord(row) {
  const lines = String(scanner.scanText || "").split(/\r?\n/);
  let removedIndex = -1;

  if (
    Number.isInteger(row.source_line_index) &&
    row.source_line_index >= 0 &&
    row.source_line_index < lines.length &&
    String(lines[row.source_line_index] || "").trim() === row.code
  ) {
    removedIndex = row.source_line_index;
  } else {
    for (let i = lines.length - 1; i >= 0; i -= 1) {
      if (String(lines[i] || "").trim() === row.code) {
        removedIndex = i;
        break;
      }
    }
  }

  if (removedIndex >= 0) {
    lines.splice(removedIndex, 1);
    for (const rec of scanner.records) {
      if (Number.isInteger(rec.source_line_index) && rec.source_line_index > removedIndex) {
        rec.source_line_index -= 1;
      }
    }
  }

  scanner.scanText = lines.join("\n");

  const hasTrailingNewline = /\r?\n$/.test(scanner.scanText);
  const currentLines = scanner.scanText.split(/\r?\n/);
  let completeLines = currentLines.length - (hasTrailingNewline ? 0 : 1);
  if (scanner.scanText.length === 0) {
    completeLines = 0;
  }
  scanner.seenLines = Math.max(0, completeLines);
}

function removeScanRecord(row) {
  const index = scanner.records.findIndex((x) => x.id === row.id);
  if (index >= 0) {
    scanner.records.splice(index, 1);
  }
}

async function undoScan(row) {
  if (row.undoing) {
    return;
  }
  row.undoing = true;
  try {
    if (row.status === "成功" && row.item_id) {
      const { data: current } = await http.get(`/items/${row.item_id}`);
      const currentQty = Number(current.quantity || 0);
      if (row.action_label === "入库") {
        if (row.created_new && currentQty <= 1) {
          await http.delete(`/items/${row.item_id}`);
          if (current.table_id === tablesStore.activeTableId) {
            itemsStore.items = itemsStore.items.filter((x) => x.id !== row.item_id);
          }
        } else {
          const nextQty = Math.max(0, currentQty - 1);
          const { data } = await http.patch(`/items/${row.item_id}`, { quantity: nextQty });
          upsertListWhenActiveTable(data);
        }
      } else if (row.action_label === "出库") {
        const { data } = await http.patch(`/items/${row.item_id}`, { quantity: currentQty + 1 });
        upsertListWhenActiveTable(data);
      }
    }

    removeScanLineForRecord(row);
    removeScanRecord(row);
    message.success("已撤回该次扫码");
  } catch (error) {
    message.error(error?.response?.data?.detail || "撤回失败");
  } finally {
    row.undoing = false;
  }
}

async function saveScannedNewItem(row) {
  const name = String(row.draft_name || "").trim();
  if (!name) {
    message.warning("请输入产品名");
    return;
  }

  row.saving = true;
  try {
    if (!row.item_id) {
      row.message = "未找到物料ID，无法改名";
      row.status = "失败";
      return;
    }
    const { data } = await http.patch(`/items/${row.item_id}`, { name });
    upsertListWhenActiveTable(data);

    row.editable_name = false;
    row.name = data.name;
    row.status = "成功";
    row.stock_after = data.quantity;
    row.message = "名称修改成功";
    row.draft_name = "";
  } catch (error) {
    row.message = error?.response?.data?.detail || "名称修改失败";
    row.status = "失败";
  } finally {
    row.saving = false;
  }
}

function goDetail(itemId) {
  router.push(`/items/${itemId}`);
}

function openQuickUpload(item) {
  quickUploadTargetItemId.value = item?.id || "";
  if (!quickUploadTargetItemId.value || !quickUploadInput.value) {
    return;
  }
  quickUploadInput.value.value = "";
  quickUploadInput.value.click();
}

async function onQuickUploadChange(event) {
  const itemId = quickUploadTargetItemId.value;
  quickUploadTargetItemId.value = "";
  const file = event?.target?.files?.[0];
  if (!itemId || !file) {
    return;
  }

  try {
    const upload = await itemsStore.uploadImage(file);
    await itemsStore.updateItemOptimistic(itemId, {
      image_original: upload.original_path,
      image_thumb: upload.thumb_path,
    });
    message.success("缩略图上传成功");
  } catch (error) {
    message.error(error?.response?.data?.detail || "缩略图上传失败");
  }
}

function goSettings() {
  router.push("/settings");
}

function logout() {
  itemsStore.stopPolling();
  authStore.logout();
  router.replace("/login");
}

const columns = computed(() => {
  const dynamicColumns = activeSchemaFields.value.map((field) => ({
    title: field.label || field.key,
    key: `prop_${field.key}`,
    minWidth: 120,
    render: (row) => row.properties?.[field.key] ?? "-",
  }));

  return [
    {
      title: "缩略图",
      key: "image_thumb",
      width: 90,
      render(row) {
        if (!row.image_thumb) {
          return h(
            NButton,
            { size: "tiny", tertiary: true, onClick: () => openQuickUpload(row) },
            { default: () => "上传缩略图" }
          );
        }
        return h("img", {
          src: mediaUrl(row.image_thumb),
          class: "list-thumb",
          alt: "缩略图",
          title: "点击更换缩略图",
          style: "cursor: pointer",
          onClick: () => openQuickUpload(row),
        });
      },
    },
    { title: "名称", key: "name", minWidth: 140 },
    { title: "编码", key: "code", minWidth: 140 },
    ...dynamicColumns,
    { title: "库存", key: "quantity", width: 90 },
    {
      title: "操作",
      key: "actions",
      width: 250,
      render(row) {
        return h(NSpace, null, {
          default: () => [
            h(
              NButton,
              { size: "tiny", type: "primary", onClick: () => openStockModal("in", row) },
              { default: () => "入库" }
            ),
            h(
              NButton,
              { size: "tiny", type: "warning", onClick: () => openStockModal("out", row) },
              { default: () => "出库" }
            ),
            h(
              NButton,
              { size: "tiny", secondary: true, onClick: () => goDetail(row.id) },
              { default: () => "编辑" }
            ),
          ],
        });
      },
    },
  ];
});

onMounted(async () => {
  window.addEventListener("resize", onResize);
  try {
    await tablesStore.fetchTables();
    await refresh();
  } catch (error) {
    message.error(error?.response?.data?.detail || "加载失败");
  }
  itemsStore.startPolling();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", onResize);
  itemsStore.stopPolling();
});
</script>
