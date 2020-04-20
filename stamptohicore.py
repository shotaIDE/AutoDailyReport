# coding: utf-8

import argparse
from time import sleep
from selenium import webdriver


def wait_for_page_loaded(browser):
    while not browser.find_elements_by_css_selector("frame"):
        sleep(1)


def switch_to_content_frame(browser):
    frames = browser.find_elements_by_css_selector("frame")
    browser.switch_to.frame(frames[1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', type=str)
    arguments = parser.parse_args()

    stamp_mode = arguments.mode
    allowed_mode_list = ['start', 'end']
    if stamp_mode not in allowed_mode_list:
        print(
            f'[ERROR] The mode argument must be one of {allowed_mode_list}')
        exit()

    HICORE_SETTINGS_PATH = 'hicore_settings.txt'

    with open(HICORE_SETTINGS_PATH, 'r', encoding='utf-8') as f:
        settings_raw = f.readlines()
    settings = [setting.replace('\n', '') for setting in settings_raw]
    LOGIN_URL = settings[0]
    LOGIN_ID = settings[1]
    LOGIN_PASSWORD = settings[2]
    OVERTIME_REASON = settings[3]

    browser = webdriver.Ie()

    browser.get(LOGIN_URL)

    wait_for_page_loaded(browser=browser)

    switch_to_content_frame(browser=browser)

    browser.find_element_by_name('userId').send_keys(LOGIN_ID)
    browser.find_element_by_name('password').send_keys(LOGIN_PASSWORD)
    browser.find_element_by_xpath('//input[@value="ログイン"]').click()

    wait_for_page_loaded(browser=browser)

    switch_to_content_frame(browser=browser)

    browser.find_element_by_link_text('出退勤打刻').click()

    wait_for_page_loaded(browser=browser)

    switch_to_content_frame(browser=browser)

    if stamp_mode == 'start':
        browser.find_element_by_xpath('//input[@value="出　勤"]').click()
    else:
        browser.find_element_by_xpath('//input[@value="退　勤"]').click()

    # ページ遷移なしのため、すぐにボタンをクリックする
    browser.find_element_by_xpath('//input[@value="登　録"]').click()

    browser.quit()


if __name__ == '__main__':
    main()
