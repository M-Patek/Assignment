import re
import time
import os
import random
import requests
import threading
import queue
import tkinter as tk
import json
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
# === II. 终极隐身补丁 (Ultra Stealth JS Injection) ===
# =======================================================================================
# 包含了 Canvas 噪音、音频噪音、WebGL 伪造、Webdriver 移除及 Native Code 伪装
STEALTH_JS = """
(() => {
    const defineProperty = Object.defineProperty;
    
    // --- 1. 基础 Webdriver 移除与 Native 伪装工具 ---
    const stripErrorStack = (stack) => {
        if (!stack) return stack;
        return stack.split('\\n').filter(line => !line.includes('at Object.apply')).join('\\n');
    };

    const makeNative = (func, name) => {
        defineProperty(func, 'name', { value: name });
        const toString = () => `function ${name}() { [native code] }`;
        defineProperty(func, 'toString', { value: toString });
        defineProperty(toString, 'toString', { value: () => `function toString() { [native code] }` });
        return func;
    };

    // --- 2. 移除 Navigator.webdriver ---
    delete navigator.webdriver;
    defineProperty(navigator, 'webdriver', { get: () => undefined });

    // --- 3. 硬件指纹混淆 (Hardware Concurrency & Memory) ---
    defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // --- 4. WebGL 指纹伪造 ---
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = makeNative(function(parameter) {
        // 37445: UNMASKED_VENDOR_WEBGL
        // 37446: UNMASKED_RENDERER_WEBGL
        if (parameter === 37445) return 'Intel Inc.'; 
        if (parameter === 37446) return 'Intel(R) Iris(R) Xe Graphics'; 
        return getParameter.apply(this, [parameter]);
    }, 'getParameter');

    // --- 5. Chrome 运行时对象深度伪造 ---
    if (!window.chrome) { window.chrome = {}; }
    const chromeMock = {
        runtime: {
            connect: makeNative(() => {}, 'connect'),
            sendMessage: makeNative(() => {}, 'sendMessage'),
            PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android' },
            PlatformArch: { ARM: 'arm', X86_64: 'x86-64' }
        },
        app: {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
            getIsInstalled: makeNative(() => false, 'getIsInstalled'),
            getDetails: makeNative(() => null, 'getDetails')
        },
        loadTimes: makeNative(() => {}, 'loadTimes'),
        csi: makeNative(() => {}, 'csi')
    };
    Object.keys(chromeMock).forEach(key => {
        if (!window.chrome[key]) window.chrome[key] = chromeMock[key];
    });

    // --- 6. 权限 API 绕过 ---
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = makeNative((parameters) => (
        parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(parameters)
    ), 'query');

    // --- 7. Canvas 指纹噪音 (关键：防止像素级追踪) ---
    const toBlob = HTMLCanvasElement.prototype.toBlob;
    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    const getImageData = CanvasRenderingContext2D.prototype.getImageData;
    
    // 注入微小的随机噪音
    const noise = {
        r: Math.floor(Math.random() * 10) - 5,
        g: Math.floor(Math.random() * 10) - 5,
        b: Math.floor(Math.random() * 10) - 5,
        a: Math.floor(Math.random() * 10) - 5
    };

    const shiftPixel = (context) => {
        const imageData = getImageData.apply(context, [0, 0, 1, 1]);
        const p = imageData.data;
        p[0] += noise.r; p[1] += noise.g; p[2] += noise.b; p[3] += noise.a;
        context.putImageData(imageData, 0, 0);
    };

    HTMLCanvasElement.prototype.toBlob = makeNative(function(cb, type, encoderOptions) {
        shiftPixel(this.getContext('2d'));
        return toBlob.apply(this, [cb, type, encoderOptions]);
    }, 'toBlob');

    HTMLCanvasElement.prototype.toDataURL = makeNative(function(type, encoderOptions) {
        shiftPixel(this.getContext('2d'));
        return toDataURL.apply(this, [type, encoderOptions]);
    }, 'toDataURL');

    // --- 8. AudioContext 指纹噪音 ---
    const originalCreateOscillator = AudioContext.prototype.createOscillator;
    const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
    
    AudioContext.prototype.createAnalyser = makeNative(function() {
        const analyser = originalCreateAnalyser.apply(this, arguments);
        const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;
        analyser.getFloatFrequencyData = makeNative(function(array) {
            const ret = originalGetFloatFrequencyData.apply(this, arguments);
            for (let i = 0; i < array.length; i += 10) {
                array[i] += (Math.random() * 0.1) - 0.05; // 增加微小扰动
            }
            return ret;
        }, 'getFloatFrequencyData');
        return analyser;
    }, 'createAnalyser');

    // --- 9. 修复 Hairline 特征 ---
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
    """
    高级拟人输入：
    1. 随机输入速度
    2. 小概率模拟输错并回退 (Typo Simulation)
    """
    try:
        page.focus(selector)
        for i, char in enumerate(text):
            # 2% 的概率输错一个字符 (仅针对长文本，避免验证码输错)
            if len(text) > 5 and random.random() < 0.02:
                wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                page.type(selector, wrong_char, delay=random.uniform(50, 150))
                time.sleep(random.uniform(0.1, 0.3))
                page.keyboard.press("Backspace")
                time.sleep(random.uniform(0.1, 0.3))
            
            page.type(selector, char, delay=random.uniform(40, 180)) # 波动更大的延迟
            
            # 句子中间偶尔停顿
            if i % 4 == 0 and random.random() < 0.1:
                time.sleep(random.uniform(0.2, 0.5))
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
                
            self.update_progress(idx + 1, total, account["email"])
            self.process_account(account)
            
            if idx < total - 1:
                # 随机休息时间，避免高频请求被风控
                rest_time = random.randint(8, 15) 
                self.log(f"任务间歇，安全冷却 {rest_time} 秒...")
                time.sleep(rest_time)
        
        self.finish()

    def process_account(self, account):
        email = account["email"]
        MAX_ACCOUNT_RETRIES = 3 
        
        for account_attempt in range(MAX_ACCOUNT_RETRIES):
            if not self.running: return

            self.log(f"\n>>> [第 {account_attempt + 1}/{MAX_ACCOUNT_RETRIES} 次] 隐身模式处理: {email}")
            
            try:
                with sync_playwright() as p:
                    # --- 启动参数深度优化 ---
                    launch_args = [
                        "--disable-blink-features=AutomationControlled", # 核心：禁用自动化特性
                        "--disable-infobars",
                        "--no-first-run",
                        "--no-service-autorun",
                        "--password-store=basic",
                        "--disable-background-networking", # 减少后台噪音
                        "--disable-features=IsolateOrigins,site-per-process", # 某些情况下有助于绕过iframe检测
                        "--lang=zh-CN,zh"
                    ]
                    
                    browser = p.chromium.launch(
                        headless=False, # 强烈建议 False，Headless 模式更容易被 Google 检测
                        args=launch_args,
                        ignore_default_args=["--enable-automation", "--enable-blink-features=IdleDetection"]
                    )
                    
                    # 随机化视口，避免标准的 1920x1080 碰撞
                    view_width = 1920 + random.randint(-50, 50)
                    view_height = 1080 + random.randint(-50, 0)
                    
                    context = browser.new_context(
                        viewport={'width': view_width, 'height': view_height},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", # 固定一个稳定的 Win10 UA，确保与 Platform 伪装一致
                        locale="zh-CN",
                        timezone_id="Asia/Shanghai", # 建议根据 IP 动态调整，这里默认
                        permissions=["clipboard-read", "clipboard-write"]
                    )
                    
                    # 注入增强版隐身脚本
                    context.add_init_script(STEALTH_JS)
                    page = context.new_page()
                    
                    try:
                        self.log("正在加载登录页面...")
                        page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")
                        
                        # 随机鼠标抖动，增加真实感
                        page.mouse.move(random.randint(100, 500), random.randint(100, 500))
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
                            # 增加等待时间，防止网络抖动
                            page.wait_for_selector('input[type="tel"]', timeout=12000)
                            self.log("[检测] 触发手机号验证，启动接码流程...")
                            
                            phone_success = False
                            for phone_attempt in range(3):
                                if not self.running: break
                                if phone_attempt > 0: self.log(f"[重试] 换号重试 (第 {phone_attempt+1} 次)...")
                                
                                # 智能回退检测
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
                                
                                # 模拟更真实的操作：点击 -> 全选 -> 删除 -> 停顿 -> 输入
                                page.click('input[type="tel"]')
                                human_delay(200, 400)
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
                                        
                                        # 验证码通常是粘贴的，模拟粘贴操作比手打更像真人行为 (有时)
                                        # 但为了保险，我们使用混合模式
                                        if random.random() > 0.5:
                                            human_type(page, code_selector, code)
                                        else:
                                            page.fill(code_selector, code)
                                            human_delay(300, 600)

                                    except Exception:
                                        try: page.fill('input[name="code"]', code)
                                        except: page.fill('input[id*="Pin"]', code)

                                    page.keyboard.press("Enter")
                                    self.log("[状态] 提交后观察中...")
                                    page.wait_for_timeout(5000)
                                    
                                    # 检查是否被 Google 拒绝号码 (此号码无法用于验证)
                                    if page.is_visible('input[type="tel"]') and not page.is_visible('input[name="code"]'):
                                        self.log("[失败] 号码被 Google 拒绝，尝试更换...")
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
# === VI. 图形界面类 (GUI) - 保持原样 ===
# =======================================================================================
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AutoGoogleVerify [Ultra Stealth Edition]")
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
        
        tk.Label(frame_log, text="执行日志 (Ultra Stealth Active):").pack(anchor="w")
        
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
                    if "[失败]" in data or "[错误]" in data: tag = "ERROR"
                    if "[成功]" in data: tag = "SUCCESS"
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
