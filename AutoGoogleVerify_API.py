import re
import time
import os
import requests
from playwright.sync_api import sync_playwright, TimeoutError

# ================= 隐身代码 =================
# 这段 JS 会在每个页面加载前注入，欺骗网页的检测机制
STEALTH_JS = """
(() => {
    // 1. 抹除 webdriver 标记
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
    });

    // 2. 伪造 Chrome 运行时对象
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // 3. 伪造插件列表 (模拟真实用户)
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });

    // 4. 伪造语言设置
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
    });

    // 5. 覆盖权限查询 (欺骗通知权限检测)
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
        Promise.resolve({ state: 'denied', onchange: null }) :
        originalQuery(parameters)
    );
})();
"""

# ================= ⚙️ 核心配置区域 =================
CONFIG = {
    "API_KEY": "86b44ef524AAb260c77481dd0fb97A1b",
    "BASE_URL": "https://hero-sms.com/stubs/handler_api.php",
    "SERVICE_CODE": "go",
    "COUNTRY_ID": "151",  # 智利
    "ACCOUNT_FILE": "accounts.txt",
    "FAILED_FILE": "failed_accounts.txt"
}

def load_accounts_from_file(file_path):
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
    try:
        with open(CONFIG["FAILED_FILE"], "a", encoding="utf-8") as f:
            f.write(f"{email}\n")
        print(f"📝 已将 {email} 加入失败名单")
    except Exception as e:
        print(f"❌ 写入失败文件时出错: {e}")

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
        print(f"📡 正在请求 Google 号码 (智利)...")
        result = self._request(params)
        if result and "ACCESS_NUMBER" in result:
            parts = result.split(":")
            if len(parts) >= 3: return parts[1], parts[2]
        if result == "NO_NUMBERS": print("❌ 智利无号。")
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

    def set_status_cancel(self, activation_id):
        self._request({"action": "setStatus", "id": activation_id, "status": "8"})
        print("🔄 订单已取消。")

class GoogleBot:
    def __init__(self):
        self.sms_api = HeroSMSClient()

    def process_account(self, account):
        email = account["email"]
        MAX_ACCOUNT_RETRIES = 3 
        
        for account_attempt in range(MAX_ACCOUNT_RETRIES):
            print(f"\n🚀 === [第 {account_attempt + 1}/{MAX_ACCOUNT_RETRIES} 次] 处理账号: {email} ===")
            
            try:
                with sync_playwright() as p:
                    # 反检测启动参数
                    browser = p.chromium.launch(
                        headless=False, 
                        args=[
                            "--disable-blink-features=AutomationControlled", # 禁用Blink自动化控制特征
                            "--no-sandbox",
                            "--disable-infobars"
                        ],
                        ignore_default_args=["--enable-automation"] # 移除"正由自动测试软件控制"提示
                    )
                    
                    context = browser.new_context(
                        permissions=["clipboard-read", "clipboard-write"],
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" # 伪造UA
                    )
                    
                    # 注入隐身脚本
                    context.add_init_script(STEALTH_JS)
                    
                    page = context.new_page()
                    
                    try:
                        # --- 1. 登录流程 ---
                        print("Loading login page...")
                        page.goto("https://accounts.google.com/signin")
                        page.fill('input[type="email"]', email)
                        page.keyboard.press("Enter")
                        page.wait_for_selector('input[type="password"]', state="visible", timeout=10000)
                        page.fill('input[type="password"]', account["pwd"])
                        page.keyboard.press("Enter")
                        
                        # --- 2. 验证流程 ---
                        try:
                            page.wait_for_selector('input[type="tel"]', timeout=8000)
                            print("⚠️ 触发验证！准备接码...")
                            
                            phone_success = False
                            for phone_attempt in range(3):
                                if phone_attempt > 0: print(f"🔄 换号重试 (第 {phone_attempt+1} 次)...")
                                
                                # 回退到填号码界面
                                if page.is_visible('input[name="code"]') or page.is_visible('input[id*="Pin"]'):
                                    print("🛑 正在回退到号码输入框...")
                                    page.go_back() 
                                    page.wait_for_timeout(2000)
                                    if not page.is_visible('input[type="tel"]'):
                                        raise Exception("回退失败")
                                
                                order_id, raw_number = self.sms_api.get_number()
                                if not order_id: 
                                    time.sleep(2)
                                    continue
                                
                                clean_digits = re.sub(r'\D', '', str(raw_number))
                                final_phone = f"+{clean_digits}"
                                print(f"📱 填入号码: {final_phone}")
                                
                                page.fill('input[type="tel"]', "")
                                page.fill('input[type="tel"]', final_phone)
                                page.keyboard.press("Enter")
                                
                                code = self.sms_api.get_sms_code(order_id)
                                if code:
                                    try:
                                        page.evaluate(f"navigator.clipboard.writeText('{code}')")
                                        try: page.focus('input[name="code"]')
                                        except: page.focus('input[id*="Pin"]')
                                        print(f"📋 模拟人工粘贴验证码: {code}")
                                        page.keyboard.press("Control+V")
                                    except:
                                        try: page.fill('input[name="code"]', code)
                                        except: page.fill('input[id*="Pin"]', code)

                                    page.keyboard.press("Enter")
                                    
                                    print("🕵️‍♀️ 提交后观察中...")
                                    page.wait_for_timeout(5000)
                                    
                                    if page.is_visible('input[type="tel"]') and not page.is_visible('input[name="code"]'):
                                        print("🔄 验证被弹回，换号...")
                                        self.sms_api.set_status_cancel(order_id)
                                        continue 
                                    else:
                                        print(f"🎉 账号 {email} 验证通过！")
                                        self.sms_api.set_status_complete(order_id)
                                        page.wait_for_timeout(3000)
                                        phone_success = True
                                        break 
                                else:
                                    print("❌ 未收到码，换号...")
                                    self.sms_api.set_status_cancel(order_id)
                                    continue
                            
                            if not phone_success:
                                raise Exception("多次换号验证均失败")
                                
                        except TimeoutError:
                            print("✅ 未检测到手机验证框，登录完成。")
                        
                        print(f"✨ 账号 {email} 处理完毕！")
                        return 
                        
                    except Exception as inner_e:
                        print(f"💥 页面操作出错: {inner_e}")
                        raise inner_e 
                    finally:
                        browser.close()
                        
            except Exception as e:
                print(f"⚠️ 本次尝试失败，正在重置... ({e})")
                time.sleep(3)
        
        print(f"❌ 账号 {email} 彻底失败。")
        log_failed_account(email)

if __name__ == "__main__":
    account_list = load_accounts_from_file(CONFIG["ACCOUNT_FILE"])
    
    if not account_list:
        print("🛑 没有加载到账号喵。")
    else:
        bot = GoogleBot()
        print(f"✨ 准备处理 {len(account_list)} 个账号...")
        print(f"🗺️ 目标: 智利 (ID: {CONFIG['COUNTRY_ID']})")
        print("🕵️‍♀️ 隐身模式: 已开启")
        
        for acc in account_list:
            bot.process_account(acc)
            print("💤 休息 5 秒...")
            time.sleep(5)
            
        print("🏁 全部完成！")
