# 从原始固件包构建功能扩展

当前用户流程只需准备原始 Z30 C 1.20 固件包和本项目 patch 程序。默认组合包含同屏、自定义电子快门声音和 M 档 900 秒曝光，不包含状态页面。

## 运行

需要 Python 3.10+。声音功能和 `mtp-fast` 需要 Keystone，首次安装依赖；固件不需要手动解包：

```powershell
python -m pip install '.[sound]'
New-Item -ItemType Directory -Force output | Out-Null
python patch.py --source path/to/Z_30_0120.bin --output output/EG209020.BIN
```

可明确指定 `full`、`liveview-dual`、`shutter-sound`、`m900`；默认 full。单独同屏和 M900 只需要标准库。

`mtp-fast` 是独立预设，只含 MTP 属性列表加速，不包含在 full 或其他预设中，也不与它们组合；它同样通过 `.[sound]` 安装的 Keystone 汇编。输出和同名 JSON 必须不存在，程序拒绝覆盖。CLI 通过 Python 运行。

原始包大小为 34,496,798 字节，SHA-256 为：

```text
1a5449ef505f1f347ed4e066a6a3f588ea542240680e83f4ebcae3b16da3434a
```

固件由用户自行准备，仓库不附原始或修改版完整固件。

## 程序执行顺序

1. 检查整个原始包的大小和 SHA-256；不匹配则退出，不解码或生成文件。
2. 从该版本已知零填充位置恢复等价周期 XOR 掩码，内部解码；不附第三方 XOR 表。
3. 检查容器结构、整包 CRC、模块边界和各模块 CRC，提取 EG 并再次检查其 SHA-256。
4. 每个补丁包含 offset、expected bytes 和 replacement bytes；检查原字节、等长、边界和不重叠后替换。
5. 在原 EG 尾部 CRC 前追加钩子代码，修补跳转地址，重建 CRC。
6. 输出 EG209020.BIN 和报告，列出修改 offset、原字节、替换字节、追加地址和输入/输出摘要。

offset 使用**解包后的 EG 模块**坐标，不是编码外层包的同一位置。输出是独立 EG 模块，不重新封装 Z_30_0120.bin。维护者已确认该 EG 模块在 Z30 C 1.20 上可安装，并已实机测试 SD 宿主与 ZMOD 加载、运行；具体记录见[验证说明](verification.md)。

本解码器仅支持哈希匹配的原始包。已知零位置索引是一组版本限定的观察数据；列/行/高位掩码通过 XOR 方程恢复，所得掩码不要求与任何上游表逐项相同，只需整体解码等价。解码后的 EG 大小为 33,939,514 字节，SHA-256：

```text
8a99ced2d8220729ba067587b0624bf30c81757abc5d728768134b1c7fd457fa
```

开发者可用 --extracted-eg 传入该模块，普通用户无需准备中间模块。

## 验证

普通测试不需要原厂固件：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m unittest discover -s tests -v
```

安装 Unicorn 后可执行原厂与补丁跳转窗口：

```powershell
python -m pip install '.[sound,verify]'
python tools/verify_liveview_gates.py --source path/to/Z_30_0120.bin --preset full
python tools/verify_extended_features.py --source path/to/Z_30_0120.bin
```

同屏检查遍历全部 256 种 DISP，核对续接地址和栈、R4、LR；在原厂后续服务之前停止。扩展检查执行 M 档判断、上限分支、速度枚举/请求解析和 WAV/PCM 转换，使用明确的属性 RAM 和可用列表输入。它们不执行完整相机或真实曝光。执行方法与覆盖范围见 [验证说明](verification.md)。

## 输出与功能范围

输出为独立 EG 模块，不重建外层 Z_30_0120.bin。固件版本菜单保留原厂 1.20，构建身份通过 JSON 报告的 SHA-256 核对。该模块的机身安装以及 SD 宿主/ZMOD 加载运行已完成实机测试。

默认组合包含同屏、自定义声音和 M900。900 秒补丁改变扩展标志读取，不写入其保存值；原厂模式判断和曝光路径保留。视频快门窗口在构建后核对为原厂字节。

默认 `full` 构建不添加状态页、计数、CFW 版本标记、视频慢快门或 SD 模块宿主；`modular` 预设会加入 SD 模块宿主。离线检查不能保证真实显示、声音或曝光行为。
