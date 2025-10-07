# adapted from: https://github.com/Sentdex/pygta5/blob/master/grabscreen.py
import cv2
import numpy as np
import win32gui, win32ui, win32con, win32api, win32process
import time
import matplotlib.pyplot as plt

from config import *


from PIL import Image
import mss


def grab_window(hwin, game_resolution=(1024,768), SHOW_IMAGE=False):
    '''
    -- Inputs --

    hwin
    this is the HWND id of the cs go window
    we play in windowed rather than full screen mode
    e.g. https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow

    game_resolution=(1024,768)
    is the windowed resolution of the game
    I think could get away with game_resolution=(640,480)
    and should be quicker to grab from
    but for now, during development, I like to see the game in reasonable
    size

    SHOW_IMAGE
    whether to display the image. probably a bad idea to
    do that here except for testing
    better to use cv2.imshow('img',img) outside the funcion

    -- Outputs --
    currently this function returns img_small
    img is the raw capture image, in BGR
    img_small is a low res image, with the thought of
    using this as input to a NN

    '''

    # we used to try to get the resolution automatically
    # but this didn't seem that reliable for some reason
    # left,top,right,bottom = win32gui.GetWindowRect(hwin)
    # width = right - left
    # height = bottom - top


    bar_height = 35 # height of header bar


    # how much of top and bottom of image to ignore
    # (reasoning we don't need the entire screen)
    # much more efficient not to grab it in the first place
    # rather than crop out later
    # this stage can be a bit of a bottle neck
    offset_height_top = 135
    offset_height_bottom = 135


    offset_sides = 100 # ignore this many pixels on sides,
    width = game_resolution[0] - 2*offset_sides
    height = game_resolution[1]-offset_height_top-offset_height_bottom


    # 获取窗口的实际尺寸
    window_rect = win32gui.GetWindowRect(hwin)
    window_width = window_rect[2] - window_rect[0]
    window_height = window_rect[3] - window_rect[1]

    print(f"窗口实际尺寸: {window_width}x{window_height}")

    # 计算截取区域
    width = window_width - 2 * offset_sides
    height = window_height - offset_height_top - offset_height_bottom - bar_height
    img = cv2.cvtColor(np.zeros((height,width,3), np.uint8), cv2.COLOR_BGR2RGB)

    print(f"计划截取区域: {width}x{height}")
    print(f"截取起始坐标: ({offset_sides}, {bar_height + offset_height_top})")

    # 验证截取区域是否在窗口范围内
    if (offset_sides < 0 or
        bar_height + offset_height_top < 0 or
        offset_sides + width > window_width or
        bar_height + offset_height_top + height > window_height):
        print("⚠️ 警告: 截取区域超出窗口范围，自动调整...")

        # 自动调整到安全区域
        offset_sides = max(0, offset_sides)
        offset_height_top = max(0, offset_height_top)
        width = min(width, window_width - offset_sides)
        height = min(height, window_height - bar_height - offset_height_top - offset_height_bottom)

        print(f"调整后截取区域: {width}x{height}")
        print(f"调整后起始坐标: ({offset_sides}, {bar_height + offset_height_top})")


    hwindc = win32gui.GetWindowDC(hwin)
    print(f"获取窗口设备上下文(dc): {hwindc}")
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    print(f"根据窗口dc创建源dc: {srcdc}")
    memdc = srcdc.CreateCompatibleDC()
    print(f"在内存中创建同步虚拟内存dc: {memdc}")
    bmp = win32ui.CreateBitmap()
    print(f"创建空位图对象: {bmp}")
    bmp.CreateCompatibleBitmap(srcdc, width, height)
    print(f"根据源dc初始化位图: {bmp}")
    memdc.SelectObject(bmp)
    print(f"将位图选入内存dc对象: {memdc}")

    res_BitBlt = memdc.BitBlt((0, 0), (width, height), srcdc, (offset_sides, bar_height+offset_height_top), win32con.SRCCOPY)
    print(f"执行位图传输操作(BitBlt)，将窗口内容复制到内存位图中: {res_BitBlt}")
    # memdc.BitBlt((0, 0), (width, height), srcdc, (0, 0), win32con.SRCCOPY)
    if res_BitBlt:
        signedIntsArray = bmp.GetBitmapBits(True)
        print("获取位图数据")
        img = np.frombuffer(signedIntsArray, dtype='uint8')
        # img.shape=(1641408,)
        # height*width=410352
        # 1641408 / (height*width)=4
        img.shape = (height,width,4)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        # img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

        # image = Image.frombuffer('RGB', (width, height), signedIntsArray, 'raw', 'BGRX', 0, 1)

    else:
        print("警告: BitBlt操作失败，未能获取窗口内容。请确保窗口句柄正确且窗口未被遮挡。")
        print("尝试截取整个窗口...")
        bmp_full = win32ui.CreateBitmap()
        bmp_full.CreateCompatibleBitmap(srcdc, window_width, window_height)
        memdc.SelectObject(bmp_full)

        result_full = memdc.BitBlt((0, 0), (window_width, window_height), srcdc, (0, 0), win32con.SRCCOPY)

        if result_full:
            print("整个窗口截取成功")
            signedIntsArray = bmp_full.GetBitmapBits(True)
            img = np.frombuffer(signedIntsArray, dtype='uint8')
            img.shape = (window_height, window_width, 4)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            # 裁剪到目标区域
            start_x = offset_sides
            start_y = bar_height + offset_height_top
            end_x = start_x + width
            end_y = start_y + height

            if end_x <= window_width and end_y <= window_height:
                img = img[start_y:end_y, start_x:end_x]
                print(f"裁剪后图像形状: {img.shape}")
            else:
                print("无法裁剪，返回完整图像")
        else:
            print("警告: BitBlt操作失败，整个窗口截取也未能获取窗口内容。请检查窗口状态。")

    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwin, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())

    if IS_CONTRAST:
        contrast = 1.5
        brightness = 1.0
        img = cv2.addWeighted(img, contrast, img, 0, brightness)


    img_small = cv2.resize(img, csgo_img_dimension[::-1])


    if SHOW_IMAGE:

        target_width = 800
        scale = target_width / img_small.shape[1] # how much to magnify
        dim = (target_width,int(img_small.shape[0] * scale))
        resized = cv2.resize(img_small, dim, interpolation = cv2.INTER_AREA)
        cv2.imshow('resized',resized)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()

    return img_small
    # return img, img_small


def grab_window_mss(hwin, game_resolution=(1024,768), SHOW_IMAGE=False):
    '''
    -- Inputs --

    hwin
    this is the HWND id of the cs go window
    we play in windowed rather than full screen mode
    e.g. https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getforegroundwindow

    game_resolution=(1024,768)
    is the windowed resolution of the game
    I think could get away with game_resolution=(640,480)
    and should be quicker to grab from
    but for now, during development, I like to see the game in reasonable
    size

    SHOW_IMAGE
    whether to display the image. probably a bad idea to
    do that here except for testing
    better to use cv2.imshow('img',img) outside the funcion

    -- Outputs --
    currently this function returns img_small
    img is the raw capture image, in BGR
    img_small is a low res image, with the thought of
    using this as input to a NN

    '''

    # we used to try to get the resolution automatically
    # but this didn't seem that reliable for some reason
    # left,top,right,bottom = win32gui.GetWindowRect(hwin)
    # width = right - left
    # height = bottom - top


    bar_height = 35 # height of header bar


    # how much of top and bottom of image to ignore
    # (reasoning we don't need the entire screen)
    # much more efficient not to grab it in the first place
    # rather than crop out later
    # this stage can be a bit of a bottle neck
    offset_height_top = 135
    offset_height_bottom = 135


    offset_sides = 100 # ignore this many pixels on sides,
    width = game_resolution[0] - 2 * offset_sides
    height = game_resolution[1] - offset_height_top - offset_height_bottom

    left, top, right, bottom = win32gui.GetWindowRect(hwin)
    capture_left = left + offset_sides
    capture_top = top + bar_height + offset_height_top
    capture_width = (right - left) - 2 * offset_sides
    capture_height = (bottom - top) - bar_height - offset_height_top - offset_height_bottom

    with mss.mss() as sct:
        monitor = {
            "left": capture_left,
            "top": capture_top,
            "width": capture_width,
            "height": capture_height
        }
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        print(f"mss截取成功: {img.shape}")

    if IS_CONTRAST:
        contrast = 1.5
        brightness = 1.0
        img = cv2.addWeighted(img, contrast, img, 0, brightness)


    img_small = cv2.resize(img, csgo_img_dimension[::-1])


    if SHOW_IMAGE:

        target_width = 800
        scale = target_width / img_small.shape[1] # how much to magnify
        dim = (target_width,int(img_small.shape[0] * scale))
        resized = cv2.resize(img_small, dim, interpolation = cv2.INTER_AREA)
        cv2.imshow('resized',resized)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()

    return img_small
    # return img, img_small



def fps_capture_test():

    if False:
        # can use this to manually find hwin, id of selected window
        # actually can look this up from name directly
        while True:
            hwin = win32gui.GetForegroundWindow()
            print(hwin)
            time.sleep(0.2)

    time_start = time.time()
    n_grabs=20000
    # hwin = win32gui.FindWindow(None,'Counter-Strike: Global Offensive')
    hwin = win32gui.FindWindow(None, 'Counter-Strike 2')

    title = win32gui.GetWindowText(hwin)
    class_name = win32gui.GetClassName(hwin)
    rect = win32gui.GetWindowRect(hwin)
    _, pid = win32process.GetWindowThreadProcessId(hwin)

    print(f"窗口句柄: {hwin}")
    print(f"窗口标题: {title}")
    print(f"窗口类名: {class_name}")
    print(f"窗口位置: {rect}")
    print(f"进程ID: {pid}")

    for i in range(n_grabs):
        # img_small = grab_window(hwin, game_resolution=(1024,768), SHOW_IMAGE=False)
        img_small = grab_window_mss(hwin, game_resolution=(1024,768), SHOW_IMAGE=False)

        if True:
            # because we use a shrunk image for input into the NN
            # we kind of want to make it larger so we can see what's happening
            # of course it's lossy compared to the original game
            target_width = 800
            scale = target_width / img_small.shape[1] # how much to magnify
            dim = (target_width,int(img_small.shape[0] * scale))
            resized = cv2.resize(img_small, dim, interpolation = cv2.INTER_AREA)
            cv2.imshow('resized',resized)


        if cv2.waitKey(1) & 0xFF == ord('q'):
            cv2.destroyAllWindows()
            break

    cv2.destroyAllWindows()

    time_end = time.time()
    avg_time = (time_end-time_start)/n_grabs
    fps = 1/avg_time
    print('avg_time',np.round(avg_time,5))
    print('fps',np.round(fps,2))
    return


if __name__ == "__main__":
    fps_capture_test()


