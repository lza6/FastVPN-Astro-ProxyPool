#!/usr/bin/env python3
"""FastVPN-Astro 本地 demo server.

端点:
  GET /                  -> 状态页 (节点总数/协议分布/测活结果)
  GET /api/servers       -> 全量节点 JSON (解密后)
  GET /api/singbox       -> sing-box outbound 片段 (可直接并入配置)
  GET /api/ss            -> ss:// 分享链接列表
  GET /api/ovpn/<city>   -> 单个 OpenVPN 配置文件
  POST /api/refresh      -> 触发上游收割 (harvest_fastvpn.fetch_servers)

端口 9099, 仅监听 127.0.0.1. 不设置任何系统代理, 不影响本机 v2ray.
"""
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
PORT = 9099


def load(name, default=None):
    p = os.path.join(ROOT, name)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8", errors="replace"))
    return default


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/":
            servers = load("servers_decrypted.json", [])
            proto = {}
            for s in servers:
                proto[s.get("protocol")] = proto.get(s.get("protocol"), 0) + 1
            live = load("probe_results.json", {})
            rows = "".join(
                f"<tr><td>{s.get('city_name','')}</td><td>{s.get('country_name','')}</td>"
                f"<td>{s.get('protocol')}</td><td>{'premium' if s.get('type')=='premium' else 'free'}</td>"
                f"<td>{s.get('ipaddress') or s.get('domain')}</td><td>{s.get('port')}</td>"
                f"<td>{live.get(s.get('city_name',''), '-')}</td></tr>"
                for s in servers
            )
            html = f"""<!doctype html><html><head><meta charset="utf-8"><title>FastVPN-Astro Node Pool</title>
<style>body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #334155;padding:6px 10px;text-align:left}}
th{{background:#1e293b}}h1{{font-size:20px}}.stat{{display:inline-block;background:#1e293b;padding:8px 16px;border-radius:8px;margin-right:12px}}</style></head>
<body><h1>FastVPN (astroapps) 节点池 demo</h1>
<p><span class="stat">总计 {len(servers)}</span>{''.join(f'<span class="stat">{k}: {v}</span>' for k,v in proto.items())}</p>
<p><a href="/api/servers" style="color:#7dd3fc">/api/servers</a> · <a href="/api/singbox" style="color:#7dd3fc">/api/singbox</a> · <a href="/api/ss" style="color:#7dd3fc">/api/ss</a> · <a href="/api/ovpn/Amsterdam" style="color:#7dd3fc">/api/ovpn/&lt;city&gt;</a></p>
<table><tr><th>城市</th><th>国家</th><th>协议</th><th>类型</th><th>地址</th><th>端口</th><th>测活</th></tr>{rows}</table></body></html>"""
            self._send(200, html, "text/html; charset=utf-8")
        elif u.path == "/api/servers":
            self._send(200, json.dumps(load("servers_decrypted.json", []), ensure_ascii=False))
        elif u.path == "/api/singbox":
            self._send(200, json.dumps(load("singbox_all_nodes.json", []), ensure_ascii=False))
        elif u.path == "/api/ss":
            links = open(os.path.join(ROOT, "ss_links.txt"), encoding="utf-8").read().splitlines() if os.path.exists(os.path.join(ROOT, "ss_links.txt")) else []
            self._send(200, "\n".join(links), "text/plain; charset=utf-8")
        elif u.path.startswith("/api/ovpn/"):
            city = urllib.parse.unquote(u.path.split("/")[-1])
            p = os.path.join(ROOT, "ovpn", f"{city}.ovpn")
            if os.path.exists(p):
                self._send(200, open(p, encoding="utf-8").read(), "text/plain; charset=utf-8")
            else:
                self._send(404, '{"error":"not found"}')
        else:
            self._send(404, '{"error":"not found"}')

    def log_message(self, fmt, *args):  # 静默
        pass


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"demo server on http://127.0.0.1:{PORT}/ (仅本机, 不碰系统代理)")
    srv.serve_forever()
