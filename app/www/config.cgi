#!/bin/sh
# 穿透管家 配置接口 CGI
# GET  -> 返回当前设置 JSON（页面回填）
# POST -> 保存设置并重启引擎（页面提交表单）
# 运行环境继承自 cmd/main 启动的 httpd，可读取 TRIM_APPDEST / TRIM_PKGVAR
DATA_DIR="${TRIM_PKGVAR:-/usr/local/apps/@appdata/fn-tunnel-hub}"
APP_DIR="${TRIM_APPDEST:-/usr/local/apps/@appcenter/fn-tunnel-hub}"
ENV_FILE="${DATA_DIR}/tunnel.env"
LOG_FILE="${DATA_DIR}/info.log"
# cmd/ 由 cmd/main 通过环境变量注入（其上 export CMD_DIR）；未注入时按 fnOS 固定安装结构探测兜底
CMD_DIR="${CMD_DIR:-/var/apps/fn-tunnel-hub/cmd}"
if [ ! -x "${CMD_DIR}/main" ]; then
  logmsg() { echo "$(date '+%Y-%m-%d %H:%M:%S') - [cgi] $1" >> "${LOG_FILE}" 2>/dev/null; }
  logmsg "CMD_DIR=${CMD_DIR} main not executable, trying fallback candidates"
  for try in /var/apps/fn-tunnel-hub/cmd /vol/@appcenter/fn-tunnel-hub/cmd; do
    [ -x "$try/main" ] && { CMD_DIR="$try"; logmsg "CMD_DIR fallback -> $try"; break; }
  done
fi

echo "Content-Type: application/json; charset=utf-8"
echo ""

logmsg() { echo "$(date '+%Y-%m-%d %H:%M:%S') - [cgi] $1" >> "${LOG_FILE}" 2>/dev/null; }

# URL decode（POST body 键值）
# 纯 POSIX 实现：不依赖 awk 的 strtonum（busybox awk 不支持该扩展），逐字节解码 %XX
urldecode() {
  s="$1"; o=""; c=""; hex=""
  s=$(printf '%s' "$s" | sed 's/+/ /g')
  while [ -n "$s" ]; do
    case "$s" in
      %[0-9A-Fa-f][0-9A-Fa-f]*)
        hex=$(printf '%s' "$s" | cut -c2-3)
        s=$(printf '%s' "$s" | cut -c4-)
        c=$(printf '%d' "0x$hex")
        o="${o}$(printf "\\$(printf '%03o' "$c")")"
        ;;
      *)
        c=$(printf '%s' "$s" | cut -c1)
        o="${o}${c}"
        s=$(printf '%s' "$s" | cut -c2-)
        ;;
    esac
  done
  printf '%s' "$o"
}

# ---------- 读取当前配置 ----------
read_json() {
  CF_TOKEN=""; CF_HOSTNAME=""; TS_AUTHKEY=""; TS_HOSTNAME="fnos-nas"
  ZT_NETID=""; P2P_PEERID=""; P2P_TOKEN=""
  ENABLE_CF=""; ENABLE_TS=""; ENABLE_ZT=""; ENABLE_P2P=""; PANEL_PORT="19999"
  if [ -f "${ENV_FILE}" ]; then
    . "${ENV_FILE}" 2>/dev/null
  fi
  # 高亮: token 部分打码，避免明文回显
  if [ -n "${CF_TOKEN:-}" ]; then CF_TOKEN="${CF_TOKEN%????}****"; fi
  if [ -n "${TS_AUTHKEY:-}" ]; then TS_AUTHKEY="${TS_AUTHKEY%????}****"; fi
  if [ -n "${P2P_TOKEN:-}" ]; then P2P_TOKEN="${P2P_TOKEN%????}****"; fi
  # JSON 值转义：仅处理用户可输入的自由文本字段，防引号破坏响应结构
  jesc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
  printf '{"cf_token":"%s","cf_hostname":"%s","ts_authkey":"%s","ts_hostname":"%s","zt_netid":"%s","p2p_peerid":"%s","p2p_token":"%s","enable_cf":"%s","enable_ts":"%s","enable_zt":"%s","enable_p2p":"%s","panel_port":"%s"}' \
    "$(jesc "${CF_TOKEN}")" "$(jesc "${CF_HOSTNAME}")" "$(jesc "${TS_AUTHKEY}")" "$(jesc "${TS_HOSTNAME}")" "$(jesc "${ZT_NETID}")" "$(jesc "${P2P_PEERID}")" "$(jesc "${P2P_TOKEN}")" \
    "${ENABLE_CF}" "${ENABLE_TS}" "${ENABLE_ZT}" "${ENABLE_P2P}" "${PANEL_PORT}"
}

# 安全转义 shell 值（写 env 用）
shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

# ---------- 保存并应用 ----------
apply_fld() { # key=value（已 urldecode），收集到 pending 文件
  kv="$1"; k=""; v=""
  [ -z "$kv" ] && return 0
  k="${kv%%=*}"
  v="${kv#*=}"
  # 统一转小写匹配白名单（POST 表单键名可能为大写）
  k="$(printf '%s' "$k" | tr 'A-Z' 'a-z')"
  case "$k" in
    cf_token|cf_hostname|ts_authkey|ts_hostname|zt_netid|p2p_peerid|p2p_token|enable_cf|enable_ts|enable_zt|enable_p2p|panel_port)
      printf '%s=%s\n' "$(echo "$k" | tr 'a-z' 'A-Z')" "$(shell_quote "$v")" >> "${DATA_DIR}/.pending${$}"
      ;;
  esac
}

# 主流程
if [ "$REQUEST_METHOD" = "GET" ]; then
  read_json
  exit 0
fi

if [ "$REQUEST_METHOD" = "POST" ]; then
  # 读取 POST body（url 编码串无换行）
  # 注意：busybox ash 在文件脚本 + CGI stdin 场景下 while/read 会读不到数据，
  # 因此按 CONTENT_LENGTH 用 dd 按字节精确读取；未下发时用 read 一行兜底。
  len="${CONTENT_LENGTH:-0}"
  rm -f "${DATA_DIR}/.pending${$}"
  body=""
  case "${len}" in
    ''|*[!0-9]*|0)
      IFS= read -r body || body=""
      ;;
    *)
      body="$(dd bs=1 count="$len" 2>/dev/null)"
      ;;
  esac
  IFSX='&'
  pair=""
  for pair in $(printf '%s' "$body" | tr '&' '\n'); do
    [ -z "$pair" ] && continue
    k="${pair%%=*}"; v="${pair#*=}"
    dv="$(urldecode "$v")"
    apply_fld "${k}=${dv}"
  done
  if [ -f "${DATA_DIR}/.pending${$}" ]; then
    # 交给 main 合并进 tunnel.env 并重启引擎
    # 必须直接执行（按 shebang 用 bash），严禁加 sh 前缀调用：真机 /bin/sh 为 busybox ash/dash，
    # 遇 cmd/main 内 ${!var} 等 bash 语法会报 bad substitution 中止，导致配置写回但引擎未重启
    if [ -x "${CMD_DIR}/main" ]; then
      if "${CMD_DIR}/main" apply_config "${DATA_DIR}/.pending${$}" >> "${LOG_FILE}" 2>&1; then
        logmsg "applied config, pending=$(wc -l < ${DATA_DIR}/.pending${$}) lines"
        rm -f "${DATA_DIR}/.pending${$}"
        printf '{"ok":true,"msg":"配置已保存，引擎已重启"}'
      else
        rc=$?
        logmsg "apply_config FAILED rc=$rc, see log above"
        rm -f "${DATA_DIR}/.pending${$}"
        printf '{"ok":false,"msg":"保存失败，请查看应用日志 info.log（rc=%s）"}' "$rc"
      fi
    else
      logmsg "cmd/main not found at ${CMD_DIR}/main"
      printf '{"ok":false,"msg":"cmd/main 缺失，请重新安装"}'
    fi
  else
    printf '{"ok":false,"msg":"未收到有效配置"}'
  fi
  exit 0
fi

printf '{"ok":false,"msg":"不支持的方法 %s"}' "$REQUEST_METHOD"
