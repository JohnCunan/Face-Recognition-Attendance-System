import re
import pickle
import pyodbc
from datetime import date
from datetime import datetime
from clock import get_time, get_date
from time_diff import get_minutes_late
from pop_ups import timeout_error_message, employee_inactive_message

with open('Persistence Files/db_name.pickle', 'rb') as f:
    database_name = pickle.load(f)

try:
    connection = pyodbc.connect(
        "".join(["Driver={SQL Server Native Client 11.0};",
                 "Server=", database_name, ";",
                 "Database=FFRUsers;",
                 "Trusted_Connection=yes;"])
    )
    cursor = connection.cursor()
except pyodbc.OperationalError as err:
    pass


######################################
#        TIME IN AND TIME OUT        #
######################################

def N_time_in(connection, detected_employee_id):
    attendance_id = str(date.today()).replace('-', '') + str(detected_employee_id)
    status = check_employee_status(detected_employee_id)

    if status == "Active":
        cursor.execute(
            "IF NOT EXISTS (SELECT EmployeeID, Date FROM AttendanceRecord "
            "WHERE EmployeeID='" + detected_employee_id + "'" + " AND Date='" + get_date() + "')"
            "BEGIN "
            "INSERT INTO AttendanceRecord(AttendanceID, EmployeeID, TimeIn, Date, PositionID) values(?, ?, ?, ?, ?)"
            "END",
            (attendance_id, detected_employee_id, get_time(), get_date(), N_get_position_id(detected_employee_id))
        )
        connection.commit()
    else:
        employee_inactive_message()


def N_time_out(connection, detected_employee):
    cursor.execute(
        "UPDATE AttendanceRecord SET TimeOut='" + get_time() + "' "
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND TimeOut IS NULL"
    )
    connection.commit()

############################################
#     ADD ACCUMULATED DAY OFF SCHEDULE     #
############################################


def N_add_accumulated_day_off(id):
    if datetime.today().isoweekday() == 7:
        cursor.execute(
            "UPDATE EmployeeInfo SET AccumulatedDayOffs = AccumulatedDayOffs + 1 WHERE EmployeeID='" + str(id) + "'"
        )
        connection.commit()


############################################
#     INSERT TIME VALUES INTO DATABASE     #
############################################


def N_minutes_late(connection, detected_employee, minutes):
    cursor.execute(
        "UPDATE AttendanceRecord SET Late_Minutes=" + str(minutes) + " " +
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    connection.commit()


def insert_hours_and_minutes(connection, detected_employee, total_time, break_period_point):
    if '-' in str(total_time):
        total_time = str(total_time)[8:]

    # Split 12-hour time format to h m s
    (h, m, s) = str(total_time).split(':')

    mins_late = int(get_minutes_late(get_employee_schedule_start(detected_employee), N_get_employee_time_in(detected_employee, get_date())))

    # Break subtractor
    if break_period_point:
        h = int(h) - 1

    # Grace Period Adder
    if mins_late <= 10:
        m = int(m) + int(mins_late)

        if m >= 60:
            h = h + 1
            m = m - 60

    # 8 Hour limiter
    if int(h) > 8:
        h = 8
        m = 0

    cursor.execute(
        "UPDATE AttendanceRecord SET Hours=" + str(h) + ", Minutes=" + str(m) + " "
        "WHERE EmployeeID='" + detected_employee + "' "
        "AND Date='" + get_date() + "' AND Hours IS NULL AND Minutes IS NULL"
    )
    connection.commit()


def insert_ot_hours(connection, detected_employee, total_ot_hours):
    (h, m, s) = str(total_ot_hours).split(':')

    cursor.execute(
        "UPDATE AttendanceRecord SET OT_Hours='" + str(h) + "' "
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND OT_Hours IS NULL"
    )
    connection.commit()


def insert_undertime_hours_and_minutes(connection, detected_employee, total_undertime_hours, check):
    if check:
        (h, m, s) = str(total_undertime_hours).split(':')

        cursor.execute(
            "UPDATE AttendanceRecord SET Undertime_Hours=" + str(h) + ", Undertime_Minutes=" + str(m) + " "
            "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' "
            "AND Undertime_Hours IS NULL AND Undertime_Minutes IS NULL"
        )
        connection.commit()
    else:
        cursor.execute(
            "UPDATE AttendanceRecord SET Undertime_Hours=0, Undertime_Minutes=0"
            "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' "
            "AND Undertime_Hours IS NULL AND Undertime_Minutes IS NULL"
        )
        connection.commit()


####################################################
#     INSERT HOLIDAY TIME VALUES INTO DATABASE     #
####################################################


def insert_reg_holiday(connection, detected_employee, hours, minutes):
    cursor.execute(
        "UPDATE AttendanceRecord SET RegularHoliday=1, SpecialHoliday=0, "
        "RH_Hours=" + str(hours) + ", RH_Minutes=" + str(minutes) + ", "
        "SH_Hours=0, SH_Minutes=0 "
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    connection.commit()


def insert_specc_holiday(connection, detected_employee, hours, minutes):
    cursor.execute(
        "UPDATE AttendanceRecord SET RegularHoliday=0, SpecialHoliday=1, "
        "SH_Hours=" + str(hours) + ", SH_Minutes=" + str(minutes) + ", "
        "RH_Hours=0, RH_Minutes=0 "
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    connection.commit()


def insert_no_holiday(connection, detected_employee):
    cursor.execute(
        "UPDATE AttendanceRecord SET SpecialHoliday=0, RegularHoliday=0, "
        "RH_Hours=0, RH_Minutes=0, SH_Hours=0, SH_Minutes=0"
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    connection.commit()


def N_check_and_insert_holiday(id, hours, break_period_point):
    holiday = ''
    size = len(str(get_date()))
    current_date = str(get_date())[:size - 6]

    if '-' in str(hours):
        hours = str(hours)[8:]

    (h, m, s) = str(hours).split(':')

    if break_period_point:
        h = int(h) - 1

    cursor.execute("SELECT Type_ FROM Holidays WHERE From_ ='" + current_date + "'")

    for row in cursor:
        time = str(row)
        holiday = re.sub("[(',)]", '', time).rstrip()

    if holiday == 'Regular Holiday':
        insert_reg_holiday(connection, detected_employee=id, hours=h, minutes=m)
    elif holiday == 'Special Non-Working Holiday':
        insert_specc_holiday(connection, detected_employee=id, hours=h, minutes=m)
    elif holiday == 'Special Working Holiday':
        insert_specc_holiday(connection, detected_employee=id, hours=h, minutes=m)
    else:
        insert_no_holiday(connection, detected_employee=id)


def N_current_holiday():
    size = len(str(get_date()))
    current_date = str(get_date())[:size - 6]

    cursor.execute("SELECT Type_ FROM Holidays WHERE From_ ='" + current_date + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


#####################################################
#  GET ATTENDANCE RECORD INFORMATION FROM DATABASE  #
#####################################################


def N_get_employee_time_in(id, date):
    cursor.execute("SELECT TimeIn FROM AttendanceRecord "
                   "WHERE Date='" + date + "' AND EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def N_get_employee_time_out(id, date):
    cursor.execute("SELECT TimeOut FROM AttendanceRecord "
                   "WHERE Date='" + date + "' AND EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_attendance_hours(id, date):
    cursor.execute("SELECT Hours FROM AttendanceRecord "
                   "WHERE Date='" + date + "' AND EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


############################################
#               CHECK LEAVE                #
############################################

def N_check_employee_leave(id, date):
    cursor.execute("SELECT Date FROM LeavePay "
                   "WHERE EmployeeID='" + id + "' AND Date='" + date + "'")
    for row in cursor:
        checked_date = str(row)
        checked_date = re.sub("[(',)]", '', checked_date).rstrip()

        if checked_date is None:
            # Employee is not on a leave
            return False
        else:
            # Employee is on a Leave
            return True


############################################
#             CHECK WEEKDAYS               #
############################################

def check_weekday(id):
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

    cursor.execute("SELECT " + weekday + " FROM EmployeeSchedule "
                                         "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        allowed = str(row)
        return re.sub("[(',)]", '', allowed).rstrip()

############################################
#            SINGLE SCHEDULE               #
############################################


def N_get_single_sched_date(id, date):
    cursor.execute("SELECT Date FROM SingleSchedule "
                   "WHERE EmployeeID='" + str(id) + "' AND Date='" + str(date) + "'")
    for row in cursor:
        allowed = str(row)
        scheduled_date = re.sub("[(')]", '', allowed).rstrip()
        return scheduled_date[:-1]


def N_get_single_sched_start(id):
    cursor.execute("SELECT ScheduleIn FROM SingleSchedule "
                   "WHERE EmployeeID='" + str(id) + "' AND Date='" + get_date() + "'")
    for row in cursor:
        allowed = str(row)
        return re.sub("[(',)]", '', allowed).rstrip()


def N_get_single_sched_end(id):
    cursor.execute("SELECT ScheduleOut FROM SingleSchedule "
                   "WHERE EmployeeID='" + str(id) + "' AND Date='" + get_date() + "'")
    for row in cursor:
        allowed = str(row)
        return re.sub("[(',)]", '', allowed).rstrip()


############################################
#  GET EMPLOYEE INFORMATION FROM DATABASE  #
############################################


def N_get_employee_name(id):
    cursor.execute("SELECT EmployeeFullName FROM EmployeeInfo "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def get_employee_schedule_start(id):
    cursor.execute("SELECT ScheduleIn FROM EmployeeSchedule "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_employee_schedule_end(id):
    cursor.execute("SELECT ScheduleOut FROM EmployeeSchedule "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def N_get_position_id(id):
    cursor.execute("SELECT PositionID FROM EmployeeInfo "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def N_get_position_name(id):
    cursor.execute("SELECT PositionName FROM Position "
                   "WHERE PositionID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def N_get_department_id(id):
    cursor.execute("SELECT DepartmentID FROM EmployeeInfo "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def N_get_department_name(id):
    cursor.execute("SELECT DepartmentName FROM Department "
                   "WHERE DepartmentID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def check_employee_status(id):
    cursor.execute("SELECT Status FROM EmployeeInfo "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        allowed = str(row)
        return re.sub("[(',)]", '', allowed).rstrip()


def N_check_allowed_ot(id):
    cursor.execute("SELECT AllowedOvertime FROM EmployeeInfo "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()

