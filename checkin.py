# -*- coding: utf-8 -*-
"""中南林业科技大学 平安打卡 —— 直连接口自动签到（失败会弹窗报警，绝不静默）

用法:
  python checkin.py --status        只查今天状态
  python checkin.py --now           立刻签到（仅 20:30-22:30 有效）
  python checkin.py --wait          等到配置的随机时刻再签到（计划任务用这个）
  python checkin.py --test-notify   预览成功/失败弹窗长什么样
"""
import argparse
import base64
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
LOG = os.path.join(HERE, "checkin.log")
STATUS_FILE = os.path.join(HERE, "LATEST-STATUS.txt")
FAIL_DIR = os.path.join(HERE, "failures")

BASE = "https://simp.csuft.edu.cn"
CLIENT_ID = "flysource_wise_wxapp"
CLIENT_SECRET = "DA788asdUDjnasd_flysource_wxappdsdadDAIUiuwqe"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/144.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
      "MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) "
      "UnifiedPCWindowsWechat(0xf2541d0c) XWEB/25510")

EXIT_OK = 0
EXIT_FAIL = 2


# ---------- 基础设施 ----------

def log(msg):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_status(ok, text):
    mark = "OK " if ok else "FAIL"
    line = "%s  [%s]  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), mark, text)
    try:
        with open(STATUS_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def notify(title, message, seconds):
    """Windows 弹窗：seconds=0 表示必须手动关掉（失败用），>0 自动消失（成功用）"""
    icon = 48 if seconds == 0 else 64  # 48=警告, 64=信息
    safe = message.replace("'", "''")
    safe_title = title.replace("'", "''")
    ps = ("$ws = New-Object -ComObject WScript.Shell; "
          "[void]$ws.Popup('%s', %d, '%s', %d)" % (safe, seconds, safe_title, icon))
    for exe in ("powershell.exe", "pwsh.exe"):
        try:
            subprocess.Popen([exe, "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                             close_fds=True)
            return True
        except Exception:
            continue
    return False


def alarm(title, message):
    """失败：弹窗不自动关 + 写失败标记 + 写状态文件 + 非零退出"""
    log("!!! 失败: %s" % message)
    notify(title, message + "\n\n日志: checkin.log", 0)
    os.makedirs(FAIL_DIR, exist_ok=True)
    try:
        with open(os.path.join(FAIL_DIR, "%s.txt" % datetime.now().strftime("%Y-%m-%d")),
                  "w", encoding="utf-8") as f:
            f.write("%s\n%s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message))
    except Exception:
        pass
    write_status(False, message)


def info(title, message):
    log("成功: %s" % message)
    notify(title, message, 25)
    write_status(True, message)


# ---------- 接口 ----------

def md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def cfg():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def api(path_with_query, method="GET", payload=None, token=None, timeout=30):
    path = path_with_query.split("?")[0]
    ts = str(int(time.time() * 1000))
    headers = {
        "Authorization": "Basic " + base64.b64encode(("%s:%s" % (CLIENT_ID, CLIENT_SECRET)).encode()).decode(),
        "FlySource-sign": md5(path + "?sign=" + md5(ts + token)) + "1." + base64.b64encode(ts.encode()).decode(),
        "FlySource-Auth": token,
        "Content-Type": "application/json",
        "Accept": "*/*",
        "xweb_xhr": "1",
        "User-Agent": UA,
        "Referer": "https://servicewechat.com/wx0e47c34c9982aa09/7/page-frame.html",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(BASE + path_with_query, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            body.setdefault("_http", exc.code)
            return body
        except Exception:
            return {"success": False, "code": exc.code, "msg": "HTTP %s" % exc.code}
    except Exception as exc:
        return {"success": False, "code": -1, "msg": "网络错误: %s" % exc}


def brief(obj, n=280):
    try:
        return json.dumps(obj, ensure_ascii=False)[:n]
    except Exception:
        return str(obj)[:n]


def get_task(c, token):
    return api("/api/flySource-yxgl/dormSignTask/getTaskByIdForApp?taskId=" + c["taskId"], token=token)


def get_record(c, token):
    return api("/api/flySource-yxgl/dormSignRecord/getOne?taskId=" + c["taskId"], token=token)


def signed_already(rec):
    data = rec.get("data") or {}
    if data.get("signTime"):
        return True
    try:
        return int(data.get("signStatus")) == 1
    except Exception:
        return False


def need_sign(rec):
    data = rec.get("data") or {}
    if signed_already(rec):
        return False
    try:
        return int(data.get("signStatus")) == 3
    except Exception:
        return "未签" in str(data.get("signStatusName") or "")


def do_sign(c, token):
    t = get_task(c, token)
    if not t.get("success"):
        return False, "取任务失败: %s" % brief(t)
    d = t.get("data") or {}
    dorm = d.get("dormitoryRegisterVO") or {}
    lat = c.get("signLat") or dorm.get("locationLat")
    lng = c.get("signLng") or dorm.get("locationLng")
    if not lat or not lng:
        return False, "任务里没有宿舍基准坐标，无法定位"
    sign_date = datetime.now().strftime("%Y-%m-%d")
    md5_input = json.dumps({
        "latitude": str(lat), "longitude": str(lng), "locationAccuracy": "0",
        "signDate": sign_date, "taskId": c["taskId"], "fileId": "",
    }, ensure_ascii=False, separators=(",", ":"))
    body = {
        "taskId": c["taskId"], "scanType": d.get("scanType") or "",
        "roomId": dorm.get("roomId") or "", "isLateStuTakePhoto": d.get("isLateStuTakePhoto") or 0,
        "signLat": float(lat), "signLng": float(lng), "locationAccuracy": 0,
        "stuTaskId": md5(md5_input), "fileId": "", "signType": 0, "scanCode": "",
    }
    log("提交: 坐标 %s,%s (宿舍 %s, 距 0 米, 允许 %s 米)" % (lat, lng, dorm.get("dormName"), d.get("locationAccuracy")))
    r = api("/api/flySource-yxgl/dormSignRecord/stuSign", method="POST", payload=body, token=token)
    if not r.get("success"):
        code = r.get("code")
        msg = r.get("msg") or brief(r)
        if code == 401 or "登录" in str(msg):
            return False, "token 已失效（需要重新抓包更新 config.json）: %s" % msg
        return False, "服务端拒绝: %s" % msg
    return True, "服务端返回成功"


# ---------- 主流程 ----------

def run_sign(c, token, when_label):
    rec = get_record(c, token)
    if not rec.get("success"):
        if rec.get("code") == 401 or "登录" in str(rec.get("msg") or ""):
            alarm("平安打卡失败 —— token 失效", "token 已过期/失效，今晚没能打卡。\n请重新抓包更新配置。")
            return EXIT_FAIL
        log("状态查询失败（稍后重试）: %s" % brief(rec))
        return None
    if signed_already(rec):
        info("平安打卡", "今天已经打过卡了（%s），无需重复。" % (rec.get("data") or {}).get("signTime", ""))
        return EXIT_OK
    if not need_sign(rec):
        info("平安打卡", "今天状态是「%s」，服务器认为不需要打卡，已跳过。" % (rec.get("data") or {}).get("signStatusName"))
        return EXIT_OK

    ok, msg = do_sign(c, token)
    if not ok:
        log("第 %s 次提交失败: %s" % (when_label, msg))
        return False
    time.sleep(3)
    rec2 = get_record(c, token)
    if signed_already(rec2):
        info("平安打卡成功", "打卡成功并已复查确认。\n时间: %s\n坐标: 宿舍基准点 %s, %s" % (
            (rec2.get("data") or {}).get("signTime", ""), c.get("signLat"), c.get("signLng")))
        return EXIT_OK
    log("提交返回成功，但复查没查到记录: %s" % brief(rec2))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--test-notify", action="store_true")
    args = ap.parse_args()

    if args.test_notify:
        info("平安打卡测试", "这是「打卡成功」的样子（25 秒后自动消失）。")
        alarm("平安打卡测试", "这是「打卡失败」的样子（必须手动关闭，并且会留失败记录）。")
        return EXIT_OK

    c = cfg()
    token = c["token"]

    if args.status:
        log("今日状态: %s" % brief(get_record(c, token), 500))
        return EXIT_OK

    win = c.get("signWindow") or {"start": "21:05", "end": "21:25"}
    delay = c.get("retrySeconds", 180)

    if args.wait:
        now = datetime.now()
        h1, m1 = [int(x) for x in win["start"].split(":")]
        h2, m2 = [int(x) for x in win["end"].split(":")]
        start = now.replace(hour=h1, minute=m1, second=0, microsecond=0)
        end = now.replace(hour=h2, minute=m2, second=0, microsecond=0)
        lo = min(int((start - now).total_seconds()), int((end - now).total_seconds()))
        hi = max(int((end - now).total_seconds()), 0)
        if hi > 0:
            wait = random.randint(max(lo, 0), hi)
            target = now + timedelta(seconds=wait)
            log("将在 %s 打卡（窗口 %s-%s）" % (target.strftime("%H:%M:%S"), win["start"], win["end"]))
            time.sleep(wait)

    while True:
        now = datetime.now()
        if not args.now:
            window_open = now.replace(hour=20, minute=30, second=0, microsecond=0)
            window_close = now.replace(hour=22, minute=30, second=0, microsecond=0)
            if not (window_open <= now <= window_close):
                if now < window_open:
                    log("还没到打卡时间（20:30 开放），等待中")
                    time.sleep(min(300, (window_open - now).total_seconds()))
                    continue
                alarm("平安打卡失败 —— 错过时间窗",
                      "已经过了 22:30，今晚没能打卡（任务在窗口内全部尝试失败）。")
                return EXIT_FAIL

        try:
            result = run_sign(c, token, now.strftime("%H:%M:%S"))
        except Exception as exc:
            log("异常: %r" % exc)
            result = False
        if result == EXIT_OK:
            return EXIT_OK
        if result == EXIT_FAIL:
            return EXIT_FAIL

        now = datetime.now()
        if not args.now and now.replace(hour=22, minute=26, second=0, microsecond=0) <= now:
            alarm("平安打卡失败 —— 重试次数用尽",
                  "从 20:30 起多次尝试都没成功，打卡时间窗(22:30)即将结束。")
            return EXIT_FAIL
        log("%d 秒后重试" % delay)
        time.sleep(delay)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(EXIT_FAIL)
