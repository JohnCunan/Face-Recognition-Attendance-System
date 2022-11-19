import os
import sys
import PIL
import cv2
import time
import pickle
import threading
import numpy as np
from tkinter import *
import tkinter.font as font
from PIL import Image, ImageTk
from clock import get_time, get_date, display_clock
from play_audio import play_time_in_audio, play_time_out_audio
from pop_ups import model_error_message, camera_error_message, \
    db_saved_message, employee_detected_error_message, employee_no_schedule_warning, employee_weekday_not_allowed, \
    employee_leave_message
from time_diff import convert, get_total_ot_hours, get_undertime_hours, get_minutes_late
from time_diff import get_hours_and_minutes

# Check if the database is connected (get_attendance.py)
db_connected = False

try:
    from database_functions import connection, N_time_in, N_time_out, N_minutes_late
    from database_functions import N_get_employee_time_in, N_get_employee_time_out, N_add_accumulated_day_off, \
        N_current_holiday
    from database_functions import get_employee_schedule_start, get_employee_schedule_end
    from database_functions import N_check_and_insert_holiday, check_weekday, N_check_allowed_ot, N_get_employee_name
    from database_functions import insert_hours_and_minutes, insert_ot_hours, insert_undertime_hours_and_minutes
    from database_functions import N_get_single_sched_date, N_get_single_sched_start, N_get_single_sched_end, \
        get_attendance_hours, N_check_employee_leave
    from database_functions import N_get_position_id, N_get_position_name, N_get_department_id, N_get_department_name

    db_connected = True
except ImportError:
    pass

# Haar Cascade Variables
face_cascade = cv2.CascadeClassifier('cascades/data/haarcascade_frontalface_alt2.xml')
recognizer = cv2.face.LBPHFaceRecognizer_create()

# GUI Variables
root = Tk()  # Master Window
root.bind('<Escape>', lambda e: sys.exit())
root.title('Face Recognition Attendance System')  # Window Title
root.resizable(False, False)  # Make Window not resizable
root['background'] = '#396544'

window_width = 1040  # Width
window_height = 520  # Height

screen_width = root.winfo_screenwidth()  # Width of the screen
screen_height = root.winfo_screenheight()  # Height of the screen

# Calculate Starting X and Y coordinates for Window
x = (screen_width / 2) - (window_width / 2)
y = (screen_height / 2) - (window_height / 2)

root.geometry('%dx%d+%d+%d' % (window_width, window_height, x, y))

lmain = Label(root)
lmain.grid(padx=20, pady=20)

# Locate Trainer Model File Directory (YML)
try:
    recognizer.read('C:\\Face Recognition Files\\trainer.yml')
except cv2.error as e:
    model_error_message()
    sys.exit()

labels = {"person_name": 1}

# Load saved employee name labels (PICKLE)
with open('C:\\Face Recognition Files\\labels.pickle', 'rb') as f:
    og_labels = pickle.load(f)
    labels = {v: k for k, v in og_labels.items()}

# Camera Variable
cap = cv2.VideoCapture(0)

# Variable to use when inserting attendance record
detected_id = None
single_schedule_on = False
minutes_late = 0


# Loop makes capturing continuous
def show_frame():
    ret, frame = cap.read()

    # Check if the camera is connected
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    except cv2.error as e:
        camera_error_message()
        sys.exit()

    # Add black space at the bottom of the camera to make date and time text visible
    cv2.rectangle(frame, (0, 900), (2100, 440), (0, 0, 0), thickness=cv2.FILLED)

    # Display time and date in the camera
    cv2.putText(frame, 'Date: ' + get_date(), (7, 465), cv2.FONT_HERSHEY_TRIPLEX, 0.7, (255, 255, 255), 1)
    cv2.putText(frame, 'Time: ' + display_clock(), (330, 465), cv2.FONT_HERSHEY_TRIPLEX, 0.7, (255, 255, 255), 1)

    # Detect Face with Haar Cascade
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=3)  # 1.5 & 2

    # For every detected face identify the person
    for (x, y, w, h) in faces:
        # ROI = Region of interest, which is the face
        roi_gray = gray[y:y + h, x:x + w]
        roi_color = frame[y:y + h, x:x + w]

        # Draw Rectangle on the detected Region of Interest (face)
        color = (255, 0, 0)
        stroke = 4
        end_cord_x = x + w
        end_cord_y = y + h
        cv2.rectangle(frame, (x, y), (end_cord_x, end_cord_y), color, stroke)

        # Recognize Face
        # 'id' are names of recognized faces stored in the labels.pickle during training
        # 'conf' is the confidence level of the recognition
        id_, conf = recognizer.predict(roi_gray)

        # 30 <= conf <= 90 # Legacy Calibration before Sept 15 2022
        if 30 <= conf <= 90:
            font = cv2.FONT_HERSHEY_SIMPLEX
            name = N_get_employee_name(labels[id_])
            color = (255, 255, 255)
            stroke = 2
            cv2.putText(frame, name, (x, y), font, 1, color, stroke, cv2.LINE_AA)

            # Declare detected_face as a global variable for time in and time out function arguments
            global detected_id
            detected_id = labels[id_]

            if N_get_single_sched_date(detected_id, get_date()) == get_date():
                global single_schedule_on
                single_schedule_on = True


        else:
            font = cv2.FONT_HERSHEY_SIMPLEX
            name = 'Unknown'
            color = (255, 255, 255)
            stroke = 2
            cv2.putText(frame, name, (x, y), font, 1, color, stroke, cv2.LINE_AA)
            detected_id = None

    # Show camera in the window
    cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
    img = PIL.Image.fromarray(cv2image)
    imgtk = ImageTk.PhotoImage(image=img)
    lmain.imgtk = imgtk
    lmain.configure(image=imgtk)
    lmain.after(10, show_frame)


# Record attendance functions
# Employee time in
def btn_time_in():
    id = detected_id

    if id is None:
        id = " "

    employee = N_get_employee_name(id)
    employee_id = id

    time_in_allowed = check_weekday(id)
    employee_leave = N_check_employee_leave(employee_id, get_date())

    ###########################
    # Normal schedule time in #
    ###########################
    if not single_schedule_on:
        if employee is not None:
            if employee_leave:
                employee_leave_message()
            else:
                if time_in_allowed == 'True':
                    play_time_in_audio()

                    N_time_in(connection, detected_employee_id=employee_id)

                    # Check employee start schedule
                    try:
                        start_time = convert(get_employee_schedule_start(employee_id))
                    except:
                        employee_no_schedule_warning()
                        return

                    in_time = convert(get_time())
                    late = None

                    # Check if employee is late
                    if in_time > start_time:
                        late = True  # Employee is late
                        minutes_late = get_minutes_late(get_employee_schedule_start(employee_id), get_time())

                        # Grace period
                        if minutes_late > 10:
                            # Grace period triggered
                            N_minutes_late(connection, detected_employee=employee_id,
                                           minutes=minutes_late)
                        else:
                            # Grace period not triggered
                            N_minutes_late(connection, detected_employee=employee_id,
                                           minutes=0)
                    else:
                        late = False  # Employee is not late
                        N_minutes_late(connection, detected_employee=detected_id, minutes=0)

                    # Record into DB if late or not
                    # late_or_not(conn, detected_employee=employee_id, state=late)
                    N_add_accumulated_day_off(employee_id)
                else:
                    employee_weekday_not_allowed()
        else:
            employee_detected_error_message()
            return
    ###########################
    # Single schedule time in #
    ###########################
    else:
        if employee is not None:
            play_time_in_audio()

            # NEW
            N_time_in(connection, detected_employee_id=employee_id)

            # Check employee start schedule
            try:
                start_time = convert(N_get_single_sched_start(employee_id))
            except:
                employee_no_schedule_warning()
                return

            in_time = convert(get_time())
            late = None

            # Check if employee is late
            if in_time > start_time:
                late = True  # Employee is late
                minutes_late = get_minutes_late(N_get_single_sched_start(employee_id), get_time())

                # Grace period
                if minutes_late > 10:
                    # Grace period triggered
                    N_minutes_late(connection, detected_employee=employee_id,
                                   minutes=minutes_late)
                else:
                    # Grace period not triggered
                    N_minutes_late(connection, detected_employee=employee_id,
                                   minutes=0)
            else:
                late = False  # Employee is not late
                N_minutes_late(connection, detected_employee=detected_id, minutes=0)

            # Record into DB if late or not
            # late_or_not(conn, detected_employee=employee_id, state=late)
            N_add_accumulated_day_off(employee_id)
        else:
            employee_detected_error_message()
            return

    # Details displayed when timing in
    employee_id_content_label = Label(
        root, text=detected_id, bg='#396544', fg='white', font='none 12 bold'
    )
    employee_id_content_label.place(x=840, y=70)

    employee_name_content_label = Label(
        root, text=employee, bg='#396544', fg='white', font='none 12 bold'
    )
    employee_name_content_label.place(x=840, y=100)

    position_id = N_get_position_id(detected_id)
    position_name = str(N_get_position_name(position_id))

    position_content_label = Label(
        root, text=position_name, bg='#396544', fg='white', font='none 12 bold'
    )
    position_content_label.place(x=840, y=130)

    department_id = N_get_department_id(detected_id)
    department_name = str(N_get_department_name(department_id))

    department_content_label = Label(
        root, text=department_name, bg='#396544', fg='white', font='none 12 bold'
    )
    department_content_label.place(x=840, y=160)

    time_in_display = str(N_get_employee_time_in(detected_id, get_date()))

    schedule_in_content_label = Label(
        root, text=time_in_display, bg='#396544', fg='white', font='none 12 bold'
    )
    schedule_in_content_label.place(x=840, y=190)

    time_out_display = str(N_get_employee_time_out(detected_id, get_date()))

    schedule_out_content_label = Label(
        root, text=time_out_display, bg='#396544', fg='white', font='none 12 bold'
    )
    schedule_out_content_label.place(x=840, y=220)

    holiday = N_current_holiday()

    holiday_content_label = Label(
        root, text=holiday, bg='#396544', fg='white', font='none 10 bold'
    )
    holiday_content_label.place(x=830, y=250)


# Break Checker
def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end


# Employee time out
def btn_time_out():
    id = detected_id

    if id is None:
        id = " "

    employee = N_get_employee_name(id)
    employee_id = id

    ###################
    # Normal time out #
    ###################
    if not single_schedule_on:
        if employee is not None:
            play_time_out_audio()

            # NEW
            N_time_out(connection, detected_employee=detected_id)

            # Calculate Total Hours
            New_employee_time_in = N_get_employee_time_in(detected_id, get_date())
            New_employee_time_out = N_get_employee_time_out(detected_id, get_date())

            hours_and_mins = get_hours_and_minutes(New_employee_time_in, New_employee_time_out,
                                                   get_employee_schedule_start(detected_id), get_employee_schedule_end(detected_id))

            # NEW
            New_end_time = convert(get_employee_schedule_end(detected_id)).rstrip()
            New_out_time = convert(get_time()).rstrip()

            # NEW
            insert_hours_and_minutes(connection, detected_employee=detected_id, total_time=hours_and_mins,
                                     break_period_point=time_in_range(New_employee_time_in, New_employee_time_out,
                                                                      '12:00:00 PM'))

            # Calculate overtime
            New_allowed_ot = N_check_allowed_ot(detected_id)
            New_ot_total = '00:00:00'

            if New_out_time < New_end_time:
                New_u_hours_minutes = get_undertime_hours(New_end_time, New_out_time)
                insert_undertime_hours_and_minutes(connection, detected_employee=detected_id,
                                                   total_undertime_hours=New_u_hours_minutes, check=True)
            else:
                insert_undertime_hours_and_minutes(connection, detected_employee=detected_id,
                                                   total_undertime_hours='00:00:00', check=False)

            # NEW
            N_check_and_insert_holiday(str(employee_id), hours_and_mins,
                                       time_in_range(New_employee_time_in, New_employee_time_out, '12:00:00 PM'))

            if New_allowed_ot == 'True':
                if New_out_time > New_end_time:
                    New_ot_total = get_total_ot_hours(New_end_time, New_out_time)
                    if str(New_ot_total) > '4:00:00':
                        New_ot_total = '04:00:00'

            insert_ot_hours(connection, detected_employee=detected_id, total_ot_hours=New_ot_total)

        else:
            employee_detected_error_message()
            return

    ############################
    # Single schedule time out #
    ############################
    else:
        if employee is not None:
            play_time_out_audio()

            N_time_out(connection, detected_employee=detected_id)

            # Calculate Total Hours
            New_employee_time_in = N_get_employee_time_in(detected_id, get_date())
            New_employee_time_out = N_get_employee_time_out(detected_id, get_date())

            hours_and_mins = get_hours_and_minutes(New_employee_time_in, New_employee_time_out,
                                                   N_get_single_sched_start(detected_id), N_get_single_sched_end(detected_id))

            # if Time in at PM then Time out at AM remove the '-1 day' from the total hours
            # if str(t_hours).find('-') != -1:
            #     t_hours = str(t_hours)[8:]

            # Insert employee total hours into DB
            # total_hours(conn, detected_employee=detected_id, total_work_hours=t_hours)

            # try:
            #     (h, m, s) = str(t_hours).split(':')
            # except ValueError:
            #     # Employee timing out without time in record error occurs here
            #     # is already caught at getattendance.py line 125
            #     return

            # total_hours_converted = "{:.2f}".format((int(h) * 3600 + int(m) * 60 + int(s)) / 3600)

            New_end_time = convert(N_get_single_sched_end(detected_id)).rstrip()
            New_out_time = convert(get_time()).rstrip()

            if New_out_time < New_end_time:
                New_u_hours_minutes = get_undertime_hours(New_end_time, New_out_time)
                insert_undertime_hours_and_minutes(connection, detected_employee=detected_id,
                                                   total_undertime_hours=New_u_hours_minutes, check=True)
            else:
                insert_undertime_hours_and_minutes(connection, detected_employee=detected_id,
                                                   total_undertime_hours='00:00:00', check=False)

            N_check_and_insert_holiday(str(employee_id), hours_and_mins,
                                       time_in_range(New_employee_time_in, New_employee_time_out, '12:00:00 PM'))

            insert_hours_and_minutes(connection, detected_employee=detected_id, total_time=hours_and_mins,
                                     break_period_point=time_in_range(New_employee_time_in, New_employee_time_out,
                                                                      '12:00:00 PM'))

            # Calculate overtime
            New_allowed_ot = N_check_allowed_ot(detected_id)
            New_ot_total = '00:00:00'

            if New_allowed_ot == 'True':
                if New_out_time > New_end_time:
                    New_ot_total = get_total_ot_hours(New_end_time, New_out_time)
                    if str(New_ot_total) > '4:00:00':
                        New_ot_total = '04:00:00'

            insert_ot_hours(connection, detected_employee=detected_id, total_ot_hours=New_ot_total)

        else:
            employee_detected_error_message()
            return

    # Details displayed when timing in
    employee_id_content_label = Label(
        root, text=detected_id, bg='#396544', fg='white', font='none 12 bold'
    )
    employee_id_content_label.place(x=840, y=70)

    employee_name_content_label = Label(
        root, text=employee, bg='#396544', fg='white', font='none 12 bold'
    )
    employee_name_content_label.place(x=840, y=100)

    position_id = N_get_position_id(detected_id)
    position_name = str(N_get_position_name(position_id))

    position_content_label = Label(
        root, text=position_name, bg='#396544', fg='white', font='none 12 bold'
    )
    position_content_label.place(x=840, y=130)

    department_id = N_get_department_id(detected_id)
    department_name = str(N_get_department_name(department_id))

    department_content_label = Label(
        root, text=department_name, bg='#396544', fg='white', font='none 12 bold'
    )
    department_content_label.place(x=840, y=160)

    time_in_display = str(N_get_employee_time_in(detected_id, get_date()))

    schedule_in_content_label = Label(
        root, text=time_in_display, bg='#396544', fg='white', font='none 12 bold'
    )
    schedule_in_content_label.place(x=840, y=190)

    time_out_display = str(N_get_employee_time_out(detected_id, get_date()))

    schedule_out_content_label = Label(
        root, text=time_out_display, bg='#396544', fg='white', font='none 12 bold'
    )
    schedule_out_content_label.place(x=840, y=220)

    holiday = N_current_holiday()

    holiday_content_label = Label(
        root, text=holiday, bg='#396544', fg='white', font='none 10 bold'
    )
    holiday_content_label.place(x=830, y=250)


########################
# -- USER INTERFACE -- #
########################

# Load saved db name
with open('Persistence Files/db_name.pickle', 'rb') as f:
    database_name = pickle.load(f)

# Time in and time out buttons
button_font = font.Font(family='Tahoma', size=16, underline=0)

time_in_button = Button(root, text='Time In', height=1, width=10, font=button_font, command=btn_time_in)
time_in_button.place(x=690, y=420)

time_out_button = Button(root, text='Time Out', height=1, width=10, font=button_font, command=btn_time_out)
time_out_button.place(x=850, y=420)

if not db_connected:
    time_in_button.config(state=DISABLED)
    time_out_button.config(state=DISABLED)


def close_db_error_window():
    sys.exit()


def open_db_error_window():
    db_error_window = Tk()
    db_error_window.geometry('400x150')
    db_error_window.resizable(False, False)
    db_error_window['background'] = '#396544'
    db_error_window.title('Enter database address')

    db_error_label = Label(db_error_window, text='Enter Database Server Address', bg='#396544',
                           fg='white', font='none 10 bold')
    db_error_label.place(x=100, y=20)

    global db_error_textbox
    db_error_textbox = Entry(db_error_window, width=50)
    db_error_textbox.place(x=50, y=50)

    save_button = Button(db_error_window, text='            Save            ',
                         command=save_db_name_error_window)
    save_button.place(x=150, y=80)

    db_error_window.protocol('WM_DELETE_WINDOW', close_db_error_window)


def open_db_change_window():
    db_error_window = Tk()
    db_error_window.geometry('400x150')
    db_error_window.resizable(False, False)
    db_error_window['background'] = '#396544'
    db_error_window.title('Enter database address')

    db_error_label = Label(db_error_window, text='Enter Database Server Address', bg='#396544',
                           fg='white', font='none 10 bold')
    db_error_label.place(x=100, y=20)

    global db_error_textbox
    db_error_textbox = Entry(db_error_window, width=50)
    db_error_textbox.place(x=50, y=50)

    save_button = Button(db_error_window, text='            Save            ',
                         command=save_db_name_error_window)
    save_button.place(x=150, y=80)


def save_db_name_error_window():
    # Create persistence file
    db_address = db_error_textbox.get()
    with open('Persistence Files/db_name.pickle', 'wb') as f:
        pickle.dump(db_address, f)

    db_saved_message()
    sys.exit()


# Locate db button
locate_db_button = Button(root, text='Locate Database Server ', command=open_db_change_window)
locate_db_button.place(x=770, y=475)

# Employee details text
employee_details_label = Label(
    root, text='Employee Details', bg='#396544', fg='white', font='none 14 bold'
)
employee_details_label.place(x=750, y=20)

employee_id_details_label = Label(
    root, text='Employee ID:', bg='#396544', fg='white', font='none 14 bold'
)
employee_id_details_label.place(x=680, y=70)

employee_name_details_label = Label(
    root, text='Employee Name:', bg='#396544', fg='white', font='none 14 bold'
)
employee_name_details_label.place(x=680, y=100)

position_details_label = Label(
    root, text='Position:', bg='#396544', fg='white', font='none 14 bold'
)
position_details_label.place(x=680, y=130)

department_details_label = Label(
    root, text='Department:', bg='#396544', fg='white', font='none 14 bold'
)
department_details_label.place(x=680, y=160)

schedule_in_details_label = Label(
    root, text='Time In:', bg='#396544', fg='white', font='none 14 bold'
)
schedule_in_details_label.place(x=680, y=190)

schedule_out_details_label = Label(
    root, text='Time Out:', bg='#396544', fg='white', font='none 14 bold'
)
schedule_out_details_label.place(x=680, y=220)

holiday_details_label = Label(
    root, text='Holiday:', bg='#396544', fg='white', font='none 14 bold'
)
holiday_details_label.place(x=680, y=250)

if not db_connected:
    open_db_error_window()
    root.withdraw()
else:
    show_frame()

root.mainloop()
