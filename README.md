# image-lossless-tool

一个轻量的图片处理小工具，支持：

- 无损压缩（尽量减小体积，不降低画质）
- 图片格式转换（优先使用无损策略）
- 桌面图形界面（GUI）一键执行
- Web 页面（浏览器使用）

### 最优方案（已替你选定）

| 用途 | 选择 | 原因 |
|------|------|------|
| 代码托管与 CI | **GitHub** | 协作、历史、Actions 一体 |
| 公网访问（算力在云端） | **Fly.io** | 与现有 `Dockerfile` / `fly.toml` 直接配套，**自动 HTTPS**，小流量可休眠省资源 |
| 自动上线 | **push 到 `main`** → 工作流 `Deploy to Fly.io` | 改完即发布（需按下方打开开关） |
| 镜像备份 / 国内机拉镜像 | **GHCR**（`docker-ghcr.yml`） | 同一推送顺带构建，**可选用** |

**本地自己用**（不对外）：继续 `python web_app.py` 或双击 `start_web.command` 即可，不必上云。

开启 **Fly 自动部署** 需要同时在 GitHub 配置：

1. **Settings → Secrets and variables → Actions → Variables**：新建 `ENABLE_FLY_DEPLOY`，值填 **`true`**  
2. **Secrets**：新建 `FLY_API_TOKEN`（本机安装 [flyctl](https://fly.io/docs/hands-on/install-flyctl/) 后执行 `fly auth token`）

未配置时，推送不会跑 Fly 部署，避免 Actions 无故失败；需要时可在 Actions 里 **手动运行** `Deploy to Fly.io`。

## 1. 安装

```bash
cd image-lossless-tool
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 如果你希望对 JPEG 做真正的无损优化，建议安装 `jpegtran`（macOS 可用 `brew install jpeg-turbo`）。

## 2. 用法

### 2.1 无损压缩

```bash
python image_tool.py compress --input ./input_images --output ./output_images --recursive
```

常用参数：

- `--recursive`：递归处理子目录
- `--overwrite`：覆盖已存在的输出文件
- `--keep-when-larger`：即使压缩后更大也保留结果（默认会回退为原图）

### 2.2 格式转换

示例：转为 PNG（无损）

```bash
python image_tool.py convert --input ./input_images --output ./converted --to png --recursive
```

示例：转为 WebP（无损 WebP）

```bash
python image_tool.py convert --input ./input_images --output ./converted --to webp --recursive
```

示例：转为 JPEG（有损，需显式允许）

```bash
python image_tool.py convert --input ./input_images --output ./converted --to jpeg --allow-lossy
```

### 2.3 图形界面（GUI）

```bash
python image_tool_gui.py
```

macOS 双击启动（推荐）：

- 双击 `start_gui.command`
- 或终端执行 `./start_gui.command`

GUI 功能：

- 选择输入文件/文件夹和输出文件夹
- 选择模式（无损压缩 / 格式转换）
- 可选递归处理与覆盖输出
- 日志窗口展示执行结果
- 支持拖拽文件/文件夹到 Input、Output 输入框
- 支持一次选择或拖拽多个文件（批量模式）
- 根据输入类型自动推荐参数（单文件默认关闭递归，文件夹默认开启递归）

### 2.4 Web 端（浏览器）

启动：

```bash
python web_app.py
```

或 macOS 双击启动：

- 双击 `start_web.command`

打开浏览器访问：

- `http://127.0.0.1:5000`

#### 局域网分享给同事（同一 Wi‑Fi）

1. 在本机终端执行，或 macOS **双击** `start_web_share.command`。
2. 终端会打印形如 `http://192.168.x.x:5000/` 的地址，发给同事用浏览器打开即可。

也可手动指定端口：

```bash
export IMG_TOOL_HOST=0.0.0.0
export IMG_TOOL_PORT=5000
python web_app.py
```

说明：图片在**运行服务的这台电脑**上处理；同事通过网页上传/下载。  
「选择文件夹」「自动打开目录」等系统对话框只在**服务器本机**弹出，远程同事请用「下载 ZIP」或手动填路径（若你为他们配置了可写目录）。

Web 功能：

- 多图上传
- 无损压缩 / 格式转换
- 可控输出体积（目标 KB，最佳努力）
- 支持输出到指定文件夹（路径可选，留空使用默认目录）
- 支持“输出到本机默认目录”选项
- 达不到目标体积时可启用“允许质量损失”
- 目标体积提供 200KB 递进快捷选项
- 上传缩略图预览墙
- 上传/处理/下载进度条
- 主题色和品牌文案可配置（环境变量）

CLI 也支持目标体积控制：

```bash
python image_tool.py compress --input ./input_images --output ./output --target-size-kb 300
python image_tool.py convert --input ./input_images --output ./output --to webp --target-size-kb 300
python image_tool.py compress --input ./input_images --output ./output --target-size-kb 300 --strict-mode
python image_tool.py compress --input ./input_images --output ./output --target-size-kb 300 --strict-mode --strict-behavior report
python image_tool.py compress --input ./input_images --output ./output --target-size-kb 300 --allow-quality-loss
```

说明：

- 目标体积是“最佳努力”策略，优先在保证可用画质前提下尽量逼近。
- 当前精确控体积主要对 `jpeg/webp` 生效；其他格式会尽力压缩但可能无法达到指定体积。

可选品牌配置（启动前设置）：

```bash
export IMG_TOOL_APP_NAME="Your Studio"
export IMG_TOOL_TAGLINE="你的品牌说明文案"
export IMG_TOOL_LOGO_TEXT="YS"
export IMG_TOOL_BRAND_COLOR="#7c5cff"
export IMG_TOOL_ACCENT_COLOR="#00d3b7"
python web_app.py
```

如果你是旧环境升级，记得重新安装依赖：

```bash
pip install -r requirements.txt
```

### 2.5 公网 / 云端部署（不占你自己电脑算力与磁盘）

把 Web 服务跑在**云服务器或容器**里后，别人通过 HTTPS 访问你的域名即可；压缩在**对方访问的那台服务器**上完成，上传与 ZIP 下载走公网。

本仓库已包含 `Dockerfile`：镜像内设置 `IMG_TOOL_CLOUD=1` 后，会自动：

- 仅保留**浏览器上传 + 下载 ZIP**（禁用本机目录选择、自动打开文件夹、扫描服务器本地文件夹等）
- 使用 **Gunicorn** 作为进程模型（比 Flask 自带服务器更适合对外）

**本地构建并运行容器示例：**

```bash
cd image-lossless-tool
docker build -t img-tool .
docker run --rm -p 8080:8080 \
  -e IMG_TOOL_ACCESS_TOKEN='请换成随机长字符串' \
  img-tool
```

浏览器打开 `http://127.0.0.1:8080` ，在页面里「保存令牌」后，再上传处理。（不设 `IMG_TOOL_ACCESS_TOKEN` 则任何人可访问，**强烈不建议**公网裸奔。）

**常用环境变量：**

| 变量 | 说明 |
|------|------|
| `IMG_TOOL_CLOUD=1` | 云端模式（Dockerfile 已默认） |
| `IMG_TOOL_ACCESS_TOKEN` | 访问令牌；前端通过 `X-Access-Token` 发送 |
| `PORT` | 监听端口，默认 `8080`（Fly.io / Render 等会注入） |
| `IMG_TOOL_MAX_UPLOAD_MB` | 单次请求最大体积，默认 `200` |

**Fly.io（示例）：** 安装 [flyctl](https://fly.io/docs/hands-on/install-flyctl/) 后，修改 `fly.toml` 里的 `app` 名称，执行 `fly launch` / `fly deploy`。

**健康检查：** `GET /health` 返回 `{"ok":true,"cloud":true}`。

**重要说明：**

- 云厂商的机器也会产生费用；大文件、高并发时请适当升配或加队列。
- 当前实现**无多用户隔离与审计**，令牌属于轻量门槛；正式对外建议再加反向代理限流、HTTPS、日志与监控。

### 2.6 在 GitHub 上托管与发布镜像（推荐配合任意云主机运行）

GitHub **不提供**长期托管 Flask 网页服务（GitHub Pages 只能放静态站），但可以：

1. **代码托管**在 GitHub 仓库；
2. 用 **GitHub Actions** 自动构建 Docker 镜像并推送到 **GitHub Container Registry（ghcr.io）**；
3. 你在阿里云 / 腾讯云 / Fly.io 等任意平台 **拉取该镜像运行** 即可对外提供网页。

**步骤概要：**

1. 在 GitHub 新建仓库，把本目录（含 `Dockerfile`、`.github/workflows/`）推上去（默认分支名为 `main` 或 `master` 均可触发工作流）。
2. 打开仓库 **Actions**，确认工作流 **Docker build & push to GHCR** 已成功。
3. 打开 **Packages**（或仓库右侧 **Packages** 链接），找到刚发布的包；若包为 **Private**，需在包设置里 **Connect repository** 并视需要改为 Public，或给运行镜像的机器配置 `docker login ghcr.io`（使用 GitHub 用户名 + Personal Access Token，权限勾选 `read:packages`）。
4. 在服务器上拉取并运行（将 `OWNER/REPO` 换成你的仓库路径，**全小写**）：

```bash
docker pull ghcr.io/owner/repo:latest
docker run -d -p 8080:8080 \
  -e IMG_TOOL_ACCESS_TOKEN='你的强随机令牌' \
  ghcr.io/owner/repo:latest
```

5. 在云平台配置 **HTTPS 反代** 到本机 `8080`（或平台提供的端口）。

> 若你的 Git 仓库根目录**不是**本工具目录（例如 monorepo 子目录），请把 `.github/workflows/docker-ghcr.yml` 里 `build-push-action` 的 `context` 改为子目录路径（如 `context: ./image-lossless-tool`），并把 `file` 改为对应 `Dockerfile` 路径。

### 2.7 推荐托管：Fly.io（HTTPS + 按量休眠，适合小工具）

在 GitHub 托管代码的前提下，**运行服务**推荐用 [Fly.io](https://fly.io)：

- 与当前 `Dockerfile` / `fly.toml` 直接配套；
- 自动 **HTTPS**；
- 机器可自动休眠，有访问再唤醒（适合低频使用）。

**第一次（只需做一次）：**

1. 安装 [flyctl](https://fly.io/docs/hands-on/install-flyctl/)，执行 `fly auth login`。
2. 在本项目目录打开 `fly.toml`，若 `app = "img-lossless-tool"` 已被占用，改成全局唯一的名字。
3. 创建应用并部署（会按 Dockerfile 构建）：

```bash
cd image-lossless-tool
fly apps create <与 fly.toml 中 app 相同的名字>   # 若 fly launch 已创建可跳过
fly secrets set IMG_TOOL_ACCESS_TOKEN="你的强随机令牌"
fly deploy
```

4. 记下 `fly status` 或控制台里的 **https://xxx.fly.dev** 地址。

**之后改代码自动上线：**

1. 仓库 **Variables** 添加 **`ENABLE_FLY_DEPLOY`** = **`true`**（见上文「最优方案」）。  
2. 仓库 **Secrets** 添加 **`FLY_API_TOKEN`**，值来自本机：

```bash
fly auth token
```

推送 **`main`** 会触发 **Deploy to Fly.io**。未设 `ENABLE_FLY_DEPLOY` 时不会自动部署，可在 Actions 里 **手动运行**该工作流。

> 同时保留 **GHCR 镜像工作流**：需要把同一镜像拉到阿里云等机器时，仍可用 §2.6 的 `docker pull ghcr.io/...`。

## 3. 格式支持

- 输入：`png/jpg/jpeg/webp/tif/tiff/bmp/gif`
- 转换输出：`png/jpeg/webp/tiff/bmp/gif`

## 4. 说明

- PNG/WebP/TIFF/GIF 会使用对应的无损压缩参数。
- JPEG 的“无损压缩”依赖 `jpegtran`，如果未安装会自动保留原图，避免二次有损压缩。
- 将已有有损图（例如 JPEG）转为无损格式（例如 PNG/WebP lossless）不会恢复丢失细节，但不会额外损失画质。
