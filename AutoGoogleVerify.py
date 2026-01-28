import re
import time
from playwright.sync_api import sync_playwright, Page, TimeoutError

# ================= 终极封装配置区域 =================
CONFIG = {
    "SMS_URL": "https://hero-sms.com/cn/services", 
    "SELECTORS": {
        # 服务列表选择
        "REGION_INDONESIA": "text='Indonesia +62'", # 示例：点击印尼地区
        "BTN_GET_NUMBER": ".services_grid .btn-primary", 
        
        # 订单卡片（基于主人 13:03:10 截图）
        "CARD_ROOT": ".services-el.cardTop", 
        "PHONE_TEXT": ".services-el.cardTop .use-free-number__choise-number b",
        "BTN_CANCEL": ".services-el.cardTop .icon-close",
        
        # 验证码监控
        "CODE_TEXT": ".use-free-number__messages .alert p",
        "TOAST_MASK": ".v-toast"
    },
    
    # 待处理账号
    "ACCOUNTS": [
        {"email": "your_email@gmail.com", "pwd": "your_password", "recovery": "rec@gmail.com"},
    ]
}

class GoogleAutoVerifier:
    def __init__(self, browser_context):
        self.context = browser_context
        self.sms_page = None
        self.google_page = None

    def init_sms_page(self):
        """初始化并登录接码平台"""
        self.sms_page = self.context.new_page()
        self.sms_page.goto(CONFIG["SMS_URL"])
        print("✅ 接码平台已打开。请主人手动登录，并在看到号码列表后按回车喵！")

    def get_clean_phone(self):
        """获取并处理号码：除去地区码(+62)，仅保留数字部分"""
        page = self.sms_page
        sel = CONFIG["SELECTORS"]
        
        try:
            # 1. 选择印度尼西亚（如果需要脚本点击）
            # page.click(sel["REGION_INDONESIA"]) 
            
            # 2. 点击购买
            page.click(sel["BTN_GET_NUMBER"])
            
            # 3. 等待卡片和号码出现
            page.wait_for_selector(sel["PHONE_TEXT"], state="visible", timeout=15000)
            raw_phone = page.inner_text(sel["PHONE_TEXT"]) # 示例: +62 (895) 31157091
            
            # 核心逻辑：除去地区码 +62，只保留纯数字部分
            # 先去除非数字
            all_digits = re.sub(r'\D', '', raw_phone) 
            # 如果以 62 开头，则截断它
            if all_digits.startswith("62"):
                clean_phone = all_digits[2:]
            else:
                clean_phone = all_digits
                
            print(f"📱 捕获原始号码: {raw_phone} -> 提取纯数字: {clean_phone}")
            return clean_phone
        except Exception as e:
            print(f"❌ 获取号码失败: {e}")
            return None

    def process_google_login(self, account):
        """自动登录谷歌账户"""
        page = self.context.new_page()
        self.google_page = page
        
        try:
            print(f"🚀 正在登录 Google: {account['email']}")
            page.goto("https://accounts.google.com/signin")
            
            # 输入账号
            page.fill('input[type="email"]', account["email"])
            page.keyboard.press("Enter")
            
            # 等待并输入密码
            page.wait_for_selector('input[type="password"]', state="visible")
            page.fill('input[type="password"]', account["pwd"])
            page.keyboard.press("Enter")
            
            # 检测是否触发手机验证
            try:
                page.wait_for_selector('input[type="tel"]', timeout=10000)
                print("⚠️ 触发安全验证，准备接码联动...")
                
                # 获取处理后的号码
                phone_to_fill = self.get_clean_phone()
                if phone_to_fill:
                    page.fill('input[type="tel"]', phone_to_fill)
                    page.keyboard.press("Enter")
                    
                    # 等待并填入验证码
                    code = self.wait_for_sms()
                    if code:
                        page.fill('input[name="code"]', code)
                        page.keyboard.press("Enter")
                        print(f"🎉 账号 {account['email']} 验证通过！")
                
            except TimeoutError:
                print(f"✅ 账号 {account['email']} 无需验证，登录成功。")

        except Exception as e:
            print(f"💥 流程中断: {e}")
        finally:
            page.close()

    def wait_for_sms(self, timeout=120):
        """轮询监控验证码"""
        start = time.time()
        while time.time() - start < timeout:
            content = self.sms_page.inner_text(CONFIG["SELECTORS"]["CODE_TEXT"])
            match = re.search(r'\b(\d{6})\b', content)
            if match:
                return match.group(1)
            self.sms_page.wait_for_timeout(3000)
        return None

def run_bot():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context()
        bot = GoogleAutoVerifier(context)
        
        bot.init_sms_page()
        input("🔴 请确保已在 HeroSMS 登录并选好地区，按回车开始喵！")
        
        for acc in CONFIG["ACCOUNTS"]:
            bot.process_google_login(acc)
            time.sleep(5)
            
        browser.close()

if __name__ == "__main__":
    run_bot()
