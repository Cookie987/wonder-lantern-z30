# Wonder Lantern Z30

面向 Nikon Z30 C 1.20 的实验性底层宿主与固件扩展研究项目，尝试构建类似 Magic Lantern 的机身端扩展能力。当前仓库是 Z30 专用原型，不是通用底层开发模板。

## 功能

- **直方图＋水平仪同屏**：扩展 DISP 可见性判断，保留原厂模式条件和显示顺序。
- **自定义电子快门声音**：从 SD 卡读取 WAV；提供声音开关、文件选择、预听和重新加载。选择页以 `*` 标记当前选项，按一次 OK 应用。
- **M 档 900 秒曝光**：启用固件已有的长曝光路径，保留原厂 M 档判断。

仅支持 Z30 C 1.20。维护者已确认独立 EG 模块可在该版本机身安装，并已实机测试 SD 宿主与 ZMOD 加载、运行；其他功能的实机覆盖范围见[验证说明](docs/verification.md)。

## 使用

第一次使用请看[简单 patch 指引](PATCH_GUIDE.md)。需要 Python 3.10+、完整项目源码和未经修改的 `Z_30_0120.bin`。

```powershell
python -m pip install '.[sound]'
New-Item -ItemType Directory -Force output | Out-Null
python patch.py --source "Z_30_0120.bin" --output "output/EG209020.BIN"
```

程序先检查原始包的 SHA-256，再解包并核对 EG 模块。随后按 offset 检查并替换原字节、追加功能代码、重建 CRC，输出独立 EG 模块 `EG209020.BIN` 和 JSON 构建报告。该模块已在 Z30 C 1.20 实机安装测试；程序不会重建完整 Nikon 更新包。原始文件不会修改，已有输出不会覆盖。

默认包含同屏、快门声音和 M 档长曝光；可以通过 `liveview-dual`、`shutter-sound` 或 `m900` 单独构建。`mtp-fast`（加快 MTP 属性列表）是独立的实验预设，不在默认构建内，需明确指定。具体输入哈希和实现方式见[构建说明](docs/build.md)。

## 自定义声音

设置菜单中的 `Shutter sound` 提供开关和声音文件选择。支持 SD 卡根目录 `SHUTTER.WAV`，以及 `SHUTTER/1.WAV` 至 `SHUTTER/4.WAV`。声音格式为 8000 Hz、单声道、16 位 PCM，最长 1.08 秒，详见[声音说明](docs/shutter-sound.md)。

根目录的 `SHUTTER.WAV` 是启用该功能的必需文件；`SHUTTER` 子目录及其中的编号声音文件可以缺省。

转换短 PCM WAV：

```powershell
python tools/prepare_wav.py input.wav SHUTTER.WAV
```

转换器使用线性插值；高采样率音频可先用带抗混叠滤波的重采样器处理。仓库不附第三方音频，脚本中的 `example(slot)` 可生成合成示例。

## 文档与许可

- [简单 patch 指引](PATCH_GUIDE.md)
- [构建说明](docs/build.md)
- [声音菜单与文件格式](docs/shutter-sound.md)
- [离线验证方法与限制](docs/verification.md)
- [SD 原生模块宿主与接口](docs/modules.md)：`modular` 构建、模块 ABI 和已完成的实机加载/运行验证。
- [许可证范围与第三方说明](THIRD_PARTY_NOTICES.md)

除声音实现的四个文件外，本项目原创代码与文档采用 [MIT](LICENSE)。声音实现采用 [Wonder Lantern Community License](licenses/Wonder-Lantern.txt)，包含免费分发等条件；使用或分发组合代码时须同时遵守相应条款。

本项目属于 WonderLantern 组织，是面向 Z30 的独立实验项目，不代表 Nikon 支持或认可。部分声音实现遵循随附的 Wonder Lantern Community License。许可证要求衍生版本不得自称为官方 Wonder Lantern 发布；该要求针对许可证覆盖的软件发布身份，不改变本仓库属于 WonderLantern 组织这一事实。许可证不授予 Nikon 固件、原厂资源或商标的权利。
