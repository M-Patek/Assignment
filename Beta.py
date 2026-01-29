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

# =======================================================================================
# === I. 全局配置区域 (Configuration) ===
# =======================================================================================
CONFIG = {
    "API_KEY": "YOUR_HERO_SMS_API_KEY",  # 请替换为您的 API Key
    "BASE_URL": "https://hero-sms.com/stubs/handler_api.php",
    "SERVICE_CODE": "go",   # Google 项目代码
    "COUNTRY_ID": "6",      # 印度尼西亚 (可修改)
    "ACCOUNT_FILE": "accounts.txt",
    "FAILED_FILE": "failed_accounts.txt"
}

# =======================================================================================
# === II. 核心隐身补丁 (Stealth JS Injection) ===
# =======================================================================================
STEALTH_JS = """
(() => {
    const defineProperty = Object.defineProperty;
    delete navigator.webdriver;
    defineProperty(navigator, 'webdriver', { get: () => undefined });
    defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel(R) Iris(R) Xe Graphics'; 
        return getParameter.apply(this, [parameter]);
    };
    if (!window.chrome) { window.chrome = {}; }
    const chromeMock = {
        runtime: {
            connect: () => {}, sendMessage: () => {},
            PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android' },
            PlatformArch: { ARM: 'arm', X86_64: 'x86-64' }
        },
        app: {
            isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
        }
    };
    Object.keys(chromeMock).forEach(key => {
        if (!window.chrome[key]) window.chrome[key] = chromeMock[key];
    });
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(parameters)
    );
    defineProperty(HTMLElement.prototype, 'offsetHeight', {
        get() { return this.getBoundingClientRect().height; }
    });
})();
"""

# =======================================================================================
# === III. 工具函数 ===
# =======================================================================================

def human_delay(min_ms=800, max_ms=2000):
    time.sleep(random.uniform(min_ms, max_ms) / 1000)

def human_type(page, selector, text):
    try:
        page.focus(selector)
        for char in text:
            page.type(selector, char, delay=random.uniform(50, 150))
    except Exception as e:
        page.fill(selector, text)

def load_accounts_from_file(file_path):
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
    try:
        with open(CONFIG["FAILED_FILE"], "a", encoding="utf-8") as f:
            f.write(f"{email}\n")
    except Exception:
        pass

# =======================================================================================
# === IV. 接码客户端 (SMS Client) ===
# =======================================================================================
class HeroSMSClient:
    def __init__(self, logger_callback):
        self.api_key = CONFIG["API_KEY"]
        self.base_url = CONFIG["BASE_URL"]
        self.log = logger_callback

    def _request(self, params):
        params["api_key"] = self.api_key
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            return response.text
        except Exception as e:
            self.log(f"[API错误] 网络请求出错: {e}")
            return None

    def get_number(self):
        params = { "action": "getNumber", "service": CONFIG["SERVICE_CODE"], "country": CONFIG["COUNTRY_ID"] }
        self.log(f"[API] 正在请求 Google 号码 (国家ID: {CONFIG['COUNTRY_ID']})...")
        result = self._request(params)
        if result and "ACCESS_NUMBER" in result:
            parts = result.split(":")
            if len(parts) >= 3: return parts[1], parts[2]
        
        if result == "NO_NUMBERS": self.log("[API] 当前国家无号")
        elif result == "NO_BALANCE": self.log("[API] 余额不足")
        else: self.log(f"[API] 错误: {result}")
        return None, None

    def get_sms_code(self, activation_id, timeout=120):
        params = {"action": "getStatus", "id": activation_id}
        self.log(f"[API] 正在监听短信 (ID: {activation_id})...")
        start = time.time()
        while time.time() - start < timeout:
            result = self._request(params)
            if result and result.startswith("STATUS_OK"):
                code = result.split(":")[1]
                self.log(f"[API] 收到验证码: {code}")
                return code
            elif result == "STATUS_CANCEL":
                self.log("[API] 订单被取消")
                return None
            time.sleep(3)
        return None

    def set_status_complete(self, activation_id):
        self._request({"action": "setStatus", "id": activation_id, "status": "6"})
        self.log("[API] 订单标记完成")

    def set_status_cancel(self, activation_id):
        self._request({"action": "setStatus", "id": activation_id, "status": "8"})
        self.log("[API] 订单已取消")

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
        self.sms_api = HeroSMSClient(logger_callback)
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        total = len(self.accounts)
        self.log(f"任务开始，共加载 {total} 个账号")
        
        for idx, account in enumerate(self.accounts):
            if not self.running:
                self.log("任务已被用户停止")
                break
                
            # 更新进度条: (当前索引+1, 总数, 当前账号)
            self.update_progress(idx + 1, total, account["email"])
            self.process_account(account)
            
            if idx < total - 1:
                rest_time = random.randint(5, 10)
                self.log(f"任务间歇，等待 {rest_time} 秒...")
                time.sleep(rest_time)
        
        self.finish()

    def process_account(self, account):
        email = account["email"]
        MAX_ACCOUNT_RETRIES = 3 
        
        for account_attempt in range(MAX_ACCOUNT_RETRIES):
            if not self.running: return

            self.log(f"\n>>> [第 {account_attempt + 1}/{MAX_ACCOUNT_RETRIES} 次] 处理账号: {email}")
            
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
                        self.log("正在加载登录页面...")
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
                        
                        # --- 验证流程 ---
                        try:
                            page.wait_for_selector('input[type="tel"]', timeout=10000)
                            self.log("[检测] 触发手机号验证，启动接码流程...")
                            
                            phone_success = False
                            for phone_attempt in range(3):
                                if not self.running: break
                                if phone_attempt > 0: self.log(f"[重试] 换号重试 (第 {phone_attempt+1} 次)...")
                                
                                if page.is_visible('input[name="code"]') or page.is_visible('input[id*="Pin"]'):
                                    self.log("[状态] 处于验证码页，尝试回退...")
                                    page.go_back() 
                                    human_delay(2000, 3000)
                                    if not page.is_visible('input[type="tel"]'):
                                        raise Exception("无法回退到号码输入页")
                                
                                order_id, raw_number = self.sms_api.get_number()
                                if not order_id: 
                                    human_delay(2000, 3000)
                                    continue
                                
                                clean_digits = re.sub(r'\D', '', str(raw_number))
                                final_phone = f"+{clean_digits}"
                                self.log(f"[输入] 尝试填入号码: {final_phone}")
                                
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
                                        code_selector = 'input[name="code"]'
                                        if not page.is_visible(code_selector):
                                            code_selector = 'input[id*="Pin"]'
                                        
                                        self.log(f"[输入] 填入验证码: {code}")
                                        human_type(page, code_selector, code)
                                        human_delay(200, 500) 
                                    except Exception:
                                        try: page.fill('input[name="code"]', code)
                                        except: page.fill('input[id*="Pin"]', code)

                                    page.keyboard.press("Enter")
                                    self.log("[状态] 提交后观察中...")
                                    page.wait_for_timeout(5000)
                                    
                                    if page.is_visible('input[type="tel"]') and not page.is_visible('input[name="code"]'):
                                        self.log("[失败] 号码被拒绝，尝试更换...")
                                        self.sms_api.set_status_cancel(order_id)
                                        continue 
                                    else:
                                        self.log(f"[成功] 账号 {email} 验证通过")
                                        self.sms_api.set_status_complete(order_id)
                                        page.wait_for_timeout(3000)
                                        phone_success = True
                                        break 
                                else:
                                    self.log("[超时] 未收到验证码，换号...")
                                    self.sms_api.set_status_cancel(order_id)
                                    continue
                            
                            if not phone_success:
                                raise Exception("多次换号验证均失败")
                                
                        except TimeoutError:
                            self.log("[通过] 未检测到手机验证框，直登成功")
                        
                        self.log(f"[完成] 账号 {email} 处理结束")
                        return 
                        
                    except Exception as inner_e:
                        self.log(f"[错误] 页面操作出错: {inner_e}")
                        raise inner_e 
                    finally:
                        human_delay(1000, 2000)
                        browser.close()
                        
            except Exception as e:
                self.log(f"[异常] 本次尝试失败，休息后重试... ({e})")
                time.sleep(5)
        
        self.log(f"[失败] 账号 {email} 彻底处理失败，已记录")
        log_failed_account(email)

# =======================================================================================
# === VI. 图形界面类 (GUI) ===
# =======================================================================================
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoGoogleVerify 验证助手")
        self.geometry("700x550")
        
        # 消息队列，用于子线程向主线程发消息
        self.msg_queue = queue.Queue()
        self.current_bot_thread = None
        
        self.setup_ui()
        self.check_queue() # 启动队列检查循环

    def setup_ui(self):
        # 1. 顶部进度区域
        frame_top = tk.Frame(self, padx=10, pady=10)
        frame_top.pack(fill=tk.X)
        
        self.lbl_progress = tk.Label(frame_top, text="等待开始...", font=("Arial", 10, "bold"))
        self.lbl_progress.pack(side=tk.TOP, anchor="w")
        
        self.progress_bar = ttk.Progressbar(frame_top, orient="horizontal", length=680, mode="determinate")
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))
        
        # 2. 日志区域
        frame_log = tk.Frame(self, padx=10, pady=5)
        frame_log.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame_log, text="执行日志:").pack(anchor="w")
        
        self.txt_log = scrolledtext.ScrolledText(frame_log, state='disabled', height=20)
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        # 定义日志颜色标签
        self.txt_log.tag_config("INFO", foreground="black")
        self.txt_log.tag_config("ERROR", foreground="red")
        self.txt_log.tag_config("SUCCESS", foreground="green")

        # 3. 底部按钮区域
        frame_btn = tk.Frame(self, padx=10, pady=10)
        frame_btn.pack(fill=tk.X)
        
        self.btn_start = tk.Button(frame_btn, text="开始运行", command=self.start_task, bg="#4CAF50", fg="white", width=15)
        self.btn_start.pack(side=tk.LEFT)
        
        self.btn_stop = tk.Button(frame_btn, text="停止", command=self.stop_task, bg="#f44336", fg="white", width=15, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.RIGHT)

    def log(self, message):
        """将日志放入队列，线程安全"""
        self.msg_queue.put(("log", message))

    def update_progress_safe(self, current, total, email):
        """将进度信息放入队列"""
        self.msg_queue.put(("progress", (current, total, email)))

    def task_finished_safe(self):
        """将完成信号放入队列"""
        self.msg_queue.put(("finish", None))

    def check_queue(self):
        """在主线程定时轮询队列，更新UI"""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                
                if msg_type == "log":
                    self.txt_log.config(state='normal')
                    tag = "INFO"
                    if "[失败]" in data or "[错误]" in data: tag = "ERROR"
                    if "[成功]" in data: tag = "SUCCESS"
                    self.txt_log.insert(tk.END, data + "\n", tag)
                    self.txt_log.see(tk.END) # 自动滚动到底部
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
            self.after(100, self.check_queue) # 每100ms检查一次

    def start_task(self):
        accounts = load_accounts_from_file(CONFIG["ACCOUNT_FILE"])
        if not accounts:
            messagebox.showerror("错误", f"未找到账号文件或文件为空: {CONFIG['ACCOUNT_FILE']}")
            return
            
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.txt_log.config(state='normal')
        self.txt_log.delete(1.0, tk.END) # 清空日志
        self.txt_log.config(state='disabled')
        self.progress_bar["value"] = 0
        
        # 启动子线程运行爬虫逻辑
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
