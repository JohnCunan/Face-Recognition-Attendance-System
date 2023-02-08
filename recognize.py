import sys
import PIL
import cv2
import pickle
from tkinter import *
import tkinter.font as font
from datetime import datetime
from datetime import timedelta
from PIL import Image, ImageTk
from clock import get_time, get_date, display_clock
from play_audio import play_time_in_audio, play_time_out_audio
from pop_ups import model_error_message, camera_error_message, \
    db_saved_message, employee_detected_error_message, employee_weekday_not_allowed, \
    employee_leave_message, wrong_password_message, timeout_error_message, employee_inactive_message
from time_diff import convert, get_total_ot_hours, get_undertime_hours, get_minutes_late
from time_diff import get_hours_and_minutes
from pop_ups import no_employee_select_message

# Check if the database is connected (get_attendance.py)
db_connected = False

try:
    from database_functions import connection, N_time_in, N_time_out, N_minutes_late
    from database_functions import N_get_employee_time_in, N_get_employee_time_out, \
        N_current_holiday, get_employee_status, get_employee_list, insert_hours_and_minutes_single_sched
    from database_functions import get_employee_schedule_start, get_employee_schedule_end, get_employee_id
    from database_functions import N_check_and_insert_holiday, check_weekday, N_check_allowed_ot, N_get_employee_name
    from database_functions import insert_hours_and_minutes, insert_ot_hours, insert_undertime_hours_and_minutes
    from database_functions import N_get_single_sched_date, N_get_single_sched_start, N_get_single_sched_end, \
        get_attendance_hours, N_check_employee_leave, get_employee_break, check_employee_overtime
    from database_functions import N_get_position_id, N_get_position_name, N_get_department_id, N_get_department_name, \
        get_single_sched_break, get_employee_list_id, check_and_insert_rest_day, time_out_no_in

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

window_width = 1070  # Width
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
no_camera_image = r'C:\Users\John Cunan\Desktop\Attendance System\Icon\blank.png'
camera_detected = False


# Loop makes capturing continuous
def show_frame():
    ret, frame = cap.read()

    # Check if the camera is connected
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        camera_detected = True
    except cv2.error as e:
        camera_detected = False
        # camera_error_message()
        src = cv2.imread(no_camera_image)
        gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        # cv2.imshow(frame, gray)
        # sys.exit()

    # Add black space at the bottom of the camera to make date and time text visible
    cv2.rectangle(frame, (0, 900), (2100, 440), (0, 0, 0), thickness=cv2.FILLED)

    # Display time and date in the camera
    cv2.putText(frame, 'Date: ' + get_date(), (7, 465), cv2.FONT_HERSHEY_TRIPLEX, 0.7, (255, 255, 255), 1)
    cv2.putText(frame, 'Time: ' + display_clock(), (330, 465), cv2.FONT_HERSHEY_TRIPLEX, 0.7, (255, 255, 255), 1)

    # Detect Face with Haar Cascade
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=3)  # 1.5 & 2, 1.3 & 3 (Default)

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

        # Uncomment the lines below to view the confidence level
        # print('Confidence Level: ' + str(conf))
        # print('Current Employee Recognized: ' + str(labels[id_]))
        # print(labels)

        # 30 <= conf <= 90 # Legacy Calibration before Sept 15 2022
        # conf < 50 in final defense
        # conf < num - The lower the "num" the more unregistered faces are likely to be detected
        # conf = confidence level of the prediction of the AI, the higher the number the lower the confidence
        # Example: 0 - 20 is very confident, 21-50 confident, 51 above is not confident
        # Adjusting the comparison of 'conf' variable with the 'num' -
        # can determine the accuracy of detecting unregistered face
        # conf < 50 has a more strict approach in recognizing faces
        # This calibration is suitable for recognizing faces with proper lighting and actual use
        # conf < 90 has a more lenient approach in recognizing faces
        # however it is less likely to detect unregistered faces, it is suitable use in testing and debugging the system
        if conf < 90:
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
                single_schedule_on = False
        else:
            font = cv2.FONT_HERSHEY_SIMPLEX
            name = 'Unknown'
            color = (255, 255, 255)
            stroke = 2
            cv2.putText(frame, name, (x, y), font, 1, color, stroke, cv2.LINE_AA)
            detected_id = None

    # Show camera in the window
    if camera_detected:
        cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        img = PIL.Image.fromarray(cv2image)
        imgtk = ImageTk.PhotoImage(image=img)
        lmain.imgtk = imgtk
        lmain.configure(image=imgtk)
        lmain.after(10, show_frame)
    else:
        cv2image = cv2.cvtColor(src, cv2.COLOR_BGR2RGBA)
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
    employee_status = get_employee_status(employee_id)

    ###########################
    # Normal schedule time in #
    ###########################
    if not single_schedule_on:
        if employee is not None:
            if employee_status == 'Active':
                if employee_leave:
                    employee_leave_message()
                else:
                    if time_in_allowed == 'True':
                        play_time_in_audio()

                        N_time_in(connection, detected_employee_id=employee_id)

                        # Check employee start schedule
                        start_time = convert(get_employee_schedule_start(employee_id))
                        # try:
                        #     start_time = convert(get_employee_schedule_start(employee_id))
                        # except:
                        #     employee_no_schedule_warning()
                        #     return

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

                    else:
                        employee_weekday_not_allowed()
            else:
                employee_inactive_message()
        else:
            employee_detected_error_message()
            return
    ###########################
    # Single schedule time in #
    ###########################
    else:
        if employee is not None:
            if employee_status == 'Active':
                if employee_leave:
                    employee_leave_message()
                else:
                    play_time_in_audio()

                    # NEW
                    N_time_in(connection, detected_employee_id=employee_id)

                    # Check employee start schedule
                    start_time = convert(N_get_single_sched_start(employee_id))
                    # try:
                    #     start_time = convert(N_get_single_sched_start(employee_id))
                    # except:
                    #     employee_no_schedule_warning()
                    #     return

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

            else:
                employee_inactive_message()
        else:
            employee_detected_error_message()
            return

    ###########################
    #      Clear Labels       #
    ###########################
    C_employee_id_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    C_employee_name_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    position_id = N_get_position_id(detected_id)
    position_name = str(N_get_position_name(position_id))
    C_position_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    department_id = N_get_department_id(detected_id)
    department_name = str(N_get_department_name(department_id))
    C_department_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    time_in_display = str(N_get_employee_time_in(detected_id, get_date()))
    C_schedule_in_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    time_out_display = str(N_get_employee_time_out(detected_id, get_date()))
    C_schedule_out_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    holiday = N_current_holiday()
    C_holiday_content_label = Label(
        root, text="                                                                       ", bg='#396544', fg='white', font='none 10 bold'
    )

    C_employee_id_content_label.place(x=840, y=70)
    C_employee_name_content_label.place(x=840, y=100)
    C_position_content_label.place(x=840, y=130)
    C_department_content_label.place(x=840, y=160)
    C_schedule_in_content_label.place(x=840, y=190)
    C_schedule_out_content_label.place(x=840, y=220)
    C_holiday_content_label.place(x=830, y=250)

    ###########################
    #     Display Labels      #
    ###########################
    # Details displayed when timing in

    employee_id_content_label = Label(
        root, text=detected_id, bg='#396544', fg='white', font='none 12 bold'
    )

    employee_name_content_label = Label(
        root, text=employee, bg='#396544', fg='white', font='none 12 bold'
    )

    position_id = N_get_position_id(detected_id)
    position_name = str(N_get_position_name(position_id))
    position_content_label = Label(
        root, text=position_name, bg='#396544', fg='white', font='none 12 bold'
    )

    department_id = N_get_department_id(detected_id)
    department_name = str(N_get_department_name(department_id))
    department_content_label = Label(
        root, text=department_name, bg='#396544', fg='white', font='none 12 bold'
    )

    time_in_display = str(N_get_employee_time_in(detected_id, get_date()))
    schedule_in_content_label = Label(
        root, text=time_in_display, bg='#396544', fg='white', font='none 12 bold'
    )

    time_out_display = str(N_get_employee_time_out(detected_id, get_date()))
    schedule_out_content_label = Label(
        root, text=time_out_display, bg='#396544', fg='white', font='none 12 bold'
    )

    holiday = N_current_holiday()
    holiday_content_label = Label(
        root, text=holiday, bg='#396544', fg='white', font='none 10 bold'
    )

    employee_id_content_label.place(x=840, y=70)
    employee_name_content_label.place(x=840, y=100)
    position_content_label.place(x=840, y=130)
    department_content_label.place(x=840, y=160)
    schedule_in_content_label.place(x=840, y=190)
    schedule_out_content_label.place(x=840, y=220)
    holiday_content_label.place(x=830, y=250)

######################
#    Break Checker   #
######################


def time_in_range(start, end, x, y):
    """Return true if x is in the range [start, end]"""
    if start is None:
        # POPS UP 2 TIMES
        # timeout_error_message()
        time_out_no_in(connection, detected_employee_id=detected_id)
        return
    elif end is None:
        return
    else:
        if start <= end:
            return start <= x <= end
        else:
            return start <= x or x <= end and start <= y or y <= end


########################
#   Employee time out  #
########################


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

            break_time = datetime.strptime(get_employee_break(detected_id), "%I:%M:%S %p")
            break_end_24 = break_time + timedelta(hours=1)
            break_end_12 = datetime.strftime(break_end_24, "%I:%M:%S %p")

            # NEW
            insert_hours_and_minutes(connection, detected_employee=detected_id, total_time=hours_and_mins,
                                     break_period_point=time_in_range(New_employee_time_in, New_employee_time_out,
                                                                      get_employee_break(detected_id), break_end_12))

            # Calculate overtime
            New_allowed_ot = check_employee_overtime(detected_id, get_date())
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
                                       time_in_range(New_employee_time_in, New_employee_time_out,
                                                     get_employee_break(detected_id), break_end_12))

            check_and_insert_rest_day(str(employee_id), hours_and_mins,
                                      time_in_range(New_employee_time_in, New_employee_time_out,
                                                    get_employee_break(detected_id), break_end_12))

            if New_allowed_ot:
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


            New_end_time = convert(N_get_single_sched_end(detected_id)).rstrip()
            New_out_time = convert(get_time()).rstrip()

            break_time = datetime.strptime(get_single_sched_break(detected_id), "%I:%M:%S %p")
            break_end_24 = break_time + timedelta(hours=1)
            break_end_12 = datetime.strftime(break_end_24, "%I:%M:%S %p")

            insert_hours_and_minutes_single_sched(connection, detected_employee=detected_id, total_time=hours_and_mins,
                                     break_period_point=time_in_range(New_employee_time_in, New_employee_time_out,
                                                                      get_single_sched_break(detected_id), break_end_12))

            if New_out_time < New_end_time:
                New_u_hours_minutes = get_undertime_hours(New_end_time, New_out_time)
                insert_undertime_hours_and_minutes(connection, detected_employee=detected_id,
                                                   total_undertime_hours=New_u_hours_minutes, check=True)
            else:
                insert_undertime_hours_and_minutes(connection, detected_employee=detected_id,
                                                   total_undertime_hours='00:00:00', check=False)

            N_check_and_insert_holiday(str(employee_id), hours_and_mins,
                                       time_in_range(New_employee_time_in, New_employee_time_out,
                                                     get_single_sched_break(detected_id), break_end_12))

            check_and_insert_rest_day(str(employee_id), hours_and_mins,
                                      time_in_range(New_employee_time_in, New_employee_time_out,
                                                    get_single_sched_break(detected_id), break_end_12))

            # Calculate overtime
            New_allowed_ot = check_employee_overtime(detected_id, get_date())
            New_ot_total = '00:00:00'

            if New_allowed_ot:
                if New_out_time > New_end_time:
                    New_ot_total = get_total_ot_hours(New_end_time, New_out_time)
                    if str(New_ot_total) > '4:00:00':
                        New_ot_total = '04:00:00'

            insert_ot_hours(connection, detected_employee=detected_id, total_ot_hours=New_ot_total)

        else:
            employee_detected_error_message()
            return

    ###########################
    #      Clear Labels       #
    ###########################
    C_employee_id_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    C_employee_name_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    position_id = N_get_position_id(detected_id)
    position_name = str(N_get_position_name(position_id))
    C_position_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    department_id = N_get_department_id(detected_id)
    department_name = str(N_get_department_name(department_id))
    C_department_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    time_in_display = str(N_get_employee_time_in(detected_id, get_date()))
    C_schedule_in_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    time_out_display = str(N_get_employee_time_out(detected_id, get_date()))
    C_schedule_out_content_label = Label(
        root, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
    )

    holiday = N_current_holiday()
    C_holiday_content_label = Label(
        root, text="                                                                       ", bg='#396544', fg='white', font='none 10 bold'
    )

    C_employee_id_content_label.place(x=840, y=70)
    C_employee_name_content_label.place(x=840, y=100)
    C_position_content_label.place(x=840, y=130)
    C_department_content_label.place(x=840, y=160)
    C_schedule_in_content_label.place(x=840, y=190)
    C_schedule_out_content_label.place(x=840, y=220)
    C_holiday_content_label.place(x=830, y=250)

    ###########################
    #     Display Labels      #
    ###########################
    # Details displayed when timing in

    employee_id_content_label = Label(
        root, text=detected_id, bg='#396544', fg='white', font='none 12 bold'
    )

    employee_name_content_label = Label(
        root, text=employee, bg='#396544', fg='white', font='none 12 bold'
    )

    position_id = N_get_position_id(detected_id)
    position_name = str(N_get_position_name(position_id))
    position_content_label = Label(
        root, text=position_name, bg='#396544', fg='white', font='none 12 bold'
    )

    department_id = N_get_department_id(detected_id)
    department_name = str(N_get_department_name(department_id))
    department_content_label = Label(
        root, text=department_name, bg='#396544', fg='white', font='none 12 bold'
    )

    time_in_display = str(N_get_employee_time_in(detected_id, get_date()))
    schedule_in_content_label = Label(
        root, text=time_in_display, bg='#396544', fg='white', font='none 12 bold'
    )

    time_out_display = str(N_get_employee_time_out(detected_id, get_date()))
    schedule_out_content_label = Label(
        root, text=time_out_display, bg='#396544', fg='white', font='none 12 bold'
    )

    holiday = N_current_holiday()
    holiday_content_label = Label(
        root, text=holiday, bg='#396544', fg='white', font='none 10 bold'
    )

    employee_id_content_label.place(x=840, y=70)
    employee_name_content_label.place(x=840, y=100)
    position_content_label.place(x=840, y=130)
    department_content_label.place(x=840, y=160)
    schedule_in_content_label.place(x=840, y=190)
    schedule_out_content_label.place(x=840, y=220)
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
time_in_button.place(x=720, y=420)

time_out_button = Button(root, text='Time Out', height=1, width=10, font=button_font, command=btn_time_out)
time_out_button.place(x=880, y=420)

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


###########################
# -- MANUAL ATTENDANCE -- #
###########################
employee_list = get_employee_list()
employee_names = []
counter = 0
manual_single_sched_on = False

while counter < len(employee_list):
    employee_names.append(N_get_employee_name(employee_list[counter]))
    counter += 1

# for index in employee_list:
#     employee_names.append(N_get_employee_name(employee_list[index]))


def open_manual_attendance_window():
    from tkinter import ttk

    manual_attendance_window = Tk()
    manual_attendance_window.geometry('500x550')
    manual_attendance_window.resizable(False, False)
    manual_attendance_window['background'] = '#396544'
    manual_attendance_window.title('Manually Time-in or Time-out')

    select_employee_label = Label(manual_attendance_window, text='Select an Employee: ', bg='#396544',
                           fg='white', font='none 13 bold')

    tv = ttk.Treeview(manual_attendance_window, columns=(1, 2), show="headings", height="5", selectmode='browse')

    tv.heading(1, text="Employee ID")
    tv.column(1, minwidth=0, width=220, stretch=NO)

    tv.heading(2, text="Employee Name")
    tv.column(2, minwidth=0, width=220, stretch=NO)

    for i in get_employee_list_id():
        tv.insert('', 'end', values=i)

    def enable_buttons(event):
        manual_time_in.config(state=NORMAL)
        manual_time_out.config(state=NORMAL)

    tv.bind('<ButtonRelease-1>', enable_buttons)

    def get_selected_id():
        selected_item = tv.focus()
        details = tv.item(selected_item)

        try:
            return details.get("values")[0]
        except IndexError:
            no_employee_select_message()
            return

    def time_in():
        id = str(get_selected_id())
        manual_single_sched_on = False
        time_in_allowed = check_weekday(id)
        employee_leave = N_check_employee_leave(id, get_date())

        if N_get_single_sched_date(id, get_date()) == get_date():
            manual_single_sched_on = True

        if not manual_single_sched_on:
            if id is not None:
                if employee_leave:
                    employee_leave_message()
                else:
                    if time_in_allowed == 'True':
                        play_time_in_audio()

                        N_time_in(connection, detected_employee_id=id)

                        # Check employee start schedule
                        start_time = convert(get_employee_schedule_start(id))
                        # try:
                        #     start_time = convert(get_employee_schedule_start(id))
                        # except:
                        #     employee_no_schedule_warning()
                        #     return

                        in_time = convert(get_time())
                        late = None

                        # Check if employee is late
                        if in_time > start_time:
                            late = True  # Employee is late
                            minutes_late = get_minutes_late(get_employee_schedule_start(id), get_time())

                            # Grace period
                            if minutes_late > 10:
                                # Grace period triggered
                                N_minutes_late(connection, detected_employee=id,
                                               minutes=minutes_late)
                            else:
                                # Grace period not triggered
                                N_minutes_late(connection, detected_employee=id,
                                               minutes=0)
                        else:
                            late = False  # Employee is not late
                            N_minutes_late(connection, detected_employee=id, minutes=0)

                        # Record into DB if late or not
                        # late_or_not(conn, detected_employee=employee_id, state=late)

                    else:
                        employee_weekday_not_allowed()
            else:
                employee_detected_error_message()
                return
        ###########################
        # Single schedule time in #
        ###########################
        else:
            if id is not None:
                play_time_in_audio()

                # NEW
                N_time_in(connection, detected_employee_id=id)

                # Check employee start schedule
                start_time = convert(N_get_single_sched_start(id))
                # try:
                #     start_time = convert(N_get_single_sched_start(id))
                # except:
                #     employee_no_schedule_warning()
                #     return

                in_time = convert(get_time())
                late = None

                # Check if employee is late
                if in_time > start_time:
                    late = True  # Employee is late
                    minutes_late = get_minutes_late(N_get_single_sched_start(id), get_time())

                    # Grace period
                    if minutes_late > 10:
                        # Grace period triggered
                        N_minutes_late(connection, detected_employee=id,
                                       minutes=minutes_late)
                    else:
                        # Grace period not triggered
                        N_minutes_late(connection, detected_employee=id,
                                       minutes=0)
                else:
                    late = False  # Employee is not late
                    N_minutes_late(connection, detected_employee=id, minutes=0)

                # Record into DB if late or not
                # late_or_not(conn, detected_employee=employee_id, state=late)

            else:
                employee_detected_error_message()
                return

        ###########################
        #      Clear Labels       #
        ###########################
        C_employee_id_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
        )
        C_employee_name_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
        )
        C_position_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
        )
        C_department_content_label = Label(
            manual_attendance_window, text="                                                                       ", bg='#396544', fg='white', font='none 12 bold'
        )
        C_schedule_in_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
        )
        C_schedule_out_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white', font='none 12 bold'
        )
        C_holiday_content_label = Label(
            manual_attendance_window, text="                                                                       ", bg='#396544',
            fg='white',
            font='none 10 bold'
        )

        C_employee_id_content_label.place(x=200, y=300)
        C_employee_name_content_label.place(x=200, y=330)
        C_position_content_label.place(x=200, y=360)
        C_department_content_label.place(x=200, y=390)
        C_schedule_in_content_label.place(x=200, y=420)
        C_schedule_out_content_label.place(x=200, y=450)
        C_holiday_content_label.place(x=200, y=480)

        ###########################
        #     Display Labels      #
        ###########################
        emp_id = str(get_selected_id())

        manual_employee_id_content_label = Label(
            manual_attendance_window, text=emp_id, bg='#396544', fg='white', font='none 12 bold'
        )
        manual_employee_name_content_label = Label(
            manual_attendance_window, text=N_get_employee_name(emp_id), bg='#396544', fg='white', font='none 12 bold'
        )
        position_id = N_get_position_id(emp_id)
        position_name = str(N_get_position_name(position_id))
        manual_position_content_label = Label(
            manual_attendance_window, text=position_name, bg='#396544', fg='white', font='none 12 bold'
        )
        department_id = N_get_department_id(emp_id)
        department_name = str(N_get_department_name(department_id))
        manual_department_content_label = Label(
            manual_attendance_window, text=department_name, bg='#396544', fg='white', font='none 12 bold'
        )
        time_in_display = str(N_get_employee_time_in(emp_id, get_date()))
        manual_schedule_in_content_label = Label(
            manual_attendance_window, text=time_in_display, bg='#396544', fg='white', font='none 12 bold'
        )
        time_out_display = str(N_get_employee_time_out(emp_id, get_date()))
        manual_schedule_out_content_label = Label(
            manual_attendance_window, text=time_out_display, bg='#396544', fg='white', font='none 12 bold'
        )
        holiday = N_current_holiday()
        manual_holiday_content_label = Label(
            manual_attendance_window, text=holiday, bg='#396544', fg='white', font='none 10 bold'
        )

        manual_employee_id_content_label.place(x=200, y=300)
        manual_employee_name_content_label.place(x=200, y=330)
        manual_position_content_label.place(x=200, y=360)
        manual_department_content_label.place(x=200, y=390)
        manual_schedule_in_content_label.place(x=200, y=420)
        manual_schedule_out_content_label.place(x=200, y=450)
        manual_holiday_content_label.place(x=200, y=480)

    def time_out():
        id = str(get_selected_id())
        manual_single_sched_on = False
        if N_get_single_sched_date(id, get_date()) == get_date():
            manual_single_sched_on = True

        global  detected_id
        detected_id = id
        ###################
        # Normal time out #
        ###################
        if not manual_single_sched_on:
            if id is not None:
                play_time_out_audio()

                # NEW
                N_time_out(connection, detected_employee=id)

                # Calculate Total Hours
                New_employee_time_in = N_get_employee_time_in(id, get_date())
                New_employee_time_out = N_get_employee_time_out(id, get_date())

                hours_and_mins = get_hours_and_minutes(New_employee_time_in, New_employee_time_out,
                                                       get_employee_schedule_start(id),
                                                       get_employee_schedule_end(id))


                # NEW
                New_end_time = convert(get_employee_schedule_end(id)).rstrip()
                New_out_time = convert(get_time()).rstrip()

                break_time = datetime.strptime(get_employee_break(id), "%I:%M:%S %p")
                break_end_24 = break_time + timedelta(hours=1)
                break_end_12 = datetime.strftime(break_end_24, "%I:%M:%S %p")

                # NEW
                insert_hours_and_minutes(connection, detected_employee=id, total_time=hours_and_mins,
                                         break_period_point=time_in_range(New_employee_time_in, New_employee_time_out,
                                                                          get_employee_break(id), break_end_12))

                check_and_insert_rest_day(str(id), hours_and_mins,
                                          time_in_range(New_employee_time_in, New_employee_time_out,
                                                        get_employee_break(id), break_end_12))

                # Calculate overtime
                New_allowed_ot = check_employee_overtime(id, get_date())
                New_ot_total = '00:00:00'

                if New_out_time < New_end_time:
                    New_u_hours_minutes = get_undertime_hours(New_end_time, New_out_time)
                    insert_undertime_hours_and_minutes(connection, detected_employee=id,
                                                       total_undertime_hours=New_u_hours_minutes, check=True)
                else:
                    insert_undertime_hours_and_minutes(connection, detected_employee=id,
                                                       total_undertime_hours='00:00:00', check=False)

                # NEW
                N_check_and_insert_holiday(str(id), hours_and_mins,
                                           time_in_range(New_employee_time_in, New_employee_time_out,
                                                         get_employee_break(id), break_end_12))

                if New_allowed_ot:
                    if New_out_time > New_end_time:
                        New_ot_total = get_total_ot_hours(New_end_time, New_out_time)
                        if str(New_ot_total) > '4:00:00':
                            New_ot_total = '04:00:00'

                insert_ot_hours(connection, detected_employee=id, total_ot_hours=New_ot_total)

            else:
                employee_detected_error_message()
                return

        ############################
        # Single schedule time out #
        ############################
        else:
            if id is not None:
                play_time_out_audio()

                N_time_out(connection, detected_employee=id)

                # Calculate Total Hours
                New_employee_time_in = N_get_employee_time_in(id, get_date())
                New_employee_time_out = N_get_employee_time_out(id, get_date())

                hours_and_mins = get_hours_and_minutes(New_employee_time_in, New_employee_time_out,
                                                       N_get_single_sched_start(id),
                                                       N_get_single_sched_end(id))

                New_end_time = convert(N_get_single_sched_end(id)).rstrip()
                New_out_time = convert(get_time()).rstrip()

                if New_out_time < New_end_time:
                    New_u_hours_minutes = get_undertime_hours(New_end_time, New_out_time)
                    insert_undertime_hours_and_minutes(connection, detected_employee=id,
                                                       total_undertime_hours=New_u_hours_minutes, check=True)
                else:
                    insert_undertime_hours_and_minutes(connection, detected_employee=id,
                                                       total_undertime_hours='00:00:00', check=False)

                break_time = datetime.strptime(get_single_sched_break(id), "%I:%M:%S %p")
                break_end_24 = break_time + timedelta(hours=1)
                break_end_12 = datetime.strftime(break_end_24, "%I:%M:%S %p")

                N_check_and_insert_holiday(str(id), hours_and_mins,
                                           time_in_range(New_employee_time_in, New_employee_time_out,
                                                         get_single_sched_break(id), break_end_12))

                check_and_insert_rest_day(str(id), hours_and_mins,
                                          time_in_range(New_employee_time_in, New_employee_time_out,
                                                        get_single_sched_break(id), break_end_12))

                insert_hours_and_minutes_single_sched(connection, detected_employee=id, total_time=hours_and_mins,
                                         break_period_point=time_in_range(New_employee_time_in, New_employee_time_out,
                                                                          get_single_sched_break(id), break_end_12))

                # Calculate overtime
                New_allowed_ot = check_employee_overtime(id, get_date())
                New_ot_total = '00:00:00'

                if New_allowed_ot:
                    if New_out_time > New_end_time:
                        New_ot_total = get_total_ot_hours(New_end_time, New_out_time)
                        if str(New_ot_total) > '4:00:00':
                            New_ot_total = '04:00:00'

                insert_ot_hours(connection, detected_employee=id, total_ot_hours=New_ot_total)

            else:
                employee_detected_error_message()
                return

        ###########################
        #      Clear Labels       #
        ###########################
        C_employee_id_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white',
            font='none 12 bold'
        )
        C_employee_name_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white',
            font='none 12 bold'
        )
        C_position_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white',
            font='none 12 bold'
        )
        C_department_content_label = Label(
            manual_attendance_window,
            text="                                                                       ", bg='#396544',
            fg='white', font='none 12 bold'
        )
        C_schedule_in_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white',
            font='none 12 bold'
        )
        C_schedule_out_content_label = Label(
            manual_attendance_window, text="                                     ", bg='#396544', fg='white',
            font='none 12 bold'
        )
        C_holiday_content_label = Label(
            manual_attendance_window,
            text="                                                                       ", bg='#396544',
            fg='white',
            font='none 10 bold'
        )

        C_employee_id_content_label.place(x=200, y=300)
        C_employee_name_content_label.place(x=200, y=330)
        C_position_content_label.place(x=200, y=360)
        C_department_content_label.place(x=200, y=390)
        C_schedule_in_content_label.place(x=200, y=420)
        C_schedule_out_content_label.place(x=200, y=450)
        C_holiday_content_label.place(x=200, y=480)

        ###########################
        #     Display Labels      #
        ###########################
        emp_id = str(get_selected_id())

        manual_employee_id_content_label = Label(
            manual_attendance_window, text=emp_id, bg='#396544', fg='white', font='none 12 bold'
        )
        manual_employee_name_content_label = Label(
            manual_attendance_window, text=N_get_employee_name(emp_id), bg='#396544', fg='white', font='none 12 bold'
        )
        position_id = N_get_position_id(emp_id)
        position_name = str(N_get_position_name(position_id))
        manual_position_content_label = Label(
            manual_attendance_window, text=position_name, bg='#396544', fg='white', font='none 12 bold'
        )
        department_id = N_get_department_id(emp_id)
        department_name = str(N_get_department_name(department_id))
        manual_department_content_label = Label(
            manual_attendance_window, text=department_name, bg='#396544', fg='white', font='none 12 bold'
        )
        time_in_display = str(N_get_employee_time_in(emp_id, get_date()))
        manual_schedule_in_content_label = Label(
            manual_attendance_window, text=time_in_display, bg='#396544', fg='white', font='none 12 bold'
        )
        time_out_display = str(N_get_employee_time_out(emp_id, get_date()))
        manual_schedule_out_content_label = Label(
            manual_attendance_window, text=time_out_display, bg='#396544', fg='white', font='none 12 bold'
        )
        holiday = N_current_holiday()
        manual_holiday_content_label = Label(
            manual_attendance_window, text=holiday, bg='#396544', fg='white', font='none 10 bold'
        )

        manual_employee_id_content_label.place(x=200, y=300)
        manual_employee_name_content_label.place(x=200, y=330)
        manual_position_content_label.place(x=200, y=360)
        manual_department_content_label.place(x=200, y=390)
        manual_schedule_in_content_label.place(x=200, y=420)
        manual_schedule_out_content_label.place(x=200, y=450)
        manual_holiday_content_label.place(x=200, y=480)

    # Manual time in/out buttons
    manual_time_in = Button(manual_attendance_window, text='            Time In            ', command=time_in)
    manual_time_out = Button(manual_attendance_window, text='           Time Out           ', command=time_out)

    # Employee Details Text
    manual_employee_details_label = Label(
        manual_attendance_window, text='Employee Details', bg='#396544', fg='white', font='none 14 bold'
    )
    manual_employee_id_details_label = Label(
        manual_attendance_window, text='Employee ID:', bg='#396544', fg='white', font='none 14 bold'
    )
    manual_employee_name_details_label = Label(
        manual_attendance_window, text='Employee Name:', bg='#396544', fg='white', font='none 14 bold'
    )
    manual_position_details_label = Label(
        manual_attendance_window, text='Position:', bg='#396544', fg='white', font='none 14 bold'
    )
    manual_department_details_label = Label(
        manual_attendance_window, text='Department:', bg='#396544', fg='white', font='none 14 bold'
    )
    manual_schedule_in_details_label = Label(
        manual_attendance_window, text='Time In:', bg='#396544', fg='white', font='none 14 bold'
    )
    manual_schedule_out_details_label = Label(
        manual_attendance_window, text='Time Out:', bg='#396544', fg='white', font='none 14 bold'
    )
    manual_holiday_details_label = Label(
        manual_attendance_window, text='Holiday:', bg='#396544', fg='white', font='none 14 bold'
    )

    ##################
    # -- PASSWORD -- #
    ##################
    def submit_password():
        if str(password_textbox.get()) == 'root':
            manual_time_out.place(x=260, y=190)
            manual_time_in.place(x=110, y=190)
            select_employee_label.place(x=30, y=20)
            tv.place(x=30, y=50)

            manual_employee_details_label.place(x=30, y=250)
            manual_employee_id_details_label.place(x=30, y=300)
            manual_employee_name_details_label.place(x=30, y=330)
            manual_position_details_label.place(x=30, y=360)
            manual_department_details_label.place(x=30, y=390)
            manual_schedule_in_details_label.place(x=30, y=420)
            manual_schedule_out_details_label.place(x=30, y=450)
            manual_holiday_details_label.place(x=30, y=480)

            password_label.place_forget()
            password_textbox.place_forget()
            password_button.place_forget()

            manual_time_in.config(state=DISABLED)
            manual_time_out.config(state=DISABLED)
        else:
            wrong_password_message()

    password_label = Label(
        manual_attendance_window, text='Enter Password: ', bg='#396544', fg='white', font='none 14 bold'
    )
    password_label.place(x=163, y=100)

    password_textbox = Entry(manual_attendance_window, width=30)
    password_textbox.place(x=150, y=130)

    password_button = Button(manual_attendance_window, text='           Submit           ', command=submit_password)
    password_button.place(x=185, y=155)

###########################
# -- SAVE TO DATABASE  -- #
###########################


def save_db_name_error_window():
    # Create persistence file
    db_address = db_error_textbox.get()
    with open('Persistence Files/db_name.pickle', 'wb') as f:
        pickle.dump(db_address, f)

    db_saved_message()
    sys.exit()


# Locate db button
# locate_db_button = Button(root, text='Locate Database Server', command=open_db_change_window)
# locate_db_button.place(x=720, y=475)

# Locate db button
manual_attendance_btn = Button(root, text='      Enter Manually       ', command=open_manual_attendance_window)
manual_attendance_btn.place(x=800, y=475)

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
