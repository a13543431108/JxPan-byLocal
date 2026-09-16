@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Smart Downloader - 全自动安装
echo ============================================
echo   Smart Downloader - 全自动安装
echo ============================================
echo.

REM 获取当前目录
set "SCRIPT_DIR=%~dp0"
set "HOST_PATH=%SCRIPT_DIR%com.smartdownloader.json"
set "REG_KEY=HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\com.smartdownloader"
set "EXE_PATH=%SCRIPT_DIR%..\下载器20.exe"

REM 第一步：检查扩展ID，如果未替换则自动获取
:CHECK_ID
findstr "__EXTENSION_ID__" "%HOST_PATH%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [步骤1] 检测到扩展ID未设置，正在尝试自动获取...
    echo.
    echo   请打开 Edge 扩展管理页面: edge://extensions/
    echo   开启"开发者模式"，点击"加载已解压的扩展"
    echo   选择: %SCRIPT_DIR%
    echo.
    echo   加载后，复制下面显示的扩展 ID：
    echo.
    set /p EXT_ID=请输入扩展 ID: 
    if "!EXT_ID!"=="" (
        echo [错误] 扩展 ID 不能为空！
        pause
        exit /b 1
    )
    
    REM 自动替换扩展ID
    powershell -Command "(Get-Content '%HOST_PATH%') -replace '__EXTENSION_ID__', '%EXT_ID%' | Set-Content '%HOST_PATH%'"
    echo [成功] 已自动写入扩展 ID: %EXT_ID%
    echo.
)

REM 第二步：检查下载器 exe
echo [步骤2] 检查下载器程序...
if not exist "%EXE_PATH%" (
    echo [警告] 找不到: %EXE_PATH%
    echo   请将打包后的 下载器20.exe 放在上级目录
    echo.
    choice /c YN /m "是否继续安装？"
    if errorlevel 2 exit /b 1
) else (
    echo [成功] 已找到下载器程序
)

REM 第三步：写入注册表
echo [步骤3] 注册 Native Messaging Host...
reg add "%REG_KEY%" /ve /t REG_SZ /d "%HOST_PATH%" /f >nul 2>&1
if %errorlevel% equ 0 (
    echo [成功] 注册完成！
    echo.
    echo ============================================
    echo   安装成功！请重启 Edge 浏览器
    echo ============================================
    echo.
    echo   效果：Edge 启动时扩展自动启动下载器
    echo   就像 IDM 一样，无需手动操作
    echo.
    echo   清单文件: %HOST_PATH%
    echo   下载器: %EXE_PATH%
) else (
    echo [失败] 注册失败，请以管理员身份运行
)

echo.
pause