# -*- coding: utf-8 -*-
"""查最近几天/整月的打卡状态（只读）"""
import json
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import checkin as C  # noqa: E402

c = C.cfg()
token = c["token"]

if len(sys.argv) > 1 and sys.argv[1] == "--month":
    month = datetime.now().strftime("%Y-%m")
    r = C.api("/api/flySource-yxgl/dormSignRecord/getUserListAppByMonth?taskId=%s&month=%s" % (c["taskId"], month), token=token)
    for day in sorted((r.get("data") or {}).keys()):
        d = r["data"][day]
        print(day, d.get("signStatusName"), "(可补签)" if d.get("isAllowLate") else "")
else:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    for i in range(days):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        r = C.api("/api/flySource-yxgl/dormSignRecord/getOne?taskId=%s&signDate=%s" % (c["taskId"], d), token=token)
        data = r.get("data") or {}
        print(d, "->", json.dumps({k: data.get(k) for k in ["signStatusName", "signTime", "isLateSign"]}, ensure_ascii=False))
