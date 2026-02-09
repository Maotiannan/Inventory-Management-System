# 进销存系统（ZNAS）

基于 `FastAPI + PostgreSQL + Vue3 + Naive UI + Docker Compose` 的 NAS 生产部署版进销存系统。

- 前端：`http://<NAS_IP>:<FRONTEND_PORT>`（默认 `8080`，可在 `.env` 中配置）
- 后端：`http://<NAS_IP>:8000`
- OpenAPI：`http://<NAS_IP>:8000/docs`

## 1. 当前版本能力

- 生产模式镜像部署（无源码热重载）
- 数据持久化：`db_data`、`images_data`、`ops_data`、`ts_state_data`
- 多表格、多字段配置（同库不同表各自字段）
- 账号密码登录 + API Key
- 人类可读操作日志（区分账号与 API Key）
- 系统运维（管理员）：
  - 仓库配置
  - 检查更新
  - 一键更新并重启
  - 精确回滚（最近版本下拉）
  - 滚回最新版（一键回到 `origin/<branch>`）
  - Tailscale 配置

## 2. 首次部署（NAS）

### 2.1 准备

- NAS 已安装 Docker + Docker Compose v2
- 项目目录示例：`/tmp/zfsv3/nvme11/.../data/docker/ZNAS`

### 2.2 拉取代码

```bash
git clone https://github.com/Maotiannan/Inventory-Management-System.git ZNAS
cd ZNAS
```

### 2.3 环境变量

```bash
cp .env.production.example .env
```

编辑 `.env`，至少修改：

```env
POSTGRES_PASSWORD=<强密码>
JWT_SECRET_KEY=<长随机串>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<强密码>
FRONTEND_PORT=18080
REPO_URL=https://github.com/Maotiannan/Inventory-Management-System.git
UPDATE_BRANCH=main
```

### 2.4 启动

```bash
COMPOSE_PROJECT_NAME=znas docker compose up -d --build
```

### 2.5 验证

```bash
COMPOSE_PROJECT_NAME=znas docker compose ps
docker logs --tail=100 znas-backend
```

## 3. 日常维护（你问的“新设备怎么维护”）

答案是：**是的，推荐这样做**。

标准流程：

1. 在新电脑 clone 仓库
2. 本地改代码并自测
3. push 到 GitHub `main`
4. 在 NAS 网页端点 `一键更新并重启`
5. 等待后端和前端健康后刷新页面

新设备最小命令：

```bash
git clone https://github.com/Maotiannan/Inventory-Management-System.git
cd Inventory-Management-System
# 修改代码后
# git add ...
# git commit -m "feat/fix: ..."
git push origin main
```

## 4. 网页端更新与回滚

入口：`设置 -> 系统运维`

### 4.1 项目更新

- `检查更新`：显示当前分支、当前版本、远端版本、状态
- `一键更新并重启`：后台执行 `scripts/nas_update.sh`

### 4.2 精确回滚

- 下拉框可选最近版本（远端最新版 / 当前版本 / Tags / 最近提交）
- 选择后点 `执行回滚`
- 或点 `滚回最新版` 直接回到远端分支最新提交

对应脚本：

- `scripts/nas_update.sh`
- `scripts/nas_rollback.sh`

运维日志：

- `ops_data/update_web.log`
- `ops_data/rollback_web.log`

## 5. 若网页更新失败，命令行兜底

### 5.1 手动更新

```bash
cd /tmp/zfsv3/nvme11/.../data/docker/ZNAS
git fetch --all --prune
git reset --hard origin/main
COMPOSE_PROJECT_NAME=znas sudo -E docker compose up -d --build backend frontend
```

### 5.2 手动回滚

```bash
cd /tmp/zfsv3/nvme11/.../data/docker/ZNAS
bash scripts/nas_rollback.sh <tag-or-commit>
```

### 5.3 回到最新版

```bash
cd /tmp/zfsv3/nvme11/.../data/docker/ZNAS
bash scripts/nas_rollback.sh origin/main
```

## 6. Git 网络不稳定（TLS/超时）处理

如果 NAS `git fetch` 偶发失败：

```bash
git config --local http.version HTTP/1.1
git remote set-url origin https://github.com/Maotiannan/Inventory-Management-System.git
git fetch --all --prune
```

如果网页端运维仓库源错误，修复：

```bash
sudo docker exec znas-backend sh -lc 'git -C /data/ops/repo remote set-url origin https://github.com/Maotiannan/Inventory-Management-System.git; git -C /data/ops/repo config http.version HTTP/1.1; printf "%s\n" "{""repo_url"":""https://github.com/Maotiannan/Inventory-Management-System.git"",""branch"":""main""}" > /data/ops/repo_config.json'
COMPOSE_PROJECT_NAME=znas sudo -E docker compose restart backend
```

## 7. API 概览

鉴权方式：

- `Authorization: Bearer <token>`
- `X-API-Key: <api_key>`

核心接口：

- 认证：`POST /auth/login`、`GET /auth/validate`
- 用户：`GET/POST/DELETE /users`
- 表格：`GET/POST/PATCH/DELETE /tables`
- 物料：`GET/POST/PATCH/DELETE /items`
- 出入库：`POST /stock/in`、`POST /stock/out`
- 上传：`POST /upload`
- 系统运维（管理员）：
  - `GET /system/update/status`
  - `POST /system/update/apply`
  - `GET /system/version/state`
  - `GET /system/version/history`
  - `GET /system/version/tags`
  - `POST /system/version/rollback`
  - `POST /system/version/rollback/latest`

## 8. 模块化开发规范

模块开发请遵循：`docs/MODULE_UPDATE_SPEC.md`

重点：

- 每个模块必须有清晰 API
- 迁移脚本可回滚
- 变更可灰度/可回退
- 发布前有最小回归检查

## 9. 常用命令速查

```bash
# 启动
COMPOSE_PROJECT_NAME=znas docker compose up -d

# 重建
COMPOSE_PROJECT_NAME=znas docker compose up -d --build

# 状态
COMPOSE_PROJECT_NAME=znas docker compose ps

# 后端日志
docker logs -f znas-backend
```
