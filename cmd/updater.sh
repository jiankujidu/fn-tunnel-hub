#!/bin/bash
# 穿透管家 自动更新守护（原生模式）
# 周期性从官方源下载四引擎 Linux 二进制的新版，覆盖到数据目录 bin/<arch>/，
# 然后重启对应引擎进程。内置二进制作为首次运行的兜底。
# 由 cmd/main 可选挂起；间隔由 UPDATE_INTERVAL（秒）控制，默认 6 小时。

DATA_DIR="${TRIM_PKGVAR:-/usr/local/apps/@appdata/fn-tunnel-hub}"
LOG_FILE="${DATA_DIR}/info.log"

case "$(uname -m)" in
    x86_64|amd64) ARCH="amd64"; TAILSUFFIX="_amd64" ;;
    aarch64|arm64) ARCH="arm64"; TAILSUFFIX="_arm64" ;;
    *) ARCH="amd64"; TAILSUFFIX="_amd64" ;;
esac
DEST="${DATA_DIR}/bin/${ARCH}"

fetch_url() {
    local url=$1 out=$2
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --connect-timeout 20 --max-time 300 "$url" -o "$out"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -T 60 -O "$out" "$url"
    else
        return 1
    fi
}

update_binary() {
    local name=$1 url=$2 tmp=$3
    mkdir -p "${DEST}"
    if fetch_url "$url" "${tmp}"; then
        chmod +x "${tmp}"
        mv -f "${tmp}" "${DEST}/${name}"
        [ -x "${DEST}/${name}" ] && echo "updated ${name}" && return 0
    fi
    rm -f "${tmp}"
    return 1
}

# 需要联网，失败不中断
run_update() {
    # Cloudflared: github release 静态二进制
    CF_VER="2026.9.0"
    update_binary "cloudflared-new" "https://github.com/cloudflare/cloudflared/releases/download/${CF_VER}/cloudflared-linux-${ARCH}" "${DATA_DIR}/.cf.tmp" && \
        mv -f "${DEST}/cloudflared-new" "${DEST}/cloudflared"

    # tailscale: 官方 tgz 内含 tailscaled + tailscale
    TS_VER="1.82.0"
    if fetch_url "https://pkgs.tailscale.com/stable/tailscale_${TS_VER}_${ARCH}.tgz" "${DATA_DIR}/.ts.tgz"; then
        tar xzf "${DATA_DIR}/.ts.tgz" -C "${DATA_DIR}" && \
        cp -f "${DATA_DIR}/tailscale_${TS_VER}_${ARCH}/tailscaled" "${DATA_DIR}/tailscale_${TS_VER}_${ARCH}/tailscale" "${DEST}/" 2>/dev/null && \
        rm -rf "${DATA_DIR}/tailscale_${TS_VER}_${ARCH}" && rm -f "${DATA_DIR}/.ts.tgz"
    fi
}

while true; do
    sleep "${UPDATE_INTERVAL:-21600}"
    run_update
    # 重新拉起（main 会优先用新版二进制；与 updater 同目录）
    MAIN="$(dirname "$(readlink -f "$0")")/main"
    [ -x "$MAIN" ] && "$MAIN" stop && "$MAIN" start
done
