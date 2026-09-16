# CUCKOO.md

## 项目概述

**Smart Downloader** 是一个功能强大的多协议下载工具，支持 HTTP/HTTPS、FTP 等协议的多线程分块下载，并集成浏览器扩展实现自动捕获下载链接。项目采用 Python + Tkinter 构建 GUI，配合 Edge 浏览器扩展提供完整的下载管理解决方案。

## 核心功能

- **多协议下载**：支持 HTTP/HTTPS、FTP 协议，自动识别 Content-Disposition 文件名
- **多线程分块下载**：支持动态块分裂与工作窃取算法，充分利用带宽资源
- **断点续传**：支持暂停/恢复下载，任务状态持久化到 resume_info.json
- **浏览器集成**：Edge 扩展通过 Native Messaging 与主程序通信，自动捕获下载链接
- **云盘支持**：夸克网盘、UC网盘、天翼云盘、移动云盘、光鸭云盘、123云盘、阿里云盘
- **哈希校验**：支持 MD5/SHA1/SHA256 文件完整性校验
- **DNS 缓存**：线程安全的 DNS 缓存，减少域名解析开销

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI | Tkinter + ttk |
| 网络请求 | requests / urllib3 |
| 多线程 | threading + concurrent.futures |
| 打包 | PyInstaller |
| 浏览器扩展 | Manifest V3 (Edge) |
| Native Messaging | Windows 注册表 + JSON 配置 |
| 云盘 API | 各网盘开放接口 / Cookie 模拟 |

## 项目结构

```
下载器21/
├── 下载器.py                 # 主程序 (约 4700+ 行)
├── cloud_drive_manager.py    # 云盘账号管理模块 (约 1090 行)
├── setup_downloader.py       # 一键安装工具 (Native Messaging 注册)
├── build.py                  # PyInstaller 打包脚本
├── 下载器.spec               # PyInstaller 规格文件
├── setup_downloader.spec     # 安装工具规格文件
├── d.ico                     # 程序图标
├── cloud_drive_accounts.json # 云盘账号配置文件 (运行时生成)
├── resume_info.json          # 下载任务断点信息 (运行时生成)
├── download with edge/       # Edge 浏览器扩展
│   ├── manifest.json         # 扩展清单 (Manifest V3)
│   ├── background.js         # Service Worker (后台脚本)
│   ├── popup.html            # 弹出界面
│   ├── popup.js              # 弹出界面逻辑
│   ├── icon.png              # 扩展图标
│   ├── com.smartdownloader.json # Native Messaging 主机配置
│   └── install_host.bat      # 主机注册脚本
├── JxPan-main/               # JxPan 本地服务器 (云盘解析)
│   ├── jxpan-local-server.js # 本地服务器
│   └── 未加密源码.js          # 解析核心
├── node/                     # Node.js 运行时 (用于 JxPan)
│   └── node.exe
├── NSIS打包/                 # NSIS 安装包构建目录
│   ├── 下载器安装器.nsi      # NSIS 脚本
│   └── dist/                 # 打包输出目录
├── __pycache__/              # Python 字节码缓存
└── 下载器.exe                # 打包后的可执行文件 (若已构建)
```

## 关键模块说明

### 下载器.py (主程序)

- **DownloadTask 类**：核心下载任务类，支持多协议、多线程分块下载
  - 工作窃取算法：动态平衡各线程负载
  - 块分裂机制：慢速块自动分裂，提升并行度
  - 断点续传：任务状态持久化
- **DNS 缓存**：通过 monkey-patch socket.getaddrinfo 实现线程安全的 LRU 缓存
- **GUI 界面**：任务列表、进度条、速度显示、日志输出

### cloud_drive_manager.py

- 支持 7 种云盘的登录与文件管理
- 使用 Cookie/Token 方式登录，配置保存在本地 JSON
- 提供文件列表、下载链接解析等功能

### setup_downloader.py

- 自动注册 Native Messaging 主机
- 写入 Windows 注册表，让 Edge 扩展能启动主程序
- 兼容开发环境和打包环境

### Edge 浏览器扩展

- 通过 webRequest API 拦截下载请求
- 通过 Native Messaging 与本地主程序通信
- 将捕获的下载链接发送给主程序进行下载

## 构建与运行

### 开发环境运行

```bash
# 安装依赖
pip install requests psutil pyinstaller

# 运行主程序
python 下载器.py

# 注册浏览器扩展 (管理员权限)
python setup_downloader.py
```

### 打包为 EXE

```bash
# 使用 PyInstaller 打包
python build.py
# 或直接使用 spec 文件
pyinstaller 下载器.spec
```

### NSIS 安装包构建

```bash
# 使用 NSIS 编译安装脚本
makensis NSIS打包/下载器安装器.nsi
```

## 配置说明

| 文件 | 用途 |
|------|------|
| cloud_drive_accounts.json | 云盘账号 Cookie/Token 存储 |
| resume_info.json | 下载任务断点续传信息 |
| com.smartdownloader.json | Native Messaging 主机路径配置 |

## 依赖项

- Python 3.7+
- requests
- psutil
- pyinstaller (仅打包时需要)
- Edge 浏览器 (扩展需要)

## 注意事项

1. 浏览器扩展需要管理员权限注册 Native Messaging 主机
2. 云盘 Cookie 有效期有限，需定期更新
3. 下载大文件时建议保持网络稳定，避免频繁暂停/恢复

---

*本文档由 CUCKOO.md 自动生成，基于项目实际代码结构编写。*