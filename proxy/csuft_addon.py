"""mitmproxy addon: CSUFT 平安打卡 抓包 + 定位改写 (只对 simp.csuft.edu.cn 生效)"""
import hashlib
import json
import os
import time

from mitmproxy import http

BASE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE, "traffic.jsonl")
STATE = os.path.join(BASE, "state.json")
TARGET = "simp.csuft.edu.cn"
FORCE_ACCURACY = "999999999"
MAXLOG = 8000


def _log(kind, payload):
    payload = dict(payload)
    payload["_kind"] = kind
    payload["_ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def _jsnum(x):
    """近似 JS Number.toString()"""
    if isinstance(x, str):
        return x
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return repr(x)


def request(flow: http.HTTPFlow) -> None:
    if TARGET not in flow.request.pretty_host:
        return
    path = flow.request.path
    try:
        body = flow.request.get_text(strict=False)
    except Exception:
        body = ""
    _log("request", {
        "method": flow.request.method,
        "url": flow.request.pretty_url,
        "token": flow.request.headers.get("FlySource-Auth", ""),
        "sign": flow.request.headers.get("FlySource-sign", ""),
        "content_type": flow.request.headers.get("Content-Type", ""),
        "body": (body or "")[:MAXLOG],
    })

    if "/dormSignRecord/stuSign" in path or "/dormSignRecord/stuLateSign" in path:
        _rewrite_sign(flow, body or "")


def _rewrite_sign(flow, body):
    st = _load_state()
    lat_s, lng_s = st.get("dormLat"), st.get("dormLng")
    if not lat_s or not lng_s:
        _log("rewrite-skip", {"reason": "no dorm coords yet", "url": flow.request.pretty_url})
        return
    try:
        data = json.loads(body)
    except Exception as exc:
        _log("rewrite-skip", {"reason": "body is not json: %s" % exc})
        return

    lat, lng = float(lat_s), float(lng_s)
    data["signLat"] = lat
    data["signLng"] = lng
    data["locationAccuracy"] = 0
    md5_input = json.dumps({
        "latitude": _jsnum(lat_s),
        "longitude": _jsnum(lng_s),
        "locationAccuracy": "0",
        "signDate": data.get("signDate", ""),
        "taskId": data.get("taskId", ""),
        "fileId": data.get("fileId") or "",
    }, separators=(",", ":"), ensure_ascii=False)
    data["stuTaskId"] = hashlib.md5(md5_input.encode("utf-8")).hexdigest()

    new_body = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    flow.request.set_text(new_body)
    _log("rewrite-request", {
        "url": flow.request.pretty_url,
        "md5_input": md5_input,
        "new_body": new_body[:MAXLOG],
    })


def response(flow: http.HTTPFlow) -> None:
    if TARGET not in flow.request.pretty_host:
        return
    try:
        text = flow.response.get_text(strict=False)
    except Exception:
        text = ""
    _log("response", {
        "url": flow.request.pretty_url,
        "status": flow.response.status_code,
        "body": (text or "")[:MAXLOG],
    })

    if "getTaskByIdForApp" not in flow.request.path:
        return
    try:
        payload = json.loads(text)
    except Exception:
        return
    data = payload.get("data") or {}
    dorm = data.get("dormitoryRegisterVO") or {}
    if dorm.get("locationLat") and dorm.get("locationLng"):
        st = _load_state()
        st.update({
            "dormLat": dorm.get("locationLat"),
            "dormLng": dorm.get("locationLng"),
            "dormName": dorm.get("dormName"),
            "roomId": dorm.get("roomId"),
            "taskName": data.get("taskName"),
            "server_locationAccuracy": data.get("locationAccuracy"),
        })
        _save_state(st)
        _log("dorm-coords", st)
    orig = data.get("locationAccuracy")
    data["locationAccuracy"] = FORCE_ACCURACY
    payload["data"] = data
    flow.response.set_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    _log("rewrite-task-response", {"orig_locationAccuracy": orig, "forced": FORCE_ACCURACY})
