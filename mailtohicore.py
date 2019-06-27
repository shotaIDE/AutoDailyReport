# coding: utf-8

import copy
import json
import os
import time
import webbrowser
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException

from mailtoreport import DailyReportMailBox

MAIL_SETTINGS_PATH = 'mail_settings.txt'
HICORE_SETTINGS_PATH = 'hicore_settings.txt'
DICTIONARY_PATH = 'dictionary.json'

wday_jp_list = {
    '月': 0,
    '火': 1,
    '水': 2,
    '木': 3,
    '金': 4,
    '土': 5,
    '日': 6,
}

with open(MAIL_SETTINGS_PATH, 'r', encoding='utf-8') as f:
    settings_raw = f.readlines()
settings = [setting.replace('\n', '') for setting in settings_raw]
MAILBOX_PATH = settings[0]
MAIL_TO = settings[1]
NAME_IN_MAIL_SUBJECT = settings[2]

with open(HICORE_SETTINGS_PATH, 'r', encoding='utf-8') as f:
    settings_raw = f.readlines()
settings = [setting.replace('\n', '') for setting in settings_raw]
LOGIN_URL = settings[0]
LOGIN_ID = settings[1]
LOGIN_PASSWORD = settings[2]

with open(DICTIONARY_PATH, 'r', encoding='utf-8') as f:
    dictionary = json.load(f)


def wait_for_page_loaded():
    while not browser.find_elements_by_css_selector('frame'):
        time.sleep(1)


def switch_to_content_frame():
    frames = browser.find_elements_by_css_selector('frame')
    browser.switch_to.frame(frames[1])


daily_report = DailyReportMailBox(MAILBOX_PATH)

browser = webdriver.Ie()

browser.get(LOGIN_URL)

wait_for_page_loaded()

switch_to_content_frame()
browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td[1]/table[2]/tbody/tr[1]/td[2]/table/tbody/tr/td[1]/input').send_keys(LOGIN_ID)
browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td[1]/table[2]/tbody/tr[2]/td[2]/table/tbody/tr/td[1]/input').send_keys(LOGIN_PASSWORD)
browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td[3]/table/tbody/tr[2]/td/input').click()

wait_for_page_loaded()

switch_to_content_frame()

browser.find_element_by_xpath('/html/body/form/table/tbody/tr/td/div/table/tbody/tr/td/table/tbody/tr/td[2]/table/tbody/tr[3]/td[2]/a').click()

wait_for_page_loaded()

switch_to_content_frame()

browser.find_element_by_xpath('/html/body/form/div/table/tbody/tr[2]/td/table/tbody/tr/td[8]/a').click()

while str(input('Please go to page you want to input...[Y/n]')).lower() == 'y':

    # FIXME: 押せなかった場合

    start_day = int(browser.find_element_by_xpath('/html/body/form/table/tbody/tr[3]/td/table/tbody/tr[2]/td[4]').text)
    start_wday_jp = browser.find_element_by_xpath('/html/body/form/table/tbody/tr[3]/td/table/tbody/tr[3]/td').text

    start_wday = wday_jp_list[start_wday_jp]

    start_date = datetime.now().date()
    while start_date.day != start_day:
        start_date -= timedelta(days=1)

    print(f'Beginning date: {start_date} (wday={start_wday})')

    hicore_works = {}
    for item in dictionary:
        project = item['hicore']['project']
        process = item['hicore']['process']
        if project not in hicore_works:
            hicore_works[project] = {}
        if process not in hicore_works[project]:
            hicore_works[project][process] = {
                'length': 0.0,
            }

    input_table_rows = browser.find_elements_by_xpath('/html/body/form/table[2]/tbody/tr[3]/td/table/tbody/tr')
    input_rows = input_table_rows[3:-3]

    work_inputs = []
    for input_row in input_rows:
        project = input_row.find_element_by_xpath('./td[2]').text

        try:
            process_select = Select(input_row.find_element_by_xpath('./td[3]/select'))
            process = process_select.first_selected_option.text
        except NoSuchElementException:
            process_text = input_row.find_element_by_xpath('./td[3]')
            process = process_text.text

        work_inputs.append({
            'project': project,
            'process': process,
        })
        print(f'Found hi-core row: {project} / {process}')

    for wday_iter in range(7):
        target_date = start_date + timedelta(days=wday_iter)

        works_to_input = copy.deepcopy(hicore_works)
        num_inputs = 0
        for (work, input_row) in zip(work_inputs, input_rows):
            project = work['project']
            process = work['process']

            try:
                length_input = input_row.find_element_by_xpath(f'./td[{4 + wday_iter}]/input[@type="text"]')
            except:
                print( f'[INFO] Ignored for no input: {project} / {process}' )
                continue
            num_inputs += 1

            try:
                works_to_input[project][process]['input'] = length_input
            except:
                print( f'[INFO] Ignored for not in dictionary: {project} / {process}' )
                continue

            print(f'Stored input: {project} / {process}')

        if num_inputs == 0:
            # 入力完了・必要なし
            print(f'Not need to input at #{target_date}')
            continue

        sum_work_actual = float(input_table_rows[-1].find_element_by_xpath(f'./td[{2 + wday_iter}]').text)

        work_raw = daily_report.get_daily_report(target_date=target_date)
        if work_raw is None:
            print(f'[INFO] Ignored for no daily report at #{target_date}')
            continue

        work_actual = work_raw['today']

        for category in work_actual:
            section = category['title']
            for task in category['tasks']:
                title = task['title']
                length = task['length']

                for date_task in dictionary:
                    if date_task['daily_report']['section'] != section:
                        continue
                    # FIXME: メールのタイトルが切れてしまうことがあるので、前方一致で
                    if not date_task['daily_report']['title'].startswith(title):
                        continue

                    project = date_task['hicore']['project']
                    process = date_task['hicore']['process']

                    if 'length' not in works_to_input[project][process]:
                        works_to_input[project][process]['length'] = 0.0
                    works_to_input[project][process]['length'] += length

        sum_work_reported = 0.0
        max_length = 0.0
        project_of_max = None
        process_of_max = None
        for project, processes in works_to_input.items():
            for process, work in processes.items():
                length = work['length']
                sum_work_reported += length
                if length > max_length:
                    max_length = length
                    project_of_max = project
                    process_of_max = process

        if sum_work_reported != sum_work_actual:
            # 帳尻合わせ
            excess = sum_work_reported - sum_work_actual
            works_to_input[project_of_max][process_of_max]['length'] -= excess

        required_forms = []
        for project, processes in works_to_input.items():
            for process, work in processes.items():
                length = work['length']
                if length == 0.0:
                    continue

                if 'input' not in work:
                    required_forms.append(f'{project} / {process}')
                    continue
                length_input = work['input']
                length_input.clear()
                input_word = f'{length}'
                length_input.send_keys(input_word)

        if len(required_forms) > 0:
            for required_form in required_forms:
                print(f'[ERROR] Please make a from: {required_form}')
            break

# TODO: 申請
