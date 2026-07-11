import requests
import time
import random
import threading
import signal
from datetime import datetime
# ====================== 配置区 ======================

# 1. 你的任务列表
TARGET_LIST = [
    "373612",
    "371579",
]


# 2. 【新增】定时启动时间 (格式: '年-月-日 时:分:秒')
#    如果留空字符串 (如 START_TIME_STR = ""），则会和以前一样，等待你手动按回车开始。
#    当前时间是 2025-07-11 12:13，我将示例时间设置为几分钟后，方便你测试。
START_TIME_STR = "2026-7-12 08:29:50"  # <--- 修改为你抢课的精确开始时间
#START_TIME_STR = "2025-08-29 13:30:20"
# 3. 执行抢课操作的 POST URL
GRAB_ACTION_URL = "https://jwxt.sias.edu.cn/eams/stdElectCourse!batchOperator.action?profileId=2011"
KEEP_ALIVE_URL = "https://jwxt.sias.edu.cn/eams/stdElectCourse!defaultPage.action?electionProfile.id=2011"

# 4. 你的有效 Cookie
COOKIE = "semester.id=322; JSESSIONID=B3D877BE11FFDA041C625ED0C9FD8698; srv_id=srv1; GSESSIONID=99E677FB6ABF0A746DEC2F9F304E5743; JSESSIONID=6C1CCC4FB85A109A0B50D60A7C63122F"
# 5. Cookie保活间隔（秒）
KEEP_ALIVE_INTERVAL = 30  # 每30秒发送一次保活请求

# 6. 正常模式（非高频模式）随机休眠区间（秒）——可自行调整
#    当不处于“高频模式”时（目标时间+5分钟之后），程序会在该区间内随机休眠
NORMAL_MODE_SLEEP_MIN = 0.2
NORMAL_MODE_SLEEP_MAX = 0.8

# 如果你也想让“高频模式”区间可配置，可以再加：
# HIGH_FREQ_SLEEP_MIN = 0.1
# HIGH_FREQ_SLEEP_MAX = 0.5
# 并在下方 get_dynamic_sleep_time 中替换对应硬编码（当前保持原样）

# ===================================================

# 添加全局变量控制抢课开始时间
grab_start_time = None
stop_keep_alive = False
successfully_grabbed_courses = []  # 记录成功抢到的课程列表
stop_event = threading.Event()  # 线程安全的停止标志
_keep_alive_thread = None  # 保活线程句柄

# 请求头
HEADERS = {
    'Cookie': COOKIE,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
}


def signal_handler(signum, frame):
    """
    信号处理函数，用于优雅地处理停止信号（如Ctrl+C）
    """
    print(f"\n\n🛑 收到停止信号 ({signum})，正在优雅退出...")
    print("⏳ 等待当前任务完成后退出程序...")
    stop_event.set()  # 设置停止标志


def wait_for_start():
    """
    【已更新】根据配置决定是定时等待还是手动开始，并提供实时倒计时。
    支持在倒计时期间立即响应中断信号。
    """
    if START_TIME_STR:
        # 解析时间字符串，异常则回退到手动模式
        try:
            start_time = datetime.strptime(START_TIME_STR, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print("⚠️ START_TIME_STR 格式错误，应为 YYYY-MM-DD HH:MM:SS，回退为手动启动模式。")
            try:
                input(">>> 已设置为手动模式，按下 Enter 键后立即开始循环发送请求...")
                return True
            except KeyboardInterrupt:
                print("\n🛑 手动启动被中断，程序退出...")
                stop_event.set()
                return False

        print(f"已设置为定时启动模式，目标时间: {START_TIME_STR}")
        print("💡 提示: 倒计时期间可按 Ctrl+C 立即中断程序")

        while datetime.now() < start_time and not stop_event.is_set():
            remaining_time = start_time - datetime.now()
            remaining_seconds = remaining_time.total_seconds()
            countdown_message = f"--> 倒计时: {remaining_seconds:6.2f} 秒..."
            print(countdown_message, end='\r', flush=True)
            # 分段休眠以快速响应停止信号
            for _ in range(10):
                if stop_event.is_set():
                    print("\n🛑 倒计时被中断，程序退出...")
                    return False
                time.sleep(0.1)

        if stop_event.is_set():
            print("\n🛑 倒计时被中断，程序退出...")
            return False

        print("\n⏰ 时间到！立即开始执行任务！" + " " * 30)
        return True
    else:
        # 手动启动模式
        try:
            input(">>> 已设置为手动模式，按下 Enter 键后立即开始循环发送请求...")
            return True
        except KeyboardInterrupt:
            print("\n🛑 手动启动被中断，程序退出...")
            stop_event.set()
            return False


def keep_cookie_alive():
    """
    定期发送请求维持Cookie有效性（已改为访问选课主页，避免误触发选课）。
    """
    global stop_keep_alive
    session = requests.Session()

    # 使用访问选课首页作为保活，不进行任何选课操作
    keep_alive_headers = {
        'Cookie': COOKIE,
        'User-Agent': HEADERS['User-Agent'],
    }

    while not stop_keep_alive and not stop_event.is_set():
        try:
            response = session.get(KEEP_ALIVE_URL, headers=keep_alive_headers, timeout=10)
            current_time = datetime.now().strftime('%H:%M:%S')
            if response.status_code == 200:
                # 粗略判断登录态
                if ("登录" in response.text) or ("login" in response.text.lower()):
                    print(f"[{current_time}] Cookie保活失败 - Cookie已失效")
                else:
                    print(f"[{current_time}] Cookie保活成功")
            else:
                print(f"[{current_time}] Cookie保活失败 - 状态码 {response.status_code}")
        except Exception as e:
            current_time = datetime.now().strftime('%H:%M:%S')
            print(f"[{current_time}] Cookie保活请求异常 - {e}")

        # 分段休眠，便于快速停止
        total_sleep = max(0.5, float(KEEP_ALIVE_INTERVAL))
        slept = 0.0
        step = 0.1
        while slept < total_sleep and not stop_keep_alive and not stop_event.is_set():
            time.sleep(step)
            slept += step


def start_keep_alive_thread():
    """
    启动Cookie保活线程，并返回线程句柄。
    """
    global _keep_alive_thread
    _keep_alive_thread = threading.Thread(target=keep_cookie_alive, daemon=True)
    _keep_alive_thread.start()
    print("Cookie保活线程已启动")
    return _keep_alive_thread


def _minutes_since(dt: datetime) -> float:
    try:
        return (datetime.now() - dt).total_seconds() / 60.0
    except Exception:
        return 0.0


def get_dynamic_sleep_time():
    """
    根据定时启动的目标时间动态计算休眠时间
    高频模式维持到目标时间+5分钟，而不是程序开始+5分钟

    正常模式休眠区间由全局变量 NORMAL_MODE_SLEEP_MIN / NORMAL_MODE_SLEEP_MAX 控制
    """
    global grab_start_time

    # 先尝试基于定时启动
    if START_TIME_STR and START_TIME_STR.strip():
        try:
            target_time = datetime.strptime(START_TIME_STR, '%Y-%m-%d %H:%M:%S')
            elapsed_minutes = _minutes_since(target_time)
        except ValueError:
            target_time = None
            elapsed_minutes = None
    else:
        elapsed_minutes = None

    # 若未能得到有效的定时基准，则回退到程序开始时间
    if elapsed_minutes is None:
        if isinstance(grab_start_time, datetime):
            elapsed_minutes = (datetime.now() - grab_start_time).total_seconds() / 60.0
        else:
            elapsed_minutes = -1.0

    # 统一决策
    if elapsed_minutes < 0:
        # 尚未建立开始时间，使用正常模式区间
        sleep = random.uniform(NORMAL_MODE_SLEEP_MIN, NORMAL_MODE_SLEEP_MAX)
    elif elapsed_minutes < 5:
        # 高频模式（仍保持原硬编码，若需灵活请开启上方注释）
        sleep = random.uniform(0.1, 0.5)
    else:
        # 正常模式使用可配置范围
        try:
            low = float(NORMAL_MODE_SLEEP_MIN)
            high = float(NORMAL_MODE_SLEEP_MAX)
            if low > high:
                low, high = high, low  # 容错：反转
            sleep = random.uniform(low, high)
        except Exception:
            sleep = random.uniform(1, 3)  # 兜底

    return sleep


def main():
    """
    主函数，按列表循环发送POST请求，直到列表为空。
    """
    global grab_start_time, stop_keep_alive, successfully_grabbed_courses, _keep_alive_thread

    # 注册信号处理器，捕捉Ctrl+C和PyCharm停止按钮信号
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    try:
        signal.signal(signal.SIGTERM, signal_handler)  # PyCharm停止按钮
        print("📡 已注册信号处理器，可使用 Ctrl+C 或 PyCharm停止按钮优雅退出程序")
    except AttributeError:
        # Windows系统可能不支持SIGTERM
        print("📡 已注册信号处理器，可使用 Ctrl+C 优雅退出程序")

    remaining_targets = list(TARGET_LIST)

    # 任务列表为空直接退出
    if not remaining_targets:
        print("⚠️ 任务列表为空，程序结束。")
        return

    print("---------- 多任务发射器已准备就绪 ----------")
    print(f"初始任务列表: {remaining_targets}")
    keep_alive_th = start_keep_alive_thread()

    try:
        # 等待开始，如果被中断则直接退出
        if not wait_for_start():
            return  # 倒计时被中断，直接退出

        # 记录抢课开始时间并停止保活
        grab_start_time = datetime.now()
        stop_keep_alive = True
        # 等待保活线程优雅退出
        if keep_alive_th is not None:
            keep_alive_th.join(timeout=12)
        print("抢课开始，Cookie保活线程已停止")

        round_count = 0
        session = requests.Session()

        # 修改循环条件：检查任务列表和停止标志
        while remaining_targets and not stop_event.is_set():
            round_count += 1
            print(f"\n=============== 开始第 {round_count} 轮尝试，剩余 {len(remaining_targets)} 个目标 ===============")

            succeeded_this_round = []

            for target_id in remaining_targets:
                # 在每个请求前检查停止标志
                if stop_event.is_set():
                    print("🛑 检测到停止信号，中断当前轮次...")
                    break

                print(f"--- 正在尝试目标: {target_id} --- [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]")

                payload = {
                    'optype': 'true',
                    'operator0': f'{target_id}:true:0',
                    'lesson0': target_id,
                }
                payload[f'schLessonGroup_{target_id}'] = 'undefined'

                try:
                    response = session.post(GRAB_ACTION_URL, headers=HEADERS, data=payload, timeout=10)
                    response_text = (response.text or '').strip()
                    print("【服务器响应】:", response_text)

                    if "成功" in response_text:
                        print(f"✅✅✅ 任务完成: 成功抢到课程 {target_id}！将从任务列表中移除。 ✅✅✅")
                        succeeded_this_round.append(target_id)
                        successfully_grabbed_courses.append(target_id)  # 记录成功抢到的课程
                    elif "已经选过" in response_text:
                        print(f"ℹ️ℹ️ℹ️ 无需再选: 课程 {target_id} 已在你的选课单中。将从任务列表中移除。 ℹ️ℹ️ℹ️")
                        succeeded_this_round.append(target_id)
                    elif "时间冲突" in response_text:
                        print(f"🔥🔥🔥 致命错误: 课程 {target_id} 时间冲突！将从任务列表中移除。 🔥🔥🔥")
                        succeeded_this_round.append(target_id)

                    time.sleep(0.5)

                except requests.exceptions.RequestException as e:
                    print(f"【网络错误】: 尝试课程 {target_id} 时失败: {e}")
                    time.sleep(1)

            if succeeded_this_round:
                remaining_targets = [tid for tid in remaining_targets if tid not in succeeded_this_round]
                print(f"\n本轮结束后，剩余任务列表: {remaining_targets}")

            if not remaining_targets:
                break

            # 检查停止标志，避免不必要的休眠
            if stop_event.is_set():
                print("🛑 检测到停止信号，跳过休眠...")
                break

            # 使用动态休眠时间
            sleep_time = get_dynamic_sleep_time()

            # 计算状态显示：基于定时启动时间而不是程序开始时间
            if START_TIME_STR:
                try:
                    target_time = datetime.strptime(START_TIME_STR, '%Y-%m-%d %H:%M:%S')
                    elapsed_minutes = (datetime.now() - target_time).total_seconds() / 60
                except ValueError:
                    elapsed_minutes = (datetime.now() - grab_start_time).total_seconds() / 60
            else:
                elapsed_minutes = (datetime.now() - grab_start_time).total_seconds() / 60

            status = "高频模式" if elapsed_minutes < 5 else "正常模式"
            print(f"\n=============== 第 {round_count} 轮完毕，{status}休眠 {sleep_time:.2f} 秒... ===============")

            # 分段休眠，以便更快响应停止信号
            sleep_segments = max(1, int(sleep_time * 10))  # 分成10段
            for _ in range(sleep_segments):
                if stop_event.is_set():
                    break
                time.sleep(sleep_time / sleep_segments)

    except KeyboardInterrupt:
        # 捕获KeyboardInterrupt异常，确保程序优雅退出
        print("\n🛑 程序被中断...")
        stop_event.set()
    except Exception as e:
        print(f"\n❌ 程序运行出现异常: {e}")
        stop_event.set()
    finally:
        # 无论如何都会执行的清理代码
        print_final_summary()


def print_final_summary():
    """
    打印最终的抢课结果汇总
    """
    # 程序结束时输出成功抢到的课程汇总
    if stop_event.is_set():
        print("\n" + "="*80)
        print("🛑🛑🛑 程序被用户中断！当前抢课结果汇总 🛑🛑🛑")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("🎉🎉🎉 程序执行完毕！抢课结果汇总 🎉🎉🎉")
        print("="*80)

    if successfully_grabbed_courses:
        print(f"✅ 成功抢到 {len(successfully_grabbed_courses)} 门课程：")
        for course_id in successfully_grabbed_courses:
            print(f"✅✅✅ 任务完成: 成功抢到课程 {course_id}！✅✅✅")
    else:
        print("❌ 很遗憾，本次没有成功抢到任何课程")

    print("="*80)
    print(f"⏰ 程序结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("所有任务均已处理完毕，程序退出。")


if __name__ == "__main__":
    main()
