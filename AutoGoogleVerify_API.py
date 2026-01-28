import re
import time
import os
import random
import requests
from playwright.sync_api import sync_playwright, TimeoutError

# =======================================================================================
# === I. AAB 级核心隐身补丁 (Stealth JS Injection) ===
# =======================================================================================
# 移植自 AAB 框架，用于深度伪造浏览器指纹，对抗 Google 的自动化检测
STEALTH_JS = """
(() => {
    // 1. 深度抹除 webdriver 标记 (不仅是简单的 delete)
    const newProto = navigator.__proto__;
    delete newProto.webdriver;
    navigator.__proto__ = newProto;

    // 2. 伪造硬件并发数与内存 (模拟真实 PC)
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

    // 3. 伪造 Chrome 运行时对象 (欺骗 Google 账号系统的关键)
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // 4. 伪造插件列表与语言 (模拟标准中文用户环境)
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

    // 5. 覆盖 Permissions API (防止通过通知权限反查)
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
    "API_KEY": "86b44ef524AAb260c77481dd0fb97A1b", # 您的 API Key
    "BASE_URL": "https://hero-sms.com/stubs/handler_api.php",
    "SERVICE_CODE": "go",   # Google 项目代码
    "COUNTRY_ID": "151",    # 智利
    "ACCOUNT_FILE": "accounts.txt",
    "FAILED_FILE": "failed_accounts.txt"
}

# =======================================================================================
# === III. 拟人化行为工具库 (Human Behavior Simulation) ===
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
        print(f"⚠️ 输入模拟遇到小问题: {e}")
        # 降级方案：如果逐字输入失败，回退到 fill 但保留前后延迟
        page.fill(selector, text)

def load_accounts_from_file(file_path):
    """加载账号文件"""
    accounts = []
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
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
    print(f"✅ 成功加载了 {len(accounts)} 个账号")
    return accounts

def log_failed_account(email):
    """记录失败账号"""
    try:
        with open(CONFIG["FAILED_FILE"], "a", encoding="utf-8") as f:
            f.write(f"{email}\n")
        print(f"📝 已将 {email} 加入失败名单")
    except Exception as e:
        print(f"❌ 写入失败文件时出错: {e}")

# =======================================================================================
# === IV. 接码平台客户端 (SMS Client) ===
# =======================================================================================
class HeroSMSClient:
    def __init__(self):
        self.api_key = CONFIG["API_KEY"]
        self.base_url = CONFIG["BASE_URL"]

    def _request(self, params):
        params["api_key"] = self.api_key
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            return response.text
        except Exception as e:
            print(f"💥 网络请求出错: {e}")
            return None

    def get_number(self):
        params = { "action": "getNumber", "service": CONFIG["SERVICE_CODE"], "country": CONFIG["COUNTRY_ID"] }
        print(f"📡 正在请求 Google 号码 (国家ID: {CONFIG['COUNTRY_ID']})...")
        result = self._request(params)
        if result and "ACCESS_NUMBER" in result:
            parts = result.split(":")
            if len(parts) >= 3: return parts[1], parts[2]
        
        if result == "NO_NUMBERS": print("❌ 当前国家无号。")
        elif result == "NO_BALANCE": print("❌ 余额不足。")
        else: print(f"❌ API 错误: {result}")
        return None, None

    def get_sms_code(self, activation_id, timeout=120):
        params = {"action": "getStatus", "id": activation_id}
        print(f"⏳ 正在监听短信 (ID: {activation_id})...")
        start = time.time()
        while time.time() - start < timeout:
            result = self._request(params)
            if result and result.startswith("STATUS_OK"):
                code = result.split(":")[1]
                print(f"📨 收到验证码: {code}")
                return code
            elif result == "STATUS_CANCEL":
                print("❌ 订单被取消。")
                return None
            time.sleep(3)
        return None

    def set_status_complete(self, activation_id):
        self._request({"action": "setStatus", "id": activation_id, "status": "6"})
        print("✅ 订单标记完成。")

    def set_status_cancel(self, activation_id):
        self._request({"action": "setStatus", "id": activation_id, "status": "8"})
        print("🔄 订单已取消。")

# =======================================================================================
# === V. 自动化机器人 (Google Bot with Stealth) ===
# =======================================================================================
class GoogleBot:
    def __init__(self):
        self.sms_api = HeroSMSClient()

    def process_account(self, account):
        email = account["email"]
        MAX_ACCOUNT_RETRIES = 3 
        
        for account_attempt in range(MAX_ACCOUNT_RETRIES):
            print(f"\n🚀 === [第 {account_attempt + 1}/{MAX_ACCOUNT_RETRIES} 次] 隐身模式处理: {email} ===")
            
            try:
                with sync_playwright() as p:
                    # --- A. 浏览器启动配置 (AAB 级隐身) ---
                    browser = p.chromium.launch(
                        headless=False,  # 建议开启界面以观察
                        args=[
                            "--disable-blink-features=AutomationControlled", # 核心：禁用自动化控制特征
                            "--no-sandbox",
                            "--disable-infobars",
                            "--start-maximized",
                            "--lang=zh-CN,zh" # 强制中文语言环境
                        ],
                        ignore_default_args=["--enable-automation"] # 移除"受到自动软件控制"横幅
                    )
                    
                    # --- B. 上下文配置 ---
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080}, # 固定分辨率防止指纹变动
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        permissions=["clipboard-read", "clipboard-write"] # 允许剪贴板
                    )
                    
                    # --- C. 注入隐身 JS ---
                    context.add_init_script(STEALTH_JS)
                    
                    page = context.new_page()
                    
                    try:
                        # --- 1. 登录流程 (拟人化) ---
                        print("Loading login page...")
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
                            print("⚠️ 触发手机验证！启动接码流程...")
                            
                            phone_success = False
                            for phone_attempt in range(3):
                                if phone_attempt > 0: print(f"🔄 换号重试 (第 {phone_attempt+1} 次)...")
                                
                                # 确保在输入号码的界面
                                if page.is_visible('input[name="code"]') or page.is_visible('input[id*="Pin"]'):
                                    print("🛑 发现处于验证码输入页，尝试回退...")
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
                                print(f"📱 尝试填入: {final_phone}")
                                
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
                                        
                                        print(f"📋 模拟人工粘贴验证码: {code}")
                                        page.keyboard.press("Control+V")
                                        human_delay(800, 1500)
                                    except:
                                        # 备选方案：直接填入
                                        try: page.fill('input[name="code"]', code)
                                        except: page.fill('input[id*="Pin"]', code)

                                    page.keyboard.press("Enter")
                                    
                                    print("🕵️‍♀️ 提交后观察中...")
                                    page.wait_for_timeout(5000)
                                    
                                    # 检查是否被弹回
                                    if page.is_visible('input[type="tel"]') and not page.is_visible('input[name="code"]'):
                                        print("🔄 验证无效 (可能号码被滥用)，换号...")
                                        self.sms_api.set_status_cancel(order_id)
                                        continue 
                                    else:
                                        print(f"🎉 账号 {email} 验证通过！")
                                        self.sms_api.set_status_complete(order_id)
                                        page.wait_for_timeout(3000)
                                        phone_success = True
                                        break 
                                else:
                                    print("❌ 超时未收到码，换号...")
                                    self.sms_api.set_status_cancel(order_id)
                                    continue
                            
                            if not phone_success:
                                raise Exception("多次换号验证均失败")
                                
                        except TimeoutError:
                            print("✅ 未检测到手机验证框，登录似乎直接成功了。")
                        
                        print(f"✨ 账号 {email} 流程结束！")
                        return 
                        
                    except Exception as inner_e:
                        print(f"💥 页面操作出错: {inner_e}")
                        raise inner_e 
                    finally:
                        human_delay(1000, 2000)
                        browser.close()
                        
            except Exception as e:
                print(f"⚠️ 本次尝试失败，休息后重试... ({e})")
                time.sleep(5)
        
        print(f"❌ 账号 {email} 彻底处理失败。")
        log_failed_account(email)

# =======================================================================================
# === VI. 主程序入口 ===
# =======================================================================================
if __name__ == "__main__":
    account_list = load_accounts_from_file(CONFIG["ACCOUNT_FILE"])
    
    if not account_list:
        print("🛑 账号文件为空或未找到 accounts.txt 喵。")
    else:
        bot = GoogleBot()
        print(f"✨ 准备处理 {len(account_list)} 个账号...")
        print(f"🗺️ 目标国家ID: {CONFIG['COUNTRY_ID']}")
        print("🕵️‍♀️ AAB 隐身模式: 已激活")
        
        for acc in account_list:
            bot.process_account(acc)
            # 账号间的大间隔，防止关联
            rest_time = random.randint(5, 10)
            print(f"💤 任务完成，休息 {rest_time} 秒...")
            time.sleep(rest_time)
            
        print("🏁 全部任务完成")
