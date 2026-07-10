import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import pyautogui
from pynput import keyboard
import ctypes
import sys

# ===================== 应用程序唯一控制 =====================
def check_single_instance():
    """
    单实例检测：通过Windows命名互斥体实现
    返回True表示是第一个实例，可以继续运行
    返回False表示已有实例在运行，直接退出
    """
    # 互斥体名称要足够独特，避免和其他软件重名
    MUTEX_NAME = "AutoClicker_Unique_Instance_Key"
    
    # 调用Windows API创建互斥体
    mutex_handle = ctypes.windll.kernel32.CreateMutexW(
        None,          # 安全属性：默认
        False,         # 是否立即拥有：否
        MUTEX_NAME     # 互斥体名称
    )
    
    # 错误码183 = ERROR_ALREADY_EXISTS，说明互斥体已存在
    if ctypes.GetLastError() == 183:
        # 弹出提示框
        ctypes.windll.user32.MessageBoxW(
            0,
            "连点器已经在运行中，请勿重复启动！",
            "运行提示",
            0x40  # 信息图标样式
        )
        # 关闭句柄并退出
        ctypes.windll.kernel32.CloseHandle(mutex_handle)
        return False
    return True

# ===================== 全局状态变量 =====================
is_running = False          # 连点运行标志位
click_interval = 100        # 默认点击间隔，单位毫秒
start_hotkey = keyboard.Key.f8   # 默认启动热键
stop_hotkey = keyboard.Key.f9    # 默认停止热键
listener = None             # 全局热键监听器对象
capturing_target = None     # 热键捕获状态：None=未捕获 / 'start'=捕获启动键 / 'stop'=捕获停止键


# ===================== 工具函数 =====================
def format_key(key):
    """
    将pynput的按键对象转换为人类可读的文本
    学习点：处理两种按键类型（普通字符键、功能键）
    """
    try:
        # 普通字母/数字键，转大写显示
        return key.char.upper()
    except AttributeError:
        # 功能键（F1-F12、空格、回车等），提取按键名并大写
        key_name = str(key).split('.')[-1]
        return key_name.upper()


# ===================== 连点核心逻辑 =====================
def click_loop():
    """后台连点循环，运行在独立子线程中，避免阻塞UI"""
    global is_running
    while is_running:
        pyautogui.click(button='left')
        time.sleep(click_interval / 1000)


def start_click():
    """启动连点逻辑，可被UI按钮和热键同时调用"""
    global is_running
    if not is_running:
        is_running = True
        # 守护线程：主程序关闭时自动销毁
        threading.Thread(target=click_loop, daemon=True).start()
        # 线程安全更新UI：子线程通过after调度到主线程执行
        root.after(0, lambda: status_label.config(text="运行中", fg="#27ae60"))


def stop_click():
    """停止连点逻辑"""
    global is_running
    is_running = False
    root.after(0, lambda: status_label.config(text="已停止", fg="#e74c3c"))


# ===================== 全局热键系统 =====================
def hotkey_listener():
    """全局热键监听线程，后台持续运行"""
    def on_press(key):
        global capturing_target, start_hotkey, stop_hotkey
        try:
            # ---------- 模式1：正在捕获自定义热键 ----------
            if capturing_target is not None:
                # 校验：启动键和停止键不能相同
                if capturing_target == 'start':
                    if key == stop_hotkey:
                        root.after(0, lambda: hotkey_tip_label.config(
                            text="热键冲突！请换一个按键", fg="#e74c3c"))
                        capturing_target = None
                        return
                    # 保存新热键并更新界面
                    start_hotkey = key
                    root.after(0, lambda k=key: start_key_label.config(text=format_key(k)))
                else:
                    if key == start_hotkey:
                        root.after(0, lambda: hotkey_tip_label.config(
                            text="热键冲突！请换一个按键", fg="#e74c3c"))
                        capturing_target = None
                        return
                    stop_hotkey = key
                    root.after(0, lambda k=key: stop_key_label.config(text=format_key(k)))

                root.after(0, lambda: hotkey_tip_label.config(text="热键设置成功", fg="#27ae60"))
                capturing_target = None
                time.sleep(3)  # 延时1秒后恢复提示文字
                end_capture()
                return

            # ---------- 模式2：正常响应热键 ----------
            if key == start_hotkey:
                start_click()
            elif key == stop_hotkey:
                stop_click()
        except Exception:
            # 忽略异常，防止监听器意外崩溃
            pass

    global listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()


def start_capture(target):
    """触发热键捕获，target指定捕获启动键还是停止键"""
    global capturing_target
    capturing_target = target
    if target == 'start':
        tip_text = "请按下要设置的【启动】热键..."
    elif target == 'stop':
        tip_text = "请按下要设置的【停止】热键..."
    hotkey_tip_label.config(text=tip_text, fg="#e67e22")

def end_capture():
    """结束热键捕获"""
    global capturing_target
    capturing_target = None
    hotkey_tip_label.config(text="点击「设置热键」后按下任意按键即可绑定",fg="#7f8c8d")
# ===================== 间隔设置与校验 =====================
def apply_interval():
    """应用点击间隔，带完整输入校验，学习点：用户输入合法性处理"""
    global click_interval
    input_text = interval_entry.get().strip()

    # 校验1：必须是纯数字
    if not input_text.isdigit():
        messagebox.showwarning("输入错误", "请输入有效的正整数（单位：毫秒）")
        # 恢复为原来的有效值
        interval_entry.delete(0, tk.END)
        interval_entry.insert(0, str(click_interval))
        return

    interval = int(input_text)
    # 校验2：范围限制，防止过小导致系统失控
    if interval < 10:
        messagebox.showwarning("输入错误", "点击间隔不能小于10毫秒（避免系统卡顿）")
        interval_entry.delete(0, tk.END)
        interval_entry.insert(0, str(click_interval))
        return
    # 校验3：上限限制
    if interval > 10000:
        messagebox.showwarning("输入错误", "点击间隔不能大于10000毫秒（10秒）")
        interval_entry.delete(0, tk.END)
        interval_entry.insert(0, str(click_interval))
        return

    # 校验通过，更新间隔
    click_interval = interval
    messagebox.showinfo("设置成功", f"点击间隔已修改为 {click_interval} 毫秒")


# ===================== 窗口关闭清理 =====================
def on_closing():
    """关闭窗口时释放所有资源，防止后台残留"""
    global listener, is_running
    is_running = False
    if listener:
        listener.stop()
    root.destroy()


# ===================== GUI界面搭建 =====================
if __name__ == "__main__":
    # 启动前先做单实例校验
    if not check_single_instance():
        sys.exit()
    
    # 主窗口初始化
    root = tk.Tk()
    root.title("自定义热键连点器")
    root.iconbitmap("assets/genshin_impact.ico")
    root.geometry("600x600")
    root.resizable(False, False)
    root.configure(bg="#f0f4f8")

    # ---------- 标题区域 ----------
    title_label = tk.Label(
        root, text="鼠标自动连点器",
        font=("微软雅黑", 18, "bold"),
        bg="#f0f4f8", fg="#2c3e50"
    )
    title_label.pack(fill=tk.X, pady=15)

    # ---------- 运行状态和点击间隔容器 ----------
    top_container = tk.Frame(root, bg="#f0f4f8")
    top_container.pack(padx=30, pady=15, fill=tk.X)

    # ---------- 运行状态区域 ----------
    status_frame = tk.LabelFrame(
        top_container, text="当前状态", font=("微软雅黑", 11, "bold"),
        bg="#f0f4f8", bd=1, relief=tk.GROOVE
    )
    status_frame.pack(side=tk.LEFT, padx=12, pady=0, fill=tk.BOTH, expand=True)
    status_label = tk.Label(status_frame, text="已停止", font=("微软雅黑", 20, "bold"), bg="#f0f4f8", fg="#e74c3c")
    status_label.pack(padx=16, pady=10)

    # ---------- 点击间隔设置区域 ----------
    interval_frame = tk.LabelFrame(
        top_container, text="点击间隔(ms)", font=("微软雅黑", 11, "bold"), 
        bg="#f0f4f8", bd=1, relief=tk.GROOVE
    )
    interval_frame.pack(side=tk.LEFT, padx=12, pady=0, fill=tk.BOTH, expand=True)

    interval_entry = ttk.Entry(interval_frame, width=12, font=("微软雅黑", 11))
    interval_entry.insert(0, str(click_interval))  # 填充默认值
    interval_entry.pack(padx=16,pady=5)
    ttk.Button(interval_frame, text="设置", command=apply_interval, width=6).pack(padx=5, pady=5)

    # ---------- 热键设置区域（分组框） ----------
    hotkey_frame = tk.LabelFrame(
        root, text="热键设置", font=("微软雅黑", 11, "bold"),
        bg="#f0f4f8", fg="#2c3e50", bd=1, relief=tk.GROOVE
    )
    hotkey_frame.pack(padx=30, pady=8, fill=tk.X, ipady=8)

    # 启动热键行
    start_row = tk.Frame(hotkey_frame, bg="#f0f4f8")
    start_row.pack(padx=15, pady=6, fill=tk.X)
    tk.Label(start_row, text="启动连点热键：", font=("微软雅黑", 10), bg="#f0f4f8").pack(side=tk.LEFT)
    start_key_label = tk.Label(
        start_row, text=format_key(start_hotkey), font=("微软雅黑", 10, "bold"),
        bg="#e8f4fd", fg="#2980b9", width=15, relief=tk.SUNKEN
    )
    start_key_label.pack(side=tk.LEFT, padx=10)
    ttk.Button(start_row, text="设置热键", command=lambda: start_capture('start'), width=10).pack(side=tk.RIGHT)

    # 停止热键行
    stop_row = tk.Frame(hotkey_frame, bg="#f0f4f8")
    stop_row.pack(padx=15, pady=6, fill=tk.X)
    tk.Label(stop_row, text="停止连点热键：", font=("微软雅黑", 10), bg="#f0f4f8").pack(side=tk.LEFT)
    stop_key_label = tk.Label(
        stop_row, text=format_key(stop_hotkey), font=("微软雅黑", 10, "bold"),
        bg="#fdecea", fg="#c0392b", width=15, relief=tk.SUNKEN
    )
    stop_key_label.pack(side=tk.LEFT, padx=10)
    ttk.Button(stop_row, text="设置热键", command=lambda: start_capture('stop'), width=10).pack(side=tk.RIGHT)

    # 热键设置提示文字
    hotkey_tip_label = tk.Label(
        hotkey_frame, text="点击「设置热键」后按下任意按键即可绑定",
        font=("微软雅黑", 9), bg="#f0f4f8", fg="#7f8c8d"
    )
    hotkey_tip_label.pack(pady=4)

    # ---------- 操作按钮区域 ----------
    btn_frame = tk.Frame(root, bg="#f0f4f8")
    btn_frame.pack(pady=12)
    ttk.Button(btn_frame, text="手动启动", command=start_click, width=12).grid(row=0, column=0, padx=8)
    ttk.Button(btn_frame, text="手动停止", command=stop_click, width=12).grid(row=0, column=1, padx=8)
    ttk.Button(btn_frame, text="退出程序", command=on_closing, width=12).grid(row=0, column=2, padx=8)

    # ---------- 底部提示 ----------
    tip_label = tk.Label(
        root, text="提示：热键为全局生效，窗口最小化也可使用",
        font=("微软雅黑", 9), bg="#f0f4f8", fg="#7f8c8d"
    )
    tip_label.pack(pady=5)

    # 绑定窗口关闭事件
    root.protocol("WM_DELETE_WINDOW", on_closing)

    # 启动后台热键监听线程
    threading.Thread(target=hotkey_listener, daemon=True).start()

    # 启动UI主循环
    root.mainloop()