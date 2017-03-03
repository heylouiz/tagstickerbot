#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
A Telegram bot that tag your favorite stickers.
"""
from __future__ import division, absolute_import, print_function, unicode_literals

import json
import logging
import sqlite3
from uuid import uuid4

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineQueryResultCachedSticker
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler,
                          ConversationHandler, InlineQueryHandler)
from telegram.ext.dispatcher import run_async

# Load config file
with open('config.json') as config_file:
    CONFIGURATION = json.load(config_file)

# The database object
conn = None  # pylint: disable=invalid-name

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

STICKER, TAGGING, UPDATE, CONFIRM_UPDATE, CONFIRM_TAG = range(5)

def start(bot, update):  # pylint: disable=unused-argument
    """Handler for the /start command"""
    update.message.reply_text("Hi! I'm a bot that can help you find and send your "
                              "favorite stickers using custom tags. "
                              "Send me a sticker to start!")
    return STICKER

def get_sticker(bot, update, user_data):  # pylint: disable=unused-argument
    """ Handler for a sticker message.

        Stores the sticker file id in the user_data to be tagged in the next state.
    """
    user_data['sticker'] = {'file_id': None, 'emoji': None}
    user_data['sticker']['file_id'] = update.message.sticker.file_id
    user_data['sticker']['emoji'] = update.message.sticker.emoji

    # Check if the user has already tagged this sticker
    cursor = conn.cursor()
    cursor.execute("SELECT USER_STICKER.rowid, * "
                   "FROM USER_STICKER, USER, STICKER "
                   "WHERE USER_STICKER.user_rowid = USER.rowid "
                   "AND USER_STICKER.sticker_rowid = STICKER.rowid "
                   "AND USER.id=? AND STICKER.file_id=?",
                   (str(update.message.from_user.id),
                    user_data['sticker']['file_id']))
    query = cursor.fetchone()
    if query:
        update.message.reply_text("You have already tagged this sticker, "
                                  "want to edit the tags or remove it?",
                                  reply_markup=ReplyKeyboardMarkup([["Edit", "Cancel", "Remove"]],
                                                                   one_time_keyboard=True))
        user_data["modify"] = True
        user_data["modify_id"] = query["rowid"] # This is the USER_STICKER.rowid
        return CONFIRM_UPDATE
    else:
        user_data["modify"] = False
        user_data["modify_id"] = None
        update.message.reply_text("Cool, now send me words to tag your sticker.\n"
                                  "You can use more tags, just send them separated by commas (,)\n"
                                  "Example: dank, meme")
        return TAGGING


def confirm_update(bot, update, user_data):
    """Handler for a message that begins with Edit, Cancel or Remove.
       Confirm what the user want to do when an already tagged sticker was sent.
    """
    if update.message.text == "Edit":
        update.message.reply_text("Cool, send me the new tags to your sticker",
                                  reply_markup=ReplyKeyboardRemove())
        return TAGGING
    elif update.message.text == "Cancel":
        return cancel(bot, update, user_data)
    elif update.message.text == "Remove":
        return remove_sticker(bot, update, user_data)

def tag_sticker(bot, update, user_data):  # pylint: disable=unused-argument
    """Handler for a text message with the user tags.
       Store tags in the user data.
    """
    user_data['tags'] = update.message.text
    update.message.reply_text("You wanna tag your sticker with the following words:\n"
                              "<b>{}</b>\n".format(user_data["tags"]) + "Is that right?",
                              parse_mode="HTML",
                              reply_markup=ReplyKeyboardMarkup([["Yes", "No"]],
                                                               one_time_keyboard=True))
    return CONFIRM_TAG

def remove_sticker(bot, update, user_data):  # pylint: disable=unused-argument
    """Removes a sticker from the database"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM USER_STICKER WHERE rowid=?",
                   (user_data["modify_id"],))
    cursor.execute("DELETE FROM STICKER_TAG WHERE user_sticker_rowid=?",
                   (user_data["modify_id"],))
    conn.commit()
    update.message.reply_text("Sticker removed successfully!")

    return ConversationHandler.END

def confirm_tag(bot, update, user_data):  # pylint: disable=unused-argument
    """Handler for a message that begins with Yes or No.
       Confirm the tags and modify the database.
    """
    if update.message.text == "Yes":
        cursor = conn.cursor()
        if user_data["modify"]:
            # Delete the previous defined tags
            cursor.execute("DELETE FROM STICKER_TAG WHERE user_sticker_rowid=?",
                           (user_data["modify_id"],))
            # Insert the new ones
            for tag in user_data['tags'].split(","):
                tag = tag.strip()
                if tag == "":
                    continue
                # Insert tag if not exist
                cursor.execute("INSERT INTO TAG(tag) SELECT ?"
                               " WHERE NOT EXISTS(SELECT tag FROM TAG WHERE tag=?)",
                               (tag, tag))
                # Get the tag rowid
                cursor.execute("SELECT rowid, tag FROM TAG WHERE tag=?", (tag,))
                tag_rowid = cursor.fetchone()["rowid"]

                cursor.execute("INSERT INTO STICKER_TAG VALUES (?, ?)",
                               (user_data["modify_id"], tag_rowid))

            conn.commit()

            update.message.reply_text("Yay! Tags updated successfully!")
        else:
            # Insert user if not exist
            cursor.execute("INSERT INTO USER(id) SELECT ?"
                           " WHERE NOT EXISTS(SELECT id FROM USER WHERE id=?)",
                           (update.message.from_user.id, update.message.from_user.id))
            # Get the user rowid
            cursor.execute("SELECT rowid, id FROM USER WHERE id=?", (update.message.from_user.id,))
            user_rowid = cursor.fetchone()["rowid"]

            # Insert sticker if not exist
            cursor.execute("INSERT INTO STICKER(file_id, emoji) SELECT ?,?"
                           "WHERE NOT EXISTS(SELECT file_id, emoji FROM STICKER WHERE file_id=?)",
                           (user_data['sticker']['file_id'],
                            user_data['sticker']['emoji'],
                            user_data['sticker']['file_id']))
            # Get the sticker rowid
            cursor.execute("SELECT rowid, file_id FROM STICKER WHERE file_id=?",
                           (user_data['sticker']['file_id'],))
            sticker_rowid = cursor.fetchone()["rowid"]

            cursor.execute("INSERT INTO USER_STICKER VALUES (?, ?)", (user_rowid, sticker_rowid))
            cursor.execute("SELECT last_insert_rowid()")
            user_sticker_rowid = cursor.fetchone()[0]

            for tag in user_data['tags'].split(","):
                tag = tag.strip()
                if tag == "":
                    continue
                # Insert tag if not exist
                cursor.execute("INSERT INTO TAG(tag) SELECT ?"
                               " WHERE NOT EXISTS(SELECT tag FROM TAG WHERE tag=?)",
                               (tag, tag))
                # Get the tag rowid
                cursor.execute("SELECT rowid, tag FROM TAG WHERE tag=?", (tag,))
                tag_rowid = cursor.fetchone()["rowid"]

                cursor.execute("INSERT INTO STICKER_TAG VALUES (?, ?)",
                               (user_sticker_rowid, tag_rowid))

            conn.commit()

            update.message.reply_text("Yay! Sticker tagged successfully!",
                                      reply_markup=ReplyKeyboardRemove())
    elif update.message.text == "No":
        return cancel(bot, update, user_data)
    else:
        update.message.reply_text("Sorry, I didn't understand. Send me a sticker to tag.",
                                  reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

def cancel(bot, update, user_data):  # pylint: disable=unused-argument
    """Cancel the state machine and delete the user data"""
    update.message.reply_text("Operation cancelled!", reply_markup=ReplyKeyboardRemove())
    for key in user_data:
        del key
    return ConversationHandler.END

def error(bot, update, err):  # pylint: disable=unused-argument
    """Log any error"""
    logger.warning("Update \"%s\" caused error \"%s\"", update, err)

@run_async
def inlinequery(bot, update):  # pylint: disable=unused-argument
    """The inline query handler.
       Finds and returns all the sticker that match the query string, all if no
       string is given.
    """
    inline_query = update.inline_query.query.strip()
    inline_results = list()

    cursor = conn.cursor()
    if inline_query == "":
        cursor.execute("SELECT * "
                       "FROM USER_STICKER, STICKER_TAG, USER, STICKER, TAG "
                       "WHERE USER.id = ? AND "
                       "USER_STICKER.user_rowid = USER.rowid AND "
                       "STICKER_TAG.tag_rowid = TAG.rowid AND "
                       "STICKER_TAG.user_sticker_rowid = USER_STICKER.rowid AND "
                       "USER_STICKER.sticker_rowid = sticker.rowid "
                       "group by USER_STICKER.sticker_rowid",
                       (str(update.inline_query.from_user.id),))
    else:
        cursor.execute("SELECT * "
                       "FROM USER_STICKER, STICKER_TAG, USER, STICKER, TAG "
                       "WHERE USER.id = ? AND "
                       "TAG.tag LIKE ? AND "
                       "USER_STICKER.user_rowid = USER.rowid AND "
                       "STICKER_TAG.tag_rowid = TAG.rowid AND "
                       "STICKER_TAG.user_sticker_rowid = USER_STICKER.rowid AND "
                       "USER_STICKER.sticker_rowid = sticker.rowid "
                       "group by USER_STICKER.sticker_rowid",
                       (str(update.inline_query.from_user.id), "%{}%".format(inline_query)))

    bd_query = cursor.fetchall()
    for sticker in bd_query:
        inline_results.append(InlineQueryResultCachedSticker(uuid4(),
                                                             sticker_file_id=sticker["file_id"]))

    update.inline_query.answer(inline_results, cache_time=0, is_personal=True)

def main():
    """The main function
       Configure the telegram api and create the database.
    """
    # FIXME(heylouiz): Do not use global variables
    global conn   # pylint: disable=global-statement,invalid-name
    # Configure the DB
    conn = sqlite3.connect("tagged_stickers.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create the USER table
    cursor.execute('''CREATE TABLE IF NOT EXISTS USER (id INTEGER)''')
    # Create the STICKER table
    cursor.execute('''CREATE TABLE IF NOT EXISTS STICKER (file_id TEXT,
                                                          emoji TEXT)''')
    # Create the TAG table
    cursor.execute('''CREATE TABLE IF NOT EXISTS TAG (tag TEXT)''')
    # Create the USER_STICKER table
    cursor.execute('''CREATE TABLE IF NOT EXISTS USER_STICKER
                      (user_rowid INTEGER,
                       sticker_rowid INTEGER,
                       FOREIGN KEY(user_rowid) REFERENCES USER(rowid),
                       FOREIGN KEY(sticker_rowid) REFERENCES STICKER(rowid))''')
    # Create the STICKER_TAG table
    cursor.execute('''CREATE TABLE IF NOT EXISTS STICKER_TAG
                      (user_sticker_rowid INTEGER,
                       tag_rowid INTEGER,
                       FOREIGN KEY(user_sticker_rowid) REFERENCES USER_STICKER(rowid),
                       FOREIGN KEY(tag_rowid) REFERENCES TAG(rowid))''')

    # Create index
    cursor.execute("CREATE INDEX IF NOT EXISTS index_user ON USER(id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS index_sticker ON STICKER(file_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS index_tag ON TAG(tag)")

    conn.commit()

    # Create the Updater and pass it your bot's token.
    updater = Updater(CONFIGURATION["telegram_token"])

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start),
                      MessageHandler(Filters.sticker, get_sticker, pass_user_data=True)],
        states={
            STICKER: [MessageHandler(Filters.sticker, get_sticker, pass_user_data=True)],
            TAGGING: [MessageHandler(Filters.text, tag_sticker, pass_user_data=True)],
            CONFIRM_TAG: [RegexHandler("^(Yes|No)$", confirm_tag, pass_user_data=True)],
            CONFIRM_UPDATE: [RegexHandler("^(Edit|Cancel|Remove)$",
                                          confirm_update,
                                          pass_user_data=True)]
        },
        fallbacks=[CommandHandler("cancel", cancel, pass_user_data=True)]
    )

    # Register the handlers
    updater.dispatcher.add_handler(conv_handler)
    updater.dispatcher.add_handler(InlineQueryHandler(inlinequery))
    updater.dispatcher.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == "__main__":
    main()
