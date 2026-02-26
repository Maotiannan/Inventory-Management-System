# 进销存系统

基于 `FastAPI + PostgreSQL + Vue3 + Naive UI + Docker Compose` 的 NAS/MACMINI 生产部署版进销存系统。

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
  - 检查更新（含版本提交时间）
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

## 3. 日常维护

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

- `检查更新`：显示当前分支、当前版本（短哈希+提交时间）、远端版本、状态
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

## 6. NAS 网络问题排查

### 6.1 HTTPS 方式 TLS 失败

NAS（ZOS 定制 Linux）环境中 `git fetch` 可能报错：

```
gnutls_handshake() failed: Error in the pull function.
```

**原因**：NAS 的 Git 2.34.1 使用的 GnuTLS 与 GitHub TLS 存在兼容性问题，加上 NAS 用户 `$HOME` 被错误设置为 `/home/`，导致 HTTPS 认证不稳定。

**解决方案**：改用 SSH 方式访问 GitHub。

```bash
# 1. 切换到 root 用户，生成 SSH key
sudo su -
ssh-keygen -t ed25519 -C "znas-root"

# 2. 将公钥添加到 GitHub 账户
cat /root/.ssh/id_ed25519.pub

# 3. 验证 SSH 连接
ssh -T git@github.com

# 4. 修改仓库远程地址为 SSH
cd /tmp/zfsv3/nvme11/.../data/docker/ZNAS
git remote set-url origin git@github.com:Maotiannan/Inventory-Management-System.git

# 5. 验证拉取
git fetch --all --prune
```

### 6.2 HTTPS 临时修复（不推荐）

```bash
git config --local http.version HTTP/1.1
git remote set-url origin https://github.com/Maotiannan/Inventory-Management-System.git
git fetch --all --prune
```

### 6.3 修复容器内运维仓库源

```bash
sudo docker exec znas-backend sh -c '\
  git -C /data/ops/repo remote set-url origin https://github.com/Maotiannan/Inventory-Management-System.git && \
  git -C /data/ops/repo config http.version HTTP/1.1 && \
  echo "{\"repo_url\":\"https://github.com/Maotiannan/Inventory-Management-System.git\",\"branch\":\"main\"}" > /data/ops/repo_config.json'
COMPOSE_PROJECT_NAME=znas sudo -E docker compose restart backend
```

### 6.4 部署架构

```
NAS (ZOS 系统)
└── root 用户
    └── /root/.ssh/id_ed25519 (GitHub SSH 认证)
        └── 项目目录 (/tmp/zfsv3/.../ZNAS)
            └── Docker Compose 部署
                ├── znas-postgres
                ├── znas-backend
                ├── znas-frontend
                └── tailscale (可选)
```

## 7. API 概览

鉴权方式：

- `Authorization: Bearer <token>`
- `X-API-Key: <api_key>`

核心接口：

| 模块 | 接口 |
|------|------|
| 认证 | `POST /auth/login`、`GET /auth/validate` |
| 用户 | `GET/POST/DELETE /users` |
| 表格 | `GET/POST/PATCH/DELETE /tables` |
| 物料 | `GET/POST/PATCH/DELETE /items` |
| 出入库 | `POST /stock/in`、`POST /stock/out` |
| 上传 | `POST /upload` |
| 系统运维 | `GET /system/update/status`、`POST /system/update/apply` |
| 版本管理 | `GET /system/version/state`、`GET /system/version/history`、`GET /system/version/tags` |
| 回滚 | `POST /system/version/rollback`、`POST /system/version/rollback/latest` |

## 8. 版本命名规则

项目根目录下的 `VERSION` 文件记录当前版本号，格式为 `V<major>.<minor>.<patch>`，网页端底部同步显示。

### 8.1 版本递增规则

| 级别 | 触发条件 | 示例 |
|------|----------|------|
| patch +0.0.1 | 每次提交到 `main` 分支 | V1.0.0 → V1.0.1 |
| minor +0.1.0 | patch 累计满 10 次（即 x.x.9 → x.x+1.0） | V1.0.9 → V1.1.0 |
| major +1.0.0 | minor 累计满 100 次（即 x.99.x → x+1.0.0） | V1.99.9 → V2.0.0 |

### 8.2 版本更新流程

1. 修改代码并自测
2. 修改 `VERSION` 文件中的版本号（按上述规则递增）
3. commit 并 push 到 `main`
4. NAS 网页端点击 `一键更新并重启`

### 8.3 版本显示

- 后端提供 `GET /version` 接口，读取 `VERSION` 文件内容
- 前端所有页面底部显示 `ZNAS V<x.y.z>`
- 系统运维页面的「检查更新」显示当前/远端版本的短哈希、提交时间、提交摘要

## 9. 模块化开发规范

模块开发请遵循：`docs/MODULE_UPDATE_SPEC.md`

- 每个模块必须有清晰 API
- 迁移脚本可回滚
- 变更可灰度/可回退
- 发布前有最小回归检查

## 10. 常用命令速查

```bash
# 启动
COMPOSE_PROJECT_NAME=znas docker compose up -d

# 重建
COMPOSE_PROJECT_NAME=znas docker compose up -d --build

# 状态
COMPOSE_PROJECT_NAME=znas docker compose ps

# 后端日志
docker logs -f znas-backend

# 前端日志
docker logs -f znas-frontend
```

