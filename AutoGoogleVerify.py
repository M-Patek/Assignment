import re
import time
from playwright.sync_api import sync_playwright, Page, TimeoutError

# ================= 最终封装配置区域 =================
CONFIG = {
    # 接码平台地址
    "SMS_URL": "https://hero-sms.com/cn/services", 
    
    # 根据主人提供的最新截图精准封装的选择器
    "SELECTORS": {
        # 匹配服务列表里那个紫色的价格按钮 (如 USA +1 行的按钮)
        "BTN_GET_NUMBER": ".services_grid .btn-primary", 
        
        # 匹配号码右侧那个带有 X 图标的取消按钮
        "BTN_CANCEL": ".use-free-number__choise-number .icon-close",
        
        # 最新订单的整行容器 (右侧订单列表)
        "LATEST_ORDER_ROW": ".use-free-number__list",
        
        # 电话号码文本 (位于 b 标签中)
        "PHONE_TEXT": ".use-free-number__choise-number b",
        
        # 验证码文本区域 (监控那个显示“复制提供给你的号码...”的 p 标签)
        "CODE_TEXT": ".alert.none-sms p",
        
        # 页面遮罩层/加载气泡
        "TOAST_MASK": ".v-toast"
    },
    
    # 账号列表 (请主人自行替换)
    "ACCOUNTS": [
        {"email": "cat_master_01@gmail.com", "pwd": "Password123", "recovery": "rec01@gmail.com"},
        {"email": "cat_master_02@gmail.com", "pwd": "Password123", "recovery": "rec02@gmail.com"},
    ]
}

class GoogleAutoVerifier:
    def __init__(self, browser_context):
        self.context = browser_context
        self.sms_page = None
        self.google_page = None

    def init_sms_page(self):
        """初始化接码平台页面"""
        print("正在打开接码平台...")
        self.sms_page = self.context.new_page()
        self.sms_page.goto(CONFIG["SMS_URL"])
        print("✅ 接码平台就绪，主人喵！请确保已手动登录并有余额。")

    def get_phone_number(self):
        """从接码平台获取一个新号码并进行清理"""
        page = self.sms_page
        selectors = CONFIG["SELECTORS"]
        
        # 检查并等待加载遮罩消失，防止点击被拦截
        if page.is_visible(selectors["TOAST_MASK"]):
            page.wait_for_selector(selectors["TOAST_MASK"], state="hidden", timeout=5000)
        
        print("🔄 正在请求新号码...")
        page.click(selectors["BTN_GET_NUMBER"])
        
        try:
            page.wait_for_selector(selectors["PHONE_TEXT"], state="visible", timeout=15000)
            raw_phone = page.inner_text(selectors["PHONE_TEXT"])
            
            # 自动清理非数字字符，方便谷歌填入 (如 +62 (831) -> 62831)
            clean_phone = re.sub(r'\D', '', raw_phone)
            print(f"📱 获取到原始号码: {raw_phone} -> 处理后: {clean_phone}")
            return clean_phone
            
        except TimeoutError:
            print("❌ 获取号码超时喵，请检查页面状态或余额。")
            return None

    def wait_for_sms_code(self, timeout=120):
        """轮询监控 DOM 变化抓取验证码"""
        page = self.sms_page
        selectors = CONFIG["SELECTORS"]
        
        print(f"⏳ 正在监控 DOM 变化等待验证码 (限时 {timeout} 秒)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 获取监控区域的最新文本
            content = page.inner_text(selectors["CODE_TEXT"])
            
            # 寻找 6 位连续数字的正则
            match = re.search(r'\b(\d{6})\b', content)
            
            if match:
                code = match.group(1)
                print(f"📨 发现目标验证码: {code}")
                return code
            
            # 稍作休息，模拟猫咪潜伏，减少 CPU 占用
            page.wait_for_timeout(3000) 
            
        print("❌ 等待超时，没抓到验证码喵...")
        return None

    def process_account(self, account):
        """完整的自动化流程封装"""
        email = account["email"]
        print(f"\n🚀 开始处理账号: {email}")
        
        page = self.context.new_page()
        self.google_page = page
        
        try:
            # 1. 登录 Google
            page.goto("https://accounts.google.com/signin")
            page.fill('input[type="email"]', email)
            page.keyboard.press("Enter")
            
            page.wait_for_selector('input[type="password"]', state="visible")
            page.fill('input[type="password"]', account["pwd"])
            page.keyboard.press("Enter")
            
            # 2. 判断是否需要接码
            try:
                page.wait_for_selector('input[type="tel"]', timeout=8000)
                print("⚠️ 检测到手机验证拦截，启动联动接码...")
                
                phone = self.get_phone_number()
                if not phone: return
                
                # 填入号码
                page.fill('input[type="tel"]', phone)
                page.keyboard.press("Enter")
                
                # 3. 等待并填入验证码
                code = self.wait_for_sms_code()
                if code:
                    self.google_page.bring_to_front()
                    # 适配谷歌验证码输入框的常见选择器
                    page.fill('input[name="code"], input[type="tel"]#idvAnyPhonePin', code)
                    page.keyboard.press("Enter")
                    print(f"🎉 账号 {email} 验证码提交成功！")
                    page.wait_for_timeout(5000)
                
            except TimeoutError:
                print(f"✅ 账号 {email} 无需接码验证。")

        except Exception as e:
            print(f"💥 运行报错: {str(e)}")
            page.screenshot(path=f"error_{email}.png")
        finally:
            page.close()

def run_bot():
    with sync_playwright() as p:
        # 禁用自动化特征避免被风控
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        
        bot = GoogleAutoVerifier(context)
        bot.init_sms_page()
        
        input("🔴 请在 HeroSMS 页面手动登录好，确认看到订单列表后，按回车开始自动执行")
        
        for acc in CONFIG["ACCOUNTS"]:
            bot.process_account(acc)
            time.sleep(5) # 账号切换间隔
            
        print("🏁 所有任务都处理完成")
        browser.close()

if __name__ == "__main__":
    run_bot()
