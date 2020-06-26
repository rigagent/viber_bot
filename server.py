#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import config
import json
import logging
import pymysql
from datetime import datetime
from flask import Flask, request, Response
from random import randrange
from viberbot import Api
from viberbot.api.bot_configuration import BotConfiguration
from viberbot.api.viber_requests import ViberConversationStartedRequest
from viberbot.api.viber_requests import ViberMessageRequest
from viberbot.api.messages import (
    TextMessage
)

app = Flask(__name__)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

viber = Api(BotConfiguration(
    name=config.BOT_NAME, avatar='', auth_token=config.BOT_TOKEN
))


def store_in_db(user_id, user_name, code, timestamp):
    timestamp //= 1000
    time = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    db = pymysql.connect(config.DB_HOST,
                         config.DB_USER,
                         config.DB_PASSWORD,
                         config.DB_NAME)
    cursor = db.cursor()
    sql = "INSERT INTO {} (user_id, user_name, code, time) VALUES ('{}', '{}', {}, '{}');".format(
        config.TABLE_NAME, user_id, user_name, code, time)
    try:
        cursor.execute(sql)
        db.commit()
    except:
        db.rollback()
    db.close()


def user_id_list():
    results_list = []
    db = pymysql.connect(config.DB_HOST,
                         config.DB_USER,
                         config.DB_PASSWORD,
                         config.DB_NAME)
    cursor = db.cursor()
    sql = "SELECT user_id FROM users;"
    cursor.execute(sql)
    results = cursor.fetchall()
    db.close()

    for result in results:
        results_list.append(result[0])

    return results_list


def get_user_last_session(user_id):
    db = pymysql.connect(config.DB_HOST,
                         config.DB_USER,
                         config.DB_PASSWORD,
                         config.DB_NAME)
    cursor = db.cursor()
    sql = "SELECT MAX(time) FROM users WHERE user_id = '{}';".format(user_id)
    cursor.execute(sql)
    result = cursor.fetchall()
    db.close()
    return result[0][0]


def get_time_from_last_session(user_id):
    current_time = datetime.now()
    user_last_session = get_user_last_session(user_id)
    if not user_last_session:
        return None
    else:
        user_last_session_time = datetime.strptime(str(user_last_session), '%Y-%m-%d %H:%M:%S')
        time_delta = current_time - user_last_session_time
        return time_delta.seconds // 60


@app.route('/', methods=['POST'])
def incoming():
    logger.debug("received request. post data: {0}".format(request.get_data()))
    if not viber.verify_signature(request.get_data(), request.headers.get('X-Viber-Content-Signature')):
        return Response(status=403)

    viber_request = viber.parse_request(request.get_data())
    timestamp = json.loads(request.get_data().decode('UTF-8'))["timestamp"]
    code = randrange(99999, 1000000)
    messages = []
    keyboard = {
        "DefaultHeight": True,
        "BgColor": "#FFFFFF",
        "Type": "keyboard",
        "Buttons": [
            {
                "Columns": 6,
                "Rows": 1,
                "BgColor": "#7f3aba",
                "BgLoop": True,
                "ActionType": "reply",
                "ActionBody": "search_code",
                "ReplyType": "message",
                "Text": "<font color=\"#dee1f0\"><b>Получить код</b></font>"
            }
        ]
    }

    if isinstance(viber_request, ViberConversationStartedRequest):
        messages.append(TextMessage(text="Нажмите на кнопку 'Получить код'...", keyboard=keyboard))
        viber.send_messages(viber_request.user.id, messages)

    elif isinstance(viber_request, ViberMessageRequest):
        last_session = get_time_from_last_session(viber_request.sender.id)
        if last_session is not None:
            if last_session < 2:
                messages.append(TextMessage(text="Вашему пользователю уже был отправлен код...", keyboard=keyboard))
                viber.send_messages(viber_request.sender.id, messages)
            else:
                messages.append(TextMessage(text="Ваш код: {}".format(code), keyboard=keyboard))
                viber.send_messages(viber_request.sender.id, messages)
                store_in_db(viber_request.sender.id, viber_request.sender.name, code, timestamp)
        else:
            messages.append(TextMessage(text="Ваш код: {}".format(code), keyboard=keyboard))
            viber.send_messages(viber_request.sender.id, messages)
            store_in_db(viber_request.sender.id, viber_request.sender.name, code, timestamp)

    return Response(status=200)


if __name__ == "__main__":
    context = (config.SSL_FULLCHAIN_PATH,
               config.SSL_PRIV_KEY_PATH)
    app.run(host='0.0.0.0', port=443, debug=True, ssl_context=context)
