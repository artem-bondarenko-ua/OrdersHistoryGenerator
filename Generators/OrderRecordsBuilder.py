import datetime
import time

import Entities.OrderRecord_pb2 as OrderRecords
import Entities.StatusSequence_pb2 as StatusSequence
import Entities.Status_pb2 as Status
from Config.Configurations import Configuration
from Config.Configurations import ValuesNames as Values
from Enums.LinearCongruentialGeneratorParameters import LinearCongruentialGeneratorParameters as LCGParams

from Generators.PseudorandomNumberGenerator.Implementation.LinearCongruentialGenerator import \
    LinearCongruentialGenerator as LCG
from Service.LoggerService.Implementation.DefaultPythonLoggingService import \
    DefaultPythonLoggingService as Logger
from Utils.Utils import Utils


class OrderRecordsBuilder:
    def __init__(self):
        self.__order_general_information = None
        self.__configs = Configuration()

        Logger.debug(__file__, 'Init OrderRecordsBuilder instance')

    def set_general_order_info(self, general_order_info):
        self.__order_general_information = general_order_info

        Logger.debug(__file__,
                     'Set general order info parameter to {}'.format(self.__order_general_information.__str__()))
        return self

    def build_order_with_records_in_green_zone(self, period_index):
        Logger.debug(__file__, 'Called building order in green zone')

        period_start = self.__configs.start_date + datetime.timedelta(days=period_index * 7)

        first_status_day_offset, second_status_day_offset, third_status_day_offset = self.__generate_days_statuses_offsets()

        first_status_date = self.__calculate_date(first_status_day_offset, period_start)
        second_status_date = self.__calculate_date(second_status_day_offset, first_status_date)
        third_status_date = self.__calculate_date(third_status_day_offset, second_status_date)

        Logger.debug(__file__,
                     f'Generated dates for records: {first_status_date}, {second_status_date}, {third_status_date}')

        first_status_time, second_status_time, third_status_time = self.__calculate_order_statuses_times(
            first_status_date,
            second_status_date,
            third_status_date)

        Logger.debug(__file__,
                     f'Generated times for records: {first_status_time}, {second_status_time}, {third_status_time}')

        Logger.debug(__file__, 'Building order records in green zone finished')

        o = OrderRecords.OrderRecord()
        self.__set_general_info(o)

        record = o.statuses_info.add()
        record.status = Status.STATUS_NEW
        record.timestamp_millis = self.__generate_ms_datetime(first_status_date, first_status_time)

        record = o.statuses_info.add()
        record.status = Status.STATUS_TO_PROVIDER
        record.timestamp_millis = self.__generate_ms_datetime(second_status_date, second_status_time)

        record = o.statuses_info.add()
        record.status = self.__get_last_status(self.__order_general_information.status_sequence)
        record.timestamp_millis = self.__generate_ms_datetime(third_status_date, third_status_time)

        return o

    def build_order_with_records_in_blue_red_zone(self, period_start, period_end):
        Logger.debug(__file__, 'Called building order in blue-red zone')

        first_status_date, second_status_date, third_status_date = \
            self.__calculate_red_blue_zone_order_dates(
                period_start, period_end)

        Logger.debug(__file__,
                     f'Generated dates for records: {first_status_date}, {second_status_date}, {third_status_date}')

        first_status_time, second_status_time, third_status_time = self.__calculate_order_statuses_times(
            first_status_date,
            second_status_date,
            third_status_date)

        Logger.debug(__file__,
                     f'Generated times for records: {first_status_time}, {second_status_time}, {third_status_time}')

        o = OrderRecords.OrderRecord()
        self.__set_general_info(o)

        if first_status_date != 0:
            record = o.statuses_info.add()
            record.status = Status.STATUS_NEW
            record.timestamp_millis = self.__generate_ms_datetime(first_status_date, first_status_time)

        if second_status_date != 0:
            record = o.statuses_info.add()
            record.status = Status.STATUS_TO_PROVIDER
            record.timestamp_millis = self.__generate_ms_datetime(second_status_date, second_status_time)

        if third_status_date != 0:
            record = o.statuses_info.add()
            record.status = self.__get_last_status(self.__order_general_information.status_sequence)
            record.timestamp_millis = self.__generate_ms_datetime(third_status_date, third_status_time)

        Logger.debug(__file__, 'Building order records in blue-red zone finished')

        return o

    def __calculate_date(self, offset, previous_date):
        previous_date_day_of_week = previous_date.weekday() + 1

        if offset == 0:
            day_with_offset = previous_date
        else:
            if previous_date_day_of_week == 5:
                day_with_offset = previous_date + datetime.timedelta(days=3 if offset == 1 else 4)
            elif previous_date_day_of_week == 1:
                day_with_offset = previous_date + datetime.timedelta(days=1)
            else:
                day_with_offset = previous_date

        if day_with_offset > datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0):
            day_with_offset = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

        return day_with_offset

    def __generate_days_statuses_offsets(self):
        first_status_day_offset = Utils.calculate_sequence_interval_value(
            LCG.get_next(Values.FIRST_STATUS_POSSIBLE_TIME_GENERATOR),
            self.__configs.settings[Values.FIRST_STATUS_POSSIBLE_TIME_GENERATOR][LCGParams.MODULUS.value]
        )

        second_status_day_offset = Utils.calculate_sequence_interval_value(
            LCG.get_next(Values.SECOND_STATUS_DATE_OFFSET_GENERATOR),
            self.__configs.settings[Values.SECOND_STATUS_DATE_OFFSET_GENERATOR][LCGParams.MODULUS.value]
        )

        third_status_day_offset = Utils.calculate_sequence_interval_value(
            LCG.get_next(Values.THIRD_STATUS_DATE_OFFSET_GENERATOR),
            self.__configs.settings[Values.THIRD_STATUS_DATE_OFFSET_GENERATOR][LCGParams.MODULUS.value]
        )

        return first_status_day_offset, second_status_day_offset, third_status_day_offset

    def __calculate_time(self, date, possible_time, previous_date, previous_date_time):
        if previous_date != date:
            return possible_time
        else:
            if previous_date_time < possible_time:
                return possible_time
            else:
                time_to_date_end = 86399999 - previous_date_time
                prev_time_minus_current_possible = previous_date_time - possible_time

                if prev_time_minus_current_possible > time_to_date_end:
                    return int(previous_date_time + (time_to_date_end / 2))
                else:
                    return previous_date_time + prev_time_minus_current_possible

    def __calculate_order_statuses_times(self, first_date, second_date, third_date):
        first_status_possible_time = LCG.get_next(Values.FIRST_STATUS_POSSIBLE_TIME_GENERATOR)
        second_status_possible_time = LCG.get_next(Values.SECOND_STATUS_POSSIBLE_TIME_GENERATOR)
        third_status_possible_time = LCG.get_next(Values.THIRD_STATUS_POSSIBLE_TIME_GENERATOR)

        first_status_time = first_status_possible_time
        second_status_time = self.__calculate_time(second_date,
                                                   second_status_possible_time,
                                                   first_date,
                                                   first_status_time)
        third_status_time = self.__calculate_time(third_date,
                                                  third_status_possible_time,
                                                  second_date,
                                                  second_status_time)

        return first_status_time, second_status_time, third_status_time

    def __generate_ms_datetime(self, date, ms_time):
        return int(time.mktime(date.timetuple()) * 1000 + ms_time)

    def __get_last_status(self, status_sequence):

        if status_sequence == 0:  # StatusSequence.FILLED:
            return Status.STATUS_FILLED

        if status_sequence == 1:  # StatusSequence.PARTIAL_FILLED:
            return Status.STATUS_PARTIAL_FILLED

        if status_sequence == 2:  # StatusSequence.REJECTED:
            return Status.STATUS_REJECTED

    def __calculate_red_blue_zone_order_dates(self, period_start, period_end):
        start_period_date = self.__configs.start_date + datetime.timedelta(
            days=(7 * (period_start + 1)) if period_start != -1 else 0)

        start_finish_period = self.__configs.start_date + datetime.timedelta(
            days=7 * (period_end + 1)) if period_end != -1 else -1

        first_status_day_offset, second_status_day_offset, third_status_day_offset = self.__generate_days_statuses_offsets()

        first_status_date = self.__calculate_date(first_status_day_offset, start_period_date)
        second_status_date = 0
        third_status_date = 0

        if self.__order_general_information.statuses_in_blue_zone == 2:
            second_status_date = self.__calculate_date(second_status_day_offset, first_status_date)
        else:
            if start_finish_period != -1:
                second_status_date = self.__calculate_date(second_status_day_offset, start_finish_period)

        if self.__order_general_information.statuses_in_blue_zone == 2:
            if start_finish_period != -1:
                third_status_date = self.__calculate_date(third_status_day_offset, start_finish_period)
        else:
            if second_status_date != 0:
                third_status_date = self.__calculate_date(third_status_day_offset, second_status_date)

        return first_status_date, second_status_date, third_status_date

    def __set_general_info(self, record):
        record.general_order_information.id = self.__order_general_information.id
        record.general_order_information.direction = self.__order_general_information.direction
        record.general_order_information.status_sequence = self.__order_general_information.status_sequence
        record.general_order_information.currency_pair_name = self.__order_general_information.currency_pair_name
        record.general_order_information.currency_pair_value = self.__order_general_information.currency_pair_value
        record.general_order_information.init_currency_pair_value = self.__order_general_information.init_currency_pair_value
        record.general_order_information.init_volume = self.__order_general_information.init_volume
        record.general_order_information.fill_currency_pair_value = self.__order_general_information.fill_currency_pair_value
        record.general_order_information.fill_volume = int(self.__order_general_information.fill_volume)
        record.general_order_information.statuses_in_blue_zone = self.__order_general_information.statuses_in_blue_zone
        record.general_order_information.tags = self.__order_general_information.tags
        record.general_order_information.description = self.__order_general_information.description