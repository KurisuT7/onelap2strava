# Telegram Bot 部署指南

[English](telegram-bot.md)

本指南从创建一个新的 Telegram Bot 开始，一直到完成一次可验证的 FIT 转换。推荐使用 Docker
Compose；文末也提供不使用 Docker 的原生 Python 方式。

## 1. 准备条件

你需要：

- 一个 Telegram 账号；
- 一台已安装 `curl`、`unzip`、Docker Engine 和 Docker Compose v2 插件的 Linux 主机；
- 一个已确认使用 GCJ-02 坐标的 FIT 运动记录，用于最终测试；
- 可选：用于自动上传的 Strava 账号和 API Application。

先确认 Docker 可用：

```bash
docker version
docker compose version
```

## 2. 通过 BotFather 创建 Bot

1. 打开 Telegram，与官方 [`@BotFather`](https://t.me/BotFather) 建立私聊。
2. 发送 `/newbot`。
3. 输入显示名称。这个名称会展示给 Telegram 用户。
4. 输入一个未被占用的用户名。用户名必须以 `bot` 结尾，例如 `my_fit_converter_bot`。
5. BotFather 会返回 API Token。它相当于 Bot 的密码，任何拿到它的人都能控制这个 Bot。

建议顺便在 BotFather 中配置命令菜单：

1. 发送 `/mybots`，选择刚创建的 Bot。
2. 依次选择 **Edit Bot**、**Edit Commands**。
3. 发送以下内容：

```text
start - 查看使用方法
help - 查看使用方法
status - 查看 Bot 和 Strava 状态
whoami - 查看你的 Telegram 用户 ID
```

不要把 Token 发到 Issue、Telegram 命令、Shell 历史、截图或 Git 跟踪文件中。如果 Token 已经
泄露，立即在 BotFather 中使用 `/revoke` 撤销并更换。

Telegram 官方也在 [BotFather 教程](https://core.telegram.org/bots/tutorial#obtain-your-bot-token)
中说明了相同的创建流程。

## 3. 下载并配置 onelap2strava

在部署主机上下载并解压 `v0.2.0` Compose 部署包：

```bash
curl -fLO https://github.com/KurisuT7/onelap2strava/releases/download/v0.2.0/onelap2strava-0.2.0-compose.zip
unzip onelap2strava-0.2.0-compose.zip
cd onelap2strava-0.2.0-compose
```

部署包中包含固定版本的 Compose 文件、空配置示例、文档和许可证。它会拉取预构建镜像，主机
不再从源码构建项目。

创建私有环境文件：

```bash
cp .env.example .env
```

Windows PowerShell 使用：

```powershell
Copy-Item .env.example .env
```

用文本编辑器打开 `.env`，填入 BotFather 返回的 Token。首次启动时白名单保持为空：

```dotenv
TELEGRAM_BOT_TOKEN=把_BOTFATHER_TOKEN_粘贴到这里
TELEGRAM_ALLOWED_USER_IDS=
TELEGRAM_UPLOAD_TO_STRAVA=true
TELEGRAM_SEND_CONVERTED=false
```

`.env` 已被 Git 忽略。不要把它改名为 `.env.example`，也不要提交它。

## 4. 首次启动 Bot

拉取固定版本镜像并启动一个长轮询实例：

```bash
docker compose pull
docker compose up -d
```

确认容器已经运行：

```bash
docker compose ps
docker compose logs --tail=50 bot
```

白名单为空时，Bot 会有意忽略文件和除 `/whoami` 外的命令。

## 5. 把自己加入白名单

1. 打开刚才在 BotFather 中创建的 Bot。
2. 点击 **Start**，然后发送 `/whoami`。
3. 从 `Your Telegram user ID is ...` 中复制纯数字 ID。
4. 把 ID 填入 `.env`：

```dotenv
TELEGRAM_ALLOWED_USER_IDS=123456789
```

允许多个用户时，用英文逗号分隔，不加空格：

```dotenv
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

重建容器，让它读取新的环境变量：

```bash
docker compose up -d --force-recreate
```

发送 `/status`。尚未授权 Strava 时应返回 `Strava: conversion only`。

## 6. 验证仅转换模式

向 Bot 发送一个已确认使用 GCJ-02 坐标的 `.fit` 文件。不要用原本就是 WGS84 的文件测试，否则
转换会让轨迹向错误方向偏移。

Bot 应该：

1. 提示转换已经开始；
2. 返回文件名以 `.wgs84.fit` 结尾的文件；
3. 报告处理了多少轨迹点和坐标对。

下载的源文件和转换结果只会在处理请求时存在于临时目录，随后立即删除。Telegram 托管的 Bot
API 当前允许 Bot 下载不超过 20 MB 的文件。

## 7. 启用 Strava 自动上传（可选）

如果只需要 Bot 返回转换后的 FIT 文件，可以跳过本节。

1. 登录 Strava，打开 [My API Application](https://www.strava.com/settings/api)。
2. 创建 Application，并填写页面要求的字段。
3. 将 **Authorization Callback Domain** 设为 `localhost`。
4. 复制纯数字 Client ID。Client Secret 必须保密。

Strava 当前的创建条件和字段说明见官方
[Getting Started](https://developers.strava.com/docs/getting-started/) 文档。

在 Compose 服务内执行授权，使生成的凭据保存在持久化的 `bot-data` 数据卷中：

```bash
docker compose run --rm bot auth --manual --no-browser --client-id 你的纯数字_CLIENT_ID
```

接下来：

1. 在隐藏输入提示中填写 Client Secret。
2. 把终端打印的授权 URL 复制到浏览器，批准 `read,activity:write` 权限。
3. 浏览器会跳转到 `http://localhost/callback?...`。如果命令运行在另一台主机上，这个页面显示
   无法连接是正常的。
4. 从浏览器地址栏复制完整地址，包括问号后的参数，粘贴到终端的 `Callback URL:` 提示中。
5. 等待终端显示 `Saved Strava authorization to /data/config.toml`。

重启并验证：

```bash
docker compose up -d --force-recreate
```

发送 `/status`，应显示 `Strava: enabled`。再发送一个已确认使用 GCJ-02 的 FIT 文件，确认 Bot
返回 Strava 活动链接。如果希望上传成功后同时收到转换文件，把
`TELEGRAM_SEND_CONVERTED` 设为 `true`。

## 8. 日常维护

查看状态和最近日志：

```bash
docker compose ps
docker compose logs --tail=100 bot
```

修改 `.env` 后重启：

```bash
docker compose up -d --force-recreate
```

升级时，下载并解压新版本的 Compose 部署包，把原目录中的 `.env` 复制到新目录，然后在新目录
执行 `docker compose pull` 和 `docker compose up -d`。Compose 项目名保持固定，因此会继续使用
原来的 `bot-data` 数据卷。升级前先阅读 Changelog，升级后重新执行一次转换验证。

停止 Bot，但保留授权信息和轮询状态：

```bash
docker compose down
```

除非你明确想删除 `bot-data` 数据卷中的 Strava 授权和 Telegram 轮询状态，否则不要添加 `-v`。

## 9. 常见问题

### Bot 不响应 `/whoami`

- 检查 `docker compose ps` 和 `docker compose logs --tail=100 bot`。
- 确认 `TELEGRAM_BOT_TOKEN` 对应当前打开的 Bot 用户名。
- 修改 `.env` 后必须重建容器。

### `/whoami` 正常，但发送文件没有反应

- 确认纯数字 ID 已加入 `TELEGRAM_ALLOWED_USER_IDS`。
- 修改白名单后重建容器。
- 以文档形式发送文件名以 `.fit` 结尾且不超过 20 MB 的运动记录。

### Telegram 报告 `409 Conflict`

同一个 Token 只能有一个长轮询进程。停止旧部署或重复容器，再只启动一个实例。如果日志提示
存在 active webhook，应先在创建该 webhook 的系统中移除它，再使用本项目的长轮询 Bot。

### `/status` 显示 `conversion only`

未完成 Strava 授权，或 `TELEGRAM_UPLOAD_TO_STRAVA=false` 时，这是正常状态。重新执行授权命令，
并确认最后出现保存 `/data/config.toml` 的提示。

### Strava 拒绝上传

- 确认授权时同意了 `activity:write`。
- 在 Bot 日志中查看 Strava API 返回的错误。
- 确认输入是有效的 FIT 运动记录，并且没有作为重复活动上传过。

### 转换后的路线明显错误

立即停止使用该输出。输入文件很可能本来就是 WGS84，或使用了其他坐标系。onelap2strava 无法
从 FIT 文件中自动判断坐标系。

## 原生 Python 部署

仅当你已经能够自行管理不使用 Docker 的常驻 Python 服务时，才建议采用这种方式。

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install "onelap2strava[bot,strava] @ https://github.com/KurisuT7/onelap2strava/releases/download/v0.2.0/onelap2strava-0.2.0-py3-none-any.whl"
export TELEGRAM_BOT_TOKEN=你的_TOKEN
export TELEGRAM_ALLOWED_USER_IDS=你的纯数字用户_ID
onelap2strava bot
```

Windows PowerShell 的激活和环境变量写法如下：

```powershell
.venv\Scripts\Activate.ps1
$env:TELEGRAM_BOT_TOKEN = "你的_TOKEN"
$env:TELEGRAM_ALLOWED_USER_IDS = "你的纯数字用户_ID"
onelap2strava bot
```

只运行一个 Bot 进程。使用操作系统的服务管理器持久化环境变量并重启进程，不要把 Token 直接
写进服务命令参数。
