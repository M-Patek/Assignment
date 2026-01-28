import re
import time
import os
import requests
from playwright.sync_api import sync_playwright, TimeoutError

# ================= ⚙️ 核心配置区域 =================
CONFIG = {
    # ✅ API Key (主人之前的)
    "API_KEY": "86b44ef524AAb260c77481dd0fb97A1b",
    
    # HeroSMS 官方接口
    "BASE_URL": "https://hero-sms.com/stubs/handler_api.php",
    
    # 服务代码 (Google = 'go')
    "SERVICE_CODE": "go",
    
    # 国家 ID (6=印尼, 187=美国)
    "COUNTRY_ID": "6", 
    
    # 📂 账号文件路径
    "ACCOUNT_FILE": "accounts.txt"
}

def load_accounts_from_file(file_path):
    """🐱 读取账号文件的助手函数"""
    accounts = []
    if not os.path.exists(file_path):
        print(f"❌ 哎呀，找不到文件: {file_path}")
        print("👉 请在同目录下新建 accounts.txt，格式: 邮箱:密码:辅助邮箱")
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue # 跳过空行和注释
            
            # 按冒号分割 (支持 : 或 | 或 ,)
            parts = re.split(r'[:|,]', line)
            
            if len(parts) >= 2:
                acc = {
                    "email": parts[0].strip(),
                    "pwd": parts[1].strip(),
                    "recovery": parts[2].strip() if len(parts) > 2 else ""
                }
                accounts.append(acc)
            else:
                print(f"⚠️ 跳过格式错误的行: {line}")
                
    print(f"✅ 成功加载了 {len(accounts)} 个账号喵！")
    return accounts

class HeroSMSClient:
    """🐱 API 助手：负责买号和查短信"""
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
        params = {
            "action": "getNumber",
            "service": CONFIG["SERVICE_CODE"],
            "country": CONFIG["COUNTRY_ID"]
        }
        print(f"📡 正在请求 Google 号码 (国家ID: {CONFIG['COUNTRY_ID']})...")
        result = self._request(params)
        
        if result and "ACCESS_NUMBER" in result:
            parts = result.split(":")
            if len(parts) >= 3:
                return parts[1], parts[2]
        
        if result == "NO_NUMBERS": print("❌ 无号码库存喵。")
        elif result == "NO_BALANCE": print("❌ 余额不足喵。")
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
        print("🔄 订单已取消退款。")

class GoogleBot:
    """🤖 浏览器操作机器人 (支持自动重试和回弹检测)"""
    def __init__(self):
        # 这里的 HeroSMSClient 必须在上面定义过，现在应该没问题了喵！
        self.sms_api = HeroSMSClient()

    def process_account(self, account):
        email = account["email"]
        print(f"\n🚀 === 开始处理账号: {email} ===")
        
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # --- 1. 登录 Google ---
                print("Loding...")
                page.goto("https://accounts.google.com/signin")
                page.fill('input[type="email"]', email)
                page.keyboard.press("Enter")
                
                # 等待密码框
                page.wait_for_selector('input[type="password"]', state="visible")
                page.fill('input[type="password"]', account["pwd"])
                page.keyboard.press("Enter")
                
                # --- 2. 循环验证逻辑 (最多重试 3 次) ---
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # 检测是否在手机验证页面
                        timeout = 8000 if attempt == 0 else 5000
                        page.wait_for_selector('input[type="tel"]', timeout=timeout)
                        
                        if attempt > 0:
                            print(f"⚠️ 验证失败，正在进行第 {attempt + 1} 次尝试换号...")
                        else:
                            print("⚠️ 触发验证！呼叫 API...")
                        
                        # === 获取号码 ===
                        order_id, raw_number = self.sms_api.get_number()
                        if not order_id:
                            print("❌ 无法获取号码，跳过此账号。")
                            break
                            
                        # 清洗并填入号码 (已修复 f-string 问题)
                        clean_digits = re.sub(r'\D', '', str(raw_number))
                        final_phone = f"+{clean_digits}"
                        print(f"📱 填入号码: {final_phone}")
                        
                        # 清空输入框并填入
                        page.fill('input[type="tel"]', "") 
                        page.fill('input[type="tel"]', final_phone)
                        page.keyboard.press("Enter")
                        
                        # === 等待验证码 ===
                        code = self.sms_api.get_sms_code(order_id)
                        
                        if code:
                            # 填入验证码
                            try:
                                page.fill('input[name="code"]', code)
                            except:
                                page.fill('input[id*="Pin"]', code)
                            page.keyboard.press("Enter")
                            
                            # === 验证后检查 (防止回弹) ===
                            print("🕵️‍♀️ 提交验证码后，正在观察页面反应...")
                            page.wait_for_timeout(5000)
                            
                            if page.is_visible('input[type="tel"]'):
                                print("🔄 Google 拒绝了验证，页面弹回。标记失败，重试...")
                                self.sms_api.set_status_cancel(order_id)
                                continue # 重试
                            else:
                                print(f"🎉 账号 {email} 验证通过！")
                                self.sms_api.set_status_complete(order_id)
                                page.wait_for_timeout(3000)
                                break # 成功退出
                        else:
                            print("❌ 未收到验证码，取消订单。")
                            self.sms_api.set_status_cancel(order_id)
                            continue 

                    except TimeoutError:
                        if attempt == 0:
                            print("✅ 登录顺畅，无需验证。")
                            break
                        else:
                            print("✅ 页面已跳转，验证可能已成功。")
                            break
                            
            except Exception as e:
                print(f"💥 发生错误: {e}")
            finally:
                browser.close()

if __name__ == "__main__":
    # 1. 读取账号
    account_list = load_accounts_from_file(CONFIG["ACCOUNT_FILE"])
    
    if not account_list:
        print("🛑 没有加载到账号，脚本停止喵。")
    else:
        # 2. 启动机器人
        bot = GoogleBot()
        print(f"✨ 准备处理 {len(account_list)} 个账号...")
        
        for acc in account_list:
            bot.process_account(acc)
            print("💤 休息 5 秒...")
            time.sleep(5)
            
        print("🏁 全部完成喵！")
