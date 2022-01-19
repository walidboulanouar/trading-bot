# ByBit Trading Bot V1.1.0
# Creator: Nikhil Ranchod
# Contributors: Alex Michaelides
# Created: 22/08/2021
# Background: High Frequency trading bot that works in crypto bull market on the ByBit platform
# ------------------------------------------------------------------------------------------------------------------- #
#TODO:
# 1. Add web socket code for pulling current market price and add it to the trailing stop loss function
# 2. Create main loop to rerun the bot over once we have pulled out of a position.
# 3. Create Flask API connected to a google sheet to allow for control over the bot from a spread sheet.
# 4. Run the bot on Steves beast PC and let it run in the background.

# Import Statements
import bybit
import time
import numpy as np
import hmac
import json
import websocket

# [START: API Authentication for ByBit API]
client = bybit.bybit(test=True, api_key="HQTNE3DOLKEcgKSLNq", api_secret="wkWUDQkGJqkdyc2kh59hO712qSKapKZFBbiG")
# [END: API Authentication for ByBit API]

# [START: Get current market price]
entryPrice = float((client.Market.Market_orderbook(symbol="XRPUSDT").result())[0]['result'][0]['price'])
# [END: Get current market price]


# ALGO SETTINGS
# ALEX: Understand these settings and tweak them carefully, keep a history of the changes you made because IT WILL CRASH THE CODE.
# ALEX: look below in the code and understand where they are used in order to improve you knowledge.
noSteps = 9
buyIncrement = 0.001  # Buy increment.
tpIncrement = 0.01  # Take profit increment.
slInterval = 0.01  # Stop loss interval.
minQuantity = 2 # Starting quantity for the calculation.
stopLossLimit = 0.005  # Stop loss limit for last step.
tslRetracement = 0.005  # Trailing stop loss retracement.
side = "Sell"

activationPrice = entryPrice + slInterval
trailingStopPrice = entryPrice - tslRetracement

# [START: Create arrays and define variables]
allocatedQuantities = [minQuantity]
priceArray = []
takeProfits = [0]
ordersArray = [0]
statusArray = []
tsQty = 0
run = True
# [END: Create arrays and define variables]

# [START: Create arrays of prices, quantities, take profits and stop losses based on current market price]
# ALEX: make sure that these are the correct prices, if you want to short the market we have to change the calc for price array.
# Create Buy Prices...
for i in range(noSteps):
    priceArray.append(float(entryPrice) + (buyIncrement * i))
    priceArray = [round(num, 4) for num in priceArray]  # Round the calculation to 4 digits for all.
# Create Quantities...
for i in range(noSteps - 1):
    allocatedQuantities.append(allocatedQuantities[i] * 2)
    allocatedQuantities = [round(num, 4) for num in allocatedQuantities]  # Round the calculation to 4 digits for all.
# Create take profits...
for i in range(noSteps):
    if i != 0:
        takeProfits.append(priceArray[i] - tpIncrement)
    takeProfits = [round(num, 4) for num in takeProfits]

print("Price Array: ", priceArray)
print("Allocated Quantities: ", allocatedQuantities)
print("Take Profits", takeProfits)
# [END: Create arrays of prices and quantities based on current market price]

# [START: Create Buy Orders]
for i in range(noSteps):

    if i == 0:
        # ALEX: check these orders and make sure the parameters are correct, you can change the side between "Buy" and "Sell" in line 38.
        # ALEX: check the bybit api documentation for all of the parameters and what we can set them to.
        # First order
        order = (client.LinearOrder.LinearOrder_new(side=side, symbol="XRPUSDT", order_type="Limit",
                                                    qty=allocatedQuantities[i], price=priceArray[i],
                                                    time_in_force="GoodTillCancel",
                                                    reduce_only=False, close_on_trigger=False).result())
        print(order)
        temp_order = order[0]['result']['order_id']
        ordersArray.append(temp_order)

        # Orders in the middle
    if 0 < i < noSteps:
        order = (client.LinearOrder.LinearOrder_new(side=side, symbol="XRPUSDT", order_type="Limit",
                                                    qty=allocatedQuantities[i], price=priceArray[i],
                                                    time_in_force="GoodTillCancel",
                                                    reduce_only=False, close_on_trigger=False,
                                                    take_profit=takeProfits[i]).result())
        print(order)
        temp_order = order[0]['result']['order_id']
        ordersArray.append(temp_order)

        # Last Order
    if i == noSteps:
        stopLossPrice = priceArray[i] - stopLossLimit
        order = (client.LinearOrder.LinearOrder_new(side=side, symbol="XRPUSDT", order_type="Limit",
                                                    qty=allocatedQuantities[i], price=priceArray[i],
                                                    stop_loss=stopLossPrice,
                                                    time_in_force="GoodTillCancel",
                                                    reduce_only=False, close_on_trigger=False,
                                                    take_profit=takeProfits[i]).result())
        temp_order = order[0]['result']['order_id']
        ordersArray.append(temp_order)

del ordersArray[0]
print(ordersArray)
# [END: Create Buy Orders]

# [START: Trailing stop loss function definition]
def trailingStopLoss(quantity):
    marketPrice = float((client.Market.Market_orderbook(symbol="XRPUSDT").result())[0]['result'][0]['price'])
    print("Market Price: ", marketPrice, "Activation Price: ", activationPrice)
    # Should be less than instead of equal to...
    if marketPrice >= activationPrice:
        trailingStopPrice == marketPrice - tslRetracement
        print("Market Price: ", marketPrice, "->", "Trailing Stop Price: ", trailingStopPrice)
    if marketPrice <= trailingStopPrice:
        # ALEX: Make sure we are closing the position correctly, it takes the qty by checking the filled orders and summing them on line 154
        # Close position by market order:
        order = (client.LinearOrder.LinearOrder_new(side="Sell", symbol="XRPUSDT", order_type="Market",
                                                    qty=quantity,
                                                    time_in_force="GoodTillCancel",
                                                    reduce_only=False, close_on_trigger=False).result())
        print(order)
        # Close all active buy orders:
        closeBuyOrders = (client.LinearOrder.LinearOrder_cancelAll(symbol="XRPUSDT").result())
        closeOrderResult = closeBuyOrders[0]['result']
        print(closeOrderResult)
        return False
    else:
        return True
# [END: Trailing stop loss function definition]


# [START: Track orders and add trailing stop loss to order set]
# ALEX: this loop runs constantly until the trailing stop loss is activated, it gives us an idea of which orders are filled.
while run:
    for i in range(noSteps):
        status = client.LinearOrder.LinearOrder_query(symbol="XRPUSDT", order_id=ordersArray[i]).result()
        statDict = {'order_id': ordersArray[i], 'status': status[0]['result']['order_status'],
                    'takeProfit': takeProfits[i], 'Quantity': allocatedQuantities[i]}
        statusArray.append(statDict)
        # Check quantity that will be used in the trailing stop loss based on filled orders
        if statusArray[i]['status'] == 'Filled':
            tsQty += statusArray[i]['Quantity']
    run = trailingStopLoss(tsQty)
    print(statusArray)
    statusArray = []
    time.sleep(1)
# [END: Track orders and add trailing stop loss to order set]
