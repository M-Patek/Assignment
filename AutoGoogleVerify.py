import re
import time
from playwright.sync_api import sync_playwright, TimeoutError

# ================= 通用配置区域 =================
CONFIG = {
    "SMS_URL": "https://hero-sms.com/cn/services",
    
    "SELECTORS": {
        # 1. 购买按钮：
        # ⚠️ 注意：脚本会点击页面上出现的“第一个”紫色购买按钮。
        # 建议主人在启动前，手动在网页搜索栏输入想要国家（如 USA），让列表只显示那一个国家。
        "BTN_GET_NUMBER": ".services_grid .btn-primary", 
        
        # 2. 订单卡片根容器
        "CARD_ROOT": ".services-el.cardTop", 
        
        # 3. 手机号文本 (位于 b 标签中)
        "PHONE_TEXT": ".services-el.cardTop .use-free-number__choise-number b",
        
        # 4. 验证码监控区域 (监控整个列表容器，适应不同DOM结构)
        "SMS_LIST_CONTAINER": ".use-free-number__list",
        
        # 5. 遮罩层/加载气泡 (用于避让)
        "TOAST_MASK": ".v-toast"
    },
    
    # 账号列表
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
        """初始化接码平台"""
        self.sms_page = self.context.new_page()
        self.sms_page.goto(CONFIG["SMS_URL"])
        print("✅ 接码平台已打开。")
        print("👉 请主人手动登录，并在搜索栏筛选好想要的国家（让购买按钮出现在第一位）。")

    def get_universal_number(self):
        """获取通用号码并添加 + 号前缀"""
        page = self.sms_page
        sel = CONFIG["SELECTORS"]
        
        try:
            print("🔄 正在获取号码 (点击列表第一个可用国家)...")
            
            # 1. 检查遮罩并点击购买
            if page.is_visible(sel["TOAST_MASK"]):
                page.wait_for_selector(sel["TOAST_MASK"], state="hidden", timeout=5000)
                
            # 使用 .first 确保如果有多个国家显示，只点第一个，防止报错
            page.locator(sel["BTN_GET_NUMBER"]).first.click()
            
            # 2. 等待号码出现
            print("⏳ 等待号码分配...")
            page.wait_for_selector(sel["PHONE_TEXT"], state="visible", timeout=20000)
            
            # 3. 获取并格式化号码
            raw_phone = page.inner_text(sel["PHONE_TEXT"]) 
            # 例如: "1 (555) 123-4567" 或 "62 812..."
            
            # === 通用清洗逻辑 ===
            # 提取所有数字
            all_digits = re.sub(r'\D', '', raw_phone)
            
            # 直接添加 "+" 号
            clean_phone = f"+{all_digits}"
            
            print(f"📱 捕获原始: {raw_phone}")
            print(f"✨ 通用格式: {clean_phone} (已适配 Google 国际格式)")
            
            return clean_phone
            
        except Exception as e:
            print(f"❌ 获取号码失败: {str(e)}")
            return None

    def wait_for_sms(self, timeout=180):
        """监控列表容器，等待包含 G-xxxxxx 或纯数字的验证码"""
        page = self.sms_page
        sel = CONFIG["SELECTORS"]
        print(f"⏳ 正在监控验证码 (限时 {timeout} 秒)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 获取整个消息列表的文本内容
                content = page.inner_text(sel["SMS_LIST_CONTAINER"])
                
                # 正则匹配：优先找 G-xxxxxx，找不到再找 6 位纯数字
                match = re.search(r'(?:G-|验证码|code\s|is\s)(\d{6})\b', content)
                if not match:
                    match = re.search(r'\b(\d{6})\b', content)

                if match:
                    code = match.group(1)
                    print(f"📨 抓取成功！验证码是: {code}")
                    return code
                
            except Exception:
                pass
                
            page.wait_for_timeout(3000)
            
        print("❌ 等待超时，未收到验证码。")
        return None

    def process_account(self, account):
        """全自动流程"""
        email = account["email"]
        print(f"\n🚀 === 开始处理账号: {email} ===")
        
        page = self.context.new_page()
        try:
            # --- Google 登录 ---
            page.goto("https://accounts.google.com/signin")
            page.fill('input[type="email"]', email)
            page.keyboard.press("Enter")
            
            page.wait_for_selector('input[type="password"]', state="visible")
            page.fill('input[type="password"]', account["pwd"])
            page.keyboard.press("Enter")
            
            # --- 检测验证 ---
            try:
                page.wait_for_selector('input[type="tel"]', timeout=8000)
                print("⚠️ 触发手机号验证！启动接码...")
                
                # 获取通用号码
                phone = self.get_universal_number()
                if not phone: return
                
                # 填入带 + 号的号码
                page.fill('input[type="tel"]', phone)
                page.keyboard.press("Enter")
                
                # 等待验证码
                code = self.wait_for_sms()
                if code:
                    page.bring_to_front()
                    try:
                        page.fill('input[name="code"]', code)
                    except:
                        page.fill('input[id*="code"], input[id*="Pin"]', code)
                        
                    page.keyboard.press("Enter")
                    print(f"🎉 账号 {email} 验证提交完成！")
                    page.wait_for_timeout(5000)
                
            except TimeoutError:
                print(f"✅ 账号 {email} 登录顺畅，无需验证。")

        except Exception as e:
            print(f"💥 发生错误: {e}")
            page.screenshot(path=f"error_{email}.png")
        finally:
            page.close()

def run_bot():
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": 1300, "height": 800})
        
        bot = GoogleAutoVerifier(context)
        bot.init_sms_page()
        
        print("\n" + "="*50)
        print("🛑 准备工作：")
        print("1. 登录 HeroSMS")
        print("2. 在搜索框输入你想要的国家（例如 USA），让它排在第一位")
        input("✅ 准备好后，请按回车键发射脚本！")
        print("="*50 + "\n")
        
        for acc in CONFIG["ACCOUNTS"]:
            bot.process_account(acc)
            print("💤 休息 5 秒...")
            time.sleep(5)
            
        print("🏁 任务全部完成喵！")
        browser.close()

if __name__ == "__main__":
    run_bot()
