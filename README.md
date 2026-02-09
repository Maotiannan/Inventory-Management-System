# 进销存系统（ZNAS）

基于 `FastAPI + PostgreSQL(JSONB) + Vue3 + Naive UI + Docker Compose` 的 NAS 进销存系统。

- 前端：`http://<NAS_IP>:8080`
- 后端：`http://<NAS_IP>:8000`
- OpenAPI：`http://<NAS_IP>:8000/docs`

## 一、当前生产特性

- 纯镜像运行：后端/前端代码完全构建进镜像，运行时不依赖源码挂载。
- 持久化数据：数据库、图片、运维数据均使用 Docker Volume。
- 健康检查：`postgres / backend / frontend` 均带 healthcheck。
- 多表格与动态字段：同库多表，每表字段可独立配置。
- API 集成：JWT + API Key。
- 审计日志：记录账号或 API Key 调用来源。
- 系统运维（管理员）：仓库配置、检查更新、一键更新、精确回滚、Tailscale 配置。

## 二、部署步骤（NAS）

### 1. 准备环境

- NAS 已安装 Docker 与 Docker Compose v2。
- 项目目录例如：`/volume1/docker/znas`。

### 2. 配置环境变量

```bash
cp .env.production.example .env
```

编辑 `.env`，至少修改：

```env
POSTGRES_PASSWORD=强密码
JWT_SECRET_KEY=高熵随机字符串
ADMIN_PASSWORD=强密码
REPO_URL=https://github.com/<你的账号>/<仓库>.git
```

### 3. 启动

```bash
docker compose up -d --build
```

### 4. 检查

```bash
docker compose ps
docker compose logs -f backend
```

## 三、为什么会提示“未配置 origin 远程仓库”

这是因为系统运维的“检查更新/一键更新/回滚”需要 Git 远程仓库来源。

处理方式有两种：

1. 网页方式（推荐）

- 进入：`系统设置 -> 系统运维 -> 仓库配置`
- 填写 `REPO_URL`（例如 GitHub 仓库地址）和分支（默认 `main`）
- 点击“保存并初始化仓库”

2. 命令行方式

```bash
git remote add origin https://github.com/<you>/<repo>.git
git fetch origin
```

## 四、手机上传图片失败的修复说明

已修复两类常见原因：

- Nginx 上传体积限制：已将 `client_max_body_size` 提升到 `30m`。
- iPhone 常见 `HEIC/HEIF`：后端已增加该格式解析支持（`pillow-heif`）。

## 五、国内源优化

已切换可切换的国内源：

- Python：`PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`
- apt：`mirrors.aliyun.com`
- npm：`https://registry.npmmirror.com`
- 基础镜像：已使用国内镜像前缀（`swr.cn-north-4...`）

## 六、生产编排说明

`docker-compose.yml` 已改为生产运行模式：

- 去除开发期源码挂载和热重载。
- 通过 `APP_VERSION`、`BACKEND_IMAGE`、`FRONTEND_IMAGE` 管理镜像版本。
- 使用命名卷：
  - `db_data`
  - `images_data`
  - `ops_data`
  - `ts_state_data`

## 七、版本管理（管理员）

入口：`系统设置 -> 系统运维`

支持：

- 仓库配置（REPO_URL/分支）
- 检查更新
- 一键更新并重启
- 查看 tag 和提交历史
- 输入 tag/commit 执行精确回滚

说明：回滚与更新执行日志写入 `ops_data` 内日志文件（`update_web.log` / `rollback_web.log`）。

## 八、API 能力概览

鉴权方式：

- `Authorization: Bearer <token>`
- `X-API-Key: <api_key>`

系统关键接口：

- 认证：`POST /auth/login`、`GET /auth/validate`
- 账号：`GET/POST/DELETE /users`
- 表格：`GET/POST/PATCH/DELETE /tables`
- 字段：`GET/PUT/POST /config/schema`
- 物料：`GET/POST/PATCH/DELETE /items`
- 库存：`POST /stock/in`、`POST /stock/out`
- 上传：`POST /upload`
- 日志与 API Key：`/integration/*`
- 系统运维（管理员）：`/system/*`

## 九、模块化更新规范

后续功能开发请遵循：

- 文档：`docs/MODULE_UPDATE_SPEC.md`

该规范包含：模块边界、API 约束、数据迁移、发布与回滚流程、准入检查清单。

## 十、常用命令

启动：

```bash
docker compose up -d
```

重建：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
```

手动更新：

```bash
bash scripts/nas_update.sh
```

手动回滚：

```bash
bash scripts/nas_rollback.sh <tag-or-commit>
```
