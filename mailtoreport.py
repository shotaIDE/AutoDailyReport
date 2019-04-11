# coding: utf-8

import mailbox
import re
import webbrowser
from datetime import date, datetime
from email.header import decode_header
from typing import NoReturn, Optional
from urllib.parse import quote

RE_CATEGORY = re.compile(r"【(.*)】.*")
RE_TASK = re.compile(r"\[(.+)\]\[([0-9]+\.[0-9][0-9])h\] (.*)")
RE_TASK_SINGLE = re.compile(r"\[([0-9]+\.[0-9][0-9])h\] (.*)")
RE_TASK_TMP = re.compile(r"\[(.+)\]\[\] (.*)")
RE_TASK_TMP2 = re.compile(r"\[(.+)\] (.*)")

def parse_tasks_in_line(line: str, category: dict) -> None:
    matched = RE_CATEGORY.match(line)
    if matched:
        category_title = matched.groups()[0]
        category.append({
            'title': category_title,
            'tasks': [],
        })
        return

    matched = RE_TASK.match(line)
    if matched:
        category[-1]['tasks'].append({
            'progress': matched.groups()[0],
            'length': float(matched.groups()[1]),
            'title': matched.groups()[2],
            'sub_tasks': [],
        })
        return

    matched = RE_TASK_SINGLE.match(line)
    if matched:
        category[-1]['tasks'].append({
            'length': float(matched.groups()[0]),
            'title': matched.groups()[1],
            'sub_tasks': [],
        })
        return

    matched = RE_TASK_TMP.match(line)
    if matched:
        category[-1]['tasks'].append({
            'progress': matched.groups()[0],
            'title': matched.groups()[1],
            'sub_tasks': [],
        })
        return

    matched = RE_TASK_TMP2.match(line)
    if matched:
        category[-1]['tasks'].append({
            'progress': matched.groups()[0],
            'title': matched.groups()[1],
            'sub_tasks': [],
        })
        return

    if line.startswith('・'):
        category[-1]['tasks'][-1]['sub_tasks'].append(line[1:])
        return

class DailyReportMailBox():
    def __init__(self, mbox_path: str) -> NoReturn:
        self.mbox_list = mailbox.mbox(mbox_path)

    def get_daily_report(self, target_date: Optional[date] = None) -> Optional[dict]:
        contents_str = self._get_daily_report_str(target_date=target_date)

        contents_list = contents_str.splitlines()
        contents = {
            'today': [],
            'tomorrow': [],
            'future': []
        }
        part = 0
        field_iter = ''

        for line in contents_list:
            line = str.strip(line.replace('\n', ''))

            if line == '':
                continue

            if line.startswith('='):
                part += 1
                if part == 2:
                    field_iter = 'today'
                elif part == 4:
                    field_iter = 'tomorrow'
                elif part == 6:
                    field_iter = 'future'
                else:
                    field_iter = ''
                continue

            if field_iter == '':
                continue

            parse_tasks_in_line(line, contents[field_iter])

        return contents

    def _get_daily_report_str(self, target_date: date) -> Optional[str]:
        contents_str = None

        raw_daily_report = self._get_raw_daily_report(target_date=target_date)

        if raw_daily_report is None:
            return

        for part in raw_daily_report.walk():
            if part.get_content_type() != 'text/plain':
                continue

            charset = part.get_content_charset()
            if charset:
                contents_str = part.get_payload(decode=True).decode(charset, 'ignore')

        if contents_str is None:
            return

        return contents_str

    def _get_raw_daily_report(self, target_date: date):
        target_key = None
        target_message = None
        for key in reversed(self.mbox_list.keys()):
            message = self.mbox_list.get(key)

            subject = ''
            for subject_b, encode in decode_header(message['Subject']):
                if encode == None:
                    subject += subject_b.decode('ascii', 'ignore')
                    continue
                subject += subject_b.decode(encode, 'ignore')

            send_datetime = datetime.strptime(subject[4:14], '%Y-%m-%d').date()

            if target_date is None or send_datetime == target_date:
                target_key = key
                target_message = message
                break

        if target_key is None:
            return

        return target_message

def main():
    SETTINGS_PATH = 'mail_settings.txt'

    settings_raw = open(SETTINGS_PATH, 'r', encoding='utf-8').readlines()
    settings = [setting.replace('\n', '') for setting in settings_raw]
    MAILBOX_PATH = settings[0]
    MAIL_TO = settings[1]
    NAME_IN_MAIL_SUBJECT = settings[2]

    line_iter = 3
    max_lines = len(settings)
    if settings[line_iter] != '===MailHeaderStart===':
        raise Exception

    line_iter += 1
    mail_body_header = ''
    while line_iter < max_lines and settings[line_iter] != '===MailHeaderEnd===':
        mail_body_header += settings[line_iter] + '\n'
        line_iter += 1

    daily_report = DailyReportMailBox(MAILBOX_PATH)

    generate_date = datetime.now().date()
    contents = daily_report.get_daily_report()
    contents['today'] = []

    if contents is None:
        exit()

    with open('today_tasks.txt', 'r', encoding='utf-8') as f:
        today_task_list = f.readlines()

    for line in today_task_list:
        line = str.strip(line.replace('\n', ''))

        if line == '':
            continue

        parse_tasks_in_line(line, contents['today'])

    mail_recipients = MAIL_TO

    mail_subject = f'[日報]{generate_date.strftime("%Y-%m-%d")}:{NAME_IN_MAIL_SUBJECT}'

    mail_body = mail_body_header

    month = generate_date.strftime('%m')
    day = generate_date.strftime('%d')
    wday_iter = int(generate_date.strftime('%w'))
    WDAY_STR_LIST = ['日', '月', '火', '水', '木', '金', '土']
    wday_str = WDAY_STR_LIST[wday_iter]
    mail_body += f'{month}月{day}日({wday_str})\n\n'

    mail_body += '''========================
    今日の作業
    ======================== 
    '''

    for category in contents['today']:
        mail_body += f'【{category["title"]}】\n'

        for task in category['tasks']:
            if 'progress' in task and task['progress'] != '':
                mail_body += f'[{task["progress"]}]'
            if 'length' in task:
                mail_body += f'[{task["length"]:.2f}h]'
            mail_body += f' {task["title"]:}\n'

            for sub_task in task['sub_tasks']:
                mail_body += f'・{sub_task}\n'

        mail_body += '\n'

    mail_body += '''========================
    翌営業日の作業
    ======================== 
    '''

    for id, category in enumerate(contents['today']):
        tasks = [x for x in category['tasks'] if 'progress' in x]

        if len(tasks) == 0:
            del contents['today'][id]
            continue

        category = {
            'title': category['title'],
            'tasks': tasks,
        }

    for category in contents['today']:
        mail_body += f'【{category["title"]}】\n'

        for task in category['tasks']:
            if 'progress' in task and task['progress'] != '':
                mail_body += f'[{task["progress"]}]'
            mail_body += f' {task["title"]}\n'

            for sub_task in task['sub_tasks']:
                mail_body += f'・{sub_task}\n'

        mail_body += '\n'

    mail_body += '''========================
    タスク
    ======================== 
    '''

    for category in contents['future']:
        mail_body += f'【{category["title"]}】\n'

        for task in category['tasks']:
            if 'progress' in task and task['progress'] != '':
                mail_body += f'[{task["progress"]}]'
            mail_body += f' {task["title"]}\n'

            for sub_task in task['sub_tasks']:
                mail_body += f'・{sub_task}\n'

        mail_body += '\n'

    scheme = 'mailto:{:}?subject={:}&body={:}'.format(
        quote(mail_recipients),
        quote(mail_subject),
        quote(mail_body)
    )
    webbrowser.open(scheme)

if __name__ == '__main__':
    main()
