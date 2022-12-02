#! /usr/bin/env python3

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
import pandas as pd
from ta.trend import EMAIndicator
import numpy as np
fig = plt.figure()
ax1 = fig.add_subplot(1,1,1)
log_file = "../logs/ppo_ruff_logfile.csv"
df = pd.read_csv(log_file)
maxy = float("-inf")
step = 0
def animate(i):
    df = pd.read_csv(log_file)
    xar = df["episode"].values
    yar_eps = df["avg_eps_reward"].values
    steps = (df["step"].values)//10
    ema10_e = EMAIndicator(close=df["avg_eps_reward"],window=300)
    ema_e = ema10_e.ema_indicator().values
    ax1.clear()
    ax1.plot(xar,yar_eps)
    ax1.plot(xar,ema_e)

    steps = sum(df["step"].values)
    global step,maxy
    if steps>step:
        step = steps
        print("number of steps: "+str(step/1e+6))
        print("-"*20)
    if np.max(yar_eps)>maxy:
        maxy = np.max(yar_eps)
        print("new maximum reward: "+str(maxy))
        maxx = np.argmax(yar_eps)
        print("achieved at episode: "+str(maxx))
        print("-"*20)
        ax1.scatter([maxx],[maxy],c="r")
#    plt.ylim(-100,10)
ani = animation.FuncAnimation(fig, animate, interval=1000)
plt.show()
print(sum(df["step"].values))
