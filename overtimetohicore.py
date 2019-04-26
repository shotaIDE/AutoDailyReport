# coding: utf-8

import os
import sys
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.support.ui import Select


def wait_for_page_loaded():
    while not browser.find_elements_by_css_selector("frame"):
        time.sleep(1)


def switch_to_content_frame():
    frames = browser.find_elements_by_css_selector("frame")
    browser.switch_to.frame(frames[1])


def wait_for_select_reset():
    while True:
        selectBox = Select(browser.find_element_by_xpath('//select[@name="sinseiKbn"]'))
        if selectBox.first_selected_option.text == '----':
            break


def request_overtime(reason: str):
    current_datetime = datetime.now()
    current_date_str = current_datetime.strftime('%Y/%m/%d')
    OVERTIME_LIMIT = datetime(
        year=current_datetime.year,
        month=current_datetime.month,
        day=current_datetime.day,
        hour=22,
        minute=0,
        second=0
    )
    LATE_OVERTIME_LIMIT = datetime(
        year=current_datetime.year,
        month=current_datetime.month,
        day=current_datetime.day,
        hour=23,
        minute=30,
        second=0
    )
    exit_time_raw = datetime.now() + timedelta(minutes=15)
    exit_time = datetime(
        year=exit_time_raw.year,
        month=exit_time_raw.month,
        day=exit_time_raw.day,
        hour=exit_time_raw.hour,
        minute=(int(exit_time_raw.minute / 15) * 15),
        second=0
    )

    request_time_hour = exit_time.hour
    request_time_min = exit_time.minute

    late_request = False

    if exit_time > OVERTIME_LIMIT:
        request_time_hour = 22
        request_time_min = 0

        late_request = True
        if exit_time > LATE_OVERTIME_LIMIT:
            late_request_time_hour = 23
            late_request_time_min = 30
        else:
            late_request_time_hour = exit_time.hour
            late_request_time_min = exit_time.minute

    browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td[1]/div/table[2]/tbody/tr/td[1]/table[2]/tbody/tr[2]/td[2]/table/tbody/tr[1]/td[2]/a').click()

    wait_for_page_loaded()

    switch_to_content_frame()
    selectBox = Select(browser.find_element_by_xpath('//select[@name="sinseiKbn"]'))
    selectBox.select_by_value('03')
    time.sleep(1) # セレクトボックス選択後のUI変更イベントを待つ
    selectBox = Select(browser.find_element_by_xpath('//select[@name="kyukaCode"]'))
    selectBox.select_by_value('41,0,1,0') # 残業(〜22時マデ)

    browser.find_element_by_xpath('//input[@tabIndex="3"]').send_keys(current_date_str)
    browser.find_element_by_xpath('//input[@tabIndex="4"]').send_keys(current_date_str)
    browser.find_element_by_xpath('//input[@name="taikin"]').send_keys(f'{request_time_hour:02d}{request_time_min:02d}')
    browser.find_element_by_xpath('//input[@name="reason"]').send_keys(reason)
    browser.find_element_by_xpath('//input[@name="btnEntry1"]').click()

    if not late_request:
        return

    wait_for_select_reset()

    selectBox = Select(browser.find_element_by_xpath('//select[@name="sinseiKbn"]'))
    selectBox.select_by_value('03')
    time.sleep(1) # セレクトボックス選択後のUI変更イベントを待つ
    selectBox = Select(browser.find_element_by_xpath('//select[@name="kyukaCode"]'))
    selectBox.select_by_value('43,0,1,0') # 深夜残業(22~2330マデ)

    browser.find_element_by_xpath('//input[@tabIndex="3"]').send_keys(current_date_str)
    browser.find_element_by_xpath('//input[@tabIndex="4"]').send_keys(current_date_str)
    browser.find_element_by_xpath('//input[@name="taikin"]').send_keys(f'{late_request_time_hour:02d}{late_request_time_min:02d}')
    browser.find_element_by_xpath('//input[@name="reason"]').send_keys(reason)
    browser.find_element_by_xpath('//input[@name="btnEntry1"]').click()


if __name__ == '__main__':
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

    wait_for_page_loaded()

    switch_to_content_frame()
    browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td[1]/table[2]/tbody/tr[1]/td[2]/table/tbody/tr/td[1]/input').send_keys(LOGIN_ID)
    browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td[1]/table[2]/tbody/tr[2]/td[2]/table/tbody/tr/td[1]/input').send_keys(LOGIN_PASSWORD)
    browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td[3]/table/tbody/tr[2]/td/input').click()

    wait_for_page_loaded()

    switch_to_content_frame()

    request_overtime(reason=OVERTIME_REASON)

    browser.quit()
