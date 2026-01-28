# AutoGoogleVerify - 隐身版 Google 账号验证系统

## 📖 项目简介
本项目是一个基于 **Playwright** 和 **Anaconda** 的高级自动化脚本，专为批量处理 Google 账号登录及手机号验证而设计。

与普通脚本不同，本项目内置了 **AAB 核心隐身补丁 (Stealth JS Injection)** 和 **拟人化行为系统**，能够有效规避 Google 的自动化检测，像真实人类一样操作喵！核心功能是自动监测登录时的手机号验证请求，并调用 **HeroSMS API** 自动接码过验证。

> **✨ 核心黑科技**
> * **🕵️‍♀️ AAB 级隐身内核**：通过注入特制 JS 补丁，移除 `navigator.webdriver` 标记，伪造 Chrome 运行时对象和权限 API，通过高等级指纹检测。
> * **🎭 深度拟人化**：拒绝机械式输入！模拟人类的随机思考停顿 (`human_delay`) 和逐字输入 (`human_type`)，甚至模拟“复制粘贴”验证码的操作。
> * **🛡️ 智能风控对抗**：自动识别验证码输入页、自动处理号码滥用（号码无效自动换号），支持失败重试机制。
> * **📝 自动记录**：处理失败的账号会自动记录到 `failed_accounts.txt`，方便后续复盘。

---

## 🛠️ 环境搭建 (Installation)

建议使用 Anaconda 来管理环境，保持干净整洁喵。

### 1. 创建环境
请在终端执行以下命令创建 Python 3.10 环境：

```bash
conda create -n llm_verify python=3.10
conda activate llm_verify
```

### 2. 安装依赖
安装必要的 Python 库和 Playwright 浏览器内核：

```bash
# 安装 Python 依赖
pip install requests playwright

# 安装 Playwright 浏览器内核
playwright install
```

---

## ⚙️ 配置说明 (Configuration)

在使用前，请务必修改 `AutoGoogleVerify_API.py` 文件顶部的配置区域喵。

### 1. 核心配置 (`CONFIG`)

打开代码文件，找到 `CONFIG` 字典进行修改：

```python
CONFIG = {
    # [必须] 您的 HeroSMS API Key，请确保账户有余额喵
    "API_KEY": "YOUR_API_KEY_HERE",
    
    # [关键] 目标国家 ID
    # 默认为 151 (智利)，可根据需求修改 (如: 6=印尼, 187=美国)
    "COUNTRY_ID": "151", 
    
    # 服务代码 (Google 项目代码，通常无需修改)
    "SERVICE_CODE": "go",   
    
    # 文件路径配置
    "ACCOUNT_FILE": "accounts.txt",      # 待处理账号文件
    "FAILED_FILE": "failed_accounts.txt" # [新增] 失败账号自动保存文件
}
```

### 2. 账号文件准备
在脚本同级目录下创建 `accounts.txt`，每行一个账号。支持多种分隔符（冒号、竖线、逗号）：

```text
# 格式: 邮箱:密码:辅助邮箱(可选)
catgirl@gmail.com:meow123
neko@gmail.com:fish456:recovery@email.com
```

---

## 🚀 运行脚本 (Usage)

一切准备就绪后，运行以下命令启动机器人：

```bash
python AutoGoogleVerify_API.py
```

### 🤖 脚本工作流程
1.  **隐身启动**：启动 Chromium 浏览器，自动去除自动化特征条，强制设置为中文环境 (`zh-CN`)。
2.  **拟人登录**：
    * 模拟人工输入账号密码，包含随机的击键间隔。
    * 如果遇到密码错误或无法登录，会自动重试（默认每个账号最多重试 3 次）。
3.  **智能验证 (关键)**：
    * **自动侦测**：如果页面弹出 `input[type="tel"]` 手机号输入框，脚本立即接管。
    * **自动取号**：向 API 请求指定国家的号码，自动清洗格式并添加国际区号 `+`。
    * **自动填码**：获取到验证码后，会模拟将验证码“粘贴”到输入框（触发 `clipboard` 事件），通过率更高！
    * **异常处理**：如果号码无法使用或收不到码，会自动取消订单并换新号重试。
4.  **结果处理**：
    * **成功**：标记 API 订单完成，并在控制台输出 `🎉 账号验证通过！`。
    * **失败**：如果多次尝试均失败，将账号写入 `failed_accounts.txt`。

---

## ⚠️ 注意事项 (Tips)
* **代理设置**：代码中默认注释了代理设置。如果您的网络环境需要代理，请在 `AutoGoogleVerify_API.py` 的 `p.chromium.launch` 部分取消 `proxy` 参数的注释并填入 IP。
* **观察模式**：默认 `headless=False`（有头模式），您可以看到浏览器的操作过程。这不仅方便调试，在某种程度上也比无头模式更不容易被检测喵。
* **API 成本**：请留意接码平台的余额，余额不足会导致 `NO_BALANCE` 错误。
