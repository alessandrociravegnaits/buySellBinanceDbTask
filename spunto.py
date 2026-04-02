import pandas as pd
from datetime import datetime
import json
import time
import math
from datetime import timedelta, datetime
import numpy as np
from locale import atof
from binance.client import Client
from urllib.request import urlopen
import telepot
from telepot.loop import MessageLoop
import copy
from binance.client import BinanceAPIException
from locale import atoi
import os
from dotenv import load_dotenv

load_dotenv()  # Carica le variabili dal file .env

### CLIENTS
binance_client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))
BOT_TOKEN = os.getenv('BOT_TOKEN')  # bot username=t.me/nomeBot
ID = os.getenv('ID')  # il proprio id telegram

echo = 1  # visualizza mess di staot su telegram
allerta = 0  # alert di btc nel caso di movimenti repentini
storicoA = 0  # valore storico di val di btcusdt
perc = 0
cont = 0
vai = False  # variabile per gestire quando inviare botMessage
pd.options.display.max_rows = 9999
s = []  # lista degli ordini sell
b = []
bf = []
s2 = []
s2f = []
b2 = []  # lista ordini buy in trailing
maxi = []  # lista coi valori massimi
maxif = []  # lista coi valori massimi
mini = []
trigger = []
triggerf = []
inc = []
incf = []
dec = []
triggerS = []
go = True
sell = False
buy = False
buyf = False
sell2 = False
sell2f = False
buy2 = False  # per ordini trailing
canc = False
com = False
tf = 900  # default 15min tf


def on_chat_message(message):
    global s, s2, s2f
    global b, b2, bf
    global go
    global buy, sell, canc, buy2, sell2, buyf
    global com
    global tf, echo, allerta, storicoA, perc

    if (go == True):
        content_type, chat_type, chat_id = telepot.glance(message)
        command = message['text']

        if command == '/info':
            bot.sendMessage(ID, 'ℹ️ *Comandi disponibili*\n\n'
                                '*/s*:  __Vende asset__  /s  btcusdt \\>o\\< ValTrigger  Quantità @pairhook  📉\n'
                                '*/b*:  __Compra asset__ /b btcusdt \\>o\\< ValTrigger  Quantità @pairhook  📈\n'
                                '*/f*:  __Compra asset e rivende in trailing__ /f btcusdt \\>o\\< ValTrigger Quantita  Val% ⚙️\n'
                                '*/S*:  __Vende asset in trailing__  /S  btcusdt Val%  Quantità  Limit @pairhook 📉\n'
                                'Se viene inserita la pairhook, verrà venduta quella\n'
                                '*/B*:  __Compra asset in trailing__ /B btcusdt Val%  Quantità Limit 📈\n'
                                '*/t*:  __Time frame__ /t tfValue 1,5,10,15,30,60,240 min ⏱️\n'
                                '*/o*:  Lista ordini /o 📋\n'
                                '*/a*:  alert di btc per variazioni rapide /a 0  1  %variazione 🚨\n'
                                '*/e*:  echo, visualizza a video /e 0 o 1 🔊   \n'
                                '*/c*:  Cancella ordine /c \\(s o S opp b o B opp f\\)  ,\\#,a \\=all 🗑️\n',
                            parse_mode='MarkdownV2')  # a=all s=sell,b=buy

        if command[0:2] == '/t':  # sell    /s axsbusd <o> valoreTrigger quantita'
            # s.append(command[3:].upper().split())
            tf = int(atoi(command[3:]) * 60)
            bot.sendMessage(ID, 'Setting TF \n', parse_mode='Markdown')

        if command[0:2] == '/a':  # sell    /s axsbusd <o> valoreTrigger quantita'
            # s.append(command[3:].upper().split())
            valore = command[3:].upper().split()
            allerta = atoi(valore[0])
            perc = 0
            if (allerta):
                perc = atof(valore[1])
                storicoA = lettura1mt('BTCUSDT')  # asset
            bot.sendMessage(ID, 'Setting alert \n', parse_mode='Markdown')

        if command[0:2] == '/e':  # sell    /s axsbusd <o> valoreTrigger quantita'
            # s.append(command[3:].upper().split())
            echo = atoi(command[3:])
            bot.sendMessage(ID, 'Setting echo \n', parse_mode='Markdown')

        if command[0:2] == '/s':  # sell    /s axsbusd <o> valoreTrigger quantita'
            # s.append(command[3:].upper().split())
            sell = command[3:].upper().split()
            bot.sendMessage(ID, 'Insert ordine *sell* in corso ..\n', parse_mode='Markdown')

        if command[0:2] == '/b':  # buy     /b axsbusd <o> valoreTrigger quantita'
            # b.append(command[3:].upper().split())
            buy = command[3:].upper().split()
            bot.sendMessage(ID, 'Insert ordine *buy* in corso ..\n', parse_mode='Markdown')

        if command[0:2] == '/f':  # function
            # b.append(command[3:].upper().split())
            command += ' 0 '  # cod che identifica che nn e' stato ancora preso l ordine se =0
            command += ' 0 '  # cod prec val
            buyf = command[3:].upper().split()
            bot.sendMessage(ID, 'Insert ordine *buy Function* in corso ..\n', parse_mode='Markdown')

        if command[0:2] == '/S':  # sell    /s axsbusd  valore% quantita'
            # s.append(command[3:].upper().split())
            sell2 = command[3:].upper().split()
            bot.sendMessage(ID, 'Insert ordine *sell in trailing* in corso ..\n', parse_mode='Markdown')

        if command[0:2] == '/B':  # buy     /b axsbusd  valore% quantita'
            # b.append(command[3:].upper().split())
            buy2 = command[3:].upper().split()
            bot.sendMessage(ID, 'Insert ordine *buy in trailing* in corso ..\n', parse_mode='Markdown')

        if command[0:2] == '/c':  # cancel order   /c  s oppure b  #
            canc = True
            com = command[3:].split()
            bot.sendMessage(ID, 'Cancellazione ordine in corso ..\n')

        if command[0:2] == '/o':  # lista ordini  /o
            bot.sendMessage(ID, '*Ordini di acquisto: *\n', parse_mode='Markdown')
            for i in range(0, len(b), 1):
                bot.sendMessage(ID, '*#' + str(i) + ':* ' + str(b[i]), parse_mode='Markdown')

            bot.sendMessage(ID, '*Ordini di vendita: *\n', parse_mode='Markdown')
            for i in range(0, len(s), 1):
                bot.sendMessage(ID, '*#' + str(i) + ':* ' + str(s[i]), parse_mode='Markdown')

            bot.sendMessage(ID, '*Ordini di acquisto pre trailing: *\n', parse_mode='Markdown')
            for i in range(0, len(bf), 1):
                bot.sendMessage(ID, '*#' + str(i) + ':* ' + str(bf[i]), parse_mode='Markdown')

            bot.sendMessage(ID, '*Ordini di acquisto trailing: *\n', parse_mode='Markdown')
            for i in range(0, len(b2), 1):
                bot.sendMessage(ID, '*#' + str(i) + ':* ' + str(b2[i]), parse_mode='Markdown')

            bot.sendMessage(ID, '*Ordini di vendita trailing: *\n', parse_mode='Markdown')
            for i in range(0, len(s2), 1):
                bot.sendMessage(ID, '*#' + str(i) + ':* ' + str(s2[i]), parse_mode='Markdown')

            bot.sendMessage(ID, '*Ordini di vendita post trailing: *\n', parse_mode='Markdown')
            for i in range(0, len(s2f), 1):
                bot.sendMessage(ID, '*#' + str(i) + ':* ' + str(s2f[i]), parse_mode='Markdown')

            bot.sendMessage(ID, '*Time frame: * ' + str(tf) + ' secondi', parse_mode='Markdown')
            bot.sendMessage(ID, '*Echo: * ' + str(echo), parse_mode='Markdown')
            bot.sendMessage(ID, '*Alert su btusdt: * ' + str(perc) + ' %', parse_mode='Markdown')


def letturaarr(A):  # lettura arrotondamenti
    try:
        x = binance_client.get_symbol_info(A)
        arr = x['filters'][1]['stepSize'].find('1') - 1
    except:
        arr = 1

    return arr


def lettura1mt(A):
    try:
        d = binance_client.get_historical_klines(A, Client.KLINE_INTERVAL_1MINUTE, "1 minute ago UTC")
        #####modifica del 31-12-24.. round di 8 anziche 6
        d = round(atof(d[0][4:5][0]), 8)  # valore close
    except:
        d = False
    return d


def put_order(a, t, q):  # t=type order,q=quantity
    if t == 'SIDE_BUY':
        try:
            order = binance_client.create_order(
                symbol=a,
                side=Client.SIDE_BUY,
                type=Client.ORDER_TYPE_MARKET,
                quantity=q)
        except:
            order = 0

    if t == 'SIDE_SELL':
        try:
            order = binance_client.create_order(
                symbol=a,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_MARKET,
                quantity=q)
        except:
            order = 0

    return order


def put_order_mT(a, t, q, p_o, ii):  # a=asset,t=type order,q=quantity CON TRAILING
    global arrO
    # put_order_m(Asset[i],'SIDE_BUy',qm,p_order) xMARTINGALA
    if a[0] == 'binance':
        if t == 'SIDE_BUY':
            try:
                order = binance_client.create_order(
                    symbol=a[1],
                    side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_LIMIT,
                    timeInForce=Client.TIME_IN_FORCE_GTC,
                    quantity=q,
                    price=p_o,
                    recvWindow=5000)
            except:
                order = {'status': 'NOT FILLED'}
                try:
                    bot.sendMessage(-1001500550874,
                                    'ERROR in acquisto Binance ->valore quota: *' + str(q) + '*\nAsset: -> *' + a[
                                        1] + '*', parse_mode='Markdown')
                except:
                    ZZ = 1

            if (order['status'] == 'NEW' or order[
                'status'] == 'FILLED'):  # se fillato scrive FILLED-->binance se in limit mette NEW
                price = order['price']  # prezzo
            else:
                price = 0

        if t == 'SIDE_SELL':
            try:

                order = binance_client.create_order(
                    symbol=a[1],
                    side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_TAKE_PROFIT_LIMIT,
                    quantity=q,
                    price=round(p_o - round((p_o / 100), arrO[ii]), arrO[ii]),  # price -1%
                    stopPrice=p_o,
                    trailingDelta=int(TTTRI[ii] * 100),  # BIPS
                    timeInForce=Client.TIME_IN_FORCE_GTC,
                    recvWindow=5000)

            except BinanceAPIException as erro:
                order = {'status': 'NOT FILLED'}
                try:
                    # bot.sendMessage(-1001500550874,'ERROR in vendita Binance ->Quantità : *'+str(q)+'*\nAsset: -> *'+a[1]+'*',parse_mode='Markdown')
                    bot.sendMessage(-1001500550874,
                                    'ERROR in vendita Binance ->Quantità : *' + str(q) + '*\nAsset: -> *' + a[
                                        1] + '*\nErr: ' + str(erro.status_code) + '\n' + str(
                                        erro.code) + '\n' + erro.message + '\n', parse_mode='Markdown')
                    # bot.sendMessage(-1001500550874,'Errore in lettura ordini : \n'+str(erro.status_code)+'\n'+str(erro.code)+'\n'+erro.message+'\nAsset: -> *'+Asset[i][1]+'*',parse_mode='Markdown')
                except:
                    ZZ = 1

            #######18/3/22#########################################
            order = binance_client.get_order(symbol=a[1], orderId=order['orderId'])
            price = order['stopPrice']

    #######################################################

    return order, price


### CONSTANTS
binsizes = {"1m": 1, "5m": 5, "1h": 60, "1d": 1440}
batch_size = 750

bot = telepot.Bot(BOT_TOKEN)
########
MessageLoop(bot, {'chat': on_chat_message}).run_as_thread()
########

storia = datetime.now()

while True:
    # if (cont+()%tf==0):
    if (cont % tf == 0) and (vai):
        for a in s:
            val = lettura1mt(a[0])  # asset
            ###Legge candela
            if (val != False):
                if a[1] == '<' and val < atof(a[2]):  # trigger
                    if (len(a) == 5):
                        arr = letturaarr(a[4])
                        oo = put_order(a[4], 'SIDE_SELL', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Vendita *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a ribasso :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            s.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Vendita *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1

                    else:
                        arr = letturaarr(a[0])
                        oo = put_order(a[0], 'SIDE_SELL', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Vendita *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a ribasso :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            s.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Vendita *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1

                if a[1] == '>' and val > atof(a[2]):  # trigger
                    if (len(a) == 5):
                        arr = letturaarr(a[4])
                        oo = put_order(a[4], 'SIDE_SELL', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Vendita *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a rialzo :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            s.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Vendita *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1
                    else:
                        arr = letturaarr(a[0])
                        oo = put_order(a[0], 'SIDE_SELL', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Vendita *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a rialzo :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            s.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Vendita *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1
                                # if (cont%20==0):
            # bot.sendMessage(chatId,'*ATTesa in THREAD*\n'+str(cont)+' '+str(cache.get('int')),parse_mode='Markdown')
            # if (cont%300==0)and(vai)and(echo):
            if (vai and echo):
                try:
                    bot.sendMessage(ID, 'Valore --> ' + str(val), parse_mode='Markdown')
                except:
                    ZZ = 1

        for a in b:
            val = lettura1mt(a[0])  # asset
            if (val != False):
                if a[1] == '<' and val < atof(a[2]):  # trigger
                    if (len(a) == 5):
                        arr = letturaarr(a[4])
                        oo = put_order(a[4], 'SIDE_BUY', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Acquisto *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a ribasso :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            b.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Acquisto *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1
                    else:
                        arr = letturaarr(a[0])
                        oo = put_order(a[0], 'SIDE_BUY', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Acquisto *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a ribasso :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            b.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Acquisto *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1

                if a[1] == '>' and val > atof(a[2]):  # trigger
                    if (len(a) == 5):
                        arr = letturaarr(a[4])
                        oo = put_order(a[4], 'SIDE_BUY', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Acquisto *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a rialzo :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            b.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Acquisto *' + a[4] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1
                    else:
                        arr = letturaarr(a[0])
                        oo = put_order(a[0], 'SIDE_BUY', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Acquisto *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '* Coin. Violato valore a rialzo :*' + a[2] + '*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            b.remove(a)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Acquisto *' + a[0] + '*di: *' + str(
                                    round(atof(a[3]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1
                            #            if (cont%20==0):
            # bot.sendMessage(chatId,'*ATTesa in THREAD*\n'+str(cont)+' '+str(cache.get('int')),parse_mode='Markdown')
            # if (cont%300==0)and(vai)and(echo):
            if (vai and echo):
                try:
                    bot.sendMessage(ID, 'Valore --> ' + str(val), parse_mode='Markdown')
                except:
                    ZZ = 1

                    ###########àTRAILING SELL e BUY
        for sx, mx, tx, ix in zip(s2, maxi, trigger, inc):
            val = lettura1mt(sx[0])  # asset
            if (val != False):
                if (val > (atof(sx[3]) + (atof(ix[0]))) and tx[0] != '-1' and sx[4] == '<'):
                    sx[3] = str(val - atof(ix[0]))  # nuovo trigger limit = al precedente massimo
                    try:
                        bot.sendMessage(ID, 'Nuovo trigger limite impostato: ' + sx[3], parse_mode='Markdown')
                    except:
                        zz = 1
                if (val > (atof(mx[0])) and tx[0] == '-1'):
                    mx[0] = str(val)
                    try:
                        bot.sendMessage(ID, 'max-->' + mx[0])
                    except:
                        ZZ = 1
                if (val < atof(sx[3]) and tx[0] != '-1' and sx[4] == '<'):
                    tx[0] = '-1'
                    try:
                        bot.sendMessage(ID, 'Trigger limite scattato', parse_mode='Markdown')
                    except:
                        zz = 1
                if (val > atof(sx[3]) and tx[0] != '-1' and sx[4] == '>'):
                    tx[0] = '-1'
                    try:
                        bot.sendMessage(ID, 'Trigger limite scattato', parse_mode='Markdown')
                    except:
                        zz = 1

                if (val < (atof(mx[0]) - ((atof(sx[1]) * atof(mx[0])) / 100))) and tx[0] == '-1':  # trigger
                    if (len(sx) == 6):
                        arr = letturaarr(sx[5])
                        oo = put_order(sx[5], 'SIDE_SELL', round(atof(sx[2]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Vendita *' + sx[5] + '*di: *' + str(
                                    round(atof(sx[2]), arr)) + '* Coin. Violato valore a ribasso :*' + sx[1] + ' %*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            s2.remove(sx)
                            maxi.remove(mx)
                            inc.remove(ix)
                            trigger.remove(tx)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Vendita *' + sx[5] + '*di: *' + str(
                                    round(atof(sx[2]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1
                    else:
                        arr = letturaarr(sx[0])
                        oo = put_order(sx[0], 'SIDE_SELL', round(atof(sx[2]), arr))  # quantity  arrotondata all asset
                        if oo != 0:
                            try:
                                bot.sendMessage(ID, 'Vendita *' + sx[0] + '*di: *' + str(
                                    round(atof(sx[2]), arr)) + '* Coin. Violato valore a ribasso :*' + sx[1] + ' %*',
                                                parse_mode='Markdown')
                            except:
                                ZZ = 1
                            s2.remove(sx)
                            maxi.remove(mx)
                            inc.remove(ix)
                            trigger.remove(tx)
                        else:
                            try:
                                bot.sendMessage(ID, '*ERRORE* Vendita *' + sx[0] + '*di: *' + str(
                                    round(atof(sx[2]), arr)) + '*', parse_mode='Markdown')
                            except:
                                ZZ = 1
                                # if (cont%20==0):
            # bot.sendMessage(chatId,'*ATTesa in THREAD*\n'+str(cont)+' '+str(cache.get('int')),parse_mode='Markdown')
            # if (cont%300==0)and(vai)and(echo):
            if (vai and echo):
                try:
                    bot.sendMessage(ID, 'Valore --> ' + str(val), parse_mode='Markdown')
                except:
                    ZZ = 1

        for b, m, t, i in zip(b2, mini, triggerS, dec):
            val = lettura1mt(b[0])  # asset
            if (val != False):
                if (val < (atof(b[3]) - (atof(i[0]))) and t[0] != '-1'):
                    b[3] = str(val + atof(i[0]))  # nuovo trigger limit = al precedente massimo
                    try:
                        bot.sendMessage(ID, 'Nuovo trigger limite impostato: ' + b[3], parse_mode='Markdown')
                    except:
                        zz = 1
                if (val < (atof(m[0]))):
                    m[0] = str(val)
                    try:
                        bot.sendMessage(ID, 'min-->' + m[0])
                    except:
                        ZZ = 1

                if (val > atof(b[3]) and t[0] != '-1'):
                    t[0] = '-1'
                    # t='-1'
                    try:
                        bot.sendMessage(ID, 'Trigger limite scattato', parse_mode='Markdown')
                    except:
                        zz = 1
                if (val > (atof(m[0]) + ((atof(b[1]) * atof(m[0])) / 100))) and t[0] == '-1':  # trigger
                    arr = letturaarr(b[0])
                    oo = put_order(b[0], 'SIDE_BUY', round(atof(b[2]), arr))  # quantity  arrotondata all asset
                    if oo != 0:
                        try:
                            bot.sendMessage(ID, 'Acquisto *' + b[0] + '*di: *' + str(
                                round(atof(b[2]), arr)) + '* Coin. Violato valore a rialzo :*' + b[1] + ' %*',
                                            parse_mode='Markdown')
                        except:
                            ZZ = 1
                        b2.remove(b)
                        mini.remove(m)
                        dec.remove(i)
                        triggerS.remove(t)
                    else:
                        try:
                            bot.sendMessage(ID,
                                            '*ERRORE* Acquisto *' + b[0] + '*di: *' + str(round(atof(b[2]), arr)) + '*',
                                            parse_mode='Markdown')
                        except:
                            ZZ = 1
                            # if (cont%20==0):
            # bot.sendMessage(chatId,'*ATTesa in THREAD*\n'+str(cont)+' '+str(cache.get('int')),parse_mode='Markdown')
            # if (cont%300==0)and(vai)and(echo):
            if (vai and echo):
                try:
                    bot.sendMessage(ID, 'Valore --> ' + str(val), parse_mode='Markdown')
                except:
                    ZZ = 1

                    ###########àTRAILING SELL e BUY in FUNCTION
        for sxf, mxf, txf, ixf in zip(s2f, maxif, triggerf, incf):
            val = lettura1mt(sxf[0])  # asset
            if (val != False):
                if (val > (atof(sxf[4]) + (atof(ixf[0]))) and txf[0] != '-1' and sxf[5] == '<'):
                    sxf[4] = str(val - atof(ixf[0]))  # nuovo trigger limit = al precedente massimo
                    try:
                        bot.sendMessage(ID, 'Nuovo trigger limite impostato: ' + sxf[4], parse_mode='Markdown')
                    except:
                        zz = 1
                if (val > (atof(mxf[0])) and txf[0] == '-1'):
                    mxf[0] = str(val)
                    try:
                        bot.sendMessage(ID, 'max-->' + mxf[0])
                    except:
                        ZZ = 1
                if (val < atof(sxf[4]) and txf[0] != '-1' and sxf[5] == '<'):
                    txf[0] = '-1'
                    try:
                        bot.sendMessage(ID, 'Trigger limite scattato', parse_mode='Markdown')
                    except:
                        zz = 1
                if (val > atof(sxf[4]) and txf[0] != '-1' and sxf[5] == '>'):
                    txf[0] = '-1'
                    try:
                        bot.sendMessage(ID, 'Trigger limite scattato', parse_mode='Markdown')
                    except:
                        zz = 1
                if (val < (atof(mxf[0]) - ((atof(sxf[1]) * atof(mxf[0])) / 100))) and txf[0] == '-1':  # trigger
                    arr = letturaarr(sxf[0])
                    oo = put_order(sxf[0], 'SIDE_SELL', round(atof(sxf[2]), arr))  # quantity  arrotondata all asset
                    if oo != 0:
                        try:
                            bot.sendMessage(ID, 'Vendita *' + sxf[0] + '*di: *' + str(
                                round(atof(sxf[2]), arr)) + '* Coin. Violato valore a ribasso :*' + sxf[1] + ' %*',
                                            parse_mode='Markdown')
                        except:
                            ZZ = 1
                        s2f.remove(sxf)
                        maxif.remove(mxf)
                        incf.remove(ixf)
                        triggerf.remove(txf)
                        try:
                            bf[sxf[3]][5] = '0'
                            bf[sxf[3]][6] = '0'
                        except:
                            zz = 1
                    else:
                        try:
                            bot.sendMessage(ID, '*ERRORE* Vendita *' + sxf[0] + '*di: *' + str(
                                round(atof(sxf[2]), arr)) + '*', parse_mode='Markdown')
                        except:
                            ZZ = 1
                            # if (cont%20==0):
            # bot.sendMessage(chatId,'*ATTesa in THREAD*\n'+str(cont)+' '+str(cache.get('int')),parse_mode='Markdown')
            # if (cont%300==0)and(vai)and(echo):
            if (vai and echo):
                try:
                    bot.sendMessage(ID, 'Valore --> ' + str(val), parse_mode='Markdown')
                except:
                    ZZ = 1

                ##01-01-24 solo per function check ogni minuto per acquisto,poi vendita a tf
    if (cont % 60 == 0) and (vai):
        c = 0
        for a in bf:
            val = lettura1mt(a[0])  # asset
            if a[6] == '0':
                if (val != False):
                    a[6] = str(val)
            if (val != False):
                if a[1] == '<' and val < atof(a[2]) and atof(a[6]) > atof(a[2]) and a[5] == '0':  # trigger
                    arr = letturaarr(a[0])
                    oo = put_order(a[0], 'SIDE_BUY', round(atof(a[3]), arr))  # quantity  arrotondata all asset
                    if oo != 0:
                        a[5] = '1'
                        try:
                            bot.sendMessage(ID, 'Acquisto *' + a[0] + '*di: *' + str(
                                round(atof(a[3]), arr)) + '* Coin. Violato valore a ribasso :*' + a[2] + '*',
                                            parse_mode='Markdown')
                        except:
                            ZZ = 1
                            # bf.remove(a)
                        # cod=a[5]
                        sell2f = (a[0] + ' ' + a[4] + ' ' + a[3] + ' ' + str(c)).upper().split()
                        try:
                            bot.sendMessage(ID, 'Insert ordine *sell in trailing* in corso ..\n', parse_mode='Markdown')
                        except:
                            ZZ = 1
                    else:
                        try:
                            bot.sendMessage(ID,
                                            '*ERRORE* Acquisto *' + a[0] + '*di: *' + str(round(atof(a[3]), arr)) + '*',
                                            parse_mode='Markdown')
                        except:
                            ZZ = 1

            if (val != False):
                a[6] = str(val)
            try:
                bot.sendMessage(ID, 'Valore --> ' + str(val), parse_mode='Markdown')
            except:
                ZZ = 1
            c += 1
    vai = False

    if (sell != False):
        hook = ''
        for j in sell:
            if j.startswith('@'):
                hook = j[1:]
                # tolgo da sell2 l'hook
                sell.remove(j)
                break
        if (hook != ''):
            sell.append(hook)
        s.append(sell)
        sell = False

    if (buy != False):
        hook = ''
        for j in buy:
            if j.startswith('@'):
                hook = j[1:]
                # tolgo da sell2 l'hook
                buy.remove(j)
                break
        if (hook != ''):
            buy.append(hook)
        b.append(buy)
        buy = False

    if (buyf != False):
        bf.append(buyf)
        buyf = False

    if (sell2 != False):
        hook = ''
        for j in sell2:
            if j.startswith('@'):
                hook = j[1:]
                # tolgo da sell2 l'hook
                sell2.remove(j)
                break
        if (len(sell2) == 3):  # caso in cui no stop limit
            trigger.append(['-1'])
            maxi.append([str(lettura1mt(sell2[0]))])  # maxi = val attuale per il calcolo del trailing
            try:
                bot.sendMessage(ID, 'Valore attuale--> ' + str(maxi[0]), parse_mode='Markdown')
            except:
                ZZ = 1
            inc.append(['0'])  # inc=0
            sell2.append(str(lettura1mt(sell2[0])))
            sell2.append('=')
            if (hook != ''):
                sell2.append(hook)
            s2.append(sell2)
        else:  # con limit
            maxi.append([sell2[3]])  # in trailing tengo conto del max
            try:
                bot.sendMessage(ID, 'Valore attuale--> ' + str(lettura1mt(sell2[0])), parse_mode='Markdown')
            except:
                ZZ = 1
            inc.append([str(abs(lettura1mt(sell2[0]) - atof(sell2[3])))])
            trigger.append(['0'])
            if (lettura1mt(sell2[0]) - atof(sell2[3]) > 0):  # val-limit >0 ,limite sotto
                sell2.append('<')
            else:
                sell2.append('>')
            if (hook != ''):
                sell2.append(hook)
            s2.append(sell2)
        sell2 = False

    if (buy2 != False):
        b2.append(buy2)
        mini.append([buy2[3]])
        dec.append(str(abs(lettura1mt(buy2[0]) - atof(buy2[3]))))
        triggerS.append(['0'])
        buy2 = False

    if (sell2f != False):
        triggerf.append(['-1'])
        maxif.append([str(lettura1mt(sell2f[0]))])  # maxi = val attuale per il calcolo del trailing
        try:
            bot.sendMessage(ID, 'Valore attuale--> ' + str(maxif[0]), parse_mode='Markdown')
        except:
            ZZ = 1
        incf.append(['0'])  # inc=0
        sell2f.append(str(lettura1mt(sell2f[0])))
        sell2f.append('=')
        s2f.append(sell2f)
        sell2f = False

    if (canc == True):
        canc = False
        if com[1] == 'a':  # caso all
            if com[0] == 's':
                s.clear()
            if com[0] == 'b':
                b.clear()
            if com[0] == 'S':  # i trailing
                s2.clear()
            if com[0] == 'B':
                b2.clear()
            if com[0] == 'f':
                bf.clear()

        else:
            if com[0] == 's':
                s.pop(int(com[1]))
            if com[0] == 'b':
                b.pop(int(com[1]))
            if com[0] == 'S':
                s2.pop(int(com[1]))
                maxi.pop(int(com[1]))
                trigger.pop(int(com[1]))
                inc.pop(int(com[1]))
            if com[0] == 'B':
                b2.pop(int(com[1]))
                mini.pop(int(com[1]))
                triggerS.pop(int(com[1]))
                dec.pop(int(com[1]))
            if com[0] == 'f':
                bf.pop(int(com[1]))

    ####modifica del 14-12-24...per precisione nella lettura timeframe
    storia2 = datetime.now()
    if (storia2.minute != storia.minute):
        cont += 60
        if (allerta):
            val = lettura1mt('BTCUSDT')  # asset
            while (val == False):
                val = lettura1mt('BTCUSDT')  # asset
            if abs((((val - storicoA) / storicoA) * 100)) > abs(perc):
                for i in range(0, 6, 1):
                    try:
                        bot.sendMessage(ID, 'ALERT Scattato --> ' + str(((val - storicoA) / storicoA) * 100) + ' %',
                                        parse_mode='Markdown')
                        time.sleep(1.5)
                    except:
                        ZZ = 1
            storicoA = val

        if ((storia2.minute % int(tf / 60) == 0) and (int(tf / 60) != 240)):
            cont = tf
            vai = True

        if int((tf / 60) == 240):
            if ((storia2.hour) % 4 == 0):  # hour-1 per fuso orario tra settembre e marzo
                cont = tf
                vai = True

        storia = storia2
    time.sleep(1)