# -*- coding: utf-8 -*-
"""把 mitmproxy 的 flows.dump 导出成 JSON（含完整请求头）"""
import json
import os

from mitmproxy.io import FlowReader

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(HERE, "flows.dump")

out = []
if os.path.exists(DUMP):
    with open(DUMP, "rb") as f:
        for flow in FlowReader(f).stream():
            out.append({
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "headers": dict(flow.request.headers),
                "body": (flow.request.get_text(strict=False) or "")[:2000],
                "status": flow.response.status_code if flow.response else None,
            })
print(json.dumps(out, ensure_ascii=False, indent=1))
