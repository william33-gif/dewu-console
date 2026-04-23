# 得物自动发布控制台

基于你给的 MVP 清单，当前目录已经搭出一套可以继续迭代的第一版工程骨架：

- `backend/`: `FastAPI + SQLAlchemy` API，负责任务、素材批次、账号设备、运行日志，以及发布触发接口。
- `frontend/`: `Next.js` 控制台页面，包含任务列表、任务详情、素材批次、账号设备、运行日志。
- `test_dewu.py`: 现有的 Appium 发布脚本，已经被后端发布接口接入。
- `infra/schema.sql`: PostgreSQL 初始化表结构。
- `docker-compose.yml`: 本地 PostgreSQL 启动配置。

## 目录结构

```text
backend/
  app/
    api/
    core/
    services/
  worker.py
frontend/
  app/
  components/
  lib/
infra/
  schema.sql
test_dewu.py
```

## 先启动数据库

```bash
docker compose up -d
```

这会启动一个本地 PostgreSQL：

- database: `dewu_console`
- user: `postgres`
- password: `postgres`
- port: `5432`

## 启动后端 API

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

可用接口：

- `GET /health`
- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `PATCH /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/approve`
- `POST /api/tasks/{task_id}/retry`
- `POST /api/tasks/{task_id}/publish`
- `GET /api/material-batches`
- `POST /api/material-batches`
- `GET /api/account-devices`
- `POST /api/account-devices`
- `PATCH /api/account-devices/{device_id}`
- `GET /api/publish-logs`
- `POST /api/feishu/sync`

## 启动前端控制台

```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:3000/tasks
```

## 当前发布链路

前端点击“开始发布”后：

1. 后端把任务写成 `publishing`
2. 记录运行日志
3. 调起根目录的 `test_dewu.py`
4. 成功则回写 `published`
5. 失败则回写 `failed` 和错误日志

## 当前这版已经覆盖的 MVP

- 任务列表页
- 任务详情页
- 素材批次页
- 账号设备页
- 运行日志页
- PostgreSQL 表结构
- 发布 API
- Worker 轮询入口
- Appium 脚本接入点
- 飞书多维表格同步入口

## 飞书多维表格同步

后端支持从飞书多维表格拉取记录，并把附件字段里的前 4 张图片下载到本地，再自动生成素材批次和发布任务。

需要在 `backend/.env` 中配置：

```text
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_APP_TOKEN=
FEISHU_TABLE_ID=
FEISHU_VIEW_ID=
MATERIAL_STORAGE_DIR=storage/materials
```

同步接口：

```bash
POST /api/feishu/sync
```

同步行为：

1. 读取指定视图中的多维表格记录
2. 下载 `素材` 附件字段中的前 4 张图到本地
3. 创建本地 `material_batches`
4. 创建本地 `publish_tasks`
5. 若本地已存在同一条飞书记录生成的任务，则自动跳过

## 下一步最值得继续补的点

- 把 `test_dewu.py` 改成可接收任务参数，而不是固定坐标脚本
- 增加素材上传和任务编辑表单
- 给任务详情页补“推图到手机”和“重新发布”按钮
- 把发布结果截图真正落盘并回写路径
- 增加设备心跳与在线检测
