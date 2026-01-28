import re
import time
import requests
from playwright.sync_api import sync_playwright, TimeoutError

# ================= ⚙️ 核心配置区域 =================
CONFIG = {
    # ✅ 主人提供的 API Key (已自动填入)
    "API_KEY": "86b44ef524AAb260c77481dd0fb97A1b",
    
    # 基础 API 地址 (HeroSMS 官方接口)
    "BASE_URL": "https://hero-sms.com/stubs/handler_api.php",
    
    # 服务代码: Google/Gmail/YouTube 的代码通常是 'go'
    "SERVICE_CODE": "go",
    
    # 国家 ID 设置
    # 6 = 印度尼西亚 (你之前常用的)
    # 187 = 美国 (USA)
    # 0 = 俄罗斯/默认
    # 如果想换国家，改这个数字即可喵！
    "COUNTRY_ID": "6", 
    
    # 待处理的谷歌账号列表
    "ACCOUNTS": [
        {"email": "your_email@gmail.com", "pwd": "your_password", "recovery": "rec@gmail.com"},
    ]
}

class HeroSMSClient:
    """🐱 API 助手：负责买号和查短信"""
    def __init__(self):
        self.api_key = CONFIG["API_KEY"]
        self.base_url = CONFIG["BASE_URL"]

    def _request(self, params):
        """发送请求通用方法"""
        params["api_key"] = self.api_key
        try:
            # 发起 GET 请求
            response = requests.get(self.base_url, params=params, timeout=15)
            return response.text
        except Exception as e:
            print(f"💥 网络请求出错: {e}")
            return None

    def get_number(self):
        """购买号码"""
        # API 指令: getNumber
        params = {
            "action": "getNumber",
            "service": CONFIG["SERVICE_CODE"],
            "country": CONFIG["COUNTRY_ID"]
        }
        
        print(f"📡 正在通过 API 请求 Google 号码 (国家ID: {CONFIG['COUNTRY_ID']})...")
        result = self._request(params)
        
        # 成功返回格式: ACCESS_NUMBER:订单ID:手机号
        # 例如: ACCESS_NUMBER:123456:62812345678
        if result and "ACCESS_NUMBER" in result:
            parts = result.split(":")
            if len(parts) >= 3:
                activation_id = parts[1]
                phone_number = parts[2]
                print(f"✅ API 购买成功! 订单ID: {activation_id}, 原始号码: {phone_number}")
                return activation_id, phone_number
        
        # 错误处理
        if result == "NO_NUMBERS":
            print("❌ 哎呀，当前国家没有号码库存了，请尝试换个 Country ID 喵。")
        elif result == "NO_BALANCE":
            print("❌ 余额不足喵！请充值。")
        else:
            print(f"❌ API 返回未知错误: {result}")
            
        return None, None

    def get_sms_code(self, activation_id, timeout=120):
        """轮询查短信"""
        # API 指令: getStatus
        params = {
            "action": "getStatus",
            "id": activation_id
        }
        
        print(f"⏳ 正在云端监听短信 (ID: {activation_id})...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self._request(params)
            
            # 情况1: 等待中
            if result == "STATUS_WAIT_CODE":
                # 继续等待，不刷屏
                pass 
                
            # 情况2: 成功! (格式: STATUS_OK:验证码)
            elif result and result.startswith("STATUS_OK"):
                code = result.split(":")[1]
                print(f"📨 抓取成功！验证码是: {code}")
                return code
            
            # 情况3: 订单被取消
            elif result == "STATUS_CANCEL":
                print("❌ 订单已被取消。")
                return None
            
            # 情况4: 其它错误
            elif result and "ERROR" in result:
                print(f"⚠️ API 错误: {result}")
            
            # 这里的 sleep 很重要，防止请求太快被封 IP
            time.sleep(3) 
            
        print("❌ 等待超时，未收到验证码。")
        return None

    def set_status_complete(self, activation_id):
        """标记订单完成 (告诉服务器任务结束)"""
        self._request({"action": "setStatus", "id": activation_id, "status": "6"})
        print("🏁 订单已标记为完成。")

    def set_status_cancel(self, activation_id):
        """取消订单 (如果没收到码，退款)"""
        self._request({"action": "setStatus", "id": activation_id, "status": "8"})
        print("🔄 订单已取消，请求退款。")

# ================= 🌐 浏览器自动化主程序 =================
class GoogleBot:
    def __init__(self):
        self.sms_api = HeroSMSClient()

    def process_account(self, account):
        email = account["email"]
        print(f"\n🚀 === 开始处理账号: {email} ===")
        
        with sync_playwright() as p:
            # 启动可见浏览器 (headless=False)
            browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # --- 1. 登录 Google ---
                page.goto("https://accounts.google.com/signin")
                page.fill('input[type="email"]', email)
                page.keyboard.press("Enter")
                
                # 等待密码框
                page.wait_for_selector('input[type="password"]', state="visible")
                page.fill('input[type="password"]', account["pwd"])
                page.keyboard.press("Enter")
                
                # --- 2. 智能检测手机验证 ---
                try:
                    # 等待手机号输入框出现 (最多等 8 秒)
                    page.wait_for_selector('input[type="tel"]', timeout=8000)
                    print("⚠️ 检测到验证拦截！正在呼叫 API 获取号码...")
                    
                    # === ⚡️ API 极速买号 ===
                    order_id, raw_number = self.sms_api.get_number()
                    
                    if order_id and raw_number:
                        # 格式清洗: 去掉所有非数字，前面加 +
                        # 例如: 62812345 -> +62812345
                        clean_digits = re.sub(r'\D', '', str(raw_number))
                        final_phone = f"+{clean_digits}"
                        
                        print(f"📱 填入号码: {final_phone}")
                        
                        # 填入号码
                        page.fill('input[type="tel"]', final_phone)
                        page.keyboard.press("Enter")
                        
                        # === ⚡️ API 自动查码 ===
                        code = self.sms_api.get_sms_code(order_id)
                        
                        if code:
                            # 填入验证码
                            # 尝试匹配两种常见的验证码框选择器
                            try:
                                page.fill('input[name="code"]', code)
                            except:
                                page.fill('input[id="idvAnyPhonePin"]', code)
                                
                            page.keyboard.press("Enter")
                            print(f"🎉 账号 {email} 验证通过！")
                            
                            # 标记订单完成
                            self.sms_api.set_status_complete(order_id)
                            page.wait_for_timeout(5000) # 等待成功跳转
                        else:
                            # 没收到码，取消订单退款
                            self.sms_api.set_status_cancel(order_id)
                    
                except TimeoutError:
                    print(f"✅ 账号 {email} 登录顺畅，无需手机验证。")

            except Exception as e:
                print(f"💥 发生错误: {e}")
            finally:
                browser.close()

if __name__ == "__main__":
    bot = GoogleBot()
    
    print("✨ 脚本已启动！API Key 已配置喵。")
    print("👉 正在使用国家 ID:", CONFIG["COUNTRY_ID"])
    
    for acc in CONFIG["ACCOUNTS"]:
        bot.process_account(acc)
        print("💤 休息 5 秒...")
        time.sleep(5)
        
    print("🏁 所有任务执行完毕喵！")
