#!/bin/sh
# 穿透管家 状态接口 CGI（GET）
# 返回各引擎运行详情（IP/域名/节点/网络ID/PID）+ 系统信息（版本/架构/内网IP/面板端口/运行时长）
# 前端「运行状态」页每 5 秒调用一次，实时展示
# 说明：纯 POSIX sh（busybox ash 兼容）：不用 local、不用 ${!var}、不用 awk 扩展

DATA_DIR="${TRIM_PKGVAR:-/usr/local/apps/@appdata/fn-tunnel-hub}"
APP_DIR="${TRIM_APPDEST:-/usr/local/apps/@appcenter/fn-tunnel-hub}"
ENV_FILE="${DATA_DIR}/tunnel.env"
LOG_FILE="${DATA_DIR}/info.log"
CMD_DIR="${CMD_DIR:-/var/apps/fn-tunnel-hub/cmd}"
[ -x "${CMD_DIR}/main" ] || CMD_DIR="/var/apps/fn-tunnel-hub/cmd"

echo "Content-Type: application/json; charset=utf-8"
echo ""

# ---------- 基础信息 ----------
case "$(uname -m)" in
  x86_64|amd64) ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *) ARCH=amd64 ;;
esac
if [ -x "${DATA_DIR}/bin/${ARCH}/busybox" ]; then
  BIN_DIR="${DATA_DIR}/bin/${ARCH}"
else
  BIN_DIR="${APP_DIR}/bin/${ARCH}"
fi

# 版本：优先从 cmd/main 取（保持与开关 VERSION 同步），兜底写死
VERSION="$(grep -m1 '^VERSION=' "${CMD_DIR}/main" 2>/dev/null | sed 's/^VERSION=//; s/^"//; s/"$//')"
[ -z "${VERSION:-}" ] && VERSION="2.2.1"

# 读取配置值（域名/节点/网络ID/PeerID/端口等）
CF_HOSTNAME=""; TS_HOSTNAME=""; ZT_NETID=""; P2P_PEERID=""; PANEL_PORT=""
[ -f "${ENV_FILE}" ] && . "${ENV_FILE}" 2>/dev/null
[ -z "${PANEL_PORT:-}" ] && PANEL_PORT=19999
[ -z "${TS_HOSTNAME:-}" ] && TS_HOSTNAME="fnos-nas"

# ---------- 工具函数 ----------
isup() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
pid_get() { cat "$1" 2>/dev/null; }
jesc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

CF_PID="$(pid_get "${DATA_DIR}/engine-cf.pid")"
TS_PID="$(pid_get "${DATA_DIR}/engine-ts.pid")"
ZT_PID="$(pid_get "${DATA_DIR}/engine-zt.pid")"
P2P_PID="$(pid_get "${DATA_DIR}/engine-p2p.pid")"

# ---------- 主机运行时长 ----------
UPTIME=""
up_s="$(awk '{print int($1)}' /proc/uptime 2>/dev/null)"
if [ -n "${up_s:-}" ] && [ "${up_s:-0}" -gt 0 ] 2>/dev/null; then
  if [ "${up_s}" -ge 3600 ]; then
    UPTIME="$((up_s/3600))小时$(((up_s%3600)/60))分"
  elif [ "${up_s}" -ge 60 ]; then
    UPTIME="$((up_s/60))分"
  else
    UPTIME="${up_s}秒"
  fi
fi

# ---------- 内网 IP ----------
LAN_IP=""
lan_candidates=""
lan_candidates="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | head -8)"
if [ -z "${lan_candidates}" ]; then
  lan_candidates="$(ip -4 addr show 2>/dev/null | sed -n 's/.*inet \([0-9.]*\)\/.*/\1/p' | grep -v '^127\.' | head -8)"
fi
for ip in ${lan_candidates}; do
  case "$ip" in
    127.*|169.254.*) continue ;;
  esac
  [ -z "$LAN_IP" ] && LAN_IP="$ip"
done

# ---------- Tailscale 分配的 IP（实时读取，socket 存在才有） ----------
TS_IP=""
if [ -S "${DATA_DIR}/ts.sock" ] && [ -x "${BIN_DIR}/tailscale" ]; then
  TS_IP="$("${BIN_DIR}/tailscale" --socket="${DATA_DIR}/ts.sock" ip -4 2>/dev/null | tr '\n' ',' | sed 's/,$//')"
fi

# ---------- ZeroTier 分配的 IP（实时读取该网络 IP） ----------
ZT_IP=""
if [ -n "${ZT_NETID:-}" ] && [ -x "${BIN_DIR}/zerotier-one" ]; then
  ZT_IP="$("${BIN_DIR}/zerotier-one" -q get "${ZT_NETID}" ip4 2>/dev/null | awk '{print $NF}')"
  case "${ZT_IP}" in
    200*|ERROR*|INVALID*) ZT_IP="" ;;
  esac
fi

# ---------- 输出 JSON ----------
{
  echo "{\"version\":\"$(jesc "${VERSION}")\",\"arch\":\"${ARCH}\",\"panelPort\":\"$(jesc "${PANEL_PORT}")\",\"lanIp\":\"$(jesc "${LAN_IP}")\",\"uptime\":\"$(jesc "${UPTIME}")\",\"engines\":{"
  echo -n "  \"cf\":{\"running\":$(isup "${CF_PID}" && echo true || echo false),\"pid\":\"${CF_PID}\",\"domain\":\"$(jesc "${CF_HOSTNAME}")\"}"
  echo -n ", \"ts\":{\"running\":$(isup "${TS_PID}" && echo true || echo false),\"pid\":\"${TS_PID}\",\"ip\":\"$(jesc "${TS_IP}")\",\"hostname\":\"$(jesc "${TS_HOSTNAME}")\"}"
  echo -n ", \"zt\":{\"running\":$(isup "${ZT_PID}" && echo true || echo false),\"pid\":\"${ZT_PID}\",\"ip\":\"$(jesc "${ZT_IP}")\",\"netid\":\"$(jesc "${ZT_NETID}")\"}"
  echo -n ", \"p2p\":{\"running\":$(isup "${P2P_PID}" && echo true || echo false),\"pid\":\"${P2P_PID}\",\"peerid\":\"$(jesc "${P2P_PEERID}")\"}"
  echo "}}"
} > "${DATA_DIR}/www/status.json.tmp"
mv -f "${DATA_DIR}/www/status.json.tmp" "${DATA_DIR}/www/status.json"
cat "${DATA_DIR}/www/status.json"
