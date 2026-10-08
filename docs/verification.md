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
```

工具使用 Unicorn 执行选定的 ARM Thumb 指令路径，输出 JSON 结果；`passed: true` 表示相应断言通过。

| 检查器 | 覆盖内容 | 限制 |
| --- | --- | --- |
| `verify_liveview_gates.py` | 两个原厂与补丁 DISP 判断窗口、256 种值、续接地址、栈及保存寄存器 | 使用合成 RAM，在原厂后续绘制服务前停止 |
| `verify_extended_features.py` | M 档长曝光标志、其他属性对照、模式与上限、速度枚举及请求解析、WAV 校验与 PCM 转换 | 属性、可用列表和缓冲区为明确输入，不执行完整相机 |

构建器还核对匹配固件、修改前字节、窗口重叠、容量、CRC 和视频快门原厂窗口。JSON 构建报告记录输入身份、补丁 offset 和输出摘要。

这些检查不验证完整启动、刷写、屏幕像素、触摸、扬声器或传感器真实曝光。相机表现需要独立验证，不能由离线结果推出。
