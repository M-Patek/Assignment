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
    # 豪猪网/易码协议配置
    "HZ_USER": "",  # 您的 API 账号
    "HZ_PWD": "",   # 您的 API 密码
    "HZ_BASE_URL": "http://api.haozhu.wang/api/do.php", # 豪猪网 API 地址 (易码协议)

    "TARGET_COUNTRY": "US", # 目标国家 keyword，用于搜索项目，如 "US" (美国) 或 "HK" (香港)

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
# === IV. 接码客户端 (HaozhumaClient - Yima Protocol) ===
# =======================================================================================
class HaozhumaClient:
    def __init__(self, username, password, logger_callback):
        self.username = username
        self.password = password
        self.base_url = CONFIG.get("HZ_BASE_URL", "http://api.haozhu.wang/api/do.php")
        self.log = logger_callback
        self.token = None
        self.sid = None  # 项目 ID (Project ID)
        self.current_phone = None

    def _request(self, params):
        """通用请求函数，处理网络异常"""
        try:
            # 自动附加 token (如果存在且不是登录请求)
            if self.token and "token" not in params and params.get("action") != "login":
                params["token"] = self.token

            resp = requests.get(self.base_url, params=params, timeout=15)
            text = resp.text.strip()

            # 简单的错误检查 (易码协议常见错误)
            if text in ["not_login", "time_out", "login_error"]:
                self.log(f"[API] 登录失效，尝试重连... ({text})")
                if self.login(): # 尝试重新登录
                    params["token"] = self.token
                    return requests.get(self.base_url, params=params, timeout=15).text.strip()
                else:
                    return "LOGIN_FAILED"
            return text
        except Exception as e:
            self.log(f"[API错误] 请求异常: {e}")
            return None

    def login(self):
        """登录获取 Token"""
        params = {
            "action": "login",
            "username": self.username,
            "password": self.password
        }
        res = self._request(params)
        if res and "|" in res:
            # 成功格式通常为: token|余额
            parts = res.split("|")
            self.token = parts[0]
            balance = parts[1]
            self.log(f"[API] 登录成功，Token: {self.token[:8]}..., 余额: {balance}")
            return True
        else:
            self.log(f"[API] 登录失败: {res}")
            return False

    def search_project_id(self, keyword="Google", country_code="US"):
        """
        搜索项目ID。
        逻辑：获取所有项目列表，查找包含 keyword (如 Google) 和 country_code (如 US/美国) 的项目。
        """
        self.log(f"[API] 正在搜索项目 ID: 关键词='{keyword}', 国家='{country_code}'...")

        # 尝试获取项目列表 (易码协议 action=getProjects 或 getSummary)
        res = self._request({"action": "getProjects"})

        if not res:
            self.log("[API] 无法获取项目列表，可能网络问题或接口变更")
            return None

        # 假设返回格式为每行: id|name|price 或 JSON
        # 这里按标准易码协议处理: 文本行, 分隔符可能不统一, 常见是 |
        lines = res.split('\n')
        candidates = []

        for line in lines:
            if keyword.lower() in line.lower():
                candidates.append(line)

        if not candidates:
             self.log(f"[API] 未找到任何包含 '{keyword}' 的项目")
             return None

        # 二次筛选国家
        final_sid = None
        target_name = ""

        country_keywords = [country_code]
        if country_code == "US": country_keywords.append("美国")
        if country_code == "HK": country_keywords.append("香港")

        for item in candidates:
            for ck in country_keywords:
                if ck in item:
                    parts = item.split('|')
                    if len(parts) >= 2:
                        final_sid = parts[0]
                        target_name = parts[1]
                        self.log(f"[API] 找到匹配项目: {target_name} (ID: {final_sid})")
                        break
            if final_sid: break

        # 如果找不到特定国家，默认取第一个包含 keyword 的
        if not final_sid and candidates:
            parts = candidates[0].split('|')
            final_sid = parts[0]
            target_name = parts[1] if len(parts) > 1 else "未知"
            self.log(f"[API] 未找到指定国家({country_code})项目，使用默认匹配: {target_name} (ID: {final_sid})")

        if final_sid:
            self.sid = final_sid
            return final_sid

        self.log("[API] 未找到符合条件的项目 ID")
        return None

    def get_number(self):
        """
        获取号码
        Returns: order_id (phone), raw_number (phone)
        为了兼容 BotThread，返回 (phone, phone)，因为易码协议中手机号即订单号
        """
        if not self.token and not self.login():
            return None, None

        if not self.sid:
            # 尝试搜索 ID，默认 Google
            target_country = CONFIG.get("TARGET_COUNTRY", "US")
            if not self.search_project_id("Google", target_country):
                self.log("❌ 无法确定项目ID，请检查配置或手动指定。")
                return None, None

        params = {
            "action": "getPhone",
            "sid": self.sid
        }

        self.log(f"[API] 正在获取号码 (项目ID: {self.sid})...")
        res = self._request(params)

        # 成功格式: success|13800138000
        # 或者直接返回号码: 13800138000
        # 易码协议标准通常是: success|phone 或 1|phone

        phone = None
        if res and ("success" in res or res.startswith("1|")):
            parts = res.split("|")
            if len(parts) >= 2:
                phone = parts[1]
            else:
                # 有些平台直接返回号码，且不是错误代码
                if len(res) > 7 and "|" not in res:
                    phone = res

        if phone:
            self.current_phone = phone
            self.log(f"✅ 获取号码成功: {phone}")
            return phone, phone # 兼容旧代码

        if "没有" in str(res) or "Lack" in str(res) or "no_phone" in str(res):
            self.log("❌ 当前项目缺货 (No numbers available)")
        elif "balance" in str(res) or "money" in str(res):
            self.log("❌ 余额不足")
        else:
            self.log(f"❌ 取号失败: {res}")

        return None, None

    def get_sms_code(self, order_id_phone, timeout=120):
        """
        获取验证码
        order_id_phone: 在 Yima 协议中，phone 就是用于查询的 ID
        """
        if not order_id_phone: return None

        self.log(f"[API] 正在监听短信 (Phone: {order_id_phone})...")
        start = time.time()

        params = {
            "action": "getMessage",
            "sid": self.sid,
            "phone": order_id_phone
        }

        while time.time() - start < timeout:
            res = self._request(params)

            # 成功格式: success|验证码内容... 或 1|验证码
            if res and ("success" in res or res.startswith("1|")):
                parts = res.split("|")
                msg_body = parts[1] if len(parts) > 1 else res

                # 尝试提取纯数字验证码 (通常6位，Google 有时是 G-xxxxxx)
                # 匹配 G-123456 或 123456
                code_match = re.search(r'(?:G-|G|)(\d{4,6})', msg_body)
                code = code_match.group(1) if code_match else msg_body

                self.log(f"✅ 收到短信: {code}")
                return code

            elif "not_receive" in res or res == "0":
                pass # 继续等待
            else:
                pass

            time.sleep(3)

        self.log("❌ 等待短信超时")
        return None

    def release_number(self, phone):
        """释放号码 (取消)"""
        if not phone: return
        self._request({
            "action": "cancelRecv",
            "sid": self.sid,
            "phone": phone
        })
        self.log(f"号码 {phone} 已释放/取消")

    def add_blacklist(self, phone):
        """拉黑号码 (标记失败)"""
        if not phone: return
        self._request({
            "action": "addBlacklist",
            "sid": self.sid,
            "phone": phone
        })
        self.log(f"号码 {phone} 已拉黑")

    # === Compatibility Methods for BotThread ===

    def set_status_cancel(self, order_id_phone):
        # 对应旧代码的 "取消订单"
        self.release_number(order_id_phone)

    def set_status_complete(self, order_id_phone):
        # 对应旧代码的 "完成订单"
        # 易码协议通常不需要显式完成，取码即扣费
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

        # === 修改点：使用新的 HaozhumaClient ===
        self.sms_api = HaozhumaClient(
            CONFIG["HZ_USER"],
            CONFIG["HZ_PWD"],
            logger_callback
        )
        # ======================================

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

        # === 预检：搜索项目 ID ===
        target_country = CONFIG.get("TARGET_COUNTRY", "US")
        self.log(f"目标国家配置: {target_country}")
        if not self.sms_api.search_project_id("Google", target_country):
            self.log("❌ 无法找到合适的项目 ID (Google US/HK)，任务终止。")
            self.finish()
            return

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
                    # --- A. 浏览器启动配置 ---
                    # 优化：移除了 --no-sandbox，这通常是服务器用的，本地跑容易被检测
                    browser = p.chromium.launch(
                        headless=False,  # 建议开启界面以观察
                        args=[
                            "--disable-blink-features=AutomationControlled", # 核心：禁用自动化控制特征
                            "--disable-infobars",
                            "--start-maximized",
                            "--lang=zh-CN,zh" # 强制中文语言环境
                        ],
                        ignore_default_args=["--enable-automation"] # 移除"受到自动软件控制"横幅
                    )

                    # --- B. 上下文配置 ---
                    # 优化：移除了硬编码的 user_agent。
                    # 让 Playwright 使用内核自带的 UA，确保 UA 版本与浏览器内核版本完美匹配。
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080}, # 固定分辨率防止指纹变动
                        permissions=["clipboard-read", "clipboard-write"] # 允许剪贴板
                    )

                    # --- C. 注入隐身 JS ---
                    context.add_init_script(STEALTH_JS)

                    page = context.new_page()

                    try:
                        # --- 1. 登录流程 (拟人化) ---
                        self.log("Loading login page...")
                        page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded")
                        human_delay(1500, 2500) # 等待页面完全渲染

                        # 输入账号
                        human_type(page, 'input[type="email"]', email)
                        human_delay(500, 1000)
                        page.keyboard.press("Enter")

                        # 等待密码框
                        page.wait_for_selector('input[type="password"]', state="visible", timeout=15000)
                        human_delay(1500, 3000) # 模拟回忆密码

                        # 输入密码
                        human_type(page, 'input[type="password"]', account["pwd"])
                        human_delay(800, 1500)
                        page.keyboard.press("Enter")

                        # --- 2. 验证流程 ---
                        try:
                            # 增加检测时间，防止网络慢导致的误判
                            page.wait_for_selector('input[type="tel"]', timeout=10000)
                            self.log("触发手机验证！启动接码流程...")

                            phone_success = False
                            for phone_attempt in range(3):
                                if not self.running: break
                                if phone_attempt > 0: self.log(f"换号重试 (第 {phone_attempt+1} 次)...")

                                # 确保在输入号码的界面
                                if page.is_visible('input[name="code"]') or page.is_visible('input[id*="Pin"]'):
                                    self.log("发现处于验证码输入页，尝试回退...")
                                    page.go_back()
                                    human_delay(2000, 3000)
                                    if not page.is_visible('input[type="tel"]'):
                                        raise Exception("无法回退到号码输入页")

                                # 获取号码
                                order_id, raw_number = self.sms_api.get_number()
                                if not order_id:
                                    human_delay(2000, 3000)
                                    continue

                                # 格式化号码
                                clean_digits = re.sub(r'\D', '', str(raw_number))
                                final_phone = f"+{clean_digits}"
                                self.log(f"尝试填入: {final_phone}")

                                # 拟人化填入号码
                                page.click('input[type="tel"]') # 先点击聚焦
                                page.keyboard.press("Control+A") # 全选
                                page.keyboard.press("Backspace") # 删除旧号码
                                human_delay(500, 1000)
                                human_type(page, 'input[type="tel"]', final_phone)
                                human_delay(1000, 2000)
                                page.keyboard.press("Enter")

                                # 获取并填入验证码
                                code = self.sms_api.get_sms_code(order_id)
                                if code:
                                    try:
                                        human_delay(1500, 3000) # 模拟看短信时间

                                        # 模拟人类复制粘贴 (比直接 type 更符合逻辑，因为一般是复制进来的)
                                        page.evaluate(f"navigator.clipboard.writeText('{code}')")

                                        # 尝试聚焦验证码框
                                        try: page.focus('input[name="code"]')
                                        except: page.focus('input[id*="Pin"]')

                                        self.log(f"模拟人工粘贴验证码: {code}")
                                        page.keyboard.press("Control+V")
                                        human_delay(800, 1500)
                                    except:
                                        # 备选方案：直接填入
                                        try: page.fill('input[name="code"]', code)
                                        except: page.fill('input[id*="Pin"]', code)

                                    page.keyboard.press("Enter")

                                    self.log("提交后观察中...")
                                    page.wait_for_timeout(5000)

                                    # 检查是否被弹回
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
        self.title("Haozhuma API - Python Client")
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
