import os
import pickle
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CALENDAR_IDS = ['zod.dr131@gmail.com', 'lorvidnoe@gmail.com']

def get_google_calendar_service():
    """Возвращает сервис Google Calendar, автоматически обновляя токен."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                os.remove('token.pickle')
                return reauthorize_google()
        else:
            return reauthorize_google()
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def reauthorize_google():
    """Принудительно запускает OAuth и сохраняет новый токен."""
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def fetch_google_calendar_events(monday_date):
    """Загружает события за неделю с понедельника monday_date (МСК)."""
    service = get_google_calendar_service()
    MSK = timezone(timedelta(hours=3))
    monday_start = datetime.combine(monday_date, datetime.min.time(), tzinfo=MSK)
    sunday_end = datetime.combine(monday_date + timedelta(days=6), datetime.max.time(), tzinfo=MSK)
    time_min = monday_start.isoformat()
    time_max = sunday_end.isoformat()

    all_events = []
    for cal_id in CALENDAR_IDS:
        events_result = service.events().list(
            calendarId=cal_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        for event in events_result.get('items', []):
            start_raw = event['start'].get('dateTime', event['start'].get('date'))
            end_raw = event['end'].get('dateTime', event['end'].get('date'))

            if 'T' in start_raw:
                date_part, time_part_with_tz = start_raw.split('T')
                time_part = time_part_with_tz[:8]
            else:
                date_part = start_raw
                time_part = '00:00:00'

            if 'T' in end_raw:
                end_time_part = end_raw.split('T')[1][:8]
            else:
                end_time_part = '00:00:00'

            if 'date' in event['start'] and 'dateTime' not in event['start']:
                continue

            all_events.append({
                'Календарь': cal_id,
                'Название события': event.get('summary', ''),
                'Описание': event.get('description', ''),
                'Дата начала (МСК)': date_part,
                'Время начала (МСК)': time_part,
                'Дата окончания (МСК)': end_raw.split('T')[0] if 'T' in end_raw else end_raw,
                'Время окончания (МСК)': end_time_part,
            })
    return all_events