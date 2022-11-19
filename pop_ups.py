from tkinter import messagebox
from datetime import datetime

weekday_number = datetime.today().isoweekday()
weekday = ""

if weekday_number == 1:
    weekday = 'Monday'
elif weekday_number == 2:
    weekday = 'Tuesday'
elif weekday_number == 3:
    weekday = 'Wednesday'
elif weekday_number == 4:
    weekday = 'Thursday'
elif weekday_number == 5:
    weekday = 'Friday'
elif weekday_number == 6:
    weekday = 'Saturday'
elif weekday_number == 7:
    weekday = 'Sunday'


def model_error_message():
    messagebox.showwarning('Trainer model', 'Trainer model is missing.\n'
                            'Make sure that the employee faces are collected and trained')


def camera_error_message():
    messagebox.showerror('Error', 'Camera is not detected, exiting program...')


def timeout_error_message():
    messagebox.showwarning('Warning', 'Employee can not time out before timing in')


def employee_detected_error_message():
    messagebox.showerror('Error', 'No recognized employee detected')


def db_saved_message():
    messagebox.showinfo('Info', 'Database server location saved, re-open the application for the changes to take effect')


def employee_no_schedule_warning():
    messagebox.showwarning('Warning', 'Employee has no schedule yet')


def employee_weekday_not_allowed():
    messagebox.showwarning('Warning', 'Employee is not scheduled to time in on ' + str(weekday))


def employee_inactive_message():
    messagebox.showwarning('Warning', 'Employee is not Active, attendance will not be recorded')


def employee_leave_message():
    messagebox.showinfo('Employee on a leave', 'Employee is on a leave today, attendance will not be recorded')



