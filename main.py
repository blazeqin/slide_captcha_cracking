import cv2 as cv
import numpy as np
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from PIL import Image
import time
import urllib.request
import threading
import random


#  传入滑块背景图片本地路径和滑块本地路径，返回滑块到缺口的距离
def findPic(img_bg_path, img_slider_path):
    """
    找出图像中最佳匹配位置
    :param img_bg_path: 滑块背景图本地路径
    :param img_slider_path: 滑块图片本地路径
    :return: 返回最差匹配、最佳匹配对应的x坐标
    """

    # 读取滑块背景图片，参数是图片路径，OpenCV默认使用BGR模式
    # cv.imread()是 image read的简写
    # img_bg 是一个numpy库ndarray数组对象
    img_bg = cv.imread(img_bg_path)

    # 对滑块背景图片进行处理，由BGR模式转为gray模式（即灰度模式，也就是黑白图片）
    # 为什么要处理？ BGR模式（彩色图片）的数据比黑白图片的数据大，处理后可以加快算法的计算
    # BGR模式：常见的是RGB模式
    # R代表红，red; G代表绿，green;  B代表蓝，blue。
    # RGB模式就是，色彩数据模式，R在高位，G在中间，B在低位。BGR正好相反。
    # 如红色：RGB模式是(255,0,0)，BGR模式是(0,0,255)
    img_bg_gray = cv.cvtColor(img_bg, cv.COLOR_BGR2GRAY)

    # 读取滑块，参数1是图片路径，参数2是使用灰度模式
    img_slider = cv.imread(img_slider_path, 0)
    cv.imshow('slider',img_slider)
    cv.waitKey(100)

    # 在滑块背景图中匹配滑块。参数cv.TM_CCOEFF_NORMED是opencv中的一种算法
    res = cv.matchTemplate(img_bg_gray, img_slider, cv.TM_CCORR_NORMED)

    print('#' * 50)
    print(type(res))  # 打印：<class 'numpy.ndarray'>
    print(res)

    print('#' * 50)

    # cv2.minMaxLoc() 从ndarray数组中找到最小值、最大值及他们的坐标
    value = cv.minMaxLoc(res)
    # 得到的value，如：(-0.1653602570295334, 0.6102921366691589, (144, 1), (141, 56))

    print(value, "#" * 30)

    # 获取x坐标，如上面的144、141
    return value[2:][0][0], value[2:][1][0]


# 对滑块进行二值化处理
def handle_slider(image):
    kernel = np.ones((8, 8), np.uint8)  # 去滑块的前景噪声内核
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    width, heigth = gray.shape
    for h in range(heigth):
        for w in range(width):
            if gray[w, h] == 0:
                gray[w, h] = 58
    # cv.imshow('gray', gray)
    binary = cv.inRange(gray, 58, 58)
    res = cv.morphologyEx(binary, cv.MORPH_OPEN, kernel)  # 开运算去除白色噪点
    # cv.imshow('res', res)
    # cv.waitKey(0)
    return res


def to_alpha(img):
    dst = cv.cvtColor(img, cv.COLOR_BGR2BGRA)
    for y in range(dst.shape[0]):
        for x in range(dst.shape[1]):
            pixel = dst[y, x]
            if pixel[0] == 255 and pixel[1] == 255 and pixel[2] == 255:
                dst[y, x][3] = 0
    cv.imwrite("./slider.png", dst)
    return dst


# 模板匹配(用于寻找缺口有点误差)
def template_match(img_target, img_template):
    tpl = handle_slider(img_template)  # 误差来源就在于滑块的背景图为白色

    blurred = cv.GaussianBlur(img_target, (3, 3), 0)  # 目标图高斯滤波
    gray = cv.cvtColor(blurred, cv.COLOR_BGR2GRAY)
    ret, target = cv.threshold(gray, 127, 255, cv.THRESH_BINARY)  # 目标图二值化
    # cv.imshow("template", tpl)
    # cv.imshow("target", target)
    # cv.waitKey(0)
    method = cv.TM_CCOEFF_NORMED
    width, height = tpl.shape[:2]
    result = cv.matchTemplate(target, tpl, method)
    min_val, max_val, min_loc, max_loc = cv.minMaxLoc(result)
    left_up = max_loc if max_loc[0] > min_loc[0] else min_loc
    print(min_loc)
    print(max_loc)
    print(left_up)
    # right_down = (left_up[0] + width, left_up[1] + height)
    # cv.rectangle(img_target, left_up, right_down, (0, 0, 255), 2)
    # cv.imshow('res', img_target)
    # cv.waitKey(0)
    return left_up[0] - 8


# 返回两个数组：一个用于加速拖动滑块，一个用于减速拖动滑块
def generate_tracks(distance):
    print("滑动距离：" + str(distance))
    # 给距离加上20，这20像素用在滑块滑过缺口后，减速折返回到缺口
    distance += 16
    v = 0
    t = 0.2
    forward_tracks = []
    current = 0
    mid = distance * 3 / 5  # 减速阀值
    while current < distance:
        if current < mid:
            a = 2  # 加速度为+2
        else:
            a = -3  # 加速度-3
        s = v * t + 0.5 * a * (t ** 2)
        v = v + a * t
        current += s
        forward_tracks.append(round(s))

    back_tracks = [-3, -3, -2, -2, -2, -1, -1, -1, -1]
    return forward_tracks, back_tracks


def move_button(driver, button, value):
    action = ActionChains(driver)
    print("try to crack captcha...x="+str(value))
    try:
        action.click_and_hold(button).perform()
    except StaleElementReferenceException as e:
        print(e)

    action.reset_actions()

    forward_tracks, back_tracks = generate_tracks(value)

    for x in forward_tracks:
        action.move_by_offset(x, 0)  # 前进移动滑块
        # print(x)

    print('#' * 50)

    for x in back_tracks:
        action.move_by_offset(x, 0)  # 后退移动滑块
        # print(x)

    action.release().perform()


def try_crack(driver, wait, flag=True):
    if flag:
        driver.refresh()
        print("refresh page")
    else:
        driver.get("https://video.kuaishou.com/short-video/3x64va4fgudq9ec?fid=2157899965&cc=share_copylink&followRefer=151&shareMethod=TOKEN&docId=0&kpn=KUAISHOU&subBiz=PHOTO&shareResourceType=PHOTO_OTHER&userId=3xr5h4kk5he7fpy&photoId=3x64va4fgudq9ec&shareType=1&et=1_v/2000392675735970993_sff0&shareMode=APP&groupName=&appType=21&shareUrlOpened=0&utm_source=app_share&utm_medium=app_share&utm_campaign=app_share&location=app_share")

    try:
        did = driver.get_cookie("did")
        print(did)

        xf = wait.until(expected_conditions.presence_of_element_located((By.XPATH, "//iframe")))
        driver.switch_to.frame(xf)

        # image-container
        container = wait.until(
            expected_conditions.presence_of_element_located((By.XPATH, "//div[@class='image-container']")))
        container.screenshot(r'./captcha1.png')

    except Exception as e:
        print(e)
        print("over the captcha")
    else:
        time.sleep(3)

        # 获取 滑块背景图
        bg_image = wait.until(
            expected_conditions.presence_of_element_located((By.CLASS_NAME, "bg-img")))
        print("\n背景：" + str(bg_image.size['width']))

        print(bg_image)
        bg_image_url = bg_image.get_attribute('src')

        print(bg_image_url)

        # 使用urllib下载背景图
        # 原因是：使用bg_image.screenshot()程序卡在这里，也不报错
        urllib.request.urlretrieve(bg_image_url, "./img_bg.png")
        bgim = Image.open('img_bg.png')
        out = bgim.resize((bg_image.size['width'], bg_image.size['height']), Image.ANTIALIAS)
        out.save('./img_bg.png')

        # 获取 滑块
        slider = wait.until(
            expected_conditions.presence_of_element_located((By.CLASS_NAME, "slider-img")))

        print("\n滑块：")
        print(slider)

        # 注意：千万不能通过截图获取滑块，因为滑块不是规则的图形
        # 而截图截出的是矩形，会把滑块周围的滑块背景图一起截取，势必影响匹配
        # slider.screenshot('./img_slider.png')
        slider_url = slider.get_attribute('src')
        print(slider_url)

        urllib.request.urlretrieve(slider_url, "./img_slider.png")
        sliderim = Image.open('img_slider.png')
        out = sliderim.resize((slider.size['width'], slider.size['height']), Image.ANTIALIAS)
        out.save('./img_slider.png')

        time.sleep(5)
        # value_1, value_2 = findPic('./img_bg.png', './img_slider.png')
        img_slider = cv.imread("./img_slider.png")
        img_bg = cv.imread("./img_bg.png")

        value = template_match(img_bg, img_slider)

        print("#" * 30)
        print("最佳匹配对应的x坐标是：")
        print(value)
        print("#" * 30)

        # 获取滑动按钮
        button = wait.until(
            expected_conditions.presence_of_element_located((By.XPATH, '//div[@class="slider-btn"]')))
        print(button)

        move_button(driver, button, value)

        time.sleep(5)
        # 尝试轮廓识别
        try:
            button = wait.until(
                expected_conditions.presence_of_element_located((By.XPATH, '//div[@class="slider-btn"]')))
            max, pos = get_pos(img_bg)
            if max == 0:
                try_crack(driver, wait)
            else:
                move_button(driver, button, max)

                time.sleep(5)
                button = wait.until(
                    expected_conditions.presence_of_element_located((By.XPATH, '//div[@class="slider-btn"]')))
                # 刷新页面 重来
                try_crack(driver, wait)
        except Exception as e:
            print(e)
            print("may captcha gone")
            try_crack(driver, wait)
    finally:
        driver.close()


def main():
    # 创建一个参数对象，用来控制谷歌浏览器以无界面模式打开
    chrome_options = Options()
    # chrome_options.add_argument('--headless')
    # chrome_options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(options=chrome_options)

    # 设置浏览器宽高
    driver.set_window_size(width=2000, height=3000)

    wait = WebDriverWait(driver, 10)

    try_crack(driver, wait, False)


# 通过轮廓识别凹槽
def get_pos(image):
    blurred = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    # blurred = cv.GaussianBlur(image, (5, 5), 0)
    canny = cv.Canny(blurred, 50, 150)
    # cv.imshow('blurr', canny)
    # cv.waitKey(0)
    contours, hierarchy = cv.findContours(canny, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
    max, poss = 0, []
    for i, contour in enumerate(contours):
        x, y, w, h = cv.boundingRect(contour)  # 外接矩形
        # print("x-->" + str(x))
        # print("width-->" + str(w))
        # print("height-->" + str(h))
        if (55 < w < 68 or 50 < h < 63) and 120 < x:
            # cv.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 2)
            # cv.imshow('image', image)
            # cv.waitKey(0)
            # pass
            print("x-->" + str(x))
            x = x - 8
            max = max if max > x else x
            poss.append(x)
    print("get pos :")
    print(poss)
    return max, poss


if __name__ == '__main__':
    # img0 = cv.imread("./img_slider.png")
    # img1 = cv.imread("./img_bg.png")
    # get_pos(img1)

    # value_2 = template_match(img1, img0)
    main()
    # for i in range(10):
    #     t = threading.Thread(target=main)
    #     t.start()

