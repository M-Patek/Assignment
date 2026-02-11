import re
import time
import os
import random
import requests
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from playwright.sync_api import sync_playwright, TimeoutError
import urllib3

# 禁用不安全请求警告 (针对部分接码平台SSL证书问题)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================================================
# === I. 核心隐身补丁 (Stealth JS Injection) ===
# =======================================================================================
STEALTH_JS = """
(() => {
    // 1. 更彻底且安全地移除 webdriver 属性
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // 2. 伪造 Chrome 运行时对象 (补全结构，避免被简单检测)
    if (!window.chrome) {
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {
                isInstalled: false,
                InstallState: {
                    DISABLED: 'disabled',
                    INSTALLED: 'installed',
                    NOT_INSTALLED: 'not_installed'
                },
                RunningState: {
                    CANNOT_RUN: 'cannot_run',
                    READY_TO_RUN: 'ready_to_run',
                    RUNNING: 'running'
                }
            }
        };
    }

    // 3. 覆盖 Permissions API (防止通过通知权限反查自动化状态)
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
    );
})();
"""

# =======================================================================================
# === II. 全局配置区域 (Configuration) ===
# =======================================================================================
CONFIG = {
    # 豪猪网/豪猪云 新版API配置
    "HZ_USER": "018133145536af6f2546c6e5d97867fb85610dc57c5e2dd095016885b0e82d63",  # 您的 API 账号
    "HZ_PWD": "753b4b715feae88d60e4d94d9d578776b3deadea5c91a3e45921060810d0571c",   # 您的 API 密码
    "HZ_BASE_URL": "https://api.haozhuma.com/sms/", # 更新为截图中的HTTPS地址

    "TARGET_COUNTRY": "US", # 目标国家 (逻辑保留，主要依赖项目ID)
    
    # 默认 Google 项目 ID (参考截图6，如果搜索失败将使用此ID)
    "DEFAULT_GOOGLE_SID": "20706",

    "ACCOUNT_FILE": "accounts.txt",
    "FAILED_FILE": "failed_accounts.txt"
}

# =======================================================================================
# === III. 工具函数 ===
# =======================================================================================

def human_delay(min_ms=800, max_ms=2000):
    """模拟人类操作时的随机思考/停顿时间"""
    time.sleep(random.uniform(min_ms, max_ms) / 1000)

def human_type(page, selector, text):
    """
    模拟人类逐字输入，包含随机的击键间隔。
    比 page.fill() 更安全，能规避输入频率检测。
    """
    try:
        page.focus(selector)
        for char in text:
            # 这里的 text 可能包含空格 (如 "+86 192...")，page.type 能正常处理空格
            page.type(selector, char, delay=random.uniform(50, 150))
    except Exception as e:
        # 降级方案：如果逐字输入失败，回退到 fill 但保留前后延迟
        page.fill(selector, text)

def load_accounts_from_file(file_path):
    """加载账号文件"""
    accounts = []
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = re.split(r'[:|,]', line)
            if len(parts) >= 2:
                acc = {
                    "email": parts[0].strip(),
                    "pwd": parts[1].strip(),
                    "recovery": parts[2].strip() if len(parts) > 2 else ""
                }
                accounts.append(acc)
    return accounts

def log_failed_account(email):
    """记录失败账号"""
    try:
        with open(CONFIG["FAILED_FILE"], "a", encoding="utf-8") as f:
            f.write(f"{email}\n")
    except Exception:
        pass

# =======================================================================================
# === IV. 接码客户端 (HaozhumaClient - New Protocol) ===
# =======================================================================================
class HaozhumaClient:
    def __init__(self, username, password, logger_callback):
        self.username = username
        self.password = password
        self.base_url = CONFIG.get("HZ_BASE_URL", "https://api.haozhuma.com/sms/")
        self.log = logger_callback
        self.token = None
        self.sid = None  # 项目 ID (Project ID)
        self.current_phone = None

    def _request(self, params):
        """通用请求函数，处理新版 JSON 协议"""
        # 1. 协议转换: 旧代码 action -> 新代码 api
        if "action" in params:
            params["api"] = params.pop("action")

        # 2. 自动附加 Token
        if self.token and "token" not in params and params.get("api") != "login":
            params["token"] = self.token
            
        try:
            # 3. 发送请求 (verify=False 防止SSL报错)
            resp = requests.get(self.base_url, params=params, timeout=15, verify=False)
            
            # 4. 解析 JSON
            try:
                data = resp.json()
                
                # 检查 Token 是否过期 (假设 code 100 或其他为过期，具体视API而定，这里做通用处理)
                # 如果是登录失效，通常需要重新登录。这里简单处理，如果 code 非0且非登录请求，尝试重连
                if str(data.get("code")) != "0" and params.get("api") != "login":
                    msg = str(data.get("msg", ""))
                    if "登录" in msg or "token" in msg.lower():
                        self.log(f"[API] Token 可能失效 ({msg})，尝试重连...")
                        if self.login():
                            params["token"] = self.token
                            # 重发请求
                            resp = requests.get(self.base_url, params=params, timeout=15, verify=False)
                            return resp.json()
                return data
            except ValueError:
                # 假如返回的不是JSON (极少情况)
                self.log(f"[API] 返回非 JSON 数据: {resp.text[:50]}")
                return None
                
        except Exception as e:
            self.log(f"[API错误] 请求异常: {e}")
            return None

    def login(self):
        """登录获取 Token (协议图2)"""
        # 参数: api=login&user=xxx&pass=xxx
        params = {
            "action": "login", # 会在 _request 中转为 api
            "user": self.username,
            "pass": self.password
        }
        res = self._request(params)
        
        # 响应: {"msg": "success", "code": 0, "token": "..."}
        if res and str(res.get("code")) == "0":
            self.token = res.get("token")
            self.log(f"[API] 登录成功，Token: {self.token[:8]}...")
            return True
        else:
            msg = res.get("msg") if res else "无响应"
            self.log(f"[API] 登录失败: {msg}")
            return False

    def search_project_id(self, keyword="Google", country_code="US"):
        """
        搜索项目ID。由于新版API文档未展示 getProjects 接口，
        此处保留旧逻辑并增加 JSON 兼容，同时增加默认 ID 回退。
        """
        # 1. 优先使用 Config 中的默认 ID (基于截图6: Google=20706)
        if keyword.lower() == "google":
            default_sid = CONFIG.get("DEFAULT_GOOGLE_SID", "20706")
            self.sid = default_sid
            self.log(f"[API] 使用默认 Google 项目 ID: {self.sid}")
            return self.sid

        # 2. 尝试调用搜索 (如果API支持)
        self.log(f"[API] 尝试搜索项目: {keyword}...")
        # 注意：这里的 params 可能会失效，如果新版没有 getProjects 接口
        res = self._request({"action": "getProjects"}) 

        if not res:
            self.log("[API] 无法获取项目列表，使用默认配置")
            return self.sid

        # 尝试解析结果 (兼容 JSON List 或 文本行)
        # 如果返回的是 JSON
        if isinstance(res, dict) and "data" in res:
             # 假设结构
             candidates = res["data"]
             # ... 遍历寻找 ...
             pass
        elif isinstance(res, list):
             # ... 遍历寻找 ...
             pass
        else:
            self.log("[API] 项目列表格式未知，跳过搜索")

        return self.sid

    def get_number(self):
        """
        获取号码 (协议图4)
        Returns: phone, phone
        """
        if not self.token and not self.login():
            return None, None

        if not self.sid:
            self.search_project_id("Google")

        # 参数: api=getPhone&token=...&sid=...
        params = {
            "action": "getPhone",
            "sid": self.sid
        }
        
        # 可选参数 (根据截图4)
        # params["exclude"] = "170_171" # 排除虚拟号段示例

        self.log(f"[API] 正在获取号码 (项目ID: {self.sid})...")
        res = self._request(params)

        # 响应推测: {"code": 0, "phone": "13800000000", ...} 或 {"code": 0, "number": "..."}
        if res and str(res.get("code")) == "0":
            # 尝试从常见字段中获取号码
            phone = res.get("phone") or res.get("number") or res.get("mobile")
            
            # 如果没有直接字段，检查 msg 是否就是号码 (部分平台特性)
            if not phone and str(res.get("msg")).isdigit() and len(str(res.get("msg"))) > 6:
                phone = str(res.get("msg"))

            if phone:
                self.current_phone = phone
                self.log(f"✅ 获取号码成功: {phone}")
                return phone, phone

        msg = res.get("msg") if res else "请求失败"
        if "余额" in msg:
            self.log("❌ 余额不足")
        elif "没有" in msg or "lack" in msg.lower():
            self.log("❌ 当前项目缺货")
        else:
            self.log(f"❌ 取号失败: {msg}")

        return None, None

    def get_sms_code(self, phone, timeout=120):
        """
        获取验证码 (协议图5)
        """
        if not phone: return None

        self.log(f"[API] 正在监听短信 (Phone: {phone})...")
        start = time.time()

        # 参数: api=getMessage&token=...&sid=...&phone=...
        params = {
            "action": "getMessage",
            "sid": self.sid,
            "phone": phone
        }

        while time.time() - start < timeout:
            res = self._request(params)

            # 响应: {"code": "0", "msg": "成功", "sms": "...", "yzm": "123456"}
            if res and str(res.get("code")) == "0":
                # 截图5显示直接返回了 'yzm' 字段，非常方便
                yzm = res.get("yzm")
                sms_content = res.get("sms", "")
                
                if yzm:
                    self.log(f"✅ 收到验证码 (API直接解析): {yzm}")
                    return yzm
                
                # 如果 yzm 字段为空，尝试从 sms 内容提取
                if sms_content:
                    code_match = re.search(r'(?:G-|G|)(\d{4,6})', sms_content)
                    if code_match:
                        code = code_match.group(1)
                        self.log(f"✅ 收到短信 (正则提取): {code}")
                        return code

            elif str(res.get("code")) == "0" and "正在" in str(res.get("sms", "")):
                 # 有时 code=0 但内容是 "正在申请..."，视为未收到
                 pass
            
            time.sleep(3)

        self.log("❌ 等待短信超时")
        return None

    def release_number(self, phone):
        """释放号码 (取消)"""
        # 注意：截图未展示 cancelRecv 接口，这里假设沿用旧名或该平台不需要显式释放
        # 如果需要释放，通常 api=cancelRecv 或 api=addBlacklist
        if not phone: return
        self._request({
            "action": "addBlacklist", # 拉黑即释放+不再取该号
            "sid": self.sid,
            "phone": phone
        })
        self.log(f"号码 {phone} 已标记/释放")

    # === Compatibility Methods for BotThread ===

    def set_status_cancel(self, order_id_phone):
        self.release_number(order_id_phone)

    def set_status_complete(self, order_id_phone):
        pass

# =======================================================================================
# === V. 核心逻辑线程 (Core Logic) ===
# =======================================================================================
class BotThread(threading.Thread):
    def __init__(self, accounts, logger_callback, progress_callback, finish_callback):
        super().__init__()
        self.accounts = accounts
        self.log = logger_callback
        self.update_progress = progress_callback
        self.finish = finish_callback

        self.sms_api = HaozhumaClient(
            CONFIG["HZ_USER"],
            CONFIG["HZ_PWD"],
            logger_callback
        )

        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        total = len(self.accounts)
        self.log(f"任务开始，共加载 {total} 个账号")

        # === 预检：登录API ===
        if not self.sms_api.login():
             self.log("❌ API 登录失败，请检查账号密码配置。任务终止。")
             self.finish()
             return

        # === 预检：设置项目 ID ===
        # 使用配置中的默认 Google ID
        self.sms_api.search_project_id("Google")
        
        self.log("隐身模式: 已激活")

        for idx, account in enumerate(self.accounts):
            if not self.running:
                self.log("任务已被用户停止")
                break

            self.update_progress(idx + 1, total, account["email"])
            self.process_account(account)

            if idx < total - 1:
                rest_time = random.randint(5, 10)
                self.log(f"任务完成，等待 {rest_time} 秒...")
                time.sleep(rest_time)

        self.finish()

    def process_account(self, account):
        email = account["email"]
        MAX_ACCOUNT_RETRIES = 3

        for account_attempt in range(MAX_ACCOUNT_RETRIES):
            if not self.running: return

            self.log(f"\n=== [第 {account_attempt + 1}/{MAX_ACCOUNT_RETRIES} 次] 隐身模式处理: {email} ===")

            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=False,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-infobars",
                            "--start-maximized",
                            "--lang=zh-CN,zh"
                        ],
                        ignore_default_args=["--enable-automation"]
                    )

                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        permissions=["clipboard-read", "clipboard-write"]
                    )

                    context.add_init_script(STEALTH_JS)

                    page = context.new_page()

                    try:
                        self.log("Loading login page...")
                        page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")
                        human_delay(1500, 2500)

                        human_type(page, 'input[type="email"]', email)
                        human_delay(500, 1000)
                        page.keyboard.press("Enter")

                        page.wait_for_selector('input[type="password"]', state="visible", timeout=15000)
                        human_delay(1500, 3000)

                        human_type(page, 'input[type="password"]', account["pwd"])
                        human_delay(800, 1500)
                        page.keyboard.press("Enter")

                        try:
                            page.wait_for_selector('input[type="tel"]', timeout=10000)
                            self.log("触发手机验证！启动接码流程...")

                            phone_success = False
                            for phone_attempt in range(3):
                                if not self.running: break
                                if phone_attempt > 0: self.log(f"换号重试 (第 {phone_attempt+1} 次)...")

                                if page.is_visible('input[name="code"]') or page.is_visible('input[id*="Pin"]'):
                                    self.log("发现处于验证码输入页，尝试回退...")
                                    page.go_back()
                                    human_delay(2000, 3000)
                                    if not page.is_visible('input[type="tel"]'):
                                        raise Exception("无法回退到号码输入页")

                                order_id, raw_number = self.sms_api.get_number()
                                if not order_id:
                                    human_delay(2000, 3000)
                                    continue
                                
                                # 格式化号码逻辑 [FIXED]
                                clean_digits = re.sub(r'\D', '', str(raw_number))
                                
                                # 针对中国号码(11位, 1开头)自动添加 +86
                                # 如果是11位且以1开头，判断为缺少国家代码的中国号码
                                if len(clean_digits) == 11 and clean_digits.startswith('1'):
                                    final_phone = f"+86 {clean_digits}"
                                else:
                                    # 否则直接加 +, 假设号码自带国家代码
                                    final_phone = f"+{clean_digits}"
                                
                                self.log(f"尝试填入: {final_phone}")

                                page.click('input[type="tel"]')
                                page.keyboard.press("Control+A")
                                page.keyboard.press("Backspace")
                                human_delay(500, 1000)
                                human_type(page, 'input[type="tel"]', final_phone)
                                human_delay(1000, 2000)
                                page.keyboard.press("Enter")

                                code = self.sms_api.get_sms_code(order_id)
                                if code:
                                    try:
                                        human_delay(1500, 3000)
                                        page.evaluate(f"navigator.clipboard.writeText('{code}')")
                                        try: page.focus('input[name="code"]')
                                        except: page.focus('input[id*="Pin"]')
                                        
                                        self.log(f"模拟人工粘贴验证码: {code}")
                                        page.keyboard.press("Control+V")
                                        human_delay(800, 1500)
                                    except:
                                        try: page.fill('input[name="code"]', code)
                                        except: page.fill('input[id*="Pin"]', code)

                                    page.keyboard.press("Enter")

                                    self.log("提交后观察中...")
                                    page.wait_for_timeout(5000)

                                    if page.is_visible('input[type="tel"]') and not page.is_visible('input[name="code"]'):
                                        self.log("验证无效 (可能号码被滥用)，换号...")
                                        self.sms_api.set_status_cancel(order_id)
                                        continue
                                    else:
                                        self.log(f"账号 {email} 验证通过！")
                                        self.sms_api.set_status_complete(order_id)
                                        page.wait_for_timeout(3000)
                                        phone_success = True
                                        break
                                else:
                                    self.log("超时未收到码，换号...")
                                    self.sms_api.set_status_cancel(order_id)
                                    continue

                            if not phone_success:
                                raise Exception("多次换号验证均失败")

                        except TimeoutError:
                            self.log("未检测到手机验证框，登录似乎直接成功了。")

                        self.log(f"账号 {email} 流程结束！")
                        return

                    except Exception as inner_e:
                        self.log(f"页面操作出错: {inner_e}")
                        raise inner_e
                    finally:
                        human_delay(1000, 2000)
                        browser.close()

            except Exception as e:
                self.log(f"本次尝试失败，休息后重试... ({e})")
                time.sleep(5)

        self.log(f"账号 {email} 彻底处理失败。")
        log_failed_account(email)

# =======================================================================================
# === VI. 图形界面类 (GUI) ===
# =======================================================================================
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Haozhuma API (v2025 JSON) - Python Client")
        self.geometry("700x550")

        self.msg_queue = queue.Queue()
        self.current_bot_thread = None

        self.setup_ui()
        self.check_queue()

    def setup_ui(self):
        frame_top = tk.Frame(self, padx=10, pady=10)
        frame_top.pack(fill=tk.X)

        self.lbl_progress = tk.Label(frame_top, text="等待开始...", font=("Arial", 10, "bold"))
        self.lbl_progress.pack(side=tk.TOP, anchor="w")

        self.progress_bar = ttk.Progressbar(frame_top, orient="horizontal", length=680, mode="determinate")
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))

        frame_log = tk.Frame(self, padx=10, pady=5)
        frame_log.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame_log, text="执行日志:").pack(anchor="w")

        self.txt_log = scrolledtext.ScrolledText(frame_log, state='disabled', height=20)
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        self.txt_log.tag_config("INFO", foreground="black")
        self.txt_log.tag_config("ERROR", foreground="red")
        self.txt_log.tag_config("SUCCESS", foreground="green")

        frame_btn = tk.Frame(self, padx=10, pady=10)
        frame_btn.pack(fill=tk.X)

        self.btn_start = tk.Button(frame_btn, text="开始运行", command=self.start_task, bg="#4CAF50", fg="white", width=15)
        self.btn_start.pack(side=tk.LEFT)

        self.btn_stop = tk.Button(frame_btn, text="停止", command=self.stop_task, bg="#f44336", fg="white", width=15, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.RIGHT)

    def log(self, message):
        self.msg_queue.put(("log", message))

    def update_progress_safe(self, current, total, email):
        self.msg_queue.put(("progress", (current, total, email)))

    def task_finished_safe(self):
        self.msg_queue.put(("finish", None))

    def check_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "log":
                    self.txt_log.config(state='normal')
                    tag = "INFO"
                    if "[失败]" in data or "[错误]" in data or "❌" in data: tag = "ERROR"
                    if "[成功]" in data or "✅" in data or "通过" in data: tag = "SUCCESS"
                    self.txt_log.insert(tk.END, data + "\n", tag)
                    self.txt_log.see(tk.END)
                    self.txt_log.config(state='disabled')
                elif msg_type == "progress":
                    current, total, email = data
                    self.progress_bar["maximum"] = total
                    self.progress_bar["value"] = current
                    self.lbl_progress.config(text=f"进度: {current}/{total} | 当前处理: {email}")
                elif msg_type == "finish":
                    self.btn_start.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    messagebox.showinfo("完成", "所有任务已处理完毕！")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.check_queue)

    def start_task(self):
        accounts = load_accounts_from_file(CONFIG["ACCOUNT_FILE"])
        if not accounts:
            messagebox.showerror("错误", f"未找到账号文件或文件为空: {CONFIG['ACCOUNT_FILE']}")
            return

        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.txt_log.config(state='normal')
        self.txt_log.delete(1.0, tk.END)
        self.txt_log.config(state='disabled')
        self.progress_bar["value"] = 0

        self.current_bot_thread = BotThread(
            accounts,
            self.log,
            self.update_progress_safe,
            self.task_finished_safe
        )
        self.current_bot_thread.start()

    def stop_task(self):
        if self.current_bot_thread and self.current_bot_thread.is_alive():
            self.current_bot_thread.stop()
            self.log("正在停止任务，请等待当前操作完成...")
            self.btn_stop.config(state=tk.DISABLED)

if __name__ == "__main__":
    app = Application()
    app.mainloop()
