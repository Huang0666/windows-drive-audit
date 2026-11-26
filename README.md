# Windows Drive Audit

离线扫描 Windows 磁盘。目录清册逐项展示完整路径、含子目录占用、仅本层文件占用、可能的所属软件、判断依据和清理建议。报告可以逐层展开，也能在全盘搜索和筛选。

## 一键运行

从 [GitHub Releases](https://github.com/Huang0666/windows-drive-audit/releases/latest) 下载 `WindowsDriveAudit.exe`。在 Windows 10 或 11 x64 双击运行，默认扫描 C 盘，完成后打开本地报告。独立版已包含运行时。要扫描 D 盘，在下载目录打开 PowerShell 并运行：

```powershell
.\WindowsDriveAudit.exe --drive D:
```

报告默认保存在 `%USERPROFILE%\Documents\WindowsDriveAudit` 下独立的扫描目录。每次生成 `index.html` 和 `directories.csv.zip`。HTML 可用当前版 Edge 或 Chrome 打开。CSV 带 UTF-8 BOM，可用 Excel 等工具读取。支持 `--output-dir` 指定保存位置，`--no-open` 只生成文件。

## 从源码运行

Windows 上安装 Python 3.12 或更新版本后，双击 `windows-drive-audit\Scan.cmd`，或者运行：

```powershell
python .\windows-drive-audit\scripts\drive_audit.py --drive E: --output-dir .\reports
```

源代码扫描器只用 Python 标准库。高级用户可以在 `scripts/rules.py` 中补充软件路径和判定规则。

## 用作 Codex Skill

把仓库里的 `windows-drive-audit` 整个文件夹复制到 Codex 的用户 skills 目录，例如 `%USERPROFILE%\.codex\skills\windows-drive-audit`，再重新打开 Codex。可以输入 `$windows-drive-audit 扫描 D 盘并生成逐目录报告`。独立扫描器和报告本身不需要调用 Codex、大模型或任何 API。通过 Codex 使用 Skill 时，Codex 照常使用你已配置的模型。

## 统计口径与隐私

- 程序读取目录元数据和本机应用登记。目录名推断与已登记软件都有单独的依据。所有清理结论供人工审核，扫描器本身只生成报告。
- NTFS 实际占用按文件标识去重。父目录包含下层文件，做加总时使用「仅本层」。其他文件系统显示逻辑文件大小，卷级差额显示为不适用。
- 无权限目录与重解析点会标记在清册里。受保护的 WindowsApps 目录按本机登记尝试读取可访问的子目录。卷级差额可能包括受保护的内容、文件系统维护数据和扫描期间的变化。
- 报告只保存在本机，其中可能含个人路径和软件名称。对外分享前应核对报告内容。

## 构建 Windows x64 独立版

在 Windows x64 以 Python 3.12+ 建立独立构建环境，并安装 [PyInstaller](https://pyinstaller.org/en/stable/usage.html)。在仓库根目录运行：

```powershell
python -m PyInstaller --clean --onefile --name WindowsDriveAudit --add-data "windows-drive-audit/assets/report.html:assets" windows-drive-audit/scripts/drive_audit.py
```

生成文件位于 `dist\WindowsDriveAudit.exe`。项目使用 [MIT 许可证](LICENSE)。

## English

Offline, read-only Windows drive inventory. Download the x64 executable from Releases and double-click it to scan C:, or run `WindowsDriveAudit.exe --drive D:`. It creates a searchable local HTML report and a ZIP containing CSV. No AI account, API key, or network access is required to scan. Source entry point requires Python 3.12+ on Windows.
