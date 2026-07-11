# 远端服务器指南 | [English](remote-server-guide-en.md)

这份文档说明如何把 FlowScribe 部署成远端转写服务器，以及 Windows 客户端怎样通过 CLI 或 GUI 连接这台服务器。

适合这些场景：

- 本地 Windows 机器只负责发任务和看结果
- URL 下载、cookies、转写都放到一台集中服务器上
- 需要把结果自动下载回本地工作目录
- 希望多台客户端共用同一套远端能力

另见：

- [server-configuration.md](server-configuration.md)
- [agent-api.md](agent-api.md)

## 新增能力

这次补齐的远端执行能力包括：

- `CLI` 和 `GUI` 都能切换到远端执行
- 可以保存远端服务器配置，包括 `Base URL`、Bearer Token、超时和服务端 `cookies.txt` 路径
- 远端结果下载会先写入服务器自己的暂存目录，再回传到本地，避免把 `E:\Temp` 这类 Windows 路径带到 Linux 服务器
- 服务端 HTTP 控制面改为线程化，请求 `status`、`events`、`result` 不会被长任务完全堵住
- 重型转写任务默认仍然只允许 1 个并发，低内存服务器会优先返回 HTTP `429`，避免内存被同时打爆

## 工作方式

典型流程如下：

1. Windows 客户端向 `/v1/tasks` 提交任务。
2. 如果源是本地文件，客户端先上传到 `/v1/uploads`。
3. 服务器在本地解析上传文件，或者自行下载 URL 媒体。
4. 服务器执行转写并写出产物。
5. 如果开启了下载产物，客户端再把结果下载回本地输出目录。

对于需要登录态的 URL，`remote_cookies_path` 是在服务器端解析的，不是客户端本地路径。

## 服务器前提

示例目标环境：

- Ubuntu 24.04
- Python 3.10+
- `ffmpeg` 在 `PATH` 中可用
- 有足够磁盘空间保存媒体下载、临时文件和转写结果

模型建议：

- `tiny`：适合 2 核 / 2 GB 小机器
- `small`：适合日常远端使用，但更慢、更吃内存
- `native-engine`：可以作为后续优化方向，但建议先把 Linux 运行时、模型路径和精度预期都验证好再切

## Ubuntu 部署步骤

安装基础依赖：

```bash
sudo apt update
sudo apt install -y git ffmpeg python3 python3-venv
```

克隆仓库并创建虚拟环境：

```bash
git clone https://github.com/Ducker-Fry/FlowScribe.git
cd FlowScribe
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

创建服务端目录：

```bash
mkdir -p ~/flowscribe/config
mkdir -p ~/flowscribe/out
mkdir -p ~/.flowscribe-secrets
```

可选：如果远端要下载需要登录态的站点，把 Netscape 格式的 cookies 文件放到服务器上：

```bash
cp /path/to/cookies.txt ~/.flowscribe-secrets/bilibili.cookies.txt
chmod 600 ~/.flowscribe-secrets/bilibili.cookies.txt
```

下载起步模型：

```bash
source .venv/bin/activate
export FLOWSCRIBE_CONFIG_DIR="$HOME/flowscribe/config"
flowscribe model download tiny
```

做一次健康检查：

```bash
flowscribe doctor
```

## 启动远端服务

前台启动示例：

```bash
source .venv/bin/activate
export FLOWSCRIBE_CONFIG_DIR="$HOME/flowscribe/config"
flowscribe serve \
  --host 0.0.0.0 \
  --port 8765 \
  --api-token CHANGE_ME \
  -o "$HOME/flowscribe/out" \
  --format txt,md,json \
  -m tiny \
  --task-retention-hours 24
```

小机器建议：

- 先从 `-m tiny` 开始
- 保持默认的单个重任务并发
- 定期看输出目录和 `/tmp` 的空间占用

## 可选：systemd 服务

示例 unit 文件：

```ini
[Unit]
Description=FlowScribe remote server
After=network.target

[Service]
Type=simple
User=fry
WorkingDirectory=/home/fry/FlowScribe
Environment=FLOWSCRIBE_CONFIG_DIR=/home/fry/flowscribe/config
ExecStart=/home/fry/FlowScribe/.venv/bin/flowscribe serve --host 0.0.0.0 --port 8765 --api-token CHANGE_ME -o /home/fry/flowscribe/out --format txt,md,json -m tiny --task-retention-hours 24
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

写入后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now flowscribe.service
sudo systemctl status flowscribe.service
```

## 验证服务器

在任意能访问服务器的客户端执行：

```powershell
Invoke-WebRequest `
  -Uri http://SERVER_IP:8765/v1/server `
  -Headers @{ Authorization = "Bearer CHANGE_ME" } |
  Select-Object -ExpandProperty Content
```

期望结果：

- 返回 HTTP `200`
- JSON 中能看到服务名、版本号、保留策略和能力字段

## CLI 连接远端服务器

先保存一个远端服务器配置：

```powershell
flowscribe remote add-server prod-linux `
  --url http://SERVER_IP:8765 `
  --token CHANGE_ME `
  --remote-cookies-path /home/fry/.flowscribe-secrets/bilibili.cookies.txt `
  --timeout 30 `
  --download-artifacts
```

查看配置：

```powershell
flowscribe remote list-servers
flowscribe remote show-server prod-linux
```

远端执行本地文件：

```powershell
flowscribe transcribe "D:\media\lecture.mp4" `
  --execution remote `
  --server prod-linux `
  -o .\client-out `
  --format json `
  --json `
  --non-interactive
```

远端执行 URL：

```powershell
flowscribe url "https://www.bilibili.com/video/BV1PC4y1G7T5/" `
  --execution remote `
  --server prod-linux `
  -o .\client-out-url `
  --format txt,md,json `
  --json `
  --non-interactive
```

常用补充命令：

```powershell
flowscribe remote status prod-linux TASK_ID
flowscribe remote events prod-linux TASK_ID
flowscribe remote result prod-linux TASK_ID -o .\recovered-out --download-artifacts
```

## GUI 连接远端服务器

1. 打开 `Settings`。
2. 在远端执行区域把 `Execution mode` 切到 `Remote`。
3. 点击 `Manage Remote Servers...`。
4. 新建一个配置，至少填：
   - `Base URL`：`http://SERVER_IP:8765`
   - `Token`：你的 Bearer Token
   - `Remote cookies path`：可选，服务端 cookies 文件路径
   - `Download artifacts by default`：建议勾选
5. 保存后，在主界面的远端执行控件里选中这个 profile。
6. 正常发起 `Single Task` 或 `Queue` 任务即可。

运行时你会看到：

- 进度文本里出现 `Submitting remote task`
- 任务获得一个远端 `task id`
- 如果启用了下载产物，结果文件会落回本地输出目录

## Provider 和模型路径说明

远端执行会把 provider 和 model 一起发给服务器。

这意味着：

- `local-whisper` 的 `tiny`、`small` 这类模型名是在服务器端解析的
- `native-engine` 的模型值必须是服务器本机可访问的路径
- `D:\models\ggml-base.en.bin` 这种 Windows 路径对 Linux 服务端无效

远端 `native-engine` 示例：

```powershell
flowscribe transcribe "D:\media\clip.wav" `
  --execution remote `
  --server prod-linux `
  --provider native-engine `
  --model /home/fry/models/ggml-base.en.bin `
  -o .\client-out
```

## 常见问题

`Timed out while contacting remote server`

- 确认服务还在运行
- 确认客户端能访问到主机和端口
- 小机器建议从 `tiny` 起步，并保持一次只跑一个任务

`Remote server is already processing the maximum number of tasks`

- 这是服务端返回了 HTTP `429`
- 说明当前已有一个重任务在跑
- 等当前任务结束后再重试即可

URL 能力失败，但本地文件上传正常：

- 检查服务器上的 `yt-dlp` 是否能访问目标站点
- 检查 `remote_cookies_path` 指向的文件是否存在
- 检查 cookies 文件是否为有效 Netscape 格式

服务器端已有结果，但本地没下载回来：

- 检查 profile 或本次任务是否启用了 `download artifacts`
- 可用 `flowscribe remote result SERVER TASK_ID --download-artifacts` 手动拉回
