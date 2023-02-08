import re
import pickle
import pyodbc
from datetime import date
from datetime import datetime
from datetime import timedelta
from clock import get_time, get_date
from time_diff import get_minutes_late, convert
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
            "WHERE EmployeeID='" + str(detected_employee_id) + "'" + " AND Date='" + get_date() + "')"
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


def time_out_no_in(connection, detected_employee_id):
    attendance_id = str(date.today()).replace('-', '') + str(detected_employee_id)
    status = check_employee_status(detected_employee_id)

    if status == "Active":
        cursor.execute(
            "IF NOT EXISTS (SELECT EmployeeID, Date FROM AttendanceRecord "
            "WHERE EmployeeID='" + str(detected_employee_id) + "'" + " AND Date='" + get_date() + "')"
            "BEGIN "
            "INSERT INTO AttendanceRecord(AttendanceID, EmployeeID, TimeOut, Date, PositionID) values(?, ?, ?, ?, ?)"
            "END",
            (attendance_id, detected_employee_id, get_time(), get_date(), N_get_position_id(detected_employee_id))
        )
        connection.commit()
    else:
        employee_inactive_message()
############################################
#     INSERT TIME VALUES INTO DATABASE     #
############################################


def time_in_range_break_time_in(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start is None:
        return
    elif end is None:
        return
    else:
        if start <= end:
            return start <= x <= end
        else:
            return start <= x or x <= end


def N_minutes_late(connection, detected_employee, minutes):
    cursor.execute(
        "UPDATE AttendanceRecord SET Late_Minutes=" + str(minutes) + " " +
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' "
        "AND Late_Minutes IS NULL"
    )
    connection.commit()


def insert_hours_and_minutes(connection, detected_employee, total_time, break_period_point):

    if '-' in str(total_time):
        total_time = str(total_time)[8:]
        total_time = '00:00:00'

    # Employee time out before timing in error catch
    if total_time is None:
        # Error is already caught on recognize.py line 322
        return

    # Split 12-hour time format to h m s
    (h, m, s) = str(total_time).split(':')

    mins_late = int(get_minutes_late(get_employee_schedule_start(detected_employee), N_get_employee_time_in(detected_employee, get_date())))

    # Break subtractor
    if break_period_point:
        h = int(h) - 1

    # If timing in during break
    break_time = datetime.strptime(get_employee_break(detected_employee), "%I:%M:%S %p")
    break_end_24 = break_time + timedelta(hours=1)
    break_end_12 = datetime.strftime(break_end_24, "%I:%M:%S %p")

    date = get_date()

    if time_in_range_break_time_in(get_employee_break(detected_employee), break_end_12, N_get_employee_time_in(detected_employee, get_date())):
        time_1 = datetime.strptime(convert(str(break_end_12)), "%H:%M:%S")
        time_2 = datetime.strptime(convert(N_get_employee_time_in(detected_employee, date))[:8], "%H:%M:%S")

        mins_break_in = time_1 - time_2
        (bh, bm, bs) = str(mins_break_in).split(':')
        h = h + 1
        m = int(m) - int(bm)

    # If timing out during break
    if time_in_range_break_time_in(get_employee_break(detected_employee), break_end_12, N_get_employee_time_out(detected_employee, get_date())):
        time_1_out = datetime.strptime(convert(get_employee_break(detected_employee))[:8], "%H:%M:%S")
        time_2_out = datetime.strptime(convert(N_get_employee_time_out(detected_employee, date))[:8], "%H:%M:%S")

        mins_break_in = time_2_out - time_1_out
        (bh, bm, bs) = str(mins_break_in).split(':')
        h = h + 1
        m = int(m) - int(bm)

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


def insert_hours_and_minutes_single_sched(connection, detected_employee, total_time, break_period_point):
    if '-' in str(total_time):
        total_time = str(total_time)[8:]
        total_time = '00:00:00'

    # Split 12-hour time format to h m s

    # Employee time out before timing in error catch
    if total_time is None:
        # Error is already caught on recognize.py line 322
        return

    (h, m, s) = str(total_time).split(':')

    mins_late = int(get_minutes_late(N_get_single_sched_start(detected_employee), N_get_employee_time_in(detected_employee, get_date())))

    # Break subtractor
    if break_period_point:
        h = int(h) - 1

    # If timing in during break
    break_time = datetime.strptime(get_single_sched_break(detected_employee), "%I:%M:%S %p")
    break_end_24 = break_time + timedelta(hours=1)
    break_end_12 = datetime.strftime(break_end_24, "%I:%M:%S %p")

    date = get_date()

    if time_in_range_break_time_in(get_single_sched_break(detected_employee), break_end_12,
                                   N_get_employee_time_in(detected_employee, get_date())):
        time_1 = datetime.strptime(convert(str(break_end_12))[:8], "%H:%M:%S")
        time_2 = datetime.strptime(convert(N_get_employee_time_in(detected_employee, date))[:8], "%H:%M:%S")

        mins_break_in = time_1 - time_2
        (bh, bm, bs) = str(mins_break_in).split(':')
        # h = h + 1
        m = int(m) - int(bm)

    # If timing out during break
    if time_in_range_break_time_in(get_single_sched_break(detected_employee), break_end_12,
                                   N_get_employee_time_out(detected_employee, get_date())):
        time_1_out = datetime.strptime(convert(get_single_sched_break(detected_employee))[:8], "%H:%M:%S")
        time_2_out = datetime.strptime(convert(N_get_employee_time_out(detected_employee, date))[:8], "%H:%M:%S")

        mins_break_in = time_2_out - time_1_out
        (bh, bm, bs) = str(mins_break_in).split(':')
        h = h + 1
        m = int(m) - int(bm)

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

    cursor.execute("SELECT Type_ FROM Holidays WHERE From_ ='" + current_date + "'")

    for row in cursor:
        time = str(row)
        holiday = re.sub("[(',)]", '', time).rstrip()

    # Time out before time in error catcher
    if hours is None:
        # Error already caught at recognize.py line 322
        return

    if '-' in str(hours):
        hours = str(hours)[8:]

    (h, m, s) = str(hours).split(':')

    if break_period_point:
        h = int(h) - 1

    # Grace Period for Single Sched and Normal Sched
    if N_get_single_sched_date(id, get_date()) == get_date():
        mins_late = int(get_minutes_late(N_get_single_sched_start(id), N_get_employee_time_in(id, get_date())))
    else:
        mins_late = int(get_minutes_late(get_employee_schedule_start(id), N_get_employee_time_in(id, get_date())))

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


####################################################
#    INSERT REST DAY TIME VALUES INTO DATABASE     #
####################################################

def insert_rest_day(connection, detected_employee, hours, minutes):
    cursor.execute(
        "UPDATE AttendanceRecord SET RestDay=1, "
        "RD_Hours=" + str(hours) + ", RD_Minutes=" + str(minutes) +
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    connection.commit()


def insert_none_rest_day(connection, detected_employee):
    cursor.execute(
        "UPDATE AttendanceRecord SET RestDay=0, "
        "RD_Hours=0, RD_Minutes=0" +
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    connection.commit()


def check_and_insert_rest_day(id, hours, break_period_point):
    # Time out before time in error catcher
    if hours is None:
        # Error already caught at recognize.py line 322
        return

    if '-' in str(hours):
        hours = str(hours)[8:]
        hours = '00:00:00'

    (h, m, s) = str(hours).split(':')

    if break_period_point:
        h = int(h) - 1

    # Grace Period for Single Sched and Normal Sched
    if N_get_single_sched_date(id, get_date()) == get_date():
        mins_late = int(get_minutes_late(N_get_single_sched_start(id), N_get_employee_time_in(id, get_date())))
    else:
        mins_late = int(get_minutes_late(get_employee_schedule_start(id), N_get_employee_time_in(id, get_date())))

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

    rest_day = get_employee_rest_day(id)

    # If false then it is rest day
    if rest_day == 'False':
        insert_rest_day(connection, detected_employee=id, hours=h, minutes=m)
    else:
        insert_none_rest_day(connection, detected_employee=id)

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
#             CHECK LEAVE & OT             #
############################################

def N_check_employee_leave(id, date):
    cursor.execute("SELECT Date FROM LeavePay "
                   "WHERE EmployeeID='" + str(id) + "' AND Date='" + date + "'")
    for row in cursor:
        checked_date = str(row)
        checked_date = re.sub("[(',)]", '', checked_date).rstrip()

        if checked_date is None:
            # Employee is not on a leave
            return False
        else:
            # Employee is on a Leave
            return True


def check_employee_overtime(id, date):

    if date is None:
        # Time out before time in error catcher
        timeout_error_message()
        return

    cursor.execute("SELECT Date FROM OvertimeDates "
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


def get_employee_id(name):
    cursor.execute("SELECT EmployeeID FROM EmployeeInfo "
                   "WHERE EmployeeFullName='" + str(name) + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


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


def get_employee_break(id):
    cursor.execute("SELECT BreakPeriod FROM EmployeeSchedule "
                   "WHERE EmployeeID=" + str(id) + "")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_employee_status(id):
    cursor.execute("SELECT Status FROM EmployeeInfo "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_employee_list():
    e_list = []

    cursor.execute("SELECT EmployeeID FROM EmployeeInfo WHERE Status='Active'")
    for row in cursor:
        emp = str(row)
        e_list.append(re.sub("[(',)]", '', emp).rstrip())

    return e_list


def get_single_sched_break(id):
    cursor.execute("SELECT BreakPeriod FROM SingleSchedule "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_employee_list_id():
    e_list = []

    cursor.execute("SELECT EmployeeID, EmployeeFullName FROM EmployeeInfo WHERE Status='Active'"
                   " ORDER BY EmployeeFullName")

    for row in cursor:
        emp = str(row)
        e_list.append(re.sub("[(')]", '', emp).rstrip().replace(" ","-").replace(",", " "))

    return e_list


def get_employee_rest_day(id):
    pop_weekday_number = datetime.today().isoweekday()
    weekday = ""

    if pop_weekday_number == 1:
        weekday = 'Monday'
    elif pop_weekday_number == 2:
        weekday = 'Tuesday'
    elif pop_weekday_number == 3:
        weekday = 'Wednesday'
    elif pop_weekday_number == 4:
        weekday = 'Thursday'
    elif pop_weekday_number == 5:
        weekday = 'Friday'
    elif pop_weekday_number == 6:
        weekday = 'Saturday'
    elif pop_weekday_number == 7:
        weekday = 'Sunday'

    cursor.execute("SELECT " + weekday + " FROM EmployeeSchedule "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()
