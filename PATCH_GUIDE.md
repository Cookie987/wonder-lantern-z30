# Wonder Lantern Z30 离线构建指引

目前只支持 **Z30 原版 C 1.20 固件**。默认生成包含直方图＋水平仪同屏、自定义快门声音和 M 档 900 秒曝光修改的独立 EG 模块产物。

构建生成独立 EG 模块，不会重建完整 Nikon 更新包。维护者已确认该模块可在 Z30 C 1.20 机身安装，并已实机测试 SD 宿主与 ZMOD 加载、运行；详细验证范围见[验证说明](docs/verification.md)。

## 1. 准备文件

安装 Python 3.10 或更新版本，下载并解压本项目的完整源码。

把原版固件 **Z_30_0120.bin** 放进项目文件夹，与 `patch.py` 放在一起。不要只下载 patch.py，项目中的 `src` 文件夹也需要保留。

## 2. 运行命令

在项目文件夹里打开 PowerShell，依次执行：

```powershell
python -m pip install '.[sound]'
New-Item -ItemType Directory -Force output | Out-Null
python patch.py --source "Z_30_0120.bin" --output "output/EG209020.BIN"
```

第一条命令安装依赖，只需首次执行。程序会检查原版固件哈希并生成 EG 模块，原始文件不会被修改。

## 3. 找到生成的固件

看到 `Built` 和输出文件路径，表示 EG 模块构建完成。该产物的机身安装与模块宿主/ZMOD 加载运行已有实机验证；其他功能覆盖见[验证说明](docs/verification.md)。

打开 `output` 文件夹：

- **EG209020.BIN**：独立 EG 模块，可在 Z30 C 1.20 上安装；不是完整 Nikon 更新包。
- **EG209020.json**：构建信息，无需复制到相机。

## 常见问题

- **找不到 python**：确认已安装 Python。Windows 下也可以把命令里的 `python` 换成 `py`。
- **SHA-256 mismatch**：固件不匹配，请使用未经修改的原版 Z30 C 1.20。
- **Output or report already exists**：移走 output 中之前生成的 BIN 和 JSON，再运行；程序不会覆盖旧文件。

这是实验性固件修改，离线检查不保证所有相机行为。
