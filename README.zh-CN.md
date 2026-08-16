# onelap2strava

[English](README.md)

将 FIT 运动记录中的 GCJ-02 坐标转换为 WGS84，并可选择上传到 Strava。项目既可以作为本地
命令行工具使用，也可以部署为自托管 Telegram Bot。

转换器只修改坐标字段。时间、传感器数据、分圈、活动摘要和设备信息保留在原 FIT 数据流中。
转换前会校验文件头和文件 CRC，转换后会重新计算文件 CRC。

## 使用前必读

仅对已确认使用 **GCJ-02** 坐标的 FIT 文件执行转换。FIT 文件不会声明坐标系，因此程序无法
自动判断输入是 GCJ-02 还是 WGS84。对中国境内本来就是 WGS84 的轨迹再次转换，会把路线移到
错误位置。

本项目不登录顽鹿账号，不调用顽鹿私有接口，也不抓取 Strava。FIT 文件由用户自行导出；上传
使用 Strava 官方 [OAuth](https://developers.strava.com/docs/authentication/) 和
[Uploads](https://developers.strava.com/docs/uploads/) API。

## 安装

需要 Python 3.11 或更高版本。

```bash
git clone https://github.com/KurisuT7/onelap2strava.git
cd onelap2strava
python -m venv .venv
. .venv/bin/activate             # Windows: .venv\Scripts\activate
python -m pip install -e .
```

本地转换：

```bash
onelap2strava convert activity.fit
# 输出 activity.wgs84.fit
```

默认不会覆盖已有文件；需要覆盖时添加 `--force`。添加 `--json` 可输出便于脚本读取的转换统计。

## 上传到 Strava

安装 Strava 可选依赖：

```bash
python -m pip install -e ".[strava]"
```

在 [Strava](https://www.strava.com/settings/api) 创建 API Application，将 Authorization
Callback Domain 设为 `localhost`，然后执行：

```bash
onelap2strava auth --client-id 你的纯数字_CLIENT_ID
onelap2strava upload activity.fit
```

`auth` 申请 `read,activity:write` 权限，在 `127.0.0.1` 接收回调，并把 Client Secret 和 Refresh
Token 写入当前用户的配置目录。Unix 下配置文件权限为 `0600`。无图形界面的主机可使用
`auth --manual`。

`upload` 会在临时目录中转换文件，并等待 Strava 完成异步处理。只有输入已经是 WGS84 时才应
添加 `--skip-conversion`。

## Telegram Bot

Bot 只接受白名单用户发送的 FIT 文件。主机已完成 Strava 授权时自动上传，否则返回转换后的
文件。每次请求都在临时目录中处理，完成后立即删除。Bot 不提供通过 Telegram 写入 Strava
凭证的命令。

完整指南从通过 `@BotFather` 创建 Bot 开始，依次说明 Docker 与原生部署、首次加入白名单并
处理 FIT、可选的 Strava 授权、日常维护和常见故障：

- [Telegram Bot 部署指南](docs/telegram-bot.zh-CN.md)
- [Telegram bot deployment guide](docs/telegram-bot.md)

Docker 容器以非 root 用户运行，根文件系统只读，移除全部 Linux capabilities，并使用具名
数据卷保存配置和轮询状态。白名单为空时，Bot 不处理任何文件，只响应 `/whoami`。

## 支持范围

- 支持 12 字节和 14 字节 FIT 文件头。
- 转换 record 轨迹点，以及标准 lap/session 坐标摘要。
- 明确拒绝 chained FIT，避免只改写文件的一部分。
- Telegram Bot API 当前只允许 Bot 下载不超过 20 MB 的文件。
- 核心转换完全离线；只有可选的 Strava 和 Telegram 命令会联网。

通过 Bot 处理位置记录前，请自行确认 Telegram 和 Strava 的隐私条款符合你的需要。

## 参与贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。测试使用程序生成的合成 FIT 数据，请勿提交个人运动记录
作为测试样本。安全问题请按 [SECURITY.md](SECURITY.md) 私下报告。

## 许可证

MIT，见 [LICENSE](LICENSE)。

本项目与顽鹿运动、Strava 不存在隶属或背书关系。相关名称及商标归各自权利人所有。
