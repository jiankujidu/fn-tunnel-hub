---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4576474b6d747480a72e43d4db8614ae_8df02751accf11f18039525400461939
---

# 穿透管家（fn-tunnel-hub）

飞牛 fnOS 多引擎内网穿透应用，一个应用集成 4 大免费方案，**免公网 IP、免 FRP 服务器**，NAS 主动出站建连，支持绑定自己的域名。
本版本为**原生模式**：四引擎二进制全部内置，无需 Docker，按架构自动加载 amd64 / arm64。

## 内置方案（全部免费）

| 引擎 | 是否限流 | 绑定自己域名 | 特点 |
|---|---|---|---|
| **Cloudflare Tunnel** | 免费不限流量 | 支持 | 全球边缘节点、自动 HTTPS、业界主流通用方案 |
| **Tailscale** | 直连不限速不限流 | 进阶可用 Funnel | P2P 打洞，组虚拟局域网 |
| **ZeroTier** | 直连不限速不限流 | 虚拟局域网 | 免费 50 节点 |
| **openP2P** | 直连不限速不限流 | 支持 | 开源 P2P 打洞，无需服务器 |

三套方案可随时切换：CF 节点抽风时一键换 P2P 类引擎兜底，互不依赖。

## 目录结构（原生模式）

```
fn-tunnel-hub/
├── manifest            # 应用元数据（version=2.2.0, service_port=19999）
├── ICON.PNG            # 64x64 图标
├── ICON_256.PNG        # 256x256 图标
├── config/             # privilege 权限声明
├── cmd/                # main（生命周期）+ updater.sh（自动更新）+ 8 个 fnOS 钩子
├── wizard/install      # 安装向导：面板端口 + 自动更新
└── app/
    ├── bin/amd64|arm64 # 四引擎二进制（cloudflared/tailscale(+d)/zerotier-one/openp2p/busybox）
    └── www/            # index.html（状态页+设置页+教程页）+ config.cgi（配置接口）
```

## 打包

```bash
# 需要官方 fnpack（https://developer.fnnas.com/docs/cli/fnpack ）
fnpack build --directory fn-tunnel-hub
# 产出 fn-tunnel-hub.fpk
```

## 安装与使用

1. 应用中心 → 设置 → 手动安装应用，选择 fpk
2. 向导设置面板端口（默认 19999）
3. 安装完成后打开 `http://NAS_IP:19999` 面板 → 「设置」页配置各引擎 Token/域名
4. 详细教程见随包说明文档，应用内「教程」页也内置完整配置步骤。

## 更新说明

- **应用内强制更新弹窗**：应用启动时自动检测 GitHub Releases 最新版本，若与本机版本不一致，面板会弹出「发现新版本」更新窗口，点击直达 GitHub Release 下载新版 fpk 覆盖安装。无需手动关注更新。
- **四引擎二进制自动更新**（可选）：设置中开启「自动更新」后，后台守护会周期性从各引擎官方源下载最新二进制并热升级对应引擎。
- 版本记录请查看 [Releases](https://github.com/jiankujidu/fn-tunnel-hub/releases)。

## 加入我们

折腾 NAS、内网穿透、HomeLab 的朋友欢迎来一起玩：

| 渠道 | 方式 | 链接 |
|---|---|---|
| QQ 群 | 加入群聊【瞎折腾】 | https://qm.qq.com/q/y5Nzu7bVWS |
| 公众号 | 微信搜索【一起瞎折腾】 | 关注获取教程与更新通知 |
| GitHub | 项目主页 / Star / Issue | https://github.com/jiankujidu/fn-tunnel-hub |
| Telegram | 频道加入 | https://t.me/+5zdHmNqXIZdmYWVl |

--- 
*内容由 AI 生成，仅供参考。*
