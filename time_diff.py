import time
from datetime import datetime
from tkinter import messagebox
from get_attendance import get_employee_end_time


# Convert 12-Hour format to 24-Hour format
def convert(time):
    if time[-2:] == 'AM':
        if time[:2] == '12':
            converted = str('00' + time[2:8])
        else:
            converted = time[:-2]
    else:
        if time[:2] == '12':
            converted = time[:-2]
        else:
            converted = str(int(time[:2]) + 12) + time[2:8]

    return converted


# Calculate the minutes late
def get_minutes_late(schedule_in, time_in):
    time_1 = datetime.strptime(schedule_in, "%I:%M:%S %p")
    time_2 = datetime.strptime(time_in, "%I:%M:%S %p")

    time_interval = time_2 - time_1

    # Add 0 to single digit hours ex 8:00:00 --> 08:00:00
    time_interval_string_lenght = len(str(time_interval))
    eight_chars = time_interval_string_lenght < 8

    if eight_chars:
        time_interval = '0' + str(time_interval)

    try:
        ftr = [3600, 60, 1]
        minutes_late = int(sum([a * b for a, b in zip(ftr, map(int, time_interval.split(':')))]) / 60)

        if minutes_late > 480:
            minutes_late = 480
            messagebox.showinfo("Minutes Late", "Minutes Late Has reached 8 or more hours, Excess Minutes will not be "
                                                "calculated")
    except AttributeError:
        minutes_late = 480
        messagebox.showinfo("Minutes Late", "Minutes Late Has reached 8 or more hours, Excess Minutes will not be "
                                            "calculated")

    return minutes_late


# Compute regular hours
# def get_regular_hours(time_in, time_out, end_time):
#     try:
#         time_1 = datetime.strptime(time_in, "%I:%M:%S %p")
#         time_2 = datetime.strptime(time_out, "%I:%M:%S %p")
#
#         time_interval = time_2 - time_1
#
#         # Add 0 to single digit hours ex 8:00:00 --> 08:00:00
#         time_interval_string_lenght = len(str(time_interval))
#         eight_chars = time_interval_string_lenght < 8
#
#         if eight_chars:
#             time_interval = '0' + str(time_interval)
#
#         if str(time_interval) > '09:00:00':
#             time_interval = '09:00:00'
#             # reg hours is 9 hours when total time is 16 hours in - 7:00am & out - 11:00pm -
#             # break period point not triggered
#
#         # 12-Hour format
#         return time_interval
#     except TypeError:
#         return


# Compute total hours
def get_total_ot_hours(end_time, time_out):
    time_1 = datetime.strptime(end_time, "%H:%M:%S")
    time_2 = datetime.strptime(time_out, "%H:%M:%S")

    time_interval = time_2 - time_1
    return time_interval


# Compute undertime hours
def get_undertime_hours(end_time, time_out):
    time_1 = datetime.strptime(end_time, "%H:%M:%S")
    time_2 = datetime.strptime(time_out, "%H:%M:%S")

    time_interval = time_1 - time_2
    return time_interval


# Return Hours and Minutes from a given time string
def get_hours_and_minutes(time_in, time_out, sched_start, sched_end):
    try:
        in_time = datetime.strptime(time_in, "%I:%M:%S %p")
        out_time = datetime.strptime(time_out, "%I:%M:%S %p")
        in_sched = datetime.strptime(sched_start, "%I:%M:%S %p")
        out_sched = datetime.strptime(sched_end, "%I:%M:%S %p")

        if in_sched > in_time and out_sched >= out_time:
            # Early time in but not early time out
            time_interval = out_time - in_sched

        elif in_sched < in_time and out_sched <= out_time:
            # Late time in but not early time out
            time_interval = out_sched - in_time

        elif out_sched > out_time and in_sched >= in_time:
            # Early time out but not late
            time_interval = out_time - in_sched

        elif in_sched < in_time and out_sched > out_time:
            # Late time in and early time out
            time_interval = out_time - in_time

        elif in_sched > in_time and out_time > out_sched:
            # Early time in and Late time out
            time_interval = out_sched - in_sched

        else:
            # Time in is okay and time out is okay, limiter can be on
            time_interval = out_time - in_time

        # Add 0 to single digit hours ex 8:00:00 --> 08:00:00
        time_interval_string_length = len(str(time_interval))
        eight_chars = time_interval_string_length < 8

        if eight_chars:
            time_interval = '0' + str(time_interval)

        if str(time_interval) > '09:00:00':
            time_interval = '09:00:00'
            # reg hours is 9 hours when total time is 16 hours in - 7:00am & out - 11:00pm -
            # break period point not triggered

        # 12-Hour format
        return time_interval
    except TypeError:
        return
