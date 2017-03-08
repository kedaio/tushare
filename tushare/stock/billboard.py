#!/usr/bin/env python
# -*- coding:utf-8 -*- 
"""
龙虎榜数据
Created on 2015年6月10日
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""

import pandas as pd
from pandas.compat import StringIO
from tushare.stock import cons as ct
import numpy as np
import time
import json
import re
import lxml.html
from lxml import etree
from tushare.util import dateu as du
from tushare.stock import ref_vars as rv
try:
    from urllib.request import urlopen, Request
except ImportError:
    from urllib2 import urlopen, Request


def top_list(date = None, retry_count=3, pause=0.001):
    """
    获取每日龙虎榜列表
    Parameters
    --------
    date:string
                明细数据日期 format：YYYY-MM-DD 如果为空，返回最近一个交易日的数据
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    
    Return
    ------
    DataFrame
        code：代码
        name ：名称
        pchange：涨跌幅     
        amount：龙虎榜成交额(万)
        buy：买入额(万)
        bratio：占总成交比例
        sell：卖出额(万)
        sratio ：占总成交比例
        reason：上榜原因
        date  ：日期
    """
    if date is None:
        if du.get_hour() < 18:
            date = du.last_tddate()
        else:
            date = du.today() 
    else:
        if(du.is_holiday(date)):
            return None
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_URL%(ct.P_TYPE['http'], ct.DOMAINS['em'], date, date))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            text = text.split('_1=')[1]
            text = eval(text, type('Dummy', (dict,), 
                                           dict(__getitem__ = lambda s, n:n))())
            text = json.dumps(text)
            text = json.loads(text)
            df = pd.DataFrame(text['data'], columns=rv.LHB_TMP_COLS)
            df.columns = rv.LHB_COLS
            df['buy'] = df['buy'].astype(float)
            df['sell'] = df['sell'].astype(float)
            df['amount'] = df['amount'].astype(float)
            df['Turnover'] = df['Turnover'].astype(float)
            df['bratio'] = df['buy'] / df['Turnover']
            df['sratio'] = df['sell'] /df['Turnover']
            df['bratio'] = df['bratio'].map(ct.FORMAT)
            df['sratio'] = df['sratio'].map(ct.FORMAT)
            df['date'] = date
            for col in ['amount', 'buy', 'sell']:
                df[col] = df[col].astype(float)
                df[col] = df[col] / 10000
                df[col] = df[col].map(ct.FORMAT)
            df = df.drop('Turnover', axis=1)
        except:
            pass
        else:
            return df
    raise IOError(ct.NETWORK_URL_ERROR_MSG)


def cap_tops(days= 5, retry_count= 3, pause= 0.001):
    """
    获取个股上榜统计数据
    Parameters
    --------
        days:int
                  天数，统计n天以来上榜次数，默认为5天，其余是10、30、60
        retry_count : int, 默认 3
                     如遇网络等问题重复执行的次数 
        pause : int, 默认 0
                    重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    Return
    ------
    DataFrame
        code：代码
        name：名称
        count：上榜次数
        bamount：累积购买额(万)     
        samount：累积卖出额(万)
        net：净额(万)
        bcount：买入席位数
        scount：卖出席位数
    """
    
    if ct._check_lhb_input(days) is True:
        ct._write_head()
        df =  _cap_tops(days, pageNo=1, retry_count=retry_count,
                        pause=pause)
        df['code'] = df['code'].map(lambda x: str(x).zfill(6))
        if df is not None:
            df = df.drop_duplicates('code')
        return df
    
    
def _cap_tops(last=5, pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[0],
                                               ct.PAGES['fd'], last, pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = rv.LHB_GGTJ_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _cap_tops(last, pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)
            

def broker_tops(days= 5, retry_count= 3, pause= 0.001):
    """
    获取营业部上榜统计数据
    Parameters
    --------
    days:int
              天数，统计n天以来上榜次数，默认为5天，其余是10、30、60
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
    Return
    ---------
    broker：营业部名称
    count：上榜次数
    bamount：累积购买额(万)
    bcount：买入席位数
    samount：累积卖出额(万)
    scount：卖出席位数
    top3：买入前三股票
    """
    if ct._check_lhb_input(days) is True:
        ct._write_head()
        df =  _broker_tops(days, pageNo=1, retry_count=retry_count,
                        pause=pause)
        return df


def _broker_tops(last=5, pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[1],
                                               ct.PAGES['fd'], last, pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = rv.LHB_YYTJ_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _broker_tops(last, pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)
        

def inst_tops(days= 5, retry_count= 3, pause= 0.001):
    """
    获取机构席位追踪统计数据
    Parameters
    --------
    days:int
              天数，统计n天以来上榜次数，默认为5天，其余是10、30、60
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
                
    Return
    --------
    code:代码
    name:名称
    bamount:累积买入额(万)
    bcount:买入次数
    samount:累积卖出额(万)
    scount:卖出次数
    net:净额(万)
    """
    if ct._check_lhb_input(days) is True:
        ct._write_head()
        df =  _inst_tops(days, pageNo=1, retry_count=retry_count,
                        pause=pause)
        df['code'] = df['code'].map(lambda x: str(x).zfill(6))
        return df 
 

def _inst_tops(last=5, pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[2],
                                               ct.PAGES['fd'], last, pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df = df.drop([2,3], axis=1)
            df.columns = rv.LHB_JGZZ_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _inst_tops(last, pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)


def inst_detail(retry_count= 3, pause= 0.001):
    """
    获取最近一个交易日机构席位成交明细统计数据
    Parameters
    --------
    retry_count : int, 默认 3
                 如遇网络等问题重复执行的次数 
    pause : int, 默认 0
                重复请求数据过程中暂停的秒数，防止请求间隔时间太短出现的问题
                
    Return
    ----------
    code:股票代码
    name:股票名称     
    date:交易日期     
    bamount:机构席位买入额(万)     
    samount:机构席位卖出额(万)     
    type:类型
    """
    ct._write_head()
    df =  _inst_detail(pageNo=1, retry_count=retry_count,
                        pause=pause)
    if len(df)>0:
        df['code'] = df['code'].map(lambda x: str(x).zfill(6))
    return df  
 

def _inst_detail(pageNo=1, retry_count=3, pause=0.001, dataArr=pd.DataFrame()):   
    ct._write_console()
    for _ in range(retry_count):
        time.sleep(pause)
        try:
            request = Request(rv.LHB_SINA_URL%(ct.P_TYPE['http'], ct.DOMAINS['vsf'], rv.LHB_KINDS[3],
                                               ct.PAGES['fd'], '', pageNo))
            text = urlopen(request, timeout=10).read()
            text = text.decode('GBK')
            html = lxml.html.parse(StringIO(text))
            res = html.xpath("//table[@id=\"dataTable\"]/tr")
            if ct.PY3:
                sarr = [etree.tostring(node).decode('utf-8') for node in res]
            else:
                sarr = [etree.tostring(node) for node in res]
            sarr = ''.join(sarr)
            sarr = '<table>%s</table>'%sarr
            df = pd.read_html(sarr)[0]
            df.columns = rv.LHB_JGMX_COLS
            dataArr = dataArr.append(df, ignore_index=True)
            nextPage = html.xpath('//div[@class=\"pages\"]/a[last()]/@onclick')
            if len(nextPage)>0:
                pageNo = re.findall(r'\d+', nextPage[0])[0]
                return _inst_detail(pageNo, retry_count, pause, dataArr)
            else:
                return dataArr
        except Exception as e:
            print(e)

            
def _f_rows(x):
    if '%' in x[3]:
        x[11] = x[6]
        for i in range(6, 11):
            x[i] = x[i-5]
        for i in range(1, 6):
            x[i] = np.NaN
    return x


def lhb_details(retry_count= 3, pause= 0.001, code=None, date=None):
	"""
	获取最近一个交易日龙虎榜上榜个股的交易详情. 包括买1-5和卖1-5的买入及卖出量,营业部名称.

	可选参数:
	证券代码(code): 指定代码用于只获取该证券的交易详情.省略的话会返回当日所有上榜证券的交易详情
	日期(date): 获取指定日期的交易详情.默认为最近一个交易日

	返回值:
	----------
	code:股票代码
	name:股票名称     
	date:交易日期     
	买1-5营业部名称及买入和卖出额及净额(万)    
	卖1-5营业部名称及买入和卖出额净额(万)    

	"""
	if date is None:
		if du.get_hour() < 18:
		    date = du.last_tddate()
		else:
		    date = du.today() 
	else:
		if(du.is_holiday(date)):
		    return None
	
	if code is None:
		print('请输入股票代码,比如： lhb_details(000001)')
		raise SystemExit(5)
		
	lhb_details_url = 'http://vip.stock.finance.sina.com.cn/q/api/jsonp.php/var%20details=/InvestConsultService.getLHBComBSData?symbol=%s&tradedate=%s&type=01'
	text = urlopen(lhb_details_url%(code,date),timeout=10).read()
	text = text.decode('GBK')
	text = text.split('details=')[1]
	text = eval(text, type('Dummy', (dict,), 
		dict(__getitem__ = lambda s, n:n))())
	text = json.dumps(text)
	text = json.loads(text)
	## text['buy'] = list of dicts
	## text['sell'] = list of dicts
	
	#for i in range(len(text['buy'])):
	#	for key in text['buy'][i].keys():
	#		print(text['buy'][i][key],end=' ')
	#	print() 
	#SYMBOL	sellAmount	buyAmount	comCode	type	netAmount	comName
	#000973 7.6802		2101.4900	80291363 01	2093.8098 浙商证券股份有限公司临安万马路证券营业部 
	#000973 0.0000		1777.2700	80348499 01 1777.27 华泰证券股份有限公司浙江分公司 
	#000973 317.3780	2069.5400	80127954 01 1752.162 安信证券股份有限公司南昌胜利路证券营业部 
	#000973 0.9050		1389.3300	80564863 01 1388.425 华鑫证券有限责任公司郑州普惠路证券营业部 
	#000973 39.0354		1239.5100	80034811 01 1200.4746 财通证券股份有限公司绍兴人民中路证券营业部 
	
	print('%4s %6s %10s %10s %10s %s' %('买入榜','股票代码','卖出额(万)','买入额(万)','买入净额(万)','营业部名称'))
	for i in range(len(text['buy'])):
		print('%-4d %-8s %-10s %-10s %-12s %s' %(i+1,text['buy'][i]['SYMBOL'],text['buy'][i]['sellAmount'],\
			text['buy'][i]['buyAmount'],text['buy'][i]['netAmount'],text['buy'][i]['comName']))   
	#1    000973   7.6802   2101.4900  2093.8098    浙商证券股份有限公司临安万马路证券营业部
	#2    000973   0.0000   1777.2700  1777.27      华泰证券股份有限公司浙江分公司
	#3    000973   317.3780 2069.5400  1752.162     安信证券股份有限公司南昌胜利路证券营业部
	#4    000973   0.9050   1389.3300  1388.425     华鑫证券有限责任公司郑州普惠路证券营业部
	#5    000973   39.0354  1239.5100  1200.4746    财通证券股份有限公司绍兴人民中路证券营业部

	print('%4s %6s %10s %10s %10s %s' %('卖出榜','股票代码','卖出额(万)','买入额(万)','买入净额(万)','营业部名称'))
	for i in range(len(text['sell'])):
		print('%-4d %-8s %-10s %-10s %-12s %s' %(i+1,text['sell'][i]['SYMBOL'],text['sell'][i]['sellAmount'],\
			text['sell'][i]['buyAmount'],text['sell'][i]['netAmount'],text['sell'][i]['comName'])) 
