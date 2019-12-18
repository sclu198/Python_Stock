#!/usr/bin/env python
# coding: utf-8

# In[8]:


# c = 股票代號
# n = 公司簡稱
# z = 當盤成交價
# tv = 當盤成交量
# v = 累積成交量
# o = 開盤價
# h = 最高價
# L = 最低價
# Y = 昨日收盤價


# In[9]:


from IPython.display import display, clear_output
from urllib.request import urlopen
import pandas as pd
import datetime
import requests
import sched
import time
import json

s = sched.scheduler(time.time, time.sleep)


# In[10]:


def tableColor(val):
    if val > 0:
        color = 'red'
    elif val < 0:
        color = 'green'
    else:
        color = 'white'
    return 'color: %s' % color


# In[11]:



def stock_crawler(targets):
    
    clear_output(wait=True)
    
    # 組成stock_list
    stock_list = '|'.join('tse_{}.tw'.format(target) for target in targets) 
    
    #　query data
    query_url = "http://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch="+ stock_list
    data = json.loads(urlopen(query_url).read())

    # 過濾出有用到的欄位
    columns = ['c','n','z','tv','v','o','h','l','y']
    df = pd.DataFrame(data['msgArray'], columns=columns)
    df.columns = ['股票代號','公司簡稱','當盤成交價','當盤成交量','累積成交量','開盤價','最高價','最低價','昨收價']
    
    # 新增漲跌百分比
    df.iloc[:, [2,3,4,5,6,7,8]] = df.iloc[:, [2,3,4,5,6,7,8]].astype(float)
    df['漲跌百分比'] = (df['當盤成交價'] - df['昨收價'])/df['昨收價'] * 100
    
    # 紀錄更新時間
    time = datetime.datetime.now()  
    print("更新時間:" + str(time.hour)+":"+str(time.minute))
    
    # show table
    df = df.style.applymap(tableColor, subset=['漲跌百分比'])
    display(df)
    
    start_time = datetime.datetime.strptime(str(time.date())+'9:30', '%Y-%m-%d%H:%M')
    end_time =  datetime.datetime.strptime(str(time.date())+'13:30', '%Y-%m-%d%H:%M')
    
    # 判斷爬蟲終止條件
    if time >= start_time and time <= end_time:
        s.enter(1, 0, stock_crawler, argument=(targets,))


# In[12]:


# 欲爬取的股票代碼
stock_list = ['2330','2344','2633','3030','3231']

# 每秒定時器
s.enter(1, 0, stock_crawler, argument=(stock_list,))
s.run()




