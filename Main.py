import sys
from PyQt5.QtWidgets import *
from PyQt5 import uic
import threading, time
from datetime import datetime, timedelta
from binance_f import RequestClient
from binance_f.model import *
import talib.abstract as ta
import numpy as np
from keys import keys
#from File_class import File_class
from binance_f.constant.test import *
from binance_f.base.printobject import *

form_class = uic.loadUiType("mainUI.ui")[0]

class Main(QMainWindow, form_class) :
    def __init__(self) :
        super().__init__()
        self.setupUi(self)
        self.api_key = keys()
        self.request_client = RequestClient(api_key=self.api_key, secret_key="")
        # self.File_class = File_class('2020_05')
        self.init_vars()
        self.init_status_bools()
        self.init_signals_bools()
        self.init_update_threads()

    def init_vars(self):
        self.my_money = 1000
        self.now_price = 0
        self.macd_hist = 0
        self.macd_12 = 0
        self.macd_26 = 0
        self.RSI = 0
        self.ATR_band_15_Top = 0
        self.ATR_band_15_bottom = 0
        self.moving_average_15m_24 = 0
        self.candleStickArrFor1m = []
        self.candloStickArrFor1m_NP = []

    def init_status_bools(self):
        self.MACD_is_it_above_X = False
        self.MACD_is_it_below_X = False
        self.macd_golden_bool = False
        self.macd_dead_bool = False
        self.RSI_is_it_below_X = False
        self.RSI_is_it_above_X = False
        self.ATR_band_rising = False
        self.ATR_band_falling = False
        self.touching_15m_20ma = False

    def init_signals_bools(self):
        self.macd_enter_long_signal =False
        self.macd_enter_short_signal = False
        self.macd_exit_short_signal = False
        self.macd_exit_long_signal = False
        self.ATR_long_signal = False
        self.ATR_short_signal = False
        self.touching_15m_20ma_signal = False

    def init_trade_threads(self):
        self.no_position_thread()

    def init_update_threads(self):
        self.update_candlestickArrFor1m_per1s_thr()
        self.update_candlestickArrFor15m_per1s_thr()

        threading.Timer(1, self.update_MACDhist_thr).start()
        threading.Timer(1, self.update_RSI_thr).start()
        threading.Timer(1, self.update_ATR_thr).start()

        threading.Timer(2, self.check_bools_and_update_signal_thr).start()
        threading.Timer(2, self.update_UI_thr).start()
        #self.main_thr()

    def update_candlestickArrFor15m_per1s_thr(self):
        try:
            tmp_Arr = self.request_client.get_candlestick_data(symbol="BTCUSDT",
                                                               interval=CandlestickInterval.MIN15,
                                                               startTime=None,
                                                               endTime=self.request_client.get_servertime(),
                                                               limit=50)
            self.newCandleStickArr_15m = tmp_Arr

        except Exception as e:
            print(f'에러 : {e}')
        threading.Timer(3, self.update_candlestickArrFor15m_per1s_thr).start()

    def update_candlestickArrFor1m_per1s_thr(self):
        try:
            self.candleStickArrFor1m = self.request_client.get_candlestick_data(symbol="BTCUSDT",
                                                               interval=CandlestickInterval.MIN1,
                                                               startTime=None,
                                                               endTime=self.request_client.get_servertime(),
                                                               limit=50)
            trash_Arr = []
            for stick in self.candleStickArrFor1m:
                trash_Arr.append(float(stick.close))
            self.candloStickArrFor1m_NP = np.array(trash_Arr, dtype='f8')
            self.now_price = float(self.candleStickArrFor1m[-1].close)
        except Exception as e:
            print(f'에러 : {e}')
            print("인터넷 연결 / 서버 확인 필요")
        threading.Timer(1, self.update_candlestickArrFor1m_per1s_thr).start()

    def update_MACDhist_thr(self): #macd 값들 ta라이브러리로 넘파이 배열을 넣어서 전역변수에 넣어준다.
        macd_12Arr, macd_26Arr, macd_histArr = ta.MACD(self.candloStickArrFor1m_NP, fastperiod=12, slowperiod=26,
                                                         signalperiod=9)
        self.macd_12 = float(macd_12Arr[-1])
        self.macd_26 = float(macd_26Arr[-1])
        self.macd_hist = float(macd_histArr[-1])
        self.macd_hist_prev = float(macd_histArr[-2])

        self.checking_MACDhist()

        threading.Timer(1, self.update_MACDhist_thr).start()

    def update_RSI_thr(self):
        self.RSI = float(ta.RSI(self.candloStickArrFor1m_NP, timperiod=14)[-1])
        self.checking_RSI()

        threading.Timer(1, self.update_RSI_thr).start()

    def update_ATR_thr(self):
        self.checking_ATR()
        # 상방 돌파
        if self.now_price >= self.ATR_band_15_Top:
            self.ATR_band_rising = True
            self.ATR_band_falling = False
        # 하방 돌파
        elif self.now_price <= self.ATR_band_15_bottom:
            self.ATR_band_falling = True
            self.ATR_band_rising = False
        # 중앙
        elif self.now_price < self.ATR_band_15_Top and self.now_price > self.ATR_band_15_bottom:
            self.ATR_band_rising = False
            self.ATR_band_falling = False

        if self.now_price == self.moving_average_15m_24:
            self.touching_15m_20ma = True

        threading.Timer(0.1, self.update_ATR_thr).start()

    def checking_MACDhist(self):
        macd_arr, macdsignal_arr, macdhist_arr = ta.MACD(self.candloStickArrFor1m_NP, fastperiod=12, slowperiod=26, signalperiod=9)

        if macdhist_arr[-2] < 0 and macdhist_arr[-1] > 0:
            self.macd_golden_bool = True
            self.macd_dead_bool = False
        if macdhist_arr[-2] > 0 and macdhist_arr[-1] < 0:
            self.macd_dead_bool = True
            self.macd_dead_bool = False
        if macd_arr[-1] < 0 and macdsignal_arr[-1] < 0:
            self.MACD_is_it_above_X = False
            self.MACD_is_it_below_X = True
        if macd_arr[-1] > 0 and macdsignal_arr[-1] > 0:
            self.MACD_is_it_above_X = True
            self.MACD_is_it_below_X = False

    def checking_RSI(self):
        X_low = 35
        X_high = 65
        if self.RSI < X_low:
            self.RSI_is_it_below_X = True
            self.RSI_is_it_above_X = False
            print(f'{self.RSI} 모드로 15분간 대기')
            time.sleep(60*15)
        elif self.RSI >= X_low and self.RSI <= X_high:
            self.RSI_is_it_below_X = False
            self.RSI_is_it_above_X = False
        elif self.RSI > X_high:
            self.RSI_is_it_below_X = False
            self.RSI_is_it_above_X = True
            print(f'{self.RSI} 모드로 15분간 대기')
            time.sleep(60*15)

    def checking_ATR(self):
        price_high = []
        price_low = []
        price_close = []

        for stick in self.newCandleStickArr_15m:
            price_high.append(float(stick.high))
            price_low.append(float(stick.low))
            price_close.append(float(stick.close))

        price_high_np = np.array(price_high, dtype='f8')
        price_low_np = np.array(price_low, dtype='f8')
        price_close_np = np.array(price_close, dtype='f8')

        real = ta.ATR(price_high_np, price_low_np, price_close_np, timeperiod=15)

        sum_15m_20 = 0
        for price in self.newCandleStickArr_15m[-20:]:
            sum_15m_20 += float(price.close)
        avg_15m_20 = sum_15m_20 / 20

        high = avg_15m_20 + (float(real[-1]) * 2)
        low = avg_15m_20 - (float(real[-1]) * 2)

        self.ATR_band_15_Top = high
        self.ATR_band_15_bottom = low
        self.moving_average_15m_24 = avg_15m_20

    def check_bools_and_update_signal_thr(self): #시그널을 끄는것은 트레이드쓰레드가 할 것
        if self.MACD_is_it_above_X == True and self.macd_dead_bool == True and self.RSI_is_it_above_X == True:
            self.macd_enter_short_signal = True
        if self.MACD_is_it_below_X == True and self.macd_golden_bool == True and self.RSI_is_it_below_X == True:
            self.macd_enter_long_signal = True
        if self.MACD_is_it_above_X == True and self.macd_golden_bool == True:
            self.macd_exit_short_signal = True
        if self.MACD_is_it_below_X == True and self.macd_dead_bool == True:
            self.macd_exit_long_signal = True
        if self.ATR_band_rising == True:
            self.ATR_long_signal = True
        if self.ATR_band_falling == True:
            self.ATR_short_signal = True
        if self.touching_15m_20ma == True:
            self.touching_15m_20ma_signal = True

        threading.Timer(1, self.check_bools_and_update_signal_thr).start()


    def update_UI_thr(self):
        self._now_price.setText(f'현재가 : {str(self.now_price)}')
        self._macd_12.setText(f'macd(12) : {str(self.macd_12)}')
        self._macd_26.setText(f'macd(26) : {str(self.macd_26)}')
        self._macd_hist.setText(f'macd_hist : {str(self.macd_hist)}')
        self._macd_hist_prev.setText(f'macd_hist_prev : {str(self.macd_hist_prev)}')
        self._RSI.setText(f'RSI : {str(self.RSI)}')
        self._ATR_band_15_Top.setText(f'ATR_Top : {str(self.ATR_band_15_Top)}')
        self._ATR_band_15_bottom.setText(f'ATR_bottom : {str(self.ATR_band_15_bottom)}')
        self._moving_average_15m_24.setText(f'mv_15m : {str(self.moving_average_15m_24)}')

        #signals UI update

        if self.MACD_is_it_above_X == True:
            self._MACD_is_it_above_X.setChecked(True)
        else:
            self._MACD_is_it_above_X.setChecked(False)
        if self.MACD_is_it_below_X == True:
            self._MACD_is_it_below_X.setChecked(True)
        else:
            self._MACD_is_it_below_X.setChecked(False)
        if self.macd_golden_bool == True:
            self._macd_goldencross_bool.setChecked(True)
        else:
            self._macd_goldencross_bool.setChecked(False)
        if self.macd_dead_bool == True:
            self._macd_deadcross_bool.setChecked(True)
        else:
            self._macd_deadcross_bool.setChecked(False)
        if self.RSI_is_it_above_X == True:
            self._RSI_is_it_above_X.setChecked(True)
        else:
            self._RSI_is_it_above_X.setChecked(False)
        if self.RSI_is_it_below_X == True:
            self._RSI_is_it_below_X.setChecked(True)
        else:
            self._RSI_is_it_below_X.setChecked(False)
        if self.ATR_band_rising == True:
            self._ATR_band_rising.setChecked(True)
        else:
            self._ATR_band_rising.setChecked(False)
        if self.ATR_band_falling == True:
            self._ATR_band_falling.setChecked(True)
        else:
            self._ATR_band_falling.setChecked(False)
        if self.touching_15m_20ma == True:
            self._touching_15m_20ma.setChecked(True)
        else:
            self._touching_15m_20ma.setChecked(False)

        #signals UI update

        if self.macd_enter_short_signal == True:
            self._macd_enter_short_signal.setChecked(True)
        else:
            self._macd_enter_short_signal.setChecked(False)
        if self.macd_enter_long_signal == True:
            self._macd_enter_long_signal.setChecked(True)
        else:
            self._macd_enter_long_signal.setChecked(False)
        if self.macd_exit_short_signal == True:
            self._macd_exit_short_signal.setChecked(True)
        else:
            self._macd_exit_short_signal.setChecked(False)
        if self.macd_exit_long_signal == True:
            self._macd_exit_long_signal.setChecked(True)
        else:
            self._macd_exit_long_signal.setChecked(False)
        if self.ATR_long_signal == True:
            self._ATR_long_signal.setChecked(True)
        else:
            self._ATR_long_signal.setChecked(False)
        if self.ATR_short_signal == True:
            self._ATR_short_signal.setChecked(True)
        else:
            self._ATR_short_signal.setChecked(False)
        if self.touching_15m_20ma_signal == True:
            self._touching_15m_20ma_signal.setChecked(True)
        else:
            self._touching_15m_20ma_signal.setChecked(False)

        threading.Timer(0.1, self.update_UI_thr).start()

    def main_thr(self):
        if self.closePer1m_is_it_updated ==True:
            print(f'{datetime.now()} : 종가가 업데이트 됐으므로 알고리즘 작동')
            self.closePer1m_is_it_updated = False

            if self.ATR_15m_is_it_below_X == True or self.ATR_15m_is_it_above_X == True: #ATR상향? 하향? 돌파를 먼저 판단하고
                if self.ATR_long_position == False and self.ATR_short_position == False: #상향 하향 돌파했는데도 ATR포지션이 아무것도 없다면 진입해야할 상황인 것.
                    self.trade_out() # 현재 포지션이 있다면 청산하고
                    if self.ATR_15m_is_it_below_X == True: # 하향돌파면
                        print(f'{datetime.now()} : ATR 하향돌파 매매')
                        self.trade_in('short') #숏 진입
                        self.ATR_short_position = True #ATR 숏진입은 특수상황이므로 기록
                        self.ATR_long_position = False
                    elif self.ATR_15m_is_it_above_X ==True: # 상향돌파면
                        print(f'{datetime.now()} : ATR 상향돌파 매매')
                        self.trade_in('long') #롱 진입
                        self.ATR_long_position = True #ATR 롱진입은 특수상황이므로 기록
                        self.ATR_short_position = False

            if self.ATR_long_position == True: #현재 포지션이 ATR 특수상황인지 판단
                if self.ATR_tradeOut_signal == True:
                    self.ATR_tradeOut_signal = False
                    self.ATR_long_position = False
                    self.trade_out()

            elif self.ATR_short_position == True: #현재 포지션이 ATR 특수상황인지 판단
                if self.ATR_tradeOut_signal == True:
                    self.ATR_tradeOut_signal = False
                    self.ATR_short_position = False
                    self.trade_out()

            if self.ATR_short_position == False and self.ATR_long_position == False: #위 ATR 특수상황이 아니라면 기존대로 MACD
                if self.position_is_it_empty == True:
                    if self.RSI_is_it_above_X == True and self.MACD_short_signal == True:
                        self.trade_in('short', 'MACD_short_signal')
                    if self.RSI_is_it_below_X == True and self.MACD_long_signal == True:
                        self.trade_in('long', 'MACD_long_signal')
                elif self.position_is_it_long == True:
                    if self.MACD_short_signal == True:
                        self.trade_out()
                    elif self.MACD_tradeOut_signal == True:
                        self.trade_out()
                elif self.position_is_it_short == True:
                    if self.MACD_long_signal == True:
                        self.trade_out()
                    elif self.MACD_tradeOut_signal == True:
                        self.trade_out()

        threading.Timer(1, self.main_thr).start()

    def update_closePrice_per1m_thr(self):
        self.close_price_1m = self.newCandleStickArr_1m[-1].close # 현재가(종가)를 불러와 전역변수에 넣어둔다.
        self.closePer1m_is_it_updated = True
        #print(f'{datetime.now()}  1분봉 종가 업데이트 {self.close_price_1m}, self.closePer1m_is_it_updated = {self.closePer1m_is_it_updated}')
        threading.Timer((60 - datetime.now().second), self.update_closePrice_per1m_thr).start() #1분마다 재귀함수 쓰레드를 반복시킨다.

    def what_time_is(self):
        serverTime = self.request_client.get_servertime()
        print(serverTime)
        print(datetime.today())
        print("server time: ", datetime.fromtimestamp(serverTime / 1000))
        server_obj = datetime.fromtimestamp((serverTime / 1000))
        pTime = server_obj - timedelta(days=2)
        print("one day ago : ", pTime)

    def del_signal(self, signal):
        if signal == '':
            print('이정민바보')
        if signal == 'MACD_short_signal':
            self.MACD_short_signal = False
        if signal == 'MACD_long_signal':
            self.MACD_long_signal = False
        if signal == 'MACD_tradeOut_signal':
            self.MACD_tradeOut_signal = False
        if signal == 'ATR_tradeOut_signal':
            self.ATR_tradeOut_signal = False

    def trade_in(self, position, signal=''):
        self.del_signal(signal)
        if self.position_is_it_long == True or self.position_is_it_short == True:
            print("잘못된 진입입니다. 이미 포지션이 있습니다.")
            return -1
        else:
            if position == 'long' and self.position_is_it_empty == True:
                self.entrance_price = self.now_price
                self.position_is_it_long = True
                self.position_is_it_empty = False
                self.position_is_it_short = False
                print(f'{datetime.now()}  롱 포지션에 진입하였습니다. 현재가 : {self.now_price}')
                self.MACD_long_signal = False
            elif position == 'short' and self.position_is_it_empty == True:
                self.entrance_price = self.now_price
                self.position_is_it_short = True
                self.position_is_it_empty = False
                self.position_is_it_long = False
                print(f'{datetime.now()}  숏 포지션에 진입하였습니다. 현재가 : {self.now_price}')
                self.MACD_short_signal = False

    def trade_out(self):
        if self.position_is_it_empty == True: #포지션이 없는가?
            print("잘못된 청산입니다. 포지션이 없습니다.")
            return -1
        else:
            if self.position_is_it_short == True:
                self.position_is_it_short = False
                self.position_is_it_empty = True
                percentage = (self.entrance_price - self.now_price)/self.entrance_price
                self.my_money += self.my_money*percentage*20
                print(f'{datetime.now()}  숏 포지션을 청산하였습니다. 현재가 : {self.now_price}, 차익 {percentage*100*20}%, 현재 지갑 {self.my_money}')
            elif self.position_is_it_long == True:
                self.position_is_it_long = False
                self.position_is_it_empty = True
                percentage = (self.now_price - self.entrance_price )/self.entrance_price
                self.my_money += self.my_money*percentage*20
                print(f'{datetime.now()}  롱 포지션을 청산하였습니다. 현재가 : {self.now_price}, 차익 {percentage*100*20}%, 현재 지갑 {self.my_money}')

if __name__ == "__main__" :
    app = QApplication(sys.argv)
    myWindow = Main()
    myWindow.show()
    app.exec_()