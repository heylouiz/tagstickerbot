# @tagstickerbot

![build passing](https://travis-ci.org/heylouiz/tagstickerbot.svg?branch=master)

A Telegram bot written in Python that tags stickers to help you find them when you "need".

Have you ever have trouble to find that dank sticker and loose the timing struging in to pages of stickers?

Your problems are about to disapear, just use the @tagstickerbot to tag and find them!

Check it out: www.telegram.me/tagstickerbot

# Usage

Follow the step to tag the sticker and use it in any chat after that!
Lets say you tagged the sticker with the word "meme"
Try to use it by typing the command bellow and select the sticker:
```bash
@tagstickerbot meme
```
If you don't type anything the bot will show all your tagged stickers.

# Start coding

Dependencies (Tested only in Python3):

Create a virtualenv (Optional):
```bash
mkdir ~/virtualenv
virtualenv -p python3 ~/virtualenv
source ~/virtualenv/bin/activate
```

Install the requirements (if you are in a virtualenv, "sudo" is not necessary):
```bash
sudo pip3 install -r requirements.txt
```

Running:

After all the requirements are installed you can run the bot using the command:
```bash
python3 tagstickerbot.py
```

Theres a script to keep the bot running "forever", you can run it with ./run_forever.sh

If you have any doubts let me know!
