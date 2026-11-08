# FastVPN (astroapps) 逆向报告

日期：2026-11-09 ｜ 目标：`com.fast.vpn.secure.unblock.proxy` v2.1.5 (Mod)

## 1. 应用画像

| 项 | 值 |
|---|---|
| 包名 | com.fast.vpn.secure.unblock.proxy |
| 厂商 | Alestrasol（后端 astroapps.io / 8-lives-cat.io，白标系） |
| 内核 | OpenVPN (libopenvpn) + Shadowsocks (libsslocal) + tun2socks + libredsocks |
| 节点下发 | 运行时 API JSON，无本地静态节点 |
| 订阅/计费 | RevenueCat |
| 鉴权模式 | OkHttp 拦截器注入 header，key 由 native 层下发 |

## 2. 逆向路径

### 2.1 端点定位

dex 直接抠 URL（jadx 反编译 `com/alestrasol/vpn` 包，无壳无混淆）：

```
BASE_URL   = https://avapi.astroapps.io/api/         (AppModule)
Retrofit   @GET("getNewServers")  @Header("key")    (GetServerListInter)
           @GET("findMe")         用户定位
           @POST("saveUserFeedback")
付费后端    https://api-production.8-lives-cat.io/  (RevenueCat proxy)
IP 探测     https://ipwho.is/  https://ipinfo.io/json
```

### 2.2 三层密钥链（全静态，无设备绑定）

```
[1] native libnative-lib.so (45KB, arm64)
    getEK() @0x7d4 → 返回 base64 密文 (adr 指向 .rodata 0x550):
      tpPEcc4XmUavOyKkwDfc5cmA+nxFimNi7E/a94lYd8QH/eOxwS0KWz1OJPYbmdaDJkJwAL4Z6KmM4m/abD5QUXyzZgg=
    getAK() @0x740 → NEON 常量池 0x540 读 16B:
      3c1256a97e1139bc1d42584f61121317

[2] AeK.k(): GCM key = getAK() ‖ {121,19,66,-112} ‖ {-95,31,62,122} ‖ {-64,93,-93,41} ‖ {97,119,25,32}
    = 32B AES-256 key: 3c1256a97e1139bc1d42584f6112131779134290a11f3e7ac05da32961771920

[3] CryH.dK(): AES-256-GCM, IV=密文前12B, tag=末16B
    → poi_xYCJzovnpEKX4CEWPrHSLme2pMfmGe3lP1AA   ← 这就是 API "key" header 的值

[4] 节点字段解密 ExtensionsKt.b(): AES-256-CBC/PKCS5
    key=AppModule.SECRET_KEY=47DEQpj8HBSa+/TImW+5JCeuQeRkm5NM
    iv =AppModule.SECRET_IV =x3VmCsrqXavLbbps
    特例: SS password 等 16B 短密文无 PKCS5, 尾部是自定义重复 pad (0x04..0x07), 按尾字节剥
    特例: 纯 IP 字段(ipaddress 大部分)是明文, 不做 base64
```

### 2.3 节点协议组装（yt.x()）

| API protocol | 真实协议 | 关键字段 |
|---|---|---|
| `shadowsocks` | SS AEAD | ipaddress(明文/加密) + port + encryption(解密=method) + password(解密) |
| `v2ray` | **SS + v2ray-plugin(ws+tls)** | domain(解密=host) + path(**明文!** 不走 ExtensionsKt.b) + password(解密) |
| `openvpn` | OpenVPN UDP | server_content(解密=完整 .ovpn, 证书内嵌 `<ca><cert><key><tls-crypt>`, 无 auth-user-pass) |

plugin_opts 拼装：`v2ray-plugin;mode=websocket;tls;host=<domain>;path=<path>`

## 3. 实测验证

- API 请求（header `key`）：200，47 节点（25 premium / 22 free，字段结构一致，服务端未区分下发）
- 重复请求无频控
- SS 9 台经 xray 本地隔离实例（127.0.0.1:21001-21009）完整 SS-AEAD 握手 + gstatic 204：
  **8/9 存活**（New York 超时）。延迟 374ms~7.5s
- v2ray-plugin 3 台 TLS 握手：Madrid(surgevpn.app) OK 763ms；Manchester/Rotterdam(hwssolutions.com) TLS 握手被断
- OpenVPN 35 台：TCP 全关（配置 proto udp 为主），UDP 静默符合 OpenVPN 行为，需真实客户端实连

## 4. 与旧白标样本的关联

- `surgevpn.app` 域名与 Bee VPN / Surge VPN 系（M0D 以前样本）同后端家族
- 节点 IP 段 108.181.x / 67.220.x / 134.195.x / 38.99.x / 136.176.x / 208.69.x 高度集中（ColoCrossing 系机房）
- 与 2026-10-28 VPN-US 样本（gp/se 池）无重叠

## 5. 遗留（R2 候选）

1. OpenVPN 35 台实连验证（openvpn 客户端 / 模拟器）
2. `findMe` / `saveUserFeedback` 端点行为
3. 同族其他白标（Bee VPN、Stag VPN 等 30+ 包名）大概率共用此 API 与密钥链——批量收割思路已写入 skill
