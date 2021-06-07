from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import requests, json
import sys
from config import *
import alpaca_trade_api as tradeapi
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.techindicators import TechIndicators
import pandas as pd
import yfinance as yf
import numpy as np
import time

BASE_URL = "https://paper-api.alpaca.markets"
ACCOUNT_URL = "{}/v2/account".format(BASE_URL)
ORDERS_URL = "{}/v2/orders".format(BASE_URL)
HEADERS = {'APCA-API-KEY-ID': API_KEY, 'APCA-API-SECRET-KEY': SECRET_KEY }

API = tradeapi.REST(
        'PKF3D1XLH52F3N738TRN',
        'kp2MNSS18DRt0jX9tlnZff7IBzamzlnbii8gAQJo',
        'https://paper-api.alpaca.markets'
        )

ts = TimeSeries(VANTAGE_KEY, output_format='pandas')
ti = TechIndicators(VANTAGE_KEY, output_format='pandas')

#list all of our orders
def list_orders(): 

    # Get the last 100 of our closed orders
    closed_orders = API.list_orders(
    status='closed',
    limit=100,
    nested=True  # show nested multi-leg orders
    )

    # Get the closed orders
    closed_aapl_orders = [o for o in closed_orders]
    
    return closed_aapl_orders

#get order from clientid
def client_id(id):
    return API.get_order_by_client_order_id(id)

#get orders
def get_orders(type_of_orders, mysql):
    orders = []

    cursor = mysql.connection.cursor()
    query = 'SELECT ticker, id FROM CamEliMax_orders WHERE type=%s'
    queryVars = (type_of_orders,)
    cursor.execute(query, queryVars)
    mysql.connection.commit()
    results = cursor.fetchall()

    for x in results:
        if x['id'] == '':
            orders.append([x['ticker'], 'N/A', 'N/A'])
        else:
            order = client_id(x['id'])
            orders.append([order.symbol, order.filled_avg_price, order.filled_at])
    
    return orders

#checks to see if ticker is valid
def check_ticker(ticker):
    ticker= yf.Ticker(ticker.upper())
    try:
        ticker.info['symbol']
        return True
    except:
        return False

#finds our daily profits and loss
def change_in_equity():
    # First, open the API connection
    api = tradeapi.REST(
        'PKF3D1XLH52F3N738TRN',
        'kp2MNSS18DRt0jX9tlnZff7IBzamzlnbii8gAQJo',
        'https://paper-api.alpaca.markets'
        )
    # Get account info
    account = api.get_account()
    # Check our current balance vs. our balance at the last market close
    balance_change = float(account.equity) - float(account.last_equity)
    return f'Today\'s portfolio balance change: ${round(balance_change,2)}'

def get_tech_indicator(symbol, interval, choice):
    choice = choice.lower()
    #statistic showing if overbought or over sold
    if choice == 'rsi':
        data, meta = ti.get_rsi(symbol, interval, 20, 'close')
        d = [meta, data]
        return d
    #ti showing the exponential average
    elif choice == 'stoch':
        data, meta = ti.get_stoch(symbol, interval)
        d = [meta, data]
        return d
    #ti showing the volume weighted average
    elif choice == 'vwap':
        data, meta = ti.get_vwap(symbol, interval, 20, 'close')
        d = [meta, data]
        return d
    #ti showing the on balance volume
    elif choice == 'obv':
        data, meta = ti.get_obv(symbol, interval)
        d = [meta, data]
        return d
    #ti showing the moving average convergence/divergence
    elif choice == 'macd':
        data, meta = ti.get_macd(symbol, interval)
        d = [meta, data]
        return d

     #ti showing the bollinger bands
    elif choice == 'bbands':
        data, meta = ti.get_bbands(symbol, interval, 20, 'close')
        d = [meta, data]
        return d
    
     #ti showing the moving average convergence/divergence
    elif choice == 'adx':
        data, meta = ti.get_a(symbol, interval, 20)
        d = [meta, data]
        return d

def get_tech_val(symbol, interval, num, choice):
    vals = []
    d = get_tech_indicator(symbol, interval, choice)
    counter = 0
    for date, ind in d[1].items():
        for i in ind:
            if counter >= (len(d[1])-num):
                vals.insert(0, i)
            counter += 1
    if num == 1:
        return vals[0]
    else:
        return vals

def create_order(symbol, qty, type, side, time_in_force):
    data = {
        "symbol": symbol,
        "qty": qty,
        "side": side,
        "type": type,
        "time_in_force": time_in_force
    }
    r = requests.post(ORDERS_URL, json=data, headers=HEADERS)
    return json.loads(r.content)

def trade(indicator, symbol, default, owned):
    #turning comma seperated string to list
    if not default:
        info = indicator.split(",") 
        indicator = info[0]
        high = info[1]
        low = info[2]


    if indicator == 'rsi':
        #need to switch all values to a table and call from the table instead of calling
        #from API each time
        rsi = get_tech_val(symbol,'daily', 1, 'rsi')
        if default:
            #sell if RSI above 80 (overbought) buy if RSI below 30 (oversold)
            if rsi >= 80:
                if owned == True:
                    print(symbol + ' would be bought but it is already owned')
                else:
                    #create_order(symbol,1, 'market', 'sell', 'gtc')
                    print(symbol + ' was overbought we sell 1 share')
                    owned = False
            elif rsi <= 30:
                if owned == False:
                    print(symbol + ' would be sold but it is not owned')
                else:
                    #create_order(symbol, 1, 'market', 'buy', 'gtc')
                    print(symbol + ' was oversold we bought 1 share')
                    owned = True
            else:
                print(symbol + ' was within range did not buy or sell')
        else:
            #sell if RSI above high (overbought) buy if RSI below low (oversold)
            if rsi >= high:
                if owned == True:
                    print(symbol + ' would be bought but it is already owned')
                else:
                    #create_order(symbol,1, 'market', 'sell', 'gtc')
                    print(symbol + ' was overbought we sold 1 share')
                    owned = False
            elif rsi <= low:
                if owned == False:
                    print(symbol + ' would be sold but it is not owned')
                else:
                    #create_order(symbol, 1, 'market', 'buy', 'gtc')
                    print(symbol + ' was oversold we bought 1 share')
                    owned = True
            else:
                print(symbol + ' was within range did not buy or sell')

    elif indicator == 'bbands':
        #need to switch all values to a table and call from the table instead of calling
        #from API each time
        bbands = get_tech_val(symbol,'daily', 1, 'bbands')
        if default:
            #sell if RSI above 80 (overbought) buy if RSI below 30 (oversold)
            if bbands >= 80:
                if owned == True:
                    print(symbol + ' would be bought but it is already owned')
                else:
                    #create_order(symbol,1, 'market', 'sell', 'gtc')
                    print(symbol + ' was overbought we sell 1 share')
                    owned = False
            elif bbands <= 30:
                if owned == False:
                    print(symbol + ' would be sold but it is not owned')
                else:
                    #create_order(symbol, 1, 'market', 'buy', 'gtc')
                    print(symbol + ' was oversold we bought 1 share')
                    owned = True
            else:
                print(symbol + ' was within range did not buy or sell')
        else:
            #sell if RSI above high (overbought) buy if RSI below low (oversold)
            if bbands >= high:
                if owned == True:
                    print(symbol + ' would be bought but it is already owned')
                else:
                    #create_order(symbol,1, 'market', 'sell', 'gtc')
                    print(symbol + ' was overbought we sold 1 share')
                    owned = False
            elif bbands <= low:
                if owned == False:
                    print(symbol + ' would be sold but it is not owned')
                else:
                    #create_order(symbol, 1, 'market', 'buy', 'gtc')
                    print(symbol + ' was oversold we bought 1 share')
                    owned = True
            else:
                print(symbol + ' was within range did not buy or sell')
    


    return owned
    

def loop_through(mysql):
    cursor = mysql.connection.cursor()
    query = 'SELECT * FROM CamEliMax_orders'
    cursor.execute(query)
    mysql.connection.commit()
    results = cursor.fetchall()

    for x in results:
        #to keep track of each order
        count = 0
        if x['type'] == 'ai':
            #get list of indicators from mysql
            #get unique_id from mysql
            #run through function to get list of indicators
            #get new data using list of indicators
            #get algorithm from second mysql using unique_id
            #run new data through algorithm
            #buy or sell given result
            cur = mysql.connection.cursor()
                
        else:
            #checks to see if stock is owned
            if x['filled'] == 0:
                own = False
            else:
                own = True
            
            #checks if preset or manual
            if x['type'] == 'preset':
                default = True
            else:
                default = False
            filled = trade(x['tech_indicator'], x['ticker'], default, own)
            time.sleep(15)
    
        cursor = mysql.connection.cursor()
        #change if the order is filled or not
        if filled:
            query = "UPDATE CamEliMax_orders SET filled='1' WHERE unique_id=%s"
        else:
            query = "UPDATE CamEliMax_orders SET filled='0' WHERE unique_id=%s"
        unique_id = x['unique_id']
        queryVars = (unique_id,)
        cursor.execute(query, queryVars)
        mysql.connection.commit()
    
    return results

def get_list(tech_ind):
    s = tech_ind.split(",")
    s.pop()
    return s
    



# for index, row in df.iterrows():
#     print(check_ticker(row['Symbol']))
