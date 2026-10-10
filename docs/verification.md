# 离线验证

## 单元测试

在项目根目录执行，无需原厂固件：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
```

覆盖输入身份、CRC、补丁边界与重叠、原字节校验、追加对齐、容量、Thumb 指令生成和合成输入的解码掩码恢复。

## 原厂指令执行检查

准备匹配的原版固件并安装可选依赖：

```powershell
python -m pip install '.[sound,verify]'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python tools/verify_liveview_gates.py --source "Z_30_0120.bin" --preset full
python tools/verify_extended_features.py --source "Z_30_0120.bin"
python tools/verify_mtp_fast.py --source "Z_30_0120.bin"
```

工具使用 Unicorn 执行选定的 ARM Thumb 指令路径，输出 JSON 结果；`passed: true` 表示相应断言通过。

| 检查器 | 覆盖内容 | 限制 |
| --- | --- | --- |
| `verify_liveview_gates.py` | 两个原厂与补丁 DISP 判断窗口、256 种值、续接地址、栈及保存寄存器 | 使用合成 RAM，在原厂后续绘制服务前停止 |
| `verify_mtp_fast.py` | `mtp-fast` 包装函数：32 种 handle 类型、取值与仅计数两种模式、builder 失败、记录获取失败、栈及保存寄存器 | 句柄转换、记录获取/释放和 builder 主体为桩，不涉及文件系统、USB 或并发 |
| `verify_extended_features.py` | M 档长曝光标志、其他属性对照、模式与上限、速度枚举及请求解析、WAV 校验与 PCM 转换 | 属性、可用列表和缓冲区为明确输入，不执行完整相机 |

构建器还核对匹配固件、修改前字节、窗口重叠、容量、CRC 和视频快门原厂窗口。JSON 构建报告记录输入身份、补丁 offset 和输出摘要。

这些检查不验证完整启动、刷写、屏幕像素、触摸、扬声器或传感器真实曝光。相机表现需要独立验证，不能由离线结果推出。

## 真机验证

维护者确认已在 Nikon Z30 C 1.20 上完成以下实机验证：

- 独立 EG 模块可通过机身更新流程安装。
- `modular` 构建的 SD 宿主可加载并运行 ZMOD 模块。
- `mtp-fast` 构建（SHA-256 `281ecaae…0dde`）在 47 JPG + 47 NEF 的卡上与原厂对照：590 条 GetObjectPropList 响应逐字节一致；文件夹属性列表约 2920 ms → 680 ms，全卡约 3220 ms → 980 ms，单对象均值约 44 ms → 19 ms。耗时随卡内文件变化；GetObjectInfo 和 GetThumb 未改动。

该确认覆盖上述安装及模块宿主流程；各常规功能（同屏显示、快门声音、M 档长曝光）的实机结果尚未在本页逐项记录。离线检查与真机验证是不同的证据来源。

### MTP 属性列表对照

`mtp-fast` 的返回内容需要在同一张卡、同一批文件上对照原厂固件。`tools/ptp_timing.py` 通过 Windows 自带 MTP 驱动发送只读操作，需要 `python -m pip install '.[timing]'`（comtypes，仅 Windows）：

```powershell
python tools/ptp_timing.py --dump stock.json      # 原厂固件
python tools/ptp_timing.py --dump patched.json    # 刷入 mtp-fast 后
python tools/ptp_timing.py --compare stock.json patched.json
```

转储覆盖每个对象的全部属性与单属性请求、文件夹 depth 1、全卡各 depth 与格式过滤，以及不存在的文件、无效 handle、不支持的属性和 group code 等失败响应；`--compare` 逐字节比较并以非零退出码报告差异。不带参数运行则测量耗时。查询期间拍摄、删除、拔卡或 USB 中断时的行为不在该对照范围内，尚未验证。
