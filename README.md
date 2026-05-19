# 抢课脚本使用说明

## 一、环境准备

1. 安装 Python 3.7+（推荐 [python.org](https://www.python.org/downloads/) 下载）
2. 打开终端（cmd 或 PowerShell），安装依赖：

```bash
pip install requests
```

## 二、配置说明

打开 `shoudong.py`，修改**配置区**（文件开头 `# ==== 配置区 ====` 下面的部分）中的以下内容：

### 1. 任务列表 `TARGET_LIST`（第 20 行）

填入你要抢的课程 ID，每行一个，用引号包起来。例如：

```python
TARGET_LIST = [
    "359700",
    "341109",
    "341074",
]
```

> 课程 ID 获取方法见"三、如何获取课程 ID 和 Cookie"。

### 2. 定时启动时间 `START_TIME_STR`（第 26 行）

设置抢课开始的精确时间，格式 `年-月-日 时:分:秒`：

```python
START_TIME_STR = "2026-5-19 12:59:50"
```

> 建议比实际抢课时间**提前 10 秒**，给网络留余量。

如果留空 `START_TIME_STR = ""`，则运行后按回车手动开始。

### 3. 选课批次 ID（第 29-30 行 URL 中的数字）

URL 末尾的 `profileId=1989` 和 `electionProfile.id=1989`，**每批选课这个数字会变**。修改方法：

```python
GRAB_ACTION_URL = "https://jwxt.sias.edu.cn/eams/stdElectCourse!batchOperator.action?profileId=1989"
KEEP_ALIVE_URL = "https://jwxt.sias.edu.cn/eams/stdElectCourse!defaultPage.action?electionProfile.id=1989"
```

把两处 `1989` 换成你当前选课批次的实际数字。

> 获取方法：登录教务系统 → 进入选课页面，看浏览器地址栏 URL，里面会有 `profileId=xxxx` 或 `electionProfile.id=xxxx`，复制那个数字替换即可。

### 4. Cookie `COOKIE`（第 33 行）

```python
COOKIE = "semester.id=282; JSESSIONID=你的JSESSIONID; ..."
```

> Cookie 获取方法见"三、如何获取课程 ID 和 Cookie"。

### 5. 保活间隔 `KEEP_ALIVE_INTERVAL`（第 35 行）

默认 30 秒发一次保活请求维持登录态，一般不用改。

### 6. 休眠区间（第 39-40 行）

抢课开始后每轮之间的等待时间（秒），会在区间内随机取值，防止请求过于规律被反爬：

```python
NORMAL_MODE_SLEEP_MIN = 0.2   # 最小等待秒数
NORMAL_MODE_SLEEP_MAX = 0.8   # 最大等待秒数
```

- **开始后 5 分钟内**（高频模式）：固定 0.1~0.5 秒（硬编码）
- **5 分钟后**（正常模式）：使用上面配置的区间

## 三、如何获取课程 ID 和 Cookie

### 获取课程 ID

1. 用浏览器登录教务系统 https://jwxt.sias.edu.cn
2. 进入选课页面，找到你要抢的课程
3. 在课程旁边的"选课"按钮上**右键 → 检查**，在开发者工具中查看按钮的 HTML，找 `lesson` 或 `id` 相关的数字（通常是一串 6 位数字）

### 获取 Cookie

1. 登录教务系统后，按 **F12** 打开开发者工具
2. 切换到 **Application（应用程序）** 标签 → 左侧 **Cookies** → 点击网站域名
3. 把以下字段的值复制出来，拼接成一行（或用下方方法直接复制完整 Cookie）：

**快捷方法**：在开发者工具的 **Network（网络）** 标签页中，刷新页面，点任意一个请求，在 **Request Headers** 里找到 `Cookie:` 那一行，整行复制过来即可。

粘贴到脚本中时，格式如下：

```python
COOKIE = "semester.id=282; JSESSIONID=xxxx; srv_id=srv6; GSESSIONID=xxxx"
```

> **注意**：
> - Cookie 包含你的登录身份，**不要分享给任何人**，也不要上传到公开仓库。
> - 获取 Cookie 后**不要关闭浏览器**，否则重新登录会导致 Cookie 刷新、之前复制的 Cookie 立即失效。

## 四、运行脚本

终端中执行：

```bash
python shoudong.py
```

### 定时模式

如果配置了 `START_TIME_STR`，脚本会：
1. 启动 Cookie 保活线程（每 30 秒刷新登录态）
2. 显示实时倒计时
3. 到达设定时间后自动开始抢课
4. 按 `Ctrl+C` 可随时退出

### 手动模式

如果 `START_TIME_STR` 为空，脚本会：
1. 启动 Cookie 保活线程
2. 等待你按 **Enter** 键
3. 按下 Enter 后立即开始抢课

## 五、运行结果解读

| 服务器返回 | 含义 | 动作 |
|---|---|---|
| 包含 `成功` | 抢到了！ | 从任务列表移除 |
| 包含 `已经选过` | 课程已在选课单中 | 从任务列表移除 |
| 包含 `时间冲突` | 与其他课程时间冲突 | 从任务列表移除 |
| 其他 / 网络错误 | 暂时失败 | 下一轮继续重试 |

程序结束后会打印汇总：成功抢到的课程列表。

## 六、常见问题

**Q: Cookie 多久失效？**
A: 通常 20-30 分钟无操作会失效。脚本的保活线程会自动维持，只要在抢课前提前几分钟运行即可。

**Q: 可以同时抢多门课吗？**
A: 可以，把课程 ID 都填进 `TARGET_LIST`，脚本会轮流尝试每个目标。

**Q: 抢课开始后能中途退出吗？**
A: 按 `Ctrl+C` 即可优雅退出，已抢到的课程会打印汇总。

**Q: 运行报错 `ModuleNotFoundError: No module named 'requests'`？**
A: 没安装依赖，执行 `pip install requests`。
