import time
from datetime import date


def display_clock():
    while True:
        return time.strftime('%I:%M:%S %p')


def get_time():
    while True:
        current_time = time.strftime('%I:%M:%S %p')

        double_zero_added = '%s%s%s' % (current_time[:6], '00', current_time[6 + 1:])

        new_time = ""

        for i in range(len(double_zero_added)):
            if i != 8:
                new_time = new_time + double_zero_added[i]
        return new_time


def get_date():
    while True:
        today = date.today()
        return today.strftime("%B %d, %Y")
