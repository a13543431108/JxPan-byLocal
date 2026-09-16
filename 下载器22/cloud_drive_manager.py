#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云盘账号管理模块
支持: 夸克网盘 | UC网盘 | 天翼云盘 | 移动云盘 | 光鸭云盘 | 123云盘 | 阿里云盘
手动输入 Token/Cookie 登录，登录信息保存到本地 JSON 文件。
"""

import tkinter as tk
from tkinter import ttk, messagebox, Toplevel
import json
import os
import threading
import time
import requests
import uuid
import base64
import random
import string
import re
from io import BytesIO
from urllib.parse import quote, urlparse, parse_qs


# 登录信息存储文件
CLOUD_DRIVE_CONFIG_FILE = "cloud_drive_accounts.json"


def _get_config_path():
    """获取配置文件绝对路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CLOUD_DRIVE_CONFIG_FILE)


def _load_configs():
    """加载已保存的云盘账号配置"""
    path = _get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_configs(configs):
    """保存云盘账号配置"""
    path = _get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=2)


# 各网盘配置元信息
DRIVE_DRIVES = [
    {
        "id": "quark",
        "name": "夸克网盘",
        "icon": "🟠",
        "auth_type": "cookie",
        "auth_key": "QK_COOKIE",
        "description": "需要 pan.quark.cn 的 Cookie",
        "input_label": "Cookie",
        "scannable": True,
        "scan_type": "quark",
    },
    {
        "id": "uc",
        "name": "UC网盘",
        "icon": "🔵",
        "auth_type": "cookie",
        "auth_key": "UC_COOKIE",
        "description": "需要 drive.uc.cn 的 Cookie",
        "input_label": "Cookie",
        "scannable": True,
        "scan_type": "uc",
    },
    {
        "id": "aliyun",
        "name": "阿里云盘",
        "icon": "�",
        "auth_type": "authorization",
        "auth_key": "ALIYUN_AUTHORIZATION",
        "description": "需要阿里云盘 Authorization Token",
        "input_label": "Authorization Token",
        "scannable": True,
        "scan_type": "aliyun",
    },
    {
        "id": "cloud189",
        "name": "天翼云盘",
        "icon": "🔴",
        "auth_type": "access_token",
        "auth_key": "CLOUD189_TOKEN",
        "description": "需要天翼云盘 AccessToken",
        "input_label": "AccessToken",
        "scannable": True,
        "scan_type": "cloud189",
    },
    {
        "id": "mcloud",
        "name": "移动云盘",
        "icon": "��",
        "auth_type": "authorization",
        "auth_key": "MCLOUD_AUTHORIZATION",
        "description": "需要移动云盘 Authorization Token",
        "input_label": "Authorization Token",
        "scannable": False,
        "scan_type": "mcloud",
    },
    {
        "id": "pan123",
        "name": "123云盘",
        "icon": "🟣",
        "auth_type": "token",
        "auth_key": "PAN123_TOKEN",
        "description": "需要123云盘 Authorization Token",
        "input_label": "Token",
        "scannable": False,
        "scan_type": "pan123",
    },
    {
        "id": "guangya",
        "name": "光鸭云盘",
        "icon": "🦆",
        "auth_type": "login_info_json",
        "auth_key": "GY_Login",
        "description": "需要登录信息 JSON（access_token + refresh_token + device_id）",
        "input_label": "登录信息 JSON",
        "scannable": True,
        "scan_type": "guangya",
    },
    {
        "id": "feijipan",
        "name": "小飞机网盘",
        "icon": "✈️",
        "auth_type": "account",
        "auth_key": "FEIJIPAN_ACCOUNT",
        "description": "需要配置账号信息（解析 >500MB 文件时必需）",
        "input_label": "账号信息 JSON",
        "scannable": False,
        "scan_type": "feijipan",
    },
]

# 无需认证的网盘列表（仅显示提示信息）
NO_AUTH_DRIVES = [
    {
        "id": "ilanzou",
        "name": "蓝奏云优享版",
        "icon": "🔵",
        "domains": "ilanzou.com",
        "description": "无需认证，直接解析分享链接即可",
    },
    {
        "id": "lanzou",
        "name": "蓝奏云",
        "icon": "🟢",
        "domains": "lanzou*.com",
        "description": "无需认证，直接解析分享链接即可",
    },
]


class DriveAccountCard:
    """单个网盘的账号管理卡片"""

    def __init__(self, parent, drive_info, app_ref):
        self.drive_info = drive_info
        self.app_ref = app_ref
        self.drive_id = drive_info["id"]
        self.configs = None  # 将在 refresh_status 中加载

        frame = tk.Frame(parent, bg="#f9f9f9", bd=1, relief=tk.RIDGE)
        frame.pack(fill=tk.X, pady=5, padx=8)

        # 顶部：名称 + 状态标记（○ 未登录 / ✅ 有效 / ❌ 无效 / ⏳ 验证中）
        top_frame = tk.Frame(frame, bg="#f9f9f9")
        top_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        self.status_mark = tk.Label(top_frame, text="○", fg="#999999", bg="#f9f9f9",
                                    font=('微软雅黑', 10, 'bold'))
        self.status_mark.pack(side=tk.LEFT, padx=(0, 3))

        tk.Label(top_frame, text=f"  {drive_info['name']}",
                 font=('微软雅黑', 10, 'bold'), bg="#f9f9f9").pack(side=tk.LEFT)

        # 描述
        self.desc_label = tk.Label(frame, text=f"  {drive_info['description']}",
                 bg="#f9f9f9", fg="#666666", font=('微软雅黑', 8),
                 anchor="w")
        self.desc_label.pack(fill=tk.X, padx=30, pady=2)

        # 输入框
        self.input_frame = tk.Frame(frame, bg="#f9f9f9")
        self.input_frame.pack(fill=tk.X, padx=30, pady=3)

        tk.Label(self.input_frame, text=f"  {drive_info['input_label']}:",
                 bg="#f9f9f9", font=('微软雅黑', 8)).pack(side=tk.LEFT)

        self.entry = tk.Entry(self.input_frame, font=('Consolas', 9), bd=1, width=55)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))

        # 按钮
        self.btn_frame = tk.Frame(frame, bg="#f9f9f9")
        self.btn_frame.pack(fill=tk.X, padx=30, pady=(3, 5))

        tk.Button(self.btn_frame, text="💾 保存", command=self.on_save,
                  bg="#4CAF50", fg="white", font=('微软雅黑', 8), width=8).pack(side=tk.LEFT, padx=2)

        tk.Button(self.btn_frame, text="🔄 清除", command=self.on_clear,
                  bg="#ff9800", fg="white", font=('微软雅黑', 8), width=8).pack(side=tk.LEFT, padx=2)

        tk.Button(self.btn_frame, text="✅ 验证", command=self.on_verify,
                  bg="#2196F3", fg="white", font=('微软雅黑', 8), width=8).pack(side=tk.LEFT, padx=2)

        if drive_info.get("scannable", False):
            tk.Button(self.btn_frame, text="📱 扫码登录", command=self.on_scan_login,
                      bg="#9C27B0", fg="white", font=('微软雅黑', 8), width=10).pack(side=tk.LEFT, padx=2)

        self.packages = frame

    def refresh_status(self, configs):
        """刷新登录状态显示，已登录的隐藏输入框和按钮，未登录的显示"""
        self.configs = configs
        auth = configs.get(self.drive_id, {})
        has_value = bool(auth.get("value"))
        if has_value:
            self.status_mark.config(text="✅", fg="#4CAF50")
            # 隐藏输入框和按钮行
            self.input_frame.pack_forget()
            self.btn_frame.pack_forget()
            nickname = auth.get("nickname", "")
            if nickname:
                self.desc_label.config(text=f"  ✅ {nickname} - 已登录，可直接解析", fg="#4CAF50")
            else:
                self.desc_label.config(text="  ✅ 已登录，可直接解析", fg="#4CAF50")
        else:
            self.status_mark.config(text="○", fg="#999999")
            # 显示输入框和按钮行
            self.input_frame.pack(fill=tk.X, padx=30, pady=3)
            self.btn_frame.pack(fill=tk.X, padx=30, pady=(3, 5))
            self.desc_label.config(text=f"  {self.drive_info['description']}", fg="#666666")

    def on_save(self):
        value = self.entry.get().strip()
        if not value:
            messagebox.showwarning("提示", f"请输入{self.drive_info['name']}{self.drive_info['input_label']}")
            return

        configs = _load_configs()
        configs[self.drive_id] = {
            "value": value,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _save_configs(configs)
        self.refresh_status(configs)
        self.entry.delete(0, tk.END)
        self._sync_to_jxpan()
        messagebox.showinfo("成功", f"{self.drive_info['name']} 登录信息已保存！")
        try:
            self.app_ref.log_message(f"[云盘] {self.drive_info['name']} 账号已保存")
        except Exception:
            pass

    def _sync_to_jxpan(self):
        """同步当前云盘账号到 JxPan 本地服务"""
        try:
            app_ref = self.app_ref
            jxpan_ready = getattr(app_ref, '_jxpan_ready', False)
            if not jxpan_ready:
                return
            from cloud_drive_manager import get_auth_for_jxpan
            auth_data = get_auth_for_jxpan()
            if auth_data:
                jxpan_port = getattr(app_ref, '_jxpan_port', 18765)
                requests.post(
                    f"http://127.0.0.1:{jxpan_port}/api/config",
                    json=auth_data,
                    timeout=5
                )
        except Exception:
            pass

    def on_clear(self):
        configs = _load_configs()
        if self.drive_id in configs:
            del configs[self.drive_id]
            _save_configs(configs)
            self.refresh_status(configs)
            self.desc_label.config(text=f"  {self.drive_info['description']}", fg="#666666")
            messagebox.showinfo("提示", f"{self.drive_info['name']} 登录信息已清除")
            try:
                self.app_ref.log_message(f"[云盘] {self.drive_info['name']} 账号已清除")
            except Exception:
                pass

    def on_verify(self):
        """验证 Token/Cookie 是否有效"""
        value = self.entry.get().strip()
        if not value:
            configs = _load_configs()
            value = configs.get(self.drive_id, {}).get("value", "")
        if not value:
            messagebox.showwarning("提示", "请先输入或保存 Token/Cookie")
            return

        self.status_mark.config(text="⏳", fg="#ff9800")
        threading.Thread(target=self._do_verify, args=(value,), daemon=True).start()

    def _do_verify(self, value):
        """后台验证"""
        try:
            drive_id = self.drive_info["id"]
            if drive_id == "quark":
                self._verify_quark(value)
            elif drive_id == "uc":
                self._verify_uc(value)
            elif drive_id == "aliyun":
                self._verify_aliyun(value)
            elif drive_id == "cloud189":
                self._verify_cloud189(value)
            elif drive_id == "mcloud":
                self._verify_mcloud(value)
            elif drive_id == "pan123":
                self._verify_pan123(value)
            elif drive_id == "guangya":
                self._verify_guangya(value)
        except Exception as e:
            self.app_ref.root.after(0, lambda: self.status_mark.config(
                text="❌", fg="#ff4444"))

    def _verify_quark(self, cookie):
        try:
            resp = requests.get("https://pan.quark.cn/account/info",
                                headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0"},
                                timeout=10)
            if resp.status_code == 200:
                name = "未知"
                try:
                    data = resp.json()
                    self.app_ref.log_message(f"[云盘] 夸克API返回: {json.dumps(data, ensure_ascii=False)[:200]}")
                    # 扁平化搜索所有可能包含昵称的字段
                    for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                        if data.get(key):
                            name = data[key]
                            break
                    else:
                        # 搜索嵌套对象
                        for obj_key in ['data', 'user_info', 'user', 'profile', 'account']:
                            obj = data.get(obj_key, {})
                            if isinstance(obj, dict):
                                for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                                    if obj.get(key):
                                        name = obj[key]
                                        break
                                if name != "未知":
                                    break
                except Exception:
                    pass
                self.app_ref.root.after(0, lambda n=name: self._on_verify_success(n))
            else:
                self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except Exception as e:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())

    def _verify_uc(self, cookie):
        try:
            resp = requests.get("https://drive.uc.cn/account/info",
                                headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0"},
                                timeout=10)
            if resp.status_code == 200:
                name = "未知"
                try:
                    data = resp.json()
                    self.app_ref.log_message(f"[云盘] UC网盘API返回: {json.dumps(data, ensure_ascii=False)[:200]}")
                    for obj_key in ['data', 'user_info', 'user', 'profile', 'account']:
                        obj = data.get(obj_key, {})
                        if isinstance(obj, dict):
                            for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                                if obj.get(key):
                                    name = obj[key]
                                    break
                            if name != "未知":
                                break
                    if name == "未知":
                        for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                            if data.get(key):
                                name = data[key]
                                break
                except Exception:
                    pass
                self.app_ref.root.after(0, lambda n=name: self._on_verify_success(n))
            else:
                self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except Exception:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())

    def _verify_aliyun(self, token):
        try:
            resp = requests.get("https://api.aliyundrive.com/adrive/v1/user/get",
                                headers={"Authorization": token, "User-Agent": "Mozilla/5.0"},
                                timeout=10)
            if resp.status_code == 200:
                name = "未知"
                try:
                    name = resp.json().get("name", "未知")
                except Exception:
                    pass
                self.app_ref.root.after(0, lambda n=name: self._on_verify_success(n))
            else:
                self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except Exception:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())

    def _verify_cloud189(self, token):
        try:
            resp = requests.get("https://api.cloud.189.cn/platform/open/api/login",
                                params={"accessToken": token},
                                headers={"User-Agent": "Mozilla/5.0"},
                                timeout=10)
            if resp.status_code == 200:
                name = "未知"
                try:
                    data = resp.json()
                    self.app_ref.log_message(f"[云盘] 天翼云盘API返回: {json.dumps(data, ensure_ascii=False)[:200]}")
                    for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                        v = data.get(key)
                        if v: name = v; break
                    if name == "未知":
                        for obj_key in ['data', 'user_info', 'user', 'profile', 'account']:
                            obj = data.get(obj_key, {})
                            if isinstance(obj, dict):
                                for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                                    if obj.get(key): name = obj[key]; break
                                if name != "未知": break
                except Exception:
                    pass
                self.app_ref.root.after(0, lambda n=name: self._on_verify_success(n))
            else:
                self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except Exception:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())

    def _verify_mcloud(self, token):
        try:
            resp = requests.get("https://ems.jz.139.com/ma-ugc/getUserInfo",
                                headers={"Authorization": token, "User-Agent": "Mozilla/5.0"},
                                timeout=10)
            if resp.status_code == 200:
                name = "未知"
                try:
                    data = resp.json()
                    self.app_ref.log_message(f"[云盘] 移动云盘API返回: {json.dumps(data, ensure_ascii=False)[:200]}")
                    for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                        v = data.get(key)
                        if v: name = v; break
                    if name == "未知":
                        for obj_key in ['data', 'user_info', 'user', 'profile', 'account']:
                            obj = data.get(obj_key, {})
                            if isinstance(obj, dict):
                                for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                                    if obj.get(key): name = obj[key]; break
                                if name != "未知": break
                except Exception:
                    pass
                self.app_ref.root.after(0, lambda n=name: self._on_verify_success(n))
            else:
                self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except Exception:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())

    def _verify_pan123(self, token):
        try:
            resp = requests.get("https://www.123pan.com/api/user/info",
                                headers={"Authorization": token, "User-Agent": "Mozilla/5.0"},
                                timeout=10)
            if resp.status_code == 200:
                name = "未知"
                try:
                    data = resp.json()
                    self.app_ref.log_message(f"[云盘] 123云盘API返回: {json.dumps(data, ensure_ascii=False)[:200]}")
                    for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                        v = data.get(key)
                        if v: name = v; break
                    if name == "未知":
                        for obj_key in ['data', 'user_info', 'user', 'profile', 'account']:
                            obj = data.get(obj_key, {})
                            if isinstance(obj, dict):
                                for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                                    if obj.get(key): name = obj[key]; break
                                if name != "未知": break
                except Exception:
                    pass
                self.app_ref.root.after(0, lambda n=name: self._on_verify_success(n))
            else:
                self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except Exception:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())

    def _verify_guangya(self, value):
        try:
            info = json.loads(value)
            access_token = info.get("access_token", "")
            if access_token:
                resp = requests.get("https://api.guangyapan.com/v1/user/info",
                                    headers={"Authorization": f"Bearer {access_token}", "User-Agent": "Mozilla/5.0"},
                                    timeout=10)
                if resp.status_code == 200:
                    name = "未知"
                    try:
                        data = resp.json()
                        self.app_ref.log_message(f"[云盘] 光鸭云盘API返回: {json.dumps(data, ensure_ascii=False)[:200]}")
                        for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                            v = data.get(key)
                            if v: name = v; break
                        if name == "未知":
                            for obj_key in ['data', 'user_info', 'user', 'profile', 'account']:
                                obj = data.get(obj_key, {})
                                if isinstance(obj, dict):
                                    for key in ['nickname', 'nick_name', 'name', 'user_name', 'username', 'display_name']:
                                        if obj.get(key): name = obj[key]; break
                                    if name != "未知": break
                    except Exception:
                        pass
                    self.app_ref.root.after(0, lambda n=name: self._on_verify_success(n))
                else:
                    self.app_ref.root.after(0, lambda: self._on_verify_fail())
            else:
                self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except json.JSONDecodeError:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())
        except Exception:
            self.app_ref.root.after(0, lambda: self._on_verify_fail())

    def _on_verify_success(self, name=""):
        """验证成功：更新状态标记，隐藏输入框和按钮，自动保存"""
        self.status_mark.config(text="✅", fg="#4CAF50")
        if name and name != "未知":
            self.desc_label.config(text=f"  ✅ {name} - 已登录，可直接解析", fg="#4CAF50")
        else:
            self.desc_label.config(text="  ✅ 已登录，可直接解析", fg="#4CAF50")
        self.input_frame.pack_forget()
        self.btn_frame.pack_forget()
        # 自动保存：如果输入框有值，自动保存到配置
        configs = _load_configs()
        entry_val = self.entry.get().strip()
        if entry_val:
            configs[self.drive_id] = {
                "value": entry_val,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            if name and name != "未知":
                configs[self.drive_id]["nickname"] = name
            _save_configs(configs)
            self.entry.delete(0, tk.END)
        else:
            # 仅保存昵称（已有配置）
            if self.drive_id in configs and name and name != "未知":
                configs[self.drive_id]["nickname"] = name
                _save_configs(configs)
        self._sync_to_jxpan()
        try:
            self.app_ref.log_message(f"[云盘] {self.drive_info['name']} 验证通过 {name}")
        except Exception:
            pass

    def _on_verify_fail(self):
        """验证失败：更新状态标记，保持输入框和按钮可见"""
        self.status_mark.config(text="❌", fg="#ff4444")
        self.desc_label.config(text=f"  ❌ {self.drive_info['description']}（验证失败）", fg="#ff4444")
        # 确保输入框和按钮可见
        try:
            self.input_frame.pack(fill=tk.X, padx=30, pady=3)
        except Exception:
            pass
        try:
            self.btn_frame.pack(fill=tk.X, padx=30, pady=(3, 5))
        except Exception:
            pass

    def on_scan_login(self):
        """扫码登录 - 通过本地 JxPan 服务获取登录信息"""
        scan_type = self.drive_info.get("scan_type", self.drive_id)
        drive_name = self.drive_info["name"]

        # 检查本地 JxPan 服务是否运行
        jxpan_port = getattr(self.app_ref, '_jxpan_port', 18765)
        jxpan_ready = getattr(self.app_ref, '_jxpan_ready', False)
        use_local = jxpan_ready

        if use_local:
            # 方案A: 通过本地 JxPan 服务扫码（推荐）
            self._scan_via_jxpan(scan_type, drive_name, jxpan_port)
        else:
            # 方案B: 直接打开浏览器扫码
            self._scan_via_browser(scan_type, drive_name)

    def _scan_via_jxpan(self, scan_type, drive_name, port):
        """通过本地 JxPan 服务进行扫码登录"""
        self.status_mark.config(text="⏳", fg="#ff9800")

        def _do_scan():
            try:
                # 1. 获取二维码
                resp = requests.get(
                    f"http://127.0.0.1:{port}/api/action",
                    params={"action": f"{scan_type}_qrcode"},
                    timeout=15
                )
                data = resp.json()
                if not data.get("success"):
                    self.app_ref.root.after(0, lambda: self.status_mark.config(
                        text="❌", fg="#ff4444"))
                    return

                qr_data = data.get("data", {})
                qr_token = qr_data.get("token", "") or qr_data.get("device_code", "")
                qr_url = qr_data.get("qrcode_url") or qr_data.get("qr_url") or qr_data.get("url") or qr_data.get("verification_uri_complete") or qr_data.get("qr_code_url", "")

                if not qr_url:
                    self.app_ref.root.after(0, lambda: self.status_mark.config(
                        text="❌", fg="#ff4444"))
                    return

                # 2. 显示二维码弹窗（使用 PIL/qrcode 库生成二维码图片）
                qr_photo = None
                try:
                    import qrcode as qrcode_lib
                    from PIL import Image, ImageTk
                    qr = qrcode_lib.QRCode(box_size=4, border=2)
                    qr.add_data(qr_url)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    qr_photo = ImageTk.PhotoImage(qr_img)
                except Exception:
                    qr_photo = None

                # 在主线创建弹窗
                popup_ready = [False]
                def _show_popup():
                    win = tk.Toplevel(self.app_ref.root)
                    win.title(f"{drive_name} 扫码登录")
                    win.geometry("320x420")
                    win.resizable(False, False)
                    win.transient(self.app_ref.root)
                    win.grab_set()

                    tk.Label(win, text=f"请使用 {drive_name} 手机APP扫码", 
                             font=('微软雅黑', 11, 'bold'), fg="#333333").pack(pady=(15, 5))

                    if qr_photo:
                        qr_label = tk.Label(win, image=qr_photo, bg="white")
                        qr_label.image = qr_photo  # 保持引用
                        qr_label.pack(pady=10)
                    else:
                        tk.Label(win, text=qr_url, fg="blue", wraplength=280,
                                 font=('微软雅黑', 8)).pack(pady=10)

                    status_label = tk.Label(win, text="等待扫码...", font=('微软雅黑', 9), fg="#666666")
                    status_label.pack(pady=5)

                    # 关闭按钮
                    cancel_btn = tk.Button(win, text="取消", width=10,
                        command=lambda: [setattr(_scan_via_jxpan_ctx, '_cancelled', True), win.destroy()])
                    cancel_btn.pack(pady=10)

                    win.protocol("WM_DELETE_WINDOW", lambda: [setattr(_scan_via_jxpan_ctx, '_cancelled', True), win.destroy()])

                    popup_ready[0] = True
                    # 保存窗口引用以便后续关闭
                    _scan_via_jxpan_ctx._win = win
                    _scan_via_jxpan_ctx._status_label = status_label

                def _update_status_label(ctx, text):
                    """安全更新状态标签，避免窗口已销毁时报错"""
                    try:
                        if ctx._status_label and ctx._win and ctx._win.winfo_exists():
                            ctx._status_label.config(text=text)
                    except Exception:
                        pass

                import types
                _scan_via_jxpan_ctx = types.SimpleNamespace()
                _scan_via_jxpan_ctx._cancelled = False
                _scan_via_jxpan_ctx._win = None
                _scan_via_jxpan_ctx._status_label = None

                self.app_ref.root.after(0, _show_popup)

                # 等待弹窗创建完成
                for _ in range(50):
                    if popup_ready[0]:
                        break
                    time.sleep(0.05)

                if _scan_via_jxpan_ctx._cancelled:
                    return

                # 3. 轮询扫码状态
                poll_interval = qr_data.get("interval", 3)
                max_polls = 120  # 最多等 120*interval 秒
                cookie_str = None

                for i in range(max_polls):
                    if _scan_via_jxpan_ctx._cancelled:
                        break

                    time.sleep(poll_interval)

                    try:
                        poll_params = {"action": f"{scan_type}_qr_poll"}
                        if scan_type == "guangya":
                            poll_params["device_code"] = qr_token
                        elif scan_type == "aliyun":
                            poll_params["t"] = qr_data.get("t", "")
                            poll_params["ck"] = qr_data.get("ck", "")
                            poll_params["csrfToken"] = qr_data.get("csrf_token", "")
                            poll_params["umidToken"] = qr_data.get("umid_token", "")
                        else:
                            poll_params["token"] = qr_token
                        poll_resp = requests.get(
                            f"http://127.0.0.1:{port}/api/action",
                            params=poll_params,
                            timeout=15
                        )
                        poll_data = poll_resp.json()

                        if poll_data.get("success") and poll_data.get("data"):
                            poll_result = poll_data["data"]
                            # 检查是否扫码成功并获取到Cookie/Authorization
                            if poll_result.get("status") == "confirmed" or poll_result.get("ticket"):
                                # 阿里云盘/移动云盘返回 authorization，其他返回 cookie
                                cookie_str = poll_result.get("cookie") or poll_result.get("cookie_str") or poll_result.get("authorization") or ""
                                if cookie_str:
                                    break
                            elif poll_result.get("status") == "expired":
                                self.app_ref.root.after(0, lambda: _update_status_label(_scan_via_jxpan_ctx, "❌ 二维码已过期"))
                                time.sleep(2)
                                break
                            elif poll_result.get("cookie") or poll_result.get("cookie_str") or poll_result.get("authorization"):
                                cookie_str = poll_result.get("cookie") or poll_result.get("cookie_str") or poll_result.get("authorization") or ""
                                break

                        # 更新状态文本
                        dots = "." * ((i % 3) + 1)
                        status_text = f"请使用手机APP扫码{dots}"
                        self.app_ref.root.after(0, lambda t=status_text: 
                            _update_status_label(_scan_via_jxpan_ctx, t))

                    except Exception:
                        continue

                # 4. 关闭弹窗，保存 Token
                if _scan_via_jxpan_ctx._win:
                    try:
                        self.app_ref.root.after(0, _scan_via_jxpan_ctx._win.destroy)
                    except Exception:
                        pass

                if cookie_str:
                    # 自动填入输入框并验证
                    self.app_ref.root.after(0, lambda c=cookie_str: self.entry.insert(0, c))
                    self.app_ref.root.after(100, lambda c=cookie_str: self.on_verify())
                    try:
                        self.app_ref.log_message(f"[云盘] {drive_name} 扫码登录成功，Token 已获取")
                    except Exception:
                        pass
                else:
                    if not _scan_via_jxpan_ctx._cancelled:
                        self.app_ref.root.after(0, lambda: self.status_mark.config(text="○", fg="#999999"))
                        try:
                            self.app_ref.log_message(f"[云盘] {drive_name} 扫码登录失败或超时")
                        except Exception:
                            pass

            except Exception as e:
                self.app_ref.root.after(0, lambda: self.status_mark.config(
                    text="❌", fg="#ff4444"))
                try:
                    self.app_ref.log_message(f"[云盘] {drive_name} 扫码登录异常: {e}")
                except Exception:
                    pass

        threading.Thread(target=_do_scan, daemon=True).start()

    def _scan_via_browser(self, scan_type, drive_name):
        """直接打开浏览器扫码登录页面"""
        import webbrowser
        scan_urls = {
            "quark": "https://pan.quark.cn/login",
            "uc": "https://drive.uc.cn/login",
            "aliyun": "https://www.aliyundrive.com/login",
            "cloud189": "https://cloud.189.cn/login",
            "mcloud": "https://yun.139.com/login",
            "guangya": "https://www.guangyapan.com/login",
        }
        url = scan_urls.get(scan_type, "")
        if url:
            webbrowser.open(url)
            messagebox.showinfo("扫码登录", f"请在浏览器中打开 {drive_name} 登录页，使用手机APP扫码登录。\n\n登录后手动复制 Cookie/Token 粘贴到输入框中保存。")
        else:
            messagebox.showinfo("扫码登录", f"请打开浏览器访问 {drive_name} 网页版，登录后复制 Cookie/Token 粘贴到输入框中保存。")


def create_cloud_drive_tab(parent, app_ref=None):
    """创建云盘管理标签页主界面"""

    # 顶部说明
    top_frame = tk.Frame(parent, bg="#f0f0f0")
    top_frame.pack(fill=tk.X, padx=10, pady=5)

    tk.Label(top_frame, text="💡 输入各网盘的 Token/Cookie 后即可使用网盘解析功能。",
             font=('微软雅黑', 9), bg="#f0f0f0", fg="#666666").pack(anchor="w")

    tk.Label(top_frame, text="  获取方式: 登录网盘网页版 → F12 开发者工具 → Network → 复制 Cookie/Token",
             font=('微软雅黑', 8), bg="#f0f0f0", fg="#999999").pack(anchor="w")

    # 按钮栏
    btn_bar = tk.Frame(parent, bg="#f0f0f0")
    btn_bar.pack(fill=tk.X, padx=10, pady=5)

    tk.Button(btn_bar, text="📋 导出配置", command=lambda: _export_config(app_ref),
              bg="#607D8B", fg="white", font=('微软雅黑', 8), width=12).pack(side=tk.LEFT, padx=2)

    tk.Button(btn_bar, text="📂 导入配置", command=lambda: _import_config(app_ref),
              bg="#607D8B", fg="white", font=('微软雅黑', 8), width=12).pack(side=tk.LEFT, padx=2)

    tk.Button(btn_bar, text="🗑️ 清除全部", command=lambda: _clear_all(app_ref),
              bg="#f44336", fg="white", font=('微软雅黑', 8), width=12).pack(side=tk.LEFT, padx=2)

    # 可滚动区域
    canvas = tk.Canvas(parent, bg="#f0f0f0", highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg="#f0f0f0")

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # 创建各网盘卡片（需要认证的）
    configs = _load_configs()
    cards = []
    for drive in DRIVE_DRIVES:
        card = DriveAccountCard(scroll_frame, drive, app_ref)
        card.refresh_status(configs)
        cards.append(card)

    # 分隔线
    sep_frame = tk.Frame(scroll_frame, bg="#e0e0e0", height=1)
    sep_frame.pack(fill=tk.X, padx=10, pady=10)

    # 无需认证的网盘提示
    no_auth_label = tk.Label(scroll_frame, text="以下平台无需认证，可直接解析分享链接：",
                             font=('微软雅黑', 9, 'bold'), bg="#f0f0f0", fg="#666666",
                             anchor="w")
    no_auth_label.pack(fill=tk.X, padx=15, pady=(0, 5))

    for nd in NO_AUTH_DRIVES:
        frame = tk.Frame(scroll_frame, bg="#f0f8f0", bd=1, relief=tk.RIDGE)
        frame.pack(fill=tk.X, pady=3, padx=8)

        tk.Label(frame, text=f"{nd['icon']}  {nd['name']}  ({nd['domains']})",
                 font=('微软雅黑', 10, 'bold'), bg="#f0f8f0", fg="#4CAF50").pack(anchor="w", padx=15, pady=8)

        tk.Label(frame, text=f"  {nd['description']}",
                 font=('微软雅黑', 8), bg="#f0f8f0", fg="#888888").pack(anchor="w", padx=30, pady=(0, 8))

    # 将cards绑定到parent以便刷新
    parent._cloud_cards = cards

    # 帮助按钮（弹窗显示获取方式）
    def _show_help():
        help_text = """=== 如何获取 Token/Cookie ===

【夸克网盘】登录 pan.quark.cn → F12 → Application → Cookies → 复制所有 Cookie
【UC网盘】登录 drive.uc.cn → F12 → Application → Cookies → 复制所有 Cookie
【阿里云盘】登录 alipan.com → F12 → Network → 任意请求 → 复制 Authorization 头
【天翼云盘】登录 cloud.189.cn → F12 → Network → 任意请求 → 复制 accessToken 参数
【移动云盘】登录 yun.139.com → F12 → Network → 任意请求 → 复制 Authorization 头
【123云盘】登录 www.123pan.com → F12 → Network → 任意请求 → 复制 Token
【小飞机网盘】登录 feijipan.com → F12 → Application → Cookies → 复制所有 Cookie
【光鸭云盘】登录 www.guangyapan.com → F12 → Network → 任意请求 → 复制登录信息 JSON
【蓝奏云系列】无需认证，直接解析分享链接即可"""

        win = tk.Toplevel(parent)
        win.title("获取 Token/Cookie 帮助")
        win.geometry("520x400")
        win.resizable(False, False)
        win.transient(parent)
        win.grab_set()

        tk.Label(win, text="如何获取 Token/Cookie", font=('微软雅黑', 12, 'bold'),
                 fg="#333333", bg="#f0f0f0").pack(pady=(15, 5))

        text_widget = tk.Text(win, font=('Consolas', 9), wrap="word",
                              bg="#ffffff", fg="#444444", padx=10, pady=10,
                              relief=tk.SOLID, bd=1)
        text_widget.insert("1.0", help_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        tk.Button(win, text="关闭", command=win.destroy,
                  width=10, bg="#607D8B", fg="white",
                  font=('微软雅黑', 9)).pack(pady=(5, 15))

    tk.Button(btn_bar, text="❓ 获取帮助", command=_show_help,
              bg="#795548", fg="white", font=('微软雅黑', 8), width=12).pack(side=tk.LEFT, padx=2)

    # 启动自动验证（延迟3秒，等待UI加载完成）
    parent.after(3000, lambda: start_auto_verify(cards, app_ref, interval_minutes=30))

    # 在日志中输出可用云盘列表
    try:
        if app_ref and hasattr(app_ref, 'log_message'):
            # 已登录的云盘
            logged_in = [d['name'] for d in DRIVE_DRIVES if d['id'] in configs and configs[d['id']].get('value')]
            # 无需认证的云盘
            no_auth = [d['name'] for d in NO_AUTH_DRIVES]
            msg = f"[云盘] 可用云盘: {'、'.join(logged_in + no_auth)}"
            parent.after(500, lambda: app_ref.log_message(msg))
    except Exception:
        pass

    # 刷新状态按钮
    tk.Button(parent, text="🔄 刷新状态",
              command=lambda: [c.refresh_status(_load_configs()) for c in cards],
              bg="#9E9E9E", fg="white", font=('微软雅黑', 8)).pack(pady=5)


def _export_config(app_ref):
    configs = _load_configs()
    if not configs:
        messagebox.showinfo("提示", "没有可导出的配置")
        return
    data = {}
    for drive in DRIVE_DRIVES:
        if drive["id"] in configs:
            data[drive["auth_key"]] = configs[drive["id"]]["value"]
    messagebox.showinfo("配置 JSON", json.dumps(data, ensure_ascii=False, indent=2))
    try:
        app_ref.log_message("[云盘] 已导出配置")
    except Exception:
        pass


def _import_config(app_ref):
    from tkinter import filedialog
    path = filedialog.askopenfilename(title="选择配置文件", filetypes=[("JSON", "*.json")])
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        configs = _load_configs()
        imported = 0
        for drive in DRIVE_DRIVES:
            val = data.get(drive["auth_key"])
            if val:
                configs[drive["id"]] = {"value": val, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                imported += 1
        _save_configs(configs)
        messagebox.showinfo("导入成功", f"已导入 {imported} 个网盘配置")
        try:
            app_ref.log_message(f"[云盘] 导入了 {imported} 个配置")
        except Exception:
            pass
    except Exception as e:
        messagebox.showerror("导入失败", str(e))


def _clear_all(app_ref):
    if not messagebox.askyesno("确认", "确定要清除所有云盘账号信息吗？"):
        return
    _save_configs({})
    try:
        app_ref.log_message("[云盘] 已清除所有账号信息")
    except Exception:
        pass
    messagebox.showinfo("提示", "已清除所有云盘账号信息")


# ==================== 供 JxPan 本地服务读取登录信息 ====================

def get_auth_for_jxpan():
    """返回 JxPan 可用的认证信息字典"""
    configs = _load_configs()
    result = {}
    for drive in DRIVE_DRIVES:
        if drive["id"] in configs:
            result[drive["auth_key"]] = configs[drive["id"]]["value"]
    return result


# ==================== 自动验证和长维持机制 ====================

# 全局变量：长维持定时器
_keepalive_timer = None
_keepalive_running = False


def start_auto_verify(cards, app_ref, interval_minutes=30):
    """
    启动自动验证和长维持机制。
    在后台线程中定期验证所有已登录的云盘账号，标记失效的账号。
    interval_minutes: 验证间隔（分钟），默认30分钟
    """
    global _keepalive_timer, _keepalive_running
    if _keepalive_running:
        return
    _keepalive_running = True

    def _do_keepalive():
        global _keepalive_timer, _keepalive_running
        try:
            configs = _load_configs()
            if not configs:
                # 没有账号，1小时后重试
                _keepalive_timer = threading.Timer(3600, _do_keepalive)
                _keepalive_timer.daemon = True
                _keepalive_timer.start()
                return

            log = getattr(app_ref, 'log_message', print)
            log("[云盘] 开始自动验证已保存的账号...")

            # 对每个卡片，如果有已保存的账号，自动验证
            for card in cards:
                drive_id = card.drive_id
                if drive_id in configs:
                    value = configs[drive_id].get("value", "")
                    if value:
                        card._do_verify(value)

            # 发送到 JxPan 本地服务保持最新
            try:
                jxpan_port = getattr(app_ref, '_jxpan_port', 18765)
                auth_data = get_auth_for_jxpan()
                if auth_data:
                    try:
                        requests.post(
                            f"http://127.0.0.1:{jxpan_port}/api/config",
                            json=auth_data,
                            timeout=5
                        )
                    except Exception:
                        pass  # JxPan 服务未运行，忽略
            except Exception:
                pass

            log(f"[云盘] 自动验证完成，下次验证在 {interval_minutes} 分钟后")
        except Exception:
            pass
        finally:
            # 安排下一次验证
            _keepalive_timer = threading.Timer(interval_minutes * 60, _do_keepalive)
            _keepalive_timer.daemon = True
            _keepalive_timer.start()

    # 延迟3秒后开始第一次验证（等待UI完全加载）
    _keepalive_timer = threading.Timer(3, _do_keepalive)
    _keepalive_timer.daemon = True
    _keepalive_timer.start()
    try:
        log = getattr(app_ref, 'log_message', print)
        log(f"[云盘] 自动验证已启动，间隔 {interval_minutes} 分钟")
    except Exception:
        pass


def stop_auto_verify():
    """停止自动验证长维持"""
    global _keepalive_timer, _keepalive_running
    if _keepalive_timer:
        _keepalive_timer.cancel()
        _keepalive_timer = None
    _keepalive_running = False
    try:
        print("[云盘] 自动验证已停止")
    except Exception:
        pass