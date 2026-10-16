# CSUFT 平安打卡 · 每晚自动签到

中南林业科技大学微信小程序「中南林学工」宿舍晚打卡的自动化脚本。

每天在指定时间窗口内自动提交打卡，**成功与失败都会弹窗通知，失败绝不静默**。

> ⚠️ 仅供学习交流。代打卡在多数高校属于违纪行为，使用后果自负。

---

## 工作原理

小程序打卡时会提交 `signLat` / `signLng`，服务端用它与**学校登记的宿舍基准点**算距离，
只要小于任务里的 `locationAccuracy`（误差半径）就算"在打卡范围内"。

本工具直接调用同一套接口，把坐标固定为宿舍基准点本身（距离 0 米），
并按客户端同样的规则生成 `stuTaskId`。

请求签名规则（客户端与服务端约定，只签 URL 路径与时间戳，不含请求体）：

```text
FlySource-sign = md5(urlPath + "?sign=" + md5(timestamp + token)) + "1." + base64(timestamp)
```

主要用到的接口：

| 接口 | 用途 |
|---|---|
| `/api/flySource-yxgl/dormSignTask/getTaskByIdForApp` | 取任务详情（含宿舍基准坐标、允许误差、时间窗） |
| `/api/flySource-yxgl/dormSignRecord/getOne` | 查某天打卡状态 |
| `/api/flySource-yxgl/dormSignRecord/stuSign` | 提交打卡 |

`stuTaskId` 规则：

```js
md5(JSON.stringify({ latitude, longitude, locationAccuracy, signDate, taskId, fileId: "" }))
```

---

## 环境

- Windows（弹窗通知用的是 WScript.Shell）
- Python 3.10+（只用标准库，无需 pip 安装任何东西）

## 快速开始

1. 复制 `config.example.json` 为 `config.json`，填好 `token` / `taskId` / 宿舍坐标：

```json
{
  "token": "eyJhbGciOi...",
  "taskId": "xxxxxxxx",
  "signLat": 28.xxxxxx,
  "signLng": 112.xxxxxx,
  "signWindow": { "start": "21:05", "end": "21:25" },
  "retrySeconds": 180
}
```

2. 常用命令：

```bash
python checkin.py --status       # 查今天状态（只读）
python checkin.py --now          # 立刻打卡（仅 20:30-22:30 有效）
python checkin.py --wait         # 等到 signWindow 内随机时刻再打卡（计划任务用）
python checkin.py --test-notify  # 预览成功/失败弹窗
python history.py 7              # 看最近 7 天状态
python history.py --month        # 看本月
```

3. 双击 `查看状态.cmd` 可以直接看最近结果、失败记录和日志尾部。

---

## 失败通知（不会静默丢失）

| 方式 | 说明 |
|---|---|
| 弹窗 | **必须手动关闭**，不会自动消失 |
| `LATEST-STATUS.txt` | 每次一行 `OK` / `FAIL` |
| `failures\<日期>.txt` | 失败按天留档，含原因 |
| 退出码 | 失败 = 2 |

窗口内（20:30–22:30）每 `retrySeconds` 秒重试一次，到 22:26 还没成功就报「重试次数用尽」。
另外 token 失效、服务端拒绝、网络异常、错过时间窗都会分别给出明确原因。

成功时弹窗 25 秒自动消失；当天已打卡或服务器标记无需打卡时不会重复提交。

---

## 挂到计划任务（每晚自动）

```powershell
$action  = New-ScheduledTaskAction -Execute '<python.exe 绝对路径>' `
  -Argument '"<项目路径>\checkin.py" --wait' -WorkingDirectory '<项目路径>'
$trigger = New-ScheduledTaskTrigger -Daily -At 20:35
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName 'CSUFT-PingAnDaka' -Action $action -Trigger $trigger -Settings $settings
```

删除：`schtasks /delete /tn "CSUFT-PingAnDaka" /f`

---

## 怎么拿 token（`proxy/` 目录）

token 是接口鉴权用的 JWT，有效期约 20 天，过期后重新抓一次即可。

1. `powershell -File proxy\start_capture.ps1`
   —— 会把 mitmproxy 的 CA 装进「当前用户→受信任的根证书」，并把系统代理临时指向 `127.0.0.1:8866`
   （脚本会先备份原来的代理设置；如果你本来在用代理，记得按需改 `start_capture.ps1` 里的 `-m upstream:...`）
2. 打开 PC 微信里的小程序，点进打卡页面
3. 从 `proxy/traffic.jsonl` 里找 `FlySource-Auth` 的值（插件也会自动写入 `proxy/state.json` 的宿舍坐标）
4. `powershell -File proxy\stop_capture.ps1` —— 还原系统代理、停掉 mitmdump

`proxy/csuft_addon.py` 除了记录流量，还支持把任务详情的 `locationAccuracy` 顶大、
把 `stuSign` 请求里的坐标改写成宿舍基准点（备用方案，正常流程用不到）。

---

## 文件说明

| 文件 | 作用 |
|---|---|
| `checkin.py` | 主脚本 |
| `history.py` | 查询历史状态（只读） |
| `config.json` | 个人配置（**已在 .gitignore 里，不会提交**） |
| `config.example.json` | 配置模板 |
| `查看状态.cmd` | 双击查看结果 |
| `proxy/` | 抓 token 用的 mitmproxy 插件与开关脚本 |

## License

MIT
