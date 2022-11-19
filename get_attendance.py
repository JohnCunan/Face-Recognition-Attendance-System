import re
import pickle
import pyodbc
from datetime import date
from datetime import datetime
from clock import get_time, get_date
from pop_ups import timeout_error_message, employee_inactive_message

with open('Persistence Files/db_name.pickle', 'rb') as f:
    database_name = pickle.load(f)

try:
    conn = pyodbc.connect(
        "".join(["Driver={SQL Server Native Client 11.0};",
                 "Server=", database_name, ";",
                 "Database=FFRUsers;",
                 "Trusted_Connection=yes;"])
    )
    cursor = conn.cursor()
except pyodbc.OperationalError as err:
    pass


def time_in(conn, detected_employee_id):
    attendance_id = str(date.today()).replace('-', '') + str(detected_employee_id)
    status = check_employee_status(detected_employee_id)

    if status == "Active":
        cursor.execute(
            "IF NOT EXISTS (SELECT EmployeeID, Date FROM AttendanceSheet "
            "WHERE EmployeeID='" + detected_employee_id + "'" + " AND Date='" + get_date() + "')"
            "BEGIN "
            "INSERT INTO AttendanceSheet(AttendanceID, EmployeeID, TimeIn, Date, PositionID) values(?, ?, ?, ?, ?)"
            "END",
            (attendance_id, detected_employee_id, get_time(), get_date(), get_position_id(detected_employee_id))
        )
        conn.commit()
    else:
        employee_inactive_message()


def time_out(conn, detected_employee):
    cursor.execute(
        "UPDATE AttendanceSheet SET TimeOut='" + get_time() + "' "
                                                              "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND TimeOut IS NULL"
    )
    conn.commit()


def total_hours(conn, detected_employee, total_work_hours):
    try:
        (h, m, s) = str(total_work_hours).split(':')
    except ValueError:
        # Employee timing out without time in record error occurs here
        # is already caught at line 125
        return

    time_to_decimal = "{:.3f}".format((int(h) * 3600 + int(m) * 60 + int(s)) / 3600)

    cursor.execute(
        "UPDATE AttendanceSheet SET TotalHours='" + str(time_to_decimal) + "' "
                                                                           "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND TotalHours IS NULL"
    )
    conn.commit()


def late_or_not(conn, detected_employee, state):
    if state:
        cursor.execute(
            "UPDATE AttendanceSheet SET Late= 1.00"
            "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND Late IS NULL"
        )
        conn.commit()
    else:
        cursor.execute(
            "UPDATE AttendanceSheet SET Late= 0.00"
            "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND Late IS NULL"
        )
        conn.commit()


def minutes_late(conn, detected_employee, minutes):
    cursor.execute(
        "UPDATE AttendanceSheet SET MinutesLate=" + str(minutes) + " " +
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    conn.commit()


def minute_rate_loss(conn, detected_employee, minutes):

    h_rate = float(get_employee_basic_rate(detected_employee))
    m_rate = h_rate / 60
    deducted = m_rate * minutes

    cursor.execute(
        "UPDATE AttendanceSheet SET MinuteRateLoss=" + str(deducted) + " " +
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    conn.commit()


def ot_hours(conn, detected_employee, total_ot_hours):
    (h, m, s) = str(total_ot_hours).split(':')
    time_to_decimal = "{:.3f}".format((int(h) * 3600 + int(m) * 60 + int(s)) / 3600)

    cursor.execute(
        "UPDATE AttendanceSheet SET OvertimeHours='" + str(time_to_decimal) + "' "
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND OvertimeHours IS NULL"
    )
    conn.commit()


def reg_hours(conn, detected_employee, total_reg_hours, break_period_point):
    if '-' in str(total_reg_hours):
        total_reg_hours = str(total_reg_hours)[8:]

    (h, m, s) = str(total_reg_hours).split(':')
    time_to_decimal = "{:.3f}".format((int(h) * 3600 + int(m) * 60 + int(s)) / 3600)

    if break_period_point:
        time_to_decimal = float(time_to_decimal) - 1.000

    cursor.execute(
        "UPDATE AttendanceSheet SET RegularHours='" + str(time_to_decimal) + "' "
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND RegularHours IS NULL"
    )
    conn.commit()


def undertime_hours(conn, detected_employee, total_undertime_hours, check):
    if check:
        (h, m, s) = str(total_undertime_hours).split(':')
        time_to_decimal = "{:.3f}".format((int(h) * 3600 + int(m) * 60 + int(s)) / 3600)

        cursor.execute(
            "UPDATE AttendanceSheet SET UndertimeHours='" + str(time_to_decimal) + "' "
                                                                                   "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND UndertimeHours IS NULL"
        )
        conn.commit()
    else:
        cursor.execute(
            "UPDATE AttendanceSheet SET UndertimeHours=0.00 "
            "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "' AND UndertimeHours IS NULL"
        )
        conn.commit()


def add_accumulated_day_off(id):
    if datetime.today().isoweekday() == 7:
        cursor.execute(
            "UPDATE EmployeeInfo SET AccumulatedDayOffs = AccumulatedDayOffs + 1 WHERE EmployeeID='" + str(id) + "'"
        )
        conn.commit()


# Return employee schedule (Get total hours)
def get_employee_time_in(id, date):
    cursor.execute("SELECT TimeIn FROM AttendanceSheet "
                   "WHERE Date='" + date + "' AND EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_employee_time_out(id, date):
    cursor.execute("SELECT TimeOut FROM AttendanceSheet "
                   "WHERE Date='" + date + "' AND EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_total_hours(time_in, time_out):
    try:
        time_1 = datetime.strptime(time_in, "%I:%M:%S %p")
        time_2 = datetime.strptime(time_out, "%I:%M:%S %p")

        time_interval = time_2 - time_1
        return time_interval
    except TypeError:
        timeout_error_message()
        return


# Check employee schedules (Late or not Late)
def get_employee_id(name):
    cursor.execute("SELECT EmployeeID FROM EmployeeInfo "
                   "WHERE EmployeeFullName='" + name + "'")
    for row in cursor:
        id = str(row)
        return re.sub("[(',)]", '', id).rstrip()


def get_employee_name(id):
    cursor.execute("SELECT EmployeeFullName FROM EmployeeInfo "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


# Error when timing out when employee has a scheduled leave
def get_position_id(id):
    cursor.execute("SELECT PositionID FROM EmployeeInfo "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def get_position_name(id):
    cursor.execute("SELECT PositionName FROM Position "
                   "WHERE PositionID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def get_department_id(id):
    cursor.execute("SELECT DepartmentID FROM EmployeeInfo "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def get_department_name(id):
    cursor.execute("SELECT DepartmentName FROM Department "
                   "WHERE DepartmentID='" + id + "'")
    for row in cursor:
        name = str(row)
        return re.sub("[(',)]", '', name).rstrip()


def get_employee_start_time(id):
    cursor.execute("SELECT ScheduleIn FROM EmployeeSchedule "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_employee_end_time(id):
    cursor.execute("SELECT ScheduleOut FROM EmployeeSchedule "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def get_employee_basic_rate(id):
    cursor.execute("SELECT BasicRate FROM Position "
                   "WHERE PositionID = (SELECT PositionID FROM EmployeeInfo WHERE EmployeeID=" + str(id) + ")")
    for row in cursor:
        rate = str(row)
        rate = re.sub("[(',)]", '', rate).rstrip()
        return rate[7:]


def check_allowed_ot(id):
    cursor.execute("SELECT AllowedOvertime FROM EmployeeInfo "
                   "WHERE EmployeeID='" + id + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


def check_employee_leave(id, date):
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

# Check time in and time out for disable buttons
def check_time_in(id):
    cursor.execute("SELECT TimeIn FROM AttendanceSheet "
                   "WHERE EmployeeID=" + str(id) +
                   "AND Date='" + get_date() + "'"
                   )


def check_time_out(id):
    cursor.execute("SELECT TimeOut FROM AttendanceSheet "
                   "WHERE EmployeeID=" + str(id) +
                   "AND Date='" + get_date() + "'"
                   )


# Input holidays
def set_reg_holiday(conn, detected_employee, total_h):
    cursor.execute(
        "UPDATE AttendanceSheet SET RegularHoliday=1, SpecialHoliday=0, "
        "RegularHolidayHours='" + str(total_h) + "', SpecialHolidayHours=0.00"
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    conn.commit()


def set_specc_holiday(conn, detected_employee, total_h):
    cursor.execute(
        "UPDATE AttendanceSheet SET SpecialHoliday=1, RegularHoliday=0, "
        "RegularHolidayHours=0.00, SpecialHolidayHours='" + str(total_h) + "'"
                                                                           "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    conn.commit()


def set_no_holiday(conn, detected_employee):
    cursor.execute(
        "UPDATE AttendanceSheet SET SpecialHoliday=0, RegularHoliday=0, "
        "RegularHolidayHours=0.00, SpecialHolidayHours=0.00"
        "WHERE EmployeeID='" + detected_employee + "' AND Date='" + get_date() + "'"
    )
    conn.commit()


# Check holiday
def check_holiday(id, hours, break_period_point):
    holiday = ''
    size = len(str(get_date()))
    current_date = str(get_date())[:size - 6]

    if '-' in str(hours):
        hours = str(hours)[8:]

    (h, m, s) = str(hours).split(':')
    time_to_decimal = "{:.3f}".format((int(h) * 3600 + int(m) * 60 + int(s)) / 3600)

    if break_period_point:
        time_to_decimal = float(time_to_decimal) - 1.000

    cursor.execute("SELECT Type_ FROM Holidays WHERE From_ ='" + current_date + "'")
    for row in cursor:
        time = str(row)
        holiday = re.sub("[(',)]", '', time).rstrip()

    if holiday == 'Regular Holiday':
        set_reg_holiday(conn, detected_employee=id, total_h=time_to_decimal)
    elif holiday == 'Special Non-Working Holiday':
        set_specc_holiday(conn, detected_employee=id, total_h=time_to_decimal)
    elif holiday == 'Special Working Holiday':
        set_specc_holiday(conn, detected_employee=id, total_h=time_to_decimal)
    else:
        set_no_holiday(conn, detected_employee=id)


def current_holiday():
    size = len(str(get_date()))
    current_date = str(get_date())[:size - 6]

    cursor.execute("SELECT Type_ FROM Holidays WHERE From_ ='" + current_date + "'")
    for row in cursor:
        time = str(row)
        return re.sub("[(',)]", '', time).rstrip()


# Schedules
def get_employee_weekday(id):
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


# Single Schedule
def get_single_sched_date(id, date):
    cursor.execute("SELECT Date FROM SingleSchedule "
                   "WHERE EmployeeID='" + str(id) + "' AND Date='" + str(date) + "'")
    for row in cursor:
        allowed = str(row)
        scheduled_date = re.sub("[(')]", '', allowed).rstrip()
        return scheduled_date[:-1]


def get_single_sched_time_in(id):
    cursor.execute("SELECT ScheduleIn FROM SingleSchedule "
                   "WHERE EmployeeID='" + str(id) + "' AND Date='" + get_date() + "'")
    for row in cursor:
        allowed = str(row)
        return re.sub("[(',)]", '', allowed).rstrip()


def get_single_sched_time_out(id):
    cursor.execute("SELECT ScheduleOut FROM SingleSchedule "
                   "WHERE EmployeeID='" + str(id) + "' AND Date='" + get_date() + "'")
    for row in cursor:
        allowed = str(row)
        return re.sub("[(',)]", '', allowed).rstrip()


# Employee Status
def check_employee_status(id):
    cursor.execute("SELECT Status FROM EmployeeInfo "
                   "WHERE EmployeeID='" + str(id) + "'")
    for row in cursor:
        allowed = str(row)
        return re.sub("[(',)]", '', allowed).rstrip()
