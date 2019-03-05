# coding: utf-8

import json
import mailbox
import re
import webbrowser
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from urllib.parse import quote

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

mbox_desc = mailbox.mbox(MAILBOX_PATH)

RE_CATEGORY = re.compile(r"【(.*)】.*")
RE_TASK = re.compile(r"\[(.+)\]\[([0-9]+\.[0-9][0-9])h\] (.*)")
RE_TASK_SINGLE = re.compile(r"\[([0-9]+\.[0-9][0-9])h\] (.*)")
RE_TASK_TMP = re.compile(r"\[(.+)\]\[\] (.*)")
RE_TASK_TMP2 = re.compile(r"\[(.+)\] (.*)")

target_key = None
target_message = None
target_date = datetime(1990, 1, 1)
generate_date = datetime.now()

for key in reversed(mbox_desc.keys()):
    message = mbox_desc.get(key)

    subject = ''
    for subject_b, encode in decode_header(message['Subject']):
        if encode == None:
            subject += subject_b.decode('ascii', 'ignore')
            continue
        subject += subject_b.decode(encode, 'ignore')

    send_datetime = datetime.strptime(subject[4:14], '%Y-%m-%d')

    if (send_datetime > target_date):
        target_date = send_datetime
        target_key = key
        target_message = message
        break

print(f'found yesterday report! ...#{key}: {subject}')

if target_key is None:
    exit()

contents_str = None

for part in message.walk():
    if part.get_content_type() != 'text/plain':
        continue

    charset = part.get_content_charset()
    if charset:
        contents_str = part.get_payload(decode=True).decode(charset, 'ignore')

if contents_str == None:
    exit()

contents_list = contents_str.splitlines()
contents = {
    'today': [],
    'tomorrow': [],
    'future': []
}
part = 0
field_iter = ''

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

    if field_iter != 'future':
        continue

    parse_tasks_in_line(line, contents[field_iter])

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
