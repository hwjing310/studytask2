# 部署手册（CampusEvent）

## 1. 目标形态

单进程单端口：后端（Python 标准库）同时提供 JSON API 与前端静态文件（`frontend/dist`）。
对外只需要 **80 端口 + 一个域名/子域名**，不依赖 Nginx、Node 或数据库服务。

```
浏览器 ──► http(s)://<host>/            → dist/index.html
        └► http(s)://<host>/api/...     → Python 后端 → SQLite
```

## 2. 平台选择

| 方案 | 可行性 | 说明 |
|---|---|---|
| **thevibehosting.com（推荐）** | ✅ | 免费 root Ubuntu 容器 + 自动 HTTPS 子域名，一条 `curl` 创建，支持长期运行与自定义域名 |
| 云厂商 VPS（阿里云/腾讯云） | ✅ | 需要自己装系统、配 Nginx、申请证书；成本更高 |
| 共享主机 / 纯静态托管 | ❌ | 只支持 PHP/静态文件，跑不了常驻 Python 进程 |

> 本项目后端零第三方依赖，任何有 Python 3.8+ 的 Linux 主机都能跑。

## 3. 本地准备

```bat
cd frontend
npm install
npm run build            :: 产出 frontend/dist

cd ..
tools\py.cmd tools\package.py   :: 产出 build/CampusEvent-deploy.zip
```

打包内容：`project/`、`frontend/dist/`、`run.py`、`tests/`、`docs/`、`README.md`、`requirements.txt`。
排除：`.git/`、`frontend/node_modules/`、`tools/python312/`、`project/data/*.db*`。

## 4. 在 thevibehosting 上创建服务器

```bash
curl -sX POST https://thevibehosting.com/create
```

返回三段信息，务必保存：

| 字段 | 用途 |
|---|---|
| `ssh`（如 `ssh root@1.2.3.4 -p 2222`） | 登录服务器 |
| `url`（如 `https://abc123.thevibehosting.com`） | 公网访问地址（自动 HTTPS） |
| `api_key`（`vibe_…`） | 账号凭证，用于管理/删除服务器 |

> 免费额度：匿名 256 MB（空闲休眠）；手机验证后 512 MB 且可常驻。本项目内存占用 < 60 MB，256 MB 足够。

## 5. 上传与启动

```bash
# 1) 上传（在本地执行）
scp -P <port> build/CampusEvent-deploy.zip root@<host>:/root/

# 2) 解压
ssh -p <port> root@<host>
apt-get update && apt-get install -y unzip python3   # Ubuntu 通常自带 python3
mkdir -p /root/app && cd /root/app
unzip -o /root/CampusEvent-deploy.zip

# 3) 启动脚本
cat > /root/run.sh <<'EOF'
#!/bin/sh
cd /root/app
exec python3 run.py --port 80 --db /root/app/project/data/campusevent.db
EOF
chmod +x /root/run.sh

# 4) 前台试跑（确认无报错后 Ctrl+C）
/root/run.sh
```

平台约定：`/root/run.sh` 会被自动拉起并监听 80 端口；崩溃后自动重启。
若平台未自动拉起，用 `nohup /root/run.sh > /root/app.log 2>&1 &` 常驻。

## 6. 验证

```bash
curl -s http://127.0.0.1/api/health        # {"status":"ok",...}
curl -s https://<subdomain>/api/health     # 公网
curl -s https://<subdomain>/               # 前端 index.html
```

浏览器打开公网地址，用 `admin / admin123` 登录，依次验证：
创建活动 → 学生报名 → 审批 → 站内消息 → 统计；再验证候补（容量 1 + 候补 1）与自动补位。

## 7. 数据与备份

- 数据库文件：`/root/app/project/data/campusevent.db`，随容器磁盘持久化（休眠/重启不丢）。
- 备份：`scp root@<host>:/root/app/project/data/campusevent.db ./backup.db`
- 重置演示数据：删除该文件后重启，首次启动会自动建表并写入种子数据。

## 8. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 502 / 页面打不开 | 进程未监听 80 或被平台休眠 | `curl 127.0.0.1/api/health`；唤醒需 1–3 s |
| `/api/health` 正常但页面 404 | 未上传 `frontend/dist` | 重新执行 `npm run build` 后打包上传 |
| 中文变问号 | 数据库被其它编码覆盖 | 删除 db 重新种子化（演示数据） |
| SQLite `database is locked` | 多进程同时写 | 确保只跑一个实例 |

## 9. 回滚

平台提供 REST 管理接口（用 `api_key`）：

```bash
curl -s -H "Authorization: Bearer vibe_xxx" https://thevibehosting.com/servers
curl -s -X DELETE -H "Authorization: Bearer vibe_xxx" https://thevibehosting.com/servers/<id>
```

本项目自身回滚：`git switch change-v2` 或 `git switch baseline-v1`，重新构建上传即可。

---

## 10. 本次部署记录（2026-11-19）

| 项 | 值 |
|---|---|
| 平台 | thevibehosting.com（匿名免费实例） |
| 公网地址 | **https://campusevent.thevibehosting.com** |
| 服务器 ID | `srv_be23a78f64` |
| 主机 / 端口 | `root@46.225.188.115 -p 51570` |
| 应用目录 | `/root/app`（zip 解压，59 个文件） |
| 启动方式 | `/root/run.sh` → `python3 run.py --port 80 --db /root/app/project/data/campusevent.db` |
| 磁盘占用 | 约 1.2 MB（代码 + dist + 初始数据库） |

**已验证（公网）**

| 检查 | 结果 |
|---|---|
| `GET /api/health` | 200 `{"status":"ok"}` |
| `GET /` | 200，返回构建后的 `index.html` |
| `POST /api/login`（admin） | 200，角色 ADMIN |
| `GET /api/activities` | 200，2 条种子活动 |
| 候补全流程 | 报名占满 → 第二人 `WAITLISTED(1)` → 取消 → 自动补位 `APPROVED` → 统计 `approved=1, waitlisted=0` |
| 重启/重置 | 删除 db 后进程自动重启并重新种子化，健康检查恢复 |

**凭据存放**

- `api_key`、`ssh_private_key`、`create.json` 保存在**本仓库外**的 `H:\temp\studytask2\.vibe\`（已加入 `.gitignore`，不会提交）。
- 丢失 `api_key` 且未验证手机/邮箱时无法找回，请自行备份。

**日常运维**

```bash
# 查看服务器
curl -s -H "Authorization: Bearer <api_key>" https://thevibehosting.com/servers
# 休眠 / 唤醒
curl -s -X POST -H "Authorization: Bearer <api_key>" https://thevibehosting.com/servers/srv_be23a78f64/sleep
# 删除（数据一并删除）
curl -s -X DELETE -H "Authorization: Bearer <api_key>" https://thevibehosting.com/servers/srv_be23a78f64
```

**更新代码**

```bash
# 本地重新构建 + 打包后
scp -i .vibe/key -P 51570 build/CampusEvent-deploy-*.zip root@46.225.188.115:/root/
ssh -i .vibe/key -p 51570 root@46.225.188.115 "cd /root/app && python3 -m zipfile -e /root/CampusEvent-deploy-*.zip . && kill -9 \$(pgrep -f '[r]un.py')"
```

> 说明：该实例为**匿名免费**档（256 MB、空闲休眠）。首次访问可能冷启动 1–3 秒；如需常驻，可用手机验证后开启 `never_sleep`。
