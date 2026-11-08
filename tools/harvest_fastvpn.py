#!/usr/bin/env python3
"""FastVPN (com.fast.vpn.secure.unblock.proxy) 节点收割器.

上游 API: https://avapi.astroapps.io/api/getNewServers
鉴权: HTTP header `key: <EK>`; EK 由 native 层 getEK() 返回的密文经 AES-256-GCM 解出.

静态密钥链 (从 APK v2.1.5 提取, 全部硬编码, 无设备绑定):
  - getAK()    -> 3c1256a97e1139bc1d42584f61121317 (16B, libnative-lib.so .rodata 0x540)
  - GCM key    = AK || 79134290 || a11f3e7a || c05da329 || 61771920 (32B AES-256)
  - getEK()    -> tpPEcc4XmUavOyKkwDfc5cmA+nxFimNi7E/a94lYd8QH/eOxwS0KWz1OJPYbmdaDJkJwAL4Z6KmM4m/abD5QUXyzZgg=
  - CryH.dK()  -> AES-256-GCM (IV=密文前12B, tag=末16B) -> "poi_xYCJzovnpEKX4CEWPrHSLme2pMfmGe3lP1AA"
  - 节点字段   -> AES-256-CBC key=47DEQpj8HBSa+/TImW+5JCeuQeRkm5NM iv=x3VmCsrqXavLbbps (AppModule.SECRET_KEY/IV)

节点协议:
  - shadowsocks: chacha20-ietf-poly1305, ipaddress+port, password 解密
  - v2ray(实为 SS+v2ray-plugin ws+tls): domain/path 解密(或 path 明文), password 解密
  - openvpn: server_content 解密后是完整 .ovpn 配置 (proto udp + tls-crypt)
"""
import base64
import json
import sys
import urllib.request

API_URL = "https://avapi.astroapps.io/api/getNewServers"
API_KEY = "poi_xYCJzovnpEKX4CEWPrHSLme2pMfmGe3lP1AA"  # CryH.dK(getEK()) 静态解出

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    sys.exit("需要 pycryptodome: pip install pycryptodome")

CBC_KEY = b"47DEQpj8HBSa+/TImW+5JCeuQeRkm5NM"
CBC_IV = b"x3VmCsrqXavLbbps"


def dec_field(s: str) -> str:
    """ExtensionsKt.b 等价实现: AES-256-CBC/PKCS5.

    16B 短密文(如 SS password)服务端无 PKCS5 padding, 需按 PaddingMode.NONE 处理.
    """
    if not s:
        return ""
    raw = AES.new(CBC_KEY, AES.MODE_CBC, CBC_IV).decrypt(base64.b64decode(s))
    if len(base64.b64decode(s)) == 16:
        # 无 padding 整块: 16B 密文解出 16B 明文中尾部是自定义 pad (观察为 0x04..0x07 连续重复)
        pad = raw[-1]
        if 0 < pad <= 16 and raw.endswith(bytes([pad]) * pad):
            raw = raw[:-pad]
        return raw.decode("utf-8", "replace").strip()
    return unpad(raw, 16).decode("utf-8")


def fetch_servers() -> list:
    req = urllib.request.Request(API_URL, headers={"key": API_KEY, "User-Agent": "okhttp/4.12.0"})
    body = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if body.get("code") != 200:
        raise RuntimeError(f"API 返回异常: {body}")
    return body["data"]


def decrypt_all(servers: list) -> list:
    import re
    ip_re = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
    out = []
    for s in servers:
        r = dict(s)
        # 纯 IP 字段本身就是明文, 不做 base64 解密 (保留原值)
        if r.get("ipaddress") and ip_re.match(r["ipaddress"]):
            pass
        for field in ("ipaddress", "domain", "password", "server_content", "encryption"):
            if not s.get(field):
                continue
            try:
                r[field] = dec_field(s[field])
                if field == "password":
                    r["password_raw"] = s["password"]
                if field == "encryption":
                    r["method"] = r["encryption"]
            except Exception as e:  # noqa: BLE001
                r["_dec_err_" + field] = str(e)
        out.append(r)
    return out


def to_singbox(servers: list) -> list:
    """转 sing-box outbound 格式; v2ray 协议按 yt.x() 逻辑拼 v2ray-plugin."""
    nodes = []
    for s in servers:
        proto = s.get("protocol")
        if proto == "shadowsocks":
            nodes.append({
                "type": "ss", "tag": s.get("city_name", "ss"),
                "server": s["ipaddress"], "server_port": s["port"],
                "method": s.get("method", "chacha20-ietf-poly1305"),
                "password": s["password"],
            })
        elif proto == "v2ray" and s.get("domain") and s.get("path"):
            nodes.append({
                "type": "ss", "tag": f"{s.get('city_name')}-v2p",
                "server": s["domain"], "server_port": s["port"],
                "method": s.get("method", "chacha20-ietf-poly1305"),
                "password": s["password"],
                "plugin": "v2ray-plugin",
                "plugin_opts": f"mode=websocket;tls;host={s['domain']};path={s['path']}",
            })
    return nodes


def to_ss_links(servers: list) -> list:
    import urllib.parse
    links = []
    for s in servers:
        if s.get("protocol") == "shadowsocks" and s.get("password") and not s.get("_dec_err_password"):
            ui = base64.urlsafe_b64encode(f"{s.get('method', 'chacha20-ietf-poly1305')}:{s['password']}".encode()).decode().rstrip("=")
            links.append(f"ss://{ui}@{s['ipaddress']}:{s['port']}#{urllib.parse.quote(s['city_name'])}")
    return links


if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    servers = decrypt_all(fetch_servers())
    json.dump(servers, open(f"{outdir}/servers_decrypted.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(to_singbox(servers), open(f"{outdir}/singbox_all_nodes.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    links = to_ss_links(servers)
    open(f"{outdir}/ss_links.txt", "w", encoding="utf-8").write("\n".join(links) + "\n")
    print(f"servers={len(servers)} ss_links={len(links)} -> {outdir}")
