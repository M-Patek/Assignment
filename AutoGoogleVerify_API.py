import re
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError

# ================= ⚙️ 配置区域 (主人请填这里) =================
CONFIG = {
    # 你的 API Key (在 HeroSMS 个人中心 -> API Key 获取)
    "API_KEY": "请把你的_API_KEY_粘贴在这里",
    
    # 基础 API 地址 (根据文档确认)
    "BASE_URL": "https://hero-sms.com/stubs/handler_api.php",
    
    # 服务代码 (Google/Gmail/YouTube 通常是 'go')
    "SERVICE_CODE": "go",
    
    # 国家 ID (例如: 6=印尼, 187=美国, 0=默认/俄罗斯)
    # 如果想随机国家，有些平台支持填特定参数，但建议填具体ID
    "COUNTRY_ID": "6", 
    
    # 谷歌账号列表
    "ACCOUNTS": [
        {"email": "your_email@gmail.com", "pwd": "your_password", "recovery": "rec@gmail.com"},
    ]
}

class HeroSMSClient:
    """🐱 专门负责跟 HeroSMS 服务器对话的 API 助手"""
    def __init__(self):
        self.api_key = CONFIG["API_KEY"]
        self.base_url = CONFIG["BASE_URL"]

    def _request(self, params):
        """发送请求的通用方法"""
        # 这一步是为了把 api_key 自动带上
        params["api_key"] = self.api_key
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            return response.text
        except Exception as e:
            print(f"💥 API 请求失败: {e}")
            return None

    def get_number(self):
        """购买号码"""
        # 对应文档: ?action=getNumber&service=go&country=6
        params = {
            "action": "getNumber",
            "service": CONFIG["SERVICE_CODE"],
            "country": CONFIG["COUNTRY_ID"]
        }
        
        print(f"📡 正在通过 API 请求 Google 号码 (国家ID: {CONFIG['COUNTRY_ID']})...")
        result = self._request(params)
        
        # 成功响应格式: ACCESS_NUMBER:12345678:79991234567
        if result and "ACCESS_NUMBER" in result:
            parts = result.split(":")
            activation_id = parts[1]
            phone_number = parts[2]
            print(f"✅ 购买成功! 订单ID: {activation_id}, 原始号码: {phone_number}")
            return activation_id, phone_number
        elif result == "NO_NUMBERS":
            print("❌ 当前国家/服务没有号码库存了喵。")
        elif result == "NO_BALANCE":
            print("❌ 余额不足喵！")
        else:
            print(f"❌ 购买错误: {result}")
            
        return None, None

    def get_sms_code(self, activation_id, timeout=180):
        """轮询等待验证码"""
        # 对应文档: ?action=getStatus&id=12345678
        params = {
            "action": "getStatus",
            "id": activation_id
        }
        
        print(f"⏳ 正在云端监听短信 (ID: {activation_id})...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self._request(params)
            
            # 状态1: 等待中
            if result == "STATUS_WAIT_CODE":
                pass # 继续等
                
            # 状态2: 成功拿到码 (格式 STATUS_OK:123456)
            elif result and result.startswith("STATUS_OK"):
                code = result.split(":")[1]
                print(f"📨 收到短信验证码: {code}")
                return code
            
            # 状态3: 订单取消
            elif result == "STATUS_CANCEL":
                print("❌ 订单已被取消。")
                return None
                
            time.sleep(3) # 每3秒问一次服务器
            
        print("❌ 等待超时，未收到验证码。")
        return None

    def set_status_complete(self, activation_id):
        """告诉服务器任务完成 (可选，但也建议做)"""
        # status 6 = 激活完成
        self._request({"action": "setStatus", "id": activation_id, "status": "6"})
        print("🏁 订单状态已更新为完成。")

    def set_status_cancel(self, activation_id):
        """取消订单 (如果没收到码)"""
        # status 8 = 取消激活
        self._request({"action": "setStatus", "id": activation_id, "status": "8"})
        print("🔄 订单已取消，退回余额。")

# ================= 🌐 浏览器主程序 =================
class GoogleBot:
    def __init__(self):
        self.sms_api = HeroSMSClient()

    def process_account(self, account):
        email = account["email"]
        print(f"\n🚀 === 开始处理账号: {email} ===")
        
        with sync_playwright() as p:
            # 启动浏览器 (headless=False 方便你看过程)
            browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # --- 1. Google 登录 ---
                page.goto("https://accounts.google.com/signin")
                page.fill('input[type="email"]', email)
                page.keyboard.press("Enter")
                
                page.wait_for_selector('input[type="password"]', state="visible")
                page.fill('input[type="password"]', account["pwd"])
                page.keyboard.press("Enter")
                
                # --- 2. 检测是否触发验证 ---
                try:
                    # 等待手机号输入框出现
                    page.wait_for_selector('input[type="tel"]', timeout=8000)
                    print("⚠️ 触发手机验证拦截！呼叫 API 助手...")
                    
                    # === API 购买号码 ===
                    order_id, raw_number = self.sms_api.get_number()
                    
                    if order_id and raw_number:
                        # 格式化号码: 移除所有非数字，前面加 +
                        clean_digits = re.sub(r'\D', '', str(raw_number))
                        final_phone = f"+{clean_digits}"
                        
                        print(f"📱 填入号码: {final_phone}")
                        
                        # 填入号码
                        page.fill('input[type="tel"]', final_phone)
                        page.keyboard.press("Enter")
                        
                        # === API 等待验证码 ===
                        # 注意：Google 发码有时需要几秒，API 轮询会搞定
                        code = self.sms_api.get_sms_code(order_id)
                        
                        if code:
                            # 填入验证码
                            # Google 的验证码框 selector 有时会变，多试几个
                            try:
                                page.fill('input[name="code"]', code)
                            except:
                                page.fill('input[id*="code"], input[id*="Pin"]', code)
                                
                            page.keyboard.press("Enter")
                            
                            print(f"🎉 账号 {email} 验证通过！")
                            self.sms_api.set_status_complete(order_id) # 标记完成
                            page.wait_for_timeout(5000) # 等待跳转
                        else:
                            # 没收到码，取消订单
                            self.sms_api.set_status_cancel(order_id)
                    
                except TimeoutError:
                    print(f"✅ 账号 {email} 登录顺畅，无需验证。")

            except Exception as e:
                print(f"💥 发生错误: {e}")
            finally:
                browser.close()

if __name__ == "__main__":
    bot = GoogleBot()
    # 循环处理所有账号
    for acc in CONFIG["ACCOUNTS"]:
        bot.process_account(acc)
        print("💤 休息 5 秒...")
        time.sleep(5)
