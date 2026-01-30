# AutoGoogleVerify - 自动化 Google 账号验证系统

## 项目概述 (Project Overview)

**AutoGoogleVerify** 是一款基于 **Playwright** 自动化框架与 **HeroSMS** 接码服务构建的高级账号验证解决方案。本项目旨在解决 Google 账号批量登录过程中频繁触发的手机号验证（PVA）问题。

系统核心集成了 **AAB (Anti-Automation Bypass) 隐身技术** 与 **拟人化行为引擎**，能够有效规避主流的风控检测。最新版本引入了基于 `Tkinter` 的图形用户界面（GUI），实现了任务的可视化管理与实时监控，大幅提升了操作效率与交互体验。

---

## 仓库目录结构与版本说明 (Directory Structure)

本仓库采用分层架构管理代码，以适应开发、生产及历史回溯等不同场景的需求。

### 1. `Frist GUI.py` (Flagship)
**【当前推荐版本】**
这是基于最新稳定逻辑构建的**图形化用户界面（GUI）版本**。它不仅继承了底层脚本的强劲功能，更在交互体验与架构设计上进行了全面升级：

* **可视化控制台 (Visual Dashboard)**：基于 `Tkinter` 框架构建，摒弃了枯燥的命令行交互，提供直观的“启动/停止”控制与参数配置入口。
* **多线程架构 (Multithreading)**：采用 `threading` + `queue` 的生产者-消费者模型，确保后台自动化任务与前台界面渲染分离，杜绝界面卡顿，保证程序运行的稳定性。
* **实时日志监控 (Real-time Logging)**：内置滚动日志面板，支持不同级别日志（INFO/ERROR/SUCCESS）的颜色分级显示，实时反馈登录状态、接码进度及异常信息。
* **进度可视化 (Progress Tracking)**：顶部集成任务进度条，实时展示当前批次账号的处理进度（如：5/100），便于大规模任务管理。

### 2. `FIN_/` (Stable Release / 生产稳定版)
* **主要文件**：`First.py`
* **定位**：**命令行接口 (CLI) 的最终稳定版本**。
* **说明**：该目录存放经过充分测试、逻辑最为稳健的代码。它剥离了图形界面组件，仅保留核心自动化逻辑。适用于需要部署在服务器（Serverless/Docker）或通过脚本批量调用的生产环境。它是 `Frist GUI.py` 的逻辑基石。

### 3. `OLD_/` (Legacy / 历史归档)
* **主要文件**：旧版 `First.py` 等
* **定位**：**上一代稳定版本备份**。
* **说明**：当新版本（FIN_）在特定网络环境或系统配置下出现兼容性问题时，该目录下的代码可作为快速回滚方案（Rollback Plan），确保业务连续性。

### 4. `ARCH_/` (Research & Archive / 研发实验室)
* **主要文件**：`AI refract.py` (Alpha), `Beta.py`, `Stable.py`
* **定位**：**实验性功能与高级对抗技术验证区**。
* **说明**：此目录包含处于开发阶段或包含激进反指纹技术的代码，供研究学习使用：
    * **`AI refract.py`**：集成了 **Ultra Stealth JS Injection V3.0**，测试了包括 Canvas 动态噪音注入、WebGL 厂商指纹深度伪造、AudioContext 阻断等高阶反爬虫对抗技术。
    * **`Beta.py`**：功能特性测试分支。
    * **注意**：此目录下的代码稳定性尚未完全验证，不建议直接用于生产环境。

---

## 核心技术特性 (Core Features)

### 隐身内核 (Stealth Engine)
* **环境伪装**：通过 CDP 协议在浏览器初始化阶段注入特制 JavaScript，深度抹除 `navigator.webdriver` 标记，重写 `Chrome Runtime` 对象及 `Permissions API`，模拟真实用户浏览器指纹。
* **指纹一致性**：强制统一硬件并发数（Hardware Concurrency）与内存信息，防止 Headless 模式下的特征泄露。

### 拟人化行为模拟 (Human Simulation)
* **非线性输入**：实现 `human_type` 算法，模拟人类键入时的随机速率与停顿，规避固定频率检测。
* **认知延迟**：在关键交互节点（如输入密码后、点击确认前）引入符合正态分布的随机思考时间 (`human_delay`)。
* **剪贴板交互**：在验证码填入环节，模拟“复制-聚焦-粘贴”的操作链路，显著提升验证通过率。

### 智能风控处理 (Smart Risk Control)
* **场景自适应**：自动检测登录过程中的异常跳转，精准识别手机号验证页面。
* **动态接码**：无缝对接 HeroSMS API，自动提取可用号码；若遇到“此号码无法用于验证”的风控提示，系统将自动取消订单并重试新号码，无需人工干预。

---

## 快速部署 (Deployment)

### 环境依赖
推荐使用 Python 3.10+ 环境。

```bash
# 安装核心依赖库
pip install requests playwright

# 安装 Playwright 浏览器驱动
playwright install chromium
```

### 启动方式
**GUI 模式（推荐）：**
```bash
python "Frist GUI.py"
```

**CLI 模式：**
```bash
python FIN_/First.py
```

---

> **免责声明**：本项目仅供技术研究与教育用途。请遵守相关法律法规及目标平台的服务条款。
