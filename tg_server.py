import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
import traceback
from telegram.ext import CallbackQueryHandler, PicklePersistence, Updater, CommandHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ParseMode, ReplyKeyboardRemove
from time import sleep
import random
import string
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import os
import signal
import queue
import schedule
from json import load, dump
import phonenumbers
from sys import exit
import os
import pymongo


s3_queue = queue.Queue()
data_queue = queue.Queue()
upload_queue = queue.Queue()
moderation_queue = queue.Queue()
s3_client = boto3.client('s3')
confirmation_numbers = set(range(100, 1000000))
MODERATION_PASSWORD = "issueadmin54321"
ALLOWED_UIDS = ["106052", "979206581"]
moderators = set()
mgclient = pymongo.MongoClient("mongodb+srv://admin:qwep-]123p=]@cluster0.sax3u.mongodb.net/Cluster0?retryWrites=true&w=majority")


with open("job_data.json", "r+", encoding="utf-8") as f:
    s = load(f)
    if "s3_queue" not in s:
        s["s3_queue"] = []
    if "data_queue" not in s:
        s["data_queue"] = []
    if "upload_queue" not in s:
        s["upload_queue"] = []
    if "moderation_queue" not in s:
        s["moderation_queue"] = []
    s3_queue.queue = queue.deque(s["s3_queue"])
    data_queue.queue = queue.deque(s["data_queue"])
    upload_queue.queue = queue.deque(s["upload_queue"])
    moderation_queue.queue = queue.deque(s["moderation_queue"])


LOADED_DUMP = False
JOBS_ALLOWED = True
GSPREAD_EMAIL = "visior-bot@active-area-251510.iam.gserviceaccount.com"
gc = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', ['https://spreadsheets.google.com/feeds']))
admin_gspread_link = "https://docs.google.com/spreadsheets/d/112_xEVXHth_px0yVQOuH4-c3d1uOnD7t_VbALDczpLY/"
sh = gc.open_by_url(admin_gspread_link)
name = "ISSUES_DATA"
try:
    data_worksheet = sh.worksheet(name)
except Exception as e:
    sh.add_worksheet(title=name, rows="5", cols="20")
    data_worksheet = sh.worksheet(name)
    data_worksheet.insert_row(["ID", "Дата подачи", "Долгота", "Широта", "Описание", "Картинка"], 1)


def get_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Отправить отчёт")]
    ])


def push_s3_job():
    print("gotta push s3")
    while not s3_queue.empty():
        print("getting...")
        file_name = s3_queue.get()
        print(file_name)
        try:
            response = s3_client.upload_file(file_name, "statpad-logs", file_name, ExtraArgs={'ACL':'public-read'})
            os.remove(file_name)
            print("success", file_name)
        except ClientError as e:
            print(e)
            print("nope, pushing again", file_name)
            s3_queue.put(file_name)
    print("done, s3 empty")


def push_data_job():
    print("gotta push data")
    while JOBS_ALLOWED and not data_queue.empty():
        row = data_queue.get()
        print("got", row)
        try:
            data_worksheet.insert_row(row, 2)
            print("success")
        except Exception as e:
            print(e)
            print("failed, pushing back", row)
            data_queue.put(row)
    print("done, data empty")


def push_upload_job():
    print("gotta push upload")
    while JOBS_ALLOWED and not upload_queue.empty():
        row = upload_queue.get()
        el, dtime, longitude, latitude, description, filename = row
        try:
            mgclient.issues_data.issues.insert_one({
                "issue_id": el,
                "created_at": dtime,
                "longitude": longitude,
                "latitude": latitude,
                "description": description,
                "photo_link": filename
            })
            print("success")
        except Exception as e:
            print(e)
            print("failed, pushing back", row)
            upload_queue.put(row)
    print("done, upload empty")


def start(update, context):
    global LOADED_DUMP
    if not LOADED_DUMP:
        with open("bot_data.json", "r+", encoding="utf-8") as f:
            s = load(f)
            for i in s:
                context.bot_data[i] = s[i]
            LOADED_DUMP = True
    uid = str(update.message.chat_id)
    print("UID: ___ ", uid)
    if uid not in context.bot_data:
        context.bot_data[uid] = {}
    context.bot_data[uid]["status"] = "ready"
    update.message.reply_text("Приветствую вас, жители Дагестана. Я - бот. С помощью меня вы сможете зафиксировать городскую проблему, и я со своей командой сделаю всё, чтобы ваша проблема решилась. Начинаем?", reply_markup=get_menu())


def texter(update, context):
    global LOADED_DUMP, phrases
    if not LOADED_DUMP:
        with open("bot_data.json", "r+", encoding="utf-8") as f:
            s = load(f)
            for i in s:
                context.bot_data[i] = s[i]
            LOADED_DUMP = True
    uid = str(update.message.chat_id)
    if uid not in context.bot_data:
        context.bot_data[uid] = {}
        context.bot_data[uid]["status"] = "ready"
        update.message.reply_text("Привет!", reply_markup=get_menu())
        return
    status = context.bot_data[uid]["status"]
    print(status)
    if status == "ready":
        text = update.message.text
        if text == "Отправить отчёт":
            update.message.reply_text('Прикрепите геолокацию / место, где находится ваша проблема. (или прикрепите геолокацию вложением)', reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton('Отправить', request_location=True)]
            ]), one_time_keyboard=True)
        context.bot_data[uid]["status"] = "place"
    elif status == "place":
        location = update.message.location
        if location:
            context.bot_data[uid]["longitude"] = location.longitude
            context.bot_data[uid]["latitude"] = location.latitude
            context.bot_data[uid]["status"] = "description"
            update.message.reply_text('Опишите найденную проблему.', reply_markup=ReplyKeyboard())
        else:
            update.message.reply_text('Прикрепите геолокацию / место, где находится ваша проблема. (или прикрепите геолокацию вложением)', reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton('Отправить', request_location=True)]
            ]), one_time_keyboard=True)
    elif status == "description":
        context.bot_data["description"] = update.message.text
        context.bot_data[uid]["status"] = "photo"
        update.message.reply_text('Прикрепите фото с проблемой.')
    elif status == "photo":
        try:
            photo = update.message.photo[-1]
            if photo:
                print(1)
                el = random.sample(confirmation_numbers, 1)[0]
                confirmation_numbers.remove(el)
                filename = f"{uid}-{el}-{photo.file_id}.jpg"
                photo.get_file().download(filename)
                moderation_queue.put([el, ''.join(str(datetime.now()).split(":")[::-1]), context.bot_data[uid]["longitude"], context.bot_data[uid]["latitude"], context.bot_data["description"], filename])
                update.message.reply_text(f'Отлично.\n Спасибо, что хотите сделать наш город лучше.\n Свою проблему вы сможете увидеть по ссылке: issuemaap.herokuapp.com \nНа основе вашего обращения наша команда сформирует официальное обращение к городским властям.')
        except Exception as e:
            print(e)
            pass
    elif status == "moderation_password":
        text = update.message.text
        if text == MODERATION_PASSWORD:
            moderators.add(uid)
            update.message.reply_text(f'Вы успешно добавлены в список модераторов')
            if not moderation_queue.empty():
                context.bot_data[uid]["status"] = "moderation_processing"
                current_moderation_issue = moderation_queue.get()
                context.bot_data[uid]["current_moderation_issue"] = current_moderation_issue
                el, dtime, longitude, latitude, description, filename = current_moderation_issue
                update.message.reply_location(latitude=latitude, longitude=longitude)
                update.message.reply_photo(photo=open(filename, "rb"), caption=f"ID: {el}\nДата отправки: {dtime}\nОписание: {description}",
                                           reply_markup=ReplyKeyboardMarkup([
                                               [KeyboardButton('✅'), KeyboardButton('❌')],
                                               [KeyboardButton('🏠')]
                                           ]), one_time_keyboard=True)
            else:
                context.bot_data[uid]["current_moderation_issue"] = []
                context.bot_data[uid]["status"] = "ready"
                update.message.reply_text('Пока заявок нет💁', reply_markup=get_menu())
        else:
            update.message.reply_text(f'Неверный пароль, попробуйте ещё раз')
    elif status == "moderation_processing":
        text = update.message.text
        if text == "🏠":
            if context.bot_data[uid]["current_moderation_issue"]:
                moderation_queue.put(context.bot_data[uid]["current_moderation_issue"])
                context.bot_data[uid]["current_moderation_issue"] = []
            context.bot_data[uid]["status"] = "ready"
            update.message.reply_text('🏠', reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton('Отправить', request_location=True)]
            ]), one_time_keyboard=True)
        if context.bot_data[uid]["current_moderation_issue"]:
            if text in ['✅', '❌']:
                if text == '✅':
                    s3_queue.put(context.bot_data[uid]["current_moderation_issue"][-1])
                    context.bot_data[uid]["current_moderation_issue"][-1] = f'https://statpad-logs.s3.amazonaws.com/{context.bot_data[uid]["current_moderation_issue"][-1]}'
                    data_queue.put(context.bot_data[uid]["current_moderation_issue"])
                    upload_queue.put(context.bot_data[uid]["current_moderation_issue"])
                if not moderation_queue.empty():
                    context.bot_data[uid]["status"] = "moderation_processing"
                    current_moderation_issue = moderation_queue.get()
                    context.bot_data[uid]["current_moderation_issue"] = current_moderation_issue
                    el, dtime, longitude, latitude, description, filename = current_moderation_issue
                    update.message.reply_location(latitude=latitude, longitude=longitude)
                    update.message.reply_photo(photo=open(filename, "rb"), caption=f"ID: {el}\nДата отправки: {dtime}\nОписание: {description}",
                                               reply_markup=ReplyKeyboardMarkup([
                                                   [KeyboardButton('✅'), KeyboardButton('❌')],
                                                   [KeyboardButton('🏠')]
                                               ]), one_time_keyboard=True)
                else:
                    context.bot_data[uid]["current_moderation_issue"] = []
                    context.bot_data[uid]["status"] = "ready"
                    update.message.reply_text('Пока заявок нет💁', reply_markup=get_menu())


def moderation(update, context):
    global LOADED_DUMP, phrases
    if not LOADED_DUMP:
        with open("bot_data.json", "r+", encoding="utf-8") as f:
            s = load(f)
            for i in s:
                context.bot_data[i] = s[i]
            LOADED_DUMP = True
    uid = str(update.message.chat_id)
    if uid not in context.bot_data:
        context.bot_data[uid] = {}
        context.bot_data[uid]["status"] = "ready"
    if uid not in moderators:
        update.message.reply_text('Введите пароль модератора:')
        context.bot_data[uid]["status"] = "moderation_password"
    else:
        if not moderation_queue.empty():
            context.bot_data[uid]["status"] = "moderation_processing"
            current_moderation_issue = moderation_queue.get()
            context.bot_data[uid]["current_moderation_issue"] = current_moderation_issue
            el, dtime, longitude, latitude, description, filename = current_moderation_issue
            update.message.reply_location(latitude=latitude, longitude=longitude)
            update.message.reply_photo(photo=open(filename, "rb"), caption=f"ID: {el}\nДата отправки: {dtime}\nОписание: {description}",
                                        reply_markup=ReplyKeyboardMarkup([
                                            [KeyboardButton('✅'), KeyboardButton('❌')],
                                            [KeyboardButton('🏠')]
                                        ]), one_time_keyboard=True)
        else:
            context.bot_data[uid]["current_moderation_issue"] = []
            context.bot_data[uid]["status"] = "ready"
            update.message.reply_text('Пока заявок нет💁', reply_markup=get_menu())


def stop(update, context):
    print(str(update.message.chat_id))
    if str(update.message.chat_id):
        os.kill(os.getpid(), signal.SIGINT)
        exit()


def save_data(update, context):
    global phrases
    print(update.message.chat_id)
    if str(update.message.chat_id) in ALLOWED_UIDS:
        with open("bot_data.json", "w+", encoding="utf-8") as f:
            dump(context.bot_data, f, ensure_ascii=False, indent=4)
            update.message.reply_text('Данные успешно сохранены')
    else:
        update.message.reply_text('Вы - не администратор')


def save_jobs(update, context):
    global JOBS_ALLOWED, phrases
    print(str(update.message.chat_id))
    if str(update.message.chat_id) in ALLOWED_UIDS:
        attempts = 0
        JOBS_ALLOWED = False
        if attempts == 4:
            update.message.reply_text('Не удалось сохранить очереди')
        else:
            with open("job_data.json", "w+", encoding="utf-8") as f:
                s = dict()
                s["s3_queue"] = list(s3_queue.queue)
                s["data_queue"] = list(data_queue.queue)
                s["upload_queue"] = list(upload_queue.queue)
                dump(s, f, ensure_ascii=False, indent=4)
        update.message.reply_text('Очереди сохранены')
    else:
        update.message.reply_text('Вы - не администратор')


def stop_updaters(update, context):
    global JOBS_ALLOWED, phrases
    if str(update.message.chat_id) in ALLOWED_UIDS:
        JOBS_ALLOWED = False
        update.message.reply_text('Загрузки приостановлены')
    else:
        update.message.reply_text('Вы - не администратор')


def resume_updaters(update, context):
    global JOBS_ALLOWED, phrases
    if str(update.message.chat_id) in ALLOWED_UIDS:
        JOBS_ALLOWED = False
        update.message.reply_text('Загрузки возобновлены')
    else:
        update.message.reply_text('Вы - не администратор')


def main():
    updater = Updater("1405089416:AAGaIYPG_43Jy3AoWGVmulsAYjCGIh_l1pY", use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("shutdown", stop))
    dp.add_handler(CommandHandler("save_data", save_data))
    dp.add_handler(CommandHandler("save_jobs", save_jobs))
    dp.add_handler(CommandHandler("stop_updaters", stop_updaters))
    dp.add_handler(CommandHandler("resume_updaters", resume_updaters))
    dp.add_handler(CommandHandler("moderation", moderation))
    dp.add_handler(MessageHandler(Filters.all, texter))
    updater.start_polling()
    schedule.every().minute.do(push_s3_job)
    schedule.every().minute.do(push_data_job)
    schedule.every().minute.do(push_upload_job)
    while True:
        try:
            print(datetime.now())
            for i in schedule.jobs:
                try:
                    if i.should_run and JOBS_ALLOWED:
                        i.run()
                except Exception as e:
                    traceback.print_exc()
            sleep(5)
        except Exception as e:
            print(e)


if __name__ == '__main__':
    main()
