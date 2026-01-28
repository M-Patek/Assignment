import re
import time
from playwright.sync_api import sync_playwright, Page, TimeoutError

# ================= 配置区域 =================
CONFIG = {
    # 接码平台地址
    "SMS_URL": "https://hero-sms.com/api",  # 替换为实际的操作面板地址
    
    # HeroSMS 的 DOM 选择器 (核心占位符)
    "SELECTORS": {
        "BTN_GET_NUMBER": "button.get-number-btn",       # 点击获取号码的按钮
        "BTN_CANCEL": "button.cancel-order",             # 取消订单/退款按钮(用于重试)
        
        # 列表中的第一行（最新订单）的容器
        "LATEST_ORDER_ROW": ".order-list .order-item:first-child",
        
        # 在最新订单行内，手机号的文本元素
        "PHONE_TEXT": ".order-list .order-item:first-child .phone-number",
        
        # 在最新订单行内，验证码的文本元素 (等待出现数字的地方)
        "CODE_TEXT": ".order-list .order-item:first-child .sms-content" 
    },
    
    # 账号列表 (格式: 邮箱, 密码, 辅助邮箱)
    "ACCOUNTS": [
        {"email": "cat_master_01@gmail.com", "pwd": "Password123", "recovery": "rec01@gmail.com"},
        {"email": "cat_master_02@gmail.com", "pwd": "Password123", "recovery": "rec02@gmail.com"},
    ]
}

class GoogleAutoVerifier:
    def __init__(self, browser_context):
        self.context = browser_context
        self.sms_page = None  # 接码页面
        self.google_page = None # 谷歌页面

    def init_sms_page(self):
        """初始化接码平台页面"""
        print("正在打开接码平台...")
        self.sms_page = self.context.new_page()
        self.sms_page.goto(CONFIG["SMS_URL"])
        
        # 这里可能需要主人手动登录一次，或者脚本增加登录逻辑
        # self.sms_page.wait_for_timeout(5000) 
        print("✅ 接码平台就绪，请确保已登录并有余额。")

    def get_phone_number(self):
        """从接码平台获取一个新号码"""
        page = self.sms_page
        selectors = CONFIG["SELECTORS"]
        
        print("🔄 正在请求新号码...")
        
        # 1. 记录当前的订单ID或内容，用于判断点击后是否刷新了新号码
        # (这里简化处理：点击后等待特定元素变化)
        
        # 点击获取号码
        page.click(selectors["BTN_GET_NUMBER"])
        
        # 2. 等待手机号元素出现
        try:
            page.wait_for_selector(selectors["PHONE_TEXT"], state="visible", timeout=10000)
            # 增加一点缓冲时间确保渲染完成
            page.wait_for_timeout(1000)
            
            raw_phone = page.inner_text(selectors["PHONE_TEXT"])
            print(f"📱 获取到原始号码: {raw_phone}")
            
            # 清理号码 (去空格，确保格式纯净)
            clean_phone = raw_phone.strip()
            return clean_phone
            
        except TimeoutError:
            print("❌ 获取号码超时，请检查余额或库存。")
            return None

    def wait_for_sms_code(self, timeout=60):
        """轮询等待验证码出现"""
        page = self.sms_page
        selectors = CONFIG["SELECTORS"]
        
        print(f"⏳ 正在等待短信验证码 (超时设定: {timeout}秒)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 获取短信框的文本
            content = page.inner_text(selectors["CODE_TEXT"])
            
            # 使用正则寻找 6 位连续数字
            match = re.search(r'\b(\d{6})\b', content)
            
            if match:
                code = match.group(1)
                print(f"📨 捕获到验证码: {code}")
                return code
            
            # 没等到，稍作休息减少CPU占用
            page.wait_for_timeout(2000) # 2秒轮询一次
            
        print("❌ 等待验证码超时。")
        # 超时后尝试点击取消/释放号码
        if page.is_visible(selectors["BTN_CANCEL"]):
            page.click(selectors["BTN_CANCEL"])
            print("🔄 已释放该号码。")
            
        return None

    def process_account(self, account):
        """处理单个账号的登录验证流程"""
        email = account["email"]
        print(f"\n🚀 开始处理账号: {email}")
        
        # 为每个谷歌账号开启新页面 (在同一个 context 下，方便切屏)
        # 注意：如果要在谷歌侧完全隔离，应该在主循环里为每个账号创建新的 context
        # 这里为了保持 SMS 页面常驻，我们复用 context，但在操作结束清理 cookies
        
        page = self.context.new_page()
        self.google_page = page
        
        try:
            # --- 1. 登录 Google ---
            page.goto("https://accounts.google.com/signin")
            page.fill('input[type="email"]', email)
            page.keyboard.press("Enter")
            
            # 等待密码框
            page.wait_for_selector('input[type="password"]', state="visible")
            page.fill('input[type="password"]', account["pwd"])
            page.keyboard.press("Enter")
            
            # --- 2. 检测是否触发手机验证 ---
            # 这里的 selector 需要根据实际出现的中文/英文提示调整
            # 常见提示: "验证您的身份", "Verify it's you", "Add a phone number"
            try:
                # 等待页面加载，判断是否进入验证环节
                # 这种判断通常需要找一个特征元素，这里假设出现了电话输入框
                page.wait_for_selector('input[type="tel"]', timeout=5000)
                print("⚠️ 触发手机号验证，准备接码...")
                
            except TimeoutError:
                print("✅ 未触发验证或直接登录成功！")
                # 截图保存成功状态
                page.screenshot(path=f"success_{email}.png")
                page.close()
                return

            # --- 3. 联动接码 ---
            phone_number = self.get_phone_number()
            if not phone_number:
                raise Exception("无法获取手机号")
            
            # 填入手机号
            page.fill('input[type="tel"]', phone_number)
            page.keyboard.press("Enter")
            
            # --- 4. 等待验证码并填入 ---
            # Google 页面现在应该在等待输入 6 位验证码
            code = self.wait_for_sms_code(timeout=60)
            
            if code:
                # 切回谷歌页面填码
                self.google_page.bring_to_front()
                
                # Google 的验证码输入框通常是 input[type="tel"] 或者 id="code"
                # 确保选择器定位到验证码框而不是之前的手机号框
                # 有时 Google 会显示 "G-"，输入框只需要填数字
                code_input_selector = 'input[name="code"]'  # 常见 name
                
                page.wait_for_selector(code_input_selector)
                page.fill(code_input_selector, code)
                page.keyboard.press("Enter")
                
                print(f"🎉 账号 {email} 验证提交完成！")
                page.wait_for_timeout(3000) # 等待跳转确认
            else:
                print(f"💀 账号 {email} 接码失败，标记为异常。")

        except Exception as e:
            print(f"💥 处理 {email} 时发生错误: {str(e)}")
            page.screenshot(path=f"error_{email}.png")
        
        finally:
            page.close()
            # 可以在这里清除 cookies 保证下一个账号干净，除了 SMS 域名的 cookie
            # (Playwright 清除 cookie 比较彻底，建议直接在主逻辑用新 Context)

def run_bot():
    with sync_playwright() as p:
        # 启动浏览器 (headless=False 方便调试)
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        
        # 创建上下文
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        bot = GoogleAutoVerifier(context)
        
        # 1. 先初始化接码平台
        bot.init_sms_page()
        
        # 主人可以在这里加一个 input，确认手动登录好接码平台后再回车继续
        input("🔴 请在弹出的浏览器中登录 HeroSMS，准备好后按回车继续...")
        
        # 2. 循环处理账号
        for acc in CONFIG["ACCOUNTS"]:
            bot.process_account(acc)
            # 账号间随机暂停，防风控
            time.sleep(3)
            
        print("🏁 所有任务执行完毕喵！")
        browser.close()

if __name__ == "__main__":
    run_bot()
