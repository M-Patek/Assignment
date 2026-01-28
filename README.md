# 🤖 AutoGoogleVerify - Google 账号自动化验证系统

## 📖 项目简介
本项目是一个基于 **Anaconda** 和 **Playwright** 的自动化脚本，专为批量处理 Google 账号登录及验证设计。
核心功能是自动监测 Google 登录时的手机号验证请求，并调用 **HeroSMS API** 自动获取号码、填入验证码，实现“无人值守”式的账号验证。

> **✨ 核心特性**
> * **通用适配**：代码已优化，支持全球号码（自动清洗格式并添加 `+` 号），不局限于特定地区。
> * **自动化流程**：从登录 -> 检测验证 -> 买号 -> 填码 -> 完成，全流程自动处理。
> * **环境隔离**：基于 Conda 环境，确保依赖纯净稳定。

---

## 🛠️ 环境搭建 (Installation)

推荐使用 Anaconda 进行环境管理。

### 1. 创建并激活环境
根据 `Start.txt` 的指引，请在终端执行以下命令创建 Python 3.10 环境：

```bash
conda create -n llm_verify python=3.10
conda activate llm_verify
```

### 2. 安装依赖
进入项目目录，安装必要的 Python 库和浏览器驱动：

```bash
# 安装 Python 依赖
pip install requests playwright

# 安装 Playwright 浏览器内核
playwright install
```

---

## ⚙️ 配置说明 (Configuration)

在运行之前，您需要配置 API 密钥和账号文件。

### 1. 修改脚本配置
打开 `AutoGoogleVerify_API.py`，编辑顶部的 `CONFIG` 字典：

```python
CONFIG = {
    # [必须] 您的 HeroSMS API 密钥
    "API_KEY": "YOUR_API_KEY_HERE",
    
    # [可选] 国家 ID (例如: 6=印尼, 187=美国, 16=英国)
    # 脚本会自动处理国际区号，您只需更改此 ID 即可切换国家
    "COUNTRY_ID": "6", 
    
    # 账号文件路径
    "ACCOUNT_FILE": "accounts.txt",
    
    # 服务代码 (Google 默认为 'go')
    "SERVICE_CODE": "go",
    
    # 接口地址
    "BASE_URL": "https://hero-sms.com/stubs/handler_api.php"
}
```

### 2. 准备账号文件
在脚本同级目录下创建 `accounts.txt`，格式如下（支持冒号、竖线或逗号分隔）：

```text
# 格式: 邮箱:密码:辅助邮箱(可选)
example1@gmail.com:password123
example2@gmail.com:password456:recovery@email.com
```

---

## 🚀 运行脚本 (Usage)

确保环境已激活且配置已保存，运行以下命令启动机器人：

```bash
python AutoGoogleVerify_API.py
```

### 🤖 脚本运行逻辑
1.  **加载账号**：读取 `accounts.txt` 中的所有有效账号。
2.  **自动登录**：使用 Playwright 模拟浏览器操作，输入账号密码。
3.  **智能验证**：
    * 如果遇到需要验证手机号的界面（`input[type="tel"]`），脚本会自动向 API 请求号码。
    * **号码处理**：自动清洗号码中的非数字字符，并统一添加 `+` 前缀（例如 `+62895...`），以适配 Google 的格式要求。
    * **填入验证码**：轮询 API 获取短信内容并自动填入。
4.  **状态同步**：验证成功后，自动向 API 发送完成状态；如果失败或超时，发送取消状态以退款。

---

## ⚠️ 注意事项
* **API 余额**：请确保 HeroSMS 账户有余额，否则会报错 `NO_BALANCE`。
* **网络环境**：请确保运行环境可以直接访问 Google 服务。
* **调试模式**：默认开启浏览器界面 (`headless=False`) 以便观察运行情况。如需后台运行，请在代码中修改为 `headless=True`。
