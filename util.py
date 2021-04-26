import re, tweepy, datetime, time, csv
from tweepy import OAuthHandler
from textblob import TextBlob
import matplotlib.pyplot as plt
import pandas as pd
import urllib.request as rq
import numpy as np
import json
import os


def loadData(url):
    try:
        dataset = rq.urlopen(url)
        dataset = dataset.read()
        dataset = json.loads(dataset)
    except Exception as e:
        print('Unable to get data from flipsidecrypto API. Check the URL below: \n{}'.format(url))

    return dataset

def formatHolders(holders):
    holder_dict = {}
    for val in holders:
        holder_dict[val['USER_ADDRESS'].lower()] = val['ALCX_USD']
    return holder_dict

def formatFEITribeVal(fei_tribe):
    holder_dict = {}
    for val in fei_tribe:
        holder_dict[val['USER_ADDRESS'].lower()] = val['VALUE']
    return holder_dict

# contract: 0xab8e74017a8cc7c15ffccd726603790d26d7deca
# def formatStaked(alcx_staking):
#     holder_dict = {}
#     for val in fei_tribe:
#         holder_dict[val['USER_ADDRESS'].lower()] = val['VALUE']
#     return holder_dict

def calculateChangeALCX(i):
    # get current ETH and ALCX values
    url = 'https://api.flipsidecrypto.com/api/v2/queries/76c022d1-721d-4511-8619-dfec2cc8edee/data/latest'
    dataset = rq.urlopen(url)
    dataset = dataset.read()
    prices = json.loads(dataset)
    price_dict = {}
    for p in prices:
        price_dict[p['SYMBOL']] = p['PRICE']


    sym = i['SYMBOL'].lower()
    sym = sym.split(" ")

    if 'alcx' in sym:
        return i['AMOUNT'] * price_dict['ALCX']
    elif 'slp' in sym:
        return i['AMOUNT'] * np.sum(np.array(list(price_dict.values())))
    elif 'alusd' in sym:
        return i['AMOUNT']
    else:
        return i['AMOUNT']

def getStakedALCX(holders_at_event, staked_string):
    url = 'https://api.flipsidecrypto.com/api/v2/queries/c44f9d8a-6a8c-4a6d-97f4-2f3a9cab6e54/data/latest'
    alcx_staking = loadData(url)
    address = '0xab8e74017a8cc7c15ffccd726603790d26d7deca'

    for i in alcx_staking:
        is_target_in_list1 = i['LOWER(FROM_ADDRESS)'].lower() in (string.lower() for string in list(holders_at_event.keys()))
        is_target_in_list2 = i['LOWER(TO_ADDRESS)'].lower() in (string.lower() for string in list(holders_at_event.keys()))

        if is_target_in_list1 or is_target_in_list2:
            change = calculateChangeALCX(i)
            if i['LOWER(FROM_ADDRESS)'].lower() == address: #increase
                holders_at_event[i['LOWER(TO_ADDRESS)']][staked_string] += change
            elif i['LOWER(TO_ADDRESS)'].lower() == address: #decrease
                holders_at_event[i['LOWER(FROM_ADDRESS)']][staked_string] -= change

    return holders_at_event

def calculateChangeFEITRIBE(i):
    # get current ETH and ALCX values

    sym = i['SYMBOL'].lower()
    sym = sym.split(" ")

    if 'fei' in sym:
        return i['AMOUNT'] * 0.8
    elif 'tribe' in sym:
        return i['AMOUNT'] * 1.2
    else:
        return i['AMOUNT'] * 2


def getStakedFEITRIBE(holders_at_event, staked_string):
    url = 'https://api.flipsidecrypto.com/api/v2/queries/821ae0c1-d953-47d8-8cc1-74a9da3a647a/data/latest' #fei tribe staked
    feitribe_staking = loadData(url)
    address = '0x9928e4046d7c6513326ccea028cd3e7a91c7590a'

    for i in feitribe_staking:
        is_target_in_list1 = i['FROM_ADDRESS'].lower() in (string.lower() for string in list(holders_at_event.keys()))
        is_target_in_list2 = i['TO_ADDRESS'].lower() in (string.lower() for string in list(holders_at_event.keys()))

        if is_target_in_list1 or is_target_in_list2:
            change = calculateChangeFEITRIBE(i)
            if i['FROM_ADDRESS'].lower() == address: #increase
                holders_at_event[i['TO_ADDRESS']][staked_string] += change
            elif i['TO_ADDRESS'].lower() == address: #decrease
                holders_at_event[i['FROM_ADDRESS']][staked_string] -= change

    return holders_at_event


def alcxHoldersAtEvent(genesis_event_users, alcx_holders, fei_tribe_val):
    holders_at_event = {}
    for val in genesis_event_users:
        is_target_in_list1 = val['TO_ADDRESS'].lower() in (string.lower() for string in list(alcx_holders.keys()))
        is_target_in_list2 = val['TO_ADDRESS'].lower() in (string.lower() for string in list(fei_tribe_val.keys()))
        if is_target_in_list1 and is_target_in_list2:
            holders_at_event[val['TO_ADDRESS'].lower()] = {'ALCX': alcx_holders[val['TO_ADDRESS'].lower()],
                                                                'FEITRIBE': fei_tribe_val[val['TO_ADDRESS'].lower()],
                                                                'STAKED_ALCX':0,
                                                                'STAKED_FEITRIBE':0}

    holders_at_event = getStakedALCX(holders_at_event, staked_string='STAKED_ALCX')
    holders_at_event = getStakedFEITRIBE(holders_at_event, staked_string='STAKED_FEITRIBE')

    to_df = []
    for val in holders_at_event.keys():
        to_df.append({"address":val,
                    "ALCX":holders_at_event[val]["ALCX"],
                    "STAKED_ALCX":holders_at_event[val]["STAKED_ALCX"],
                    "STAKED_FEITRIBE":holders_at_event[val]["STAKED_FEITRIBE"],})

    df = pd.DataFrame(to_df)
    return df


def valStaked(alcx_genesis_event):
    fei_val, alcx_val_staked, fei_tribe_staked = 0, 0, 0
    for i in alcx_genesis_event.keys():
        fei_val+=alcx_genesis_event[i]['FEITRIBE']
        alcx_val_staked+=alcx_genesis_event[i]['STAKED_ALCX']
        fei_tribe_staked+=alcx_genesis_event[i]['STAKED_FEITRIBE']

    return fei_val, alcx_val_staked, fei_tribe_staked

def barGraphDist(df, column_to_sort, y_label_str, title_str):
    df = df.sort_values(column_to_sort, ascending=False)

    vals = np.array(df[column_to_sort])
    adds = np.array(df['address'])
    if column_to_sort == 'STAKED_ALCX' or column_to_sort == 'STAKED_FEITRIBE':
        vals = -1*np.flip(vals)
    pop_mean = np.mean(vals)

    x_vals = np.linspace(0, vals.size, 10)
    x_val_str = []
    for i in range(0,x_vals.size):
        x_val_str.append(str(int(i*10)))

    fig = plt.figure(figsize=(12, 6))
    plt.bar(np.arange(vals.size),vals)
    plt.ylabel(y_label_str, fontsize=18)
    plt.xlabel("% of Users", fontsize=18)
    plt.xticks(x_vals, x_val_str, fontsize=18)
    plt.yticks(fontsize=15)
    plt.title(title_str+"; Mean: "+str(round(100*pop_mean,1)), fontsize=18)
    plt.show()


# contract_liquidity_pool = '0x7a250d5630b4cf539739df2c5dacb4c659f2488d'
# from_add = '0x0000000000000000000000000000000000000000'


# 0x9928e4046d7c6513326ccea028cd3e7a91c7590a
# url = 'https://api.flipsidecrypto.com/api/v2/queries/821ae0c1-d953-47d8-8cc1-74a9da3a647a/data/latest' #fei tribe staked
# fei_tribe_staked = loadData(url)
# for i, val in enumerate(fei_tribe_staked):
#     print(val['SYMBOL'])
#     if i == 100: exit()
# # print(fei_tribe_staked[0])
# exit()

# # load/format value of users with FEI and Tribe
# url = 'https://api.flipsidecrypto.com/api/v2/queries/9b0a847f-a4dd-4d21-a3d3-f57d64b07090/data/latest' # current users and USD value of FEI and Tribe
# fei_tribe = loadData(url)
# fei_tribe_val = formatFEITribeVal(fei_tribe)
#
#
# # get event attendees
# url = 'https://api.flipsidecrypto.com/api/v2/queries/7c26c1cd-f59f-40b0-892d-f0d229052df3/data/latest' # GENESIS event user ids
# genesis_event_users = loadData(url)
#
# # get alcx holders
# url = 'https://api.flipsidecrypto.com/api/v2/queries/ddf70c0d-d6e2-41a1-a014-6f33e84fab72/data/latest' # current ALCX holders
# alcx_holders = loadData(url)
# alcx_holders = formatHolders(alcx_holders)
#
# # get alcx holders who attended event
# alcx_genesis_event = alcxHoldersAtEvent(genesis_event_users, alcx_holders, fei_tribe_val)
#
# fei_val, alcx_val_staked, fei_tribe_staked = valStaked(alcx_genesis_event)
#
# print("Number of Alchemix users who participated in FEI's Token Genesis Event:  ", len(list(alcx_genesis_event.keys())))
# print("Combined Value in FEI/Tribe for Genesis Event attendees (USD):           ", fei_val)
# print("Combined Amount Staked in ALCX for Genesis Event attendees (USD):        ", alcx_val_staked)
# print("Combined Amount Staked in FEI/TRIBE for Genesis Event attendees (USD):   ", fei_tribe_staked)
