import datetime

start = datetime.datetime.strptime('2024-02-27', '%Y-%m-%d')
end = datetime.datetime.now()
while start.date() != end.date():
    end_of_day = datetime.datetime(start.year, start.month, start.day, 23, 59, 59)
    voice_duration = int((end_of_day-start).total_seconds())+1
    start = end_of_day + datetime.timedelta(seconds=1)
    print(voice_duration)
voice_duration = int((end - start).total_seconds())
print(voice_duration)