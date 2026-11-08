# new-api 代理池对接文档 — FastVPN-Astro 节点源

> 本文档自包含：执行会话无需任何前情上下文，按顺序照做即可。
> 来源仓库：https://github.com/lza6/FastVPN-Astro-ProxyPool

## 0. 你将得到什么

| 资产 | 位置 | 说明 |
|---|---|---|
| 收割器 | `tools/harvest_fastvpn.py` | 拉 API + 解密 + 产出 sing-box/ss://，需 `pip install pycryptodome` |
| SS 节点 ×9（8 活） | `ss_links.txt` / `singbox_all_nodes.json` | chacha20-ietf-poly1305，443 端口 |
| SS+v2ray-plugin ×3 | `singbox_all_nodes.json`（tag 带 `-v2p`） | ws+tls，Madrid 已验 TLS |
| OpenVPN ×35 | `ovpn/*.ovpn` | 免认证（证书内嵌），**未实连验证，先不入生产池** |
| demo | `demo_server.py` | 127.0.0.1:9099，`/api/singbox` 直接给 sing-box 片段 |

API key（收割器已内置，如需单独引用）：

```
上游:  GET https://avapi.astroapps.io/api/getNewServers
鉴权:  header "key: poi_xYCJzovnpEKX4CEWPrHSLme2pMfmGe3lP1AA"
UA 必须带: okhttp/4.12.0 (无 UA 会 403)
```

## 1. 总原则（铁律，勿绕过）

1. **严禁触碰本机 v2rayN/xray 的系统代理（127.0.0.1:10808）**。所有测活必须走**独立 xray/sing-box 实例**（独立端口 + `127.0.0.1` 监听），历史教训：借系统代理测节点延迟正常但测速零延迟，流量被代理层污染。
2. **二轮测活只认真实出口 IP**：第一轮 TCP/TLS 握手筛选 → 第二轮必须经代理请求 IP 归属接口（如 `https://ipwho.is/`），比对出口国家与节点宣称国家，不一致即弃。
3. **new-api 共享代理池已有铁律**：`proxy_pool.go` 的 LoadProxies / TraceProbes 只探测 `source==free` 的记录——本源节点 type 字段虽有 premium，但 API 实际全量同结构下发，入池时统一标 `source=free`。
4. 禁止把未通过二轮测活的节点写入生产池；禁止在生产主机上跑收割/压测。

## 2. 路线 A（推荐）：SS 直入 new-api 共享代理池

适用：new-api 的代理池调度（Acquire/Release 接口）。

```text
步骤:
 1. 在本机(或任一测试机)跑: python tools/harvest_fastvpn.py <输出目录>
    产出 singbox_all_nodes.json (13 nodes)
 2. 起 sing-box/xray 隔离实例加载这些 outbound:
    - sing-box: 直接并入 config.outbounds, 加 clash-api 或每 outbound 一个 socks inbound
    - xray(仅支持裸 SS, 不支持 v2ray-plugin): 用仓库根 xray_probe_config.json 的模式,
      每 SS 一个 socks inbound (21001+i), routing 按 inboundTag 分流
 3. 二轮测活脚本(参考 VPN-US 仓库 tools/probe_socks 的逻辑):
    for each socks port: 经其请求 https://ipwho.is/ → 校验 exit IP 国家 ∈ {宣称国家} → 记录延迟
 4. 活节点写入 new-api 共享代理池(与现有 gp/se 池同表同 schema), 标注:
    source=free, protocol=shadowsocks, origin=fastvpn-astro
 5. 定时刷新: cron/计划任务 每 6h 重跑 harvest + 测活, 增量 upsert
```

sing-box outbound 样例（仓库 `/api/singbox` 同款）：

```json
{
  "type": "ss",
  "tag": "Amsterdam II",
  "server": "108.181.122.170",
  "server_port": 443,
  "method": "chacha20-ietf-poly1305",
  "password": "CJmTCCx7Ltud"
}
```

v2ray-plugin 变体（仅 sing-box 支持）：

```json
{
  "type": "ss",
  "tag": "Madrid-v2p",
  "server": "spain.surgevpn.app",
  "server_port": 443,
  "method": "chacha20-ietf-poly1305",
  "password": "53879d9f6e24590a5a01ab7d628010071ad765cfaadf6346",
  "plugin": "v2ray-plugin",
  "plugin_opts": "mode=websocket;tls;host=spain.surgevpn.app;path=/cc5cbb935a2d3bc3676dbdcb"
}
```

## 3. 路线 B：OpenVPN 桥接（可选，验证后再做）

35 份 `.ovpn` 免用户名密码（证书内嵌），但**未实测连通**（UDP 静默）：

```text
1. 找一台有 openvpn 客户端的机器: openvpn --config ovpn/Amsterdam.ovpn --verb 3
   (Windows: OpenVPN GUI 导入即可; Linux: apt install openvpn)
2. 若握手成功: tun 设备起一个本地 socks 桥 (参考 VPN-US 仓库 tools/tcpfwd 思路)
3. 二轮测活通过才入池; 失败则整组放弃 (35 台同机房, 大概率同状态)
```

## 4. 已知坑（勿重复踩）

| 坑 | 说明 |
|---|---|
| 无 UA 请求 403 | 上游 Cloudflare 层校验 UA，必须 `okhttp/4.12.0` |
| 16B 短密文解密报 padding 错 | 服务端没按 PKCS5 填充，收割器已按尾字节剥 pad 处理，勿自己重写解密 |
| `ipaddress` 字段部分明文部分密文 | 纯 IP 正则判断跳过解密，收割器已内置 |
| Chicago/New York SS 时快时慢 | 二轮测活带重试，连续 2 次失败才弃 |
| hwssolutions.com 两台 v2ray-plugin | TLS 握手被断（可能是 SNI 检测），默认弃用，除非后续复测转好 |
| xray 不支持 v2ray-plugin outbound | 测 v2ray-plugin 节点必须用 sing-box |
| JSON 落盘 | 一律 `encoding='utf-8'`，Windows 默认 GBK 会写坏 Querétaro 等城市名 |

## 5. 验收清单（执行会话完成标准）

- [ ] 收割器在本机跑通，产出 4 类文件
- [ ] 隔离 xray/sing-box 实例启动（netstat 确认只听 127.0.0.1 且端口未与 10808 冲突）
- [ ] ≥7 台 SS 通过二轮测活（出口 IP 与宣称国家一致）
- [ ] 节点已写入 new-api 共享代理池（source=free, origin=fastvpn-astro）
- [ ] 定时刷新任务已配置
- [ ] 测试用临时实例/进程全部清理（按端口精确匹配杀，勿模糊匹配杀到其他项目 demo）
