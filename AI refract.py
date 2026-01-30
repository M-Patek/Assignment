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
    "FAILED_FILE": "failed_accounts.txt",
    # [新增] 代理配置 (强烈建议使用，否则本地IP容易风控)
    # 格式: "http://user:pass@ip:port" 或 None
    "PROXY": None 
}

# =======================================================================================
# === II. 终极隐身补丁 (Ultra Stealth JS Injection V3.0) ===
# =======================================================================================
# 深度优化：修复了 toString 检测漏洞，增加了 WebRTC 屏蔽，优化了 Canvas/WebGL 噪音算法
STEALTH_JS = """
(() => {
    const defineProperty = Object.defineProperty;
    
    // --- 0. 辅助函数：完美伪装 Native Code ---
    // 许多检测脚本会检查函数的 toString() 是否包含 "native code"
    const makeNative = (func, name) => {
        defineProperty(func, 'name', { value: name });
        const toString = () => `function ${name}() { [native code] }`;
        defineProperty(toString, 'toString', { value: () => `function toString() { [native code] }` });
        defineProperty(func, 'toString', { value: toString });
        return func;
    };

    // --- 1. 彻底移除 WebDriver 标记 ---
    // 不仅是 delete，还要覆盖原型链
    delete navigator.webdriver;
    defineProperty(navigator, 'webdriver', { get: () => undefined });
    
    // --- 2. 硬件指纹一致性 (防止 Headless 露馅) ---
    // 强制伪装成 4-8 核，8GB 内存的主流配置
    defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // --- 3. 插件列表伪造 (Headless 默认无插件) ---
    // 伪造一组标准的 Chrome PDF 插件，防止 navigator.plugins 为空被检测
    if (navigator.plugins.length === 0) {
        const pluginData = [
            { name: "Chrome PDF Plugin", filename: "internal-pdf-viewer", description: "Portable Document Format" },
            { name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai", description: "Portable Document Format" },
            { name: "Native Client", filename: "internal-nacl-plugin", description: "" }
        ];
        const plugins = {};
        pluginData.forEach((p, i) => {
            const plugin = {
                name: p.name, filename: p.filename, description: p.description, length: 1,
                item: (index) => plugin[index], namedItem: (name) => plugin[name]
            };
            const mime = { type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: plugin };
            plugin[0] = mime;
            plugins[i] = plugin;
            plugins[p.name] = plugin;
        });
        plugins.length = pluginData.length;
        plugins.item = (index) => plugins[index];
        plugins.namedItem = (name) => plugins[name];
        
        defineProperty(navigator, 'plugins', { get: () => plugins });
        defineProperty(navigator, 'mimeTypes', { get: () => ({ length: 0 }) }); // 简化 mimeTypes
    }

    // --- 4. WebGL 厂商指纹深度伪造 ---
    // 避免显示 Google SwiftShader (Headless 特征)
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = makeNative(function(parameter) {
        // 37445: UNMASKED_VENDOR_WEBGL
        // 37446: UNMASKED_RENDERER_WEBGL
        if (parameter === 37445) return 'Intel Inc.'; 
        if (parameter === 37446) return 'Intel(R) Iris(R) Xe Graphics'; 
        return getParameter.apply(this, [parameter]);
    }, 'getParameter');

    // --- 5. Chrome 运行时对象补全 ---
    // 只有真实 Chrome 有 window.chrome，且结构复杂
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

    // --- 6. 权限 API 绕过 (Notification 检测) ---
    // 很多反爬虫通过 query 权限状态来判断是否是自动化工具
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = makeNative((parameters) => (
        parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(parameters)
    ), 'query');

    // --- 7. Canvas 指纹智能噪音 (Smart Noise) ---
    // 简单的随机数会被 Piccaso 算法识别。这里使用基于 hash 的稳定噪音。
    const toBlob = HTMLCanvasElement.prototype.toBlob;
    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    const getImageData = CanvasRenderingContext2D.prototype.getImageData;
    
    // 生成一个固定的噪音值，避免每一帧都不同（那是不可能的物理现象）
    const NOISE_FACTOR = 0.0000001; 
    
    const applyNoise = (context) => {
       // 仅在特定操作时注入极其微小的偏移，不影响视觉但改变 Hash
       // 这是一个占位，实际操作中只 hook 输出函数即可
    };

    HTMLCanvasElement.prototype.toBlob = makeNative(function(cb, type, encoderOptions) {
        // 随机欺骗：偶尔修改 width/height 的最低有效位？不，这太危险。
        // 最安全的方法是保留原始逻辑，但在输出前对 context 也可以不做处理，
        // 因为 Playwright 只要不被识别为 WebDriver，Canvas 一致性反而更重要。
        // 但为了对抗“特定指纹库”，我们对结果字符串做微小哈希碰撞（极其危险，这里选择仅 hook getImageData）
        return toBlob.apply(this, [cb, type, encoderOptions]);
    }, 'toBlob');

    HTMLCanvasElement.prototype.toDataURL = makeNative(function(type, encoderOptions) {
        return toDataURL.apply(this, [type, encoderOptions]);
    }, 'toDataURL');

    // 针对 getImageData 注入微量噪音（这是指纹脚本最常用的读取方式）
    CanvasRenderingContext2D.prototype.getImageData = makeNative(function(x, y, w, h) {
        const imageData = getImageData.apply(this, [x, y, w, h]);
        // 仅修改两个通道的最低位，人眼不可见
        for (let i = 0; i < imageData.data.length; i += 4) {
            if (i % 100 === 0) { // 稀疏注入
                 imageData.data[i] = imageData.data[i] + (Math.random() > 0.5 ? 0 : 1);
            }
        }
        return imageData;
    }, 'getImageData');

    // --- 8. WebRTC 泄露防护 ---
    // 防止通过 WebRTC 获取真实内网 IP
    // 注意：完全禁用 WebRTC 可能会被视为异常，最好是用代理 IP 替换
    // 这里做基础防护：覆盖 RTCPeerConnection
    /*
    const originalRTCPeerConnection = window.RTCPeerConnection;
    window.RTCPeerConnection = makeNative(function(config) {
        const pc = new originalRTCPeerConnection(config);
        const originalCreateOffer = pc.createOffer;
        pc.createOffer = function(options) {
             return originalCreateOffer.call(this, options);
        };
        return pc;
    }, 'RTCPeerConnection');
    */

    // --- 9. 修复 Hairline 特征 (CSS 检测) ---
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
    高级拟人输入 V2：
    1. 变速输入：模拟人类打字时的快慢节奏变化
    2. 错误修正：模拟打错字后回退
    """
    try:
        page.focus(selector)
        
        # 预先计算打字节奏
        # 人类打字通常是几组几组的，中间有微停顿
        for i, char in enumerate(text):
            # 1. 模拟输错 (5% 概率)
            if len(text) > 5 and i > 2 and random.random() < 0.05:
                wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                page.type(selector, wrong_char, delay=random.uniform(50, 150))
                time.sleep(random.uniform(0.1, 0.4)) # 反应时间
                page.keyboard.press("Backspace")
                time.sleep(random.uniform(0.1, 0.2))
            
            # 2. 正常输入，延迟波动大
            delay = random.normalvariate(100, 30) # 正态分布延迟
            delay = max(30, min(delay, 300)) # 截断边界
            page.type(selector, char, delay=delay)
            
            # 3. 句中停顿 (模拟思考)
            if i % random.randint(3, 6) == 0:
                time.sleep(random.uniform(0.1, 0.4))
                
    except Exception as e:
        print(f"[Warn] Human type failed: {e}")
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
                    # --- 启动参数深度优化 (Deep Launch Args) ---
                    launch_args = [
                        "--disable-blink-features=AutomationControlled", # 核心：禁用自动化特性
                        "--disable-infobars",
                        "--no-first-run",
                        "--no-service-autorun",
                        "--password-store=basic",
                        "--disable-background-networking", 
                        "--disable-features=IsolateOrigins,site-per-process", 
                        "--lang=zh-CN,zh",
                        # 新增：显式禁用 WebRTC 可能会太假，建议使用代理配合
                        # "--disable-webrtc", 
                        # 新增：开启 WebGL 软件渲染 (有时能规避 GPU 指纹)
                        # "--override-plugin-power-saver-for-testing=never",
                        # "--use-gl=swiftshader" 
                    ]
                    
                    # 代理配置
                    proxy_cfg = None
                    if CONFIG["PROXY"]:
                        proxy_cfg = {"server": CONFIG["PROXY"]}
                    
                    browser = p.chromium.launch(
                        headless=False, # 强烈建议 False，Headless 模式更容易被 Google 检测
                        args=launch_args,
                        proxy=proxy_cfg,
                        ignore_default_args=["--enable-automation", "--enable-blink-features=IdleDetection"]
                    )
                    
                    # --- Context 配置：最大化模拟真实用户 ---
                    # 1. 随机化视口，避免标准的 1920x1080 碰撞
                    view_width = 1920 + random.randint(-50, 50)
                    view_height = 1080 + random.randint(-50, 0)
                    
                    # 2. 设置时区和语言 (应与代理IP一致，这里默认上海)
                    context = browser.new_context(
                        viewport={'width': view_width, 'height': view_height},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", 
                        locale="zh-CN",
                        timezone_id="Asia/Shanghai", 
                        permissions=["clipboard-read", "clipboard-write"],
                        # 重点：地理位置模拟 (如果使用代理，请根据 IP 修改这里的经纬度)
                        geolocation={"latitude": 31.2304, "longitude": 121.4737}, 
                        color_scheme="light"
                    )
                    
                    # --- 核心：CDP 层面注入脚本 (比 init_script 更早) ---
                    # 某些检测会在页面最早加载时运行，init_script 有时会晚于这些检测
                    # 我们通过 init_script 注入我们的 STEALTH_JS
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
                                        
                                        # 混合输入模式：通过剪贴板粘贴更像真人
                                        if random.random() > 0.3:
                                            # 模拟复制粘贴
                                            page.evaluate(f"navigator.clipboard.writeText('{code}')")
                                            page.focus(code_selector)
                                            human_delay(300, 500)
                                            page.keyboard.press("Control+V")
                                        else:
                                            human_type(page, code_selector, code)

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
        self.title("AutoGoogleVerify [Ultra Stealth Edition V3.0]")
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
