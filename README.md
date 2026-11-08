# FastVPN-Astro-ProxyPool

来源：`com.fast.vpn.secure.unblock.proxy_v2.1.5_Mod.apk`（Alestrasol / astroapps 白标 VPN，com.fast.vpn.secure.unblock.proxy）。

完整还原其节点下发协议与三层加密，产出可直接入池的 shadowsocks / SS+v2ray-plugin / OpenVPN 节点集合。

> ⚠️ 仅供安全研究与协议学习。所有凭据均提取自该 APK 的公开分发版本。

## 状态表

| 模块 | 状态 | 说明 |
|---|---|---|
| 上游 API 还原 | ✅ 已验证 | `GET https://avapi.astroapps.io/api/getNewServers`，header `key: poi_…P1AA` |
| 三层密钥链 | ✅ 已验证 | native getAK/getEK → AES-256-GCM 解出 API key → 节点字段 AES-256-CBC |
| 收割器 | ✅ 已验证 | `tools/harvest_fastvpn.py` 端到端跑通，重复调用无频控 |
| 代理级真实测活 | ✅ 已验证 | xray 本地隔离实例完整 SS-AEAD 握手 + HTTP 204：**SS 8/9 存活** |
| sing-box / ss:// 输出 | ✅ 已验证 | 13 个 sing-box outbound + 10 条 ss:// 链接 |
| OpenVPN 节点 | ⚠️ 待实测 | 35 份完整配置（证书内嵌免 auth），UDP 静默，需真实客户端验证 |
| demo server | ✅ 已验证 | 127.0.0.1:9099，5 端点全 200 |
| new-api 渠道对接 | 📄 文档就绪 | 见 `docs/NEWAPI_INTEGRATION.md`（自包含，可交另一会话执行） |

## 快照节点构成（2026-11-09）

| 协议 | 数量 | 真实测活 | 备注 |
|---|---|---|---|
| shadowsocks (chacha20-ietf-poly1305) | 9 | 8/9 ✅ | 443 端口 |
| "v2ray"（实为 SS + v2ray-plugin ws+tls） | 3 | 1/3 TLS OK | host=domain（加密），path=明文 |
| openvpn (UDP, tls-crypt) | 35 | TCP 不可达 | 证书内嵌无 auth-user-pass，待实连 |
| premium/free | 25/22 | — | 字段结构完全一致，服务端未区分下发 |

## 协议速查

```
API        GET https://avapi.astroapps.io/api/getNewServers
鉴权       header "key: <EK解密结果>"
节点加密    AES-256-CBC  key=47DEQpj8HBSa+/TImW+5JCeuQeRkm5NM  iv=x3VmCsrqXavLbbps
           （16B 短密文无 PKCS5，按尾字节剥 pad；纯 IP 字段为明文不加密）
API key 加密 AES-256-GCM  key=getAK(16B:3c1256a97e1139bc1d42584f61121317)
           + 79134290 + a11f3e7a + c05da329 + 61771920 (concat = 32B)
           EK 密文前 12B = IV，末 16B = tag
"v2ray" 节点 = SS + v2ray-plugin; opts: mode=websocket;tls;host=<domain解密>;path=<path明文>
```

## 使用

```bash
pip install pycryptodome

# 收割 + 解密 + 产出（servers_decrypted.json / singbox_all_nodes.json / ss_links.txt / ovpn/）
python tools/harvest_fastvpn.py .

# demo（仅 127.0.0.1，不触碰系统代理）
python demo_server.py
#   GET /                  状态页（协议分布 / 测活标注）
#   GET /api/servers       全量节点 JSON
#   GET /api/singbox       sing-box outbound 片段
#   GET /api/ss            ss:// 分享链接
#   GET /api/ovpn/<city>   单个 OpenVPN 配置
```

## 接入线上代理池

1. SS 节点直接可用：`singbox_all_nodes.json`（clash / sing-box 兼容）
2. 周期刷新：cron 调 `harvest_fastvpn.py`，API 无频控迹象
3. new-api 侧对接：**看 `docs/NEWAPI_INTEGRATION.md`**，含二轮测活铁律（只认真实出口 IP）
4. OpenVPN 部分：需 openvpn 客户端或 Android 模拟器实测后决定是否入池

## 同批 APK 判定

| APK | 结论 |
|---|---|
| **fast.vpn v2.1.5** ⭐ | 唯一金矿：API 活、密钥全静态、无频控，直接入池 |
| TunnelBear 5.0.10 | ScKit 壳；老 API 全线 410，新 API `api.polargrizzly.com` 401 需 Bearer（R2 需模拟器 Frida hook TokenAuthPlugin） |
| 7NET v5.6 | v2rayNG 换皮（2dust 全套字符串），节点用户自填，无价值 |
| Opera 103.3 | 内置 VPN = tunnel.googlezip.net + cdnbroker.opera.com，需浏览器 token，仅 ~3 区域，价值低 |

## 目录结构

```
├── README.md                  # 本文件
├── tools/
│   └── harvest_fastvpn.py     # 收割器（含完整密钥链文档头）
├── demo_server.py             # 本地 demo（127.0.0.1:9099）
├── servers_decrypted.json     # 全量节点（已解密快照）
├── singbox_all_nodes.json     # sing-box outbound 片段
├── ss_links.txt               # ss:// 分享链接
├── ovpn/                      # 35 份 OpenVPN 配置
└── docs/
    ├── REVERSE_REPORT.md      # 完整逆向报告
    └── NEWAPI_INTEGRATION.md  # new-api 对接交接文档（自包含）
```
