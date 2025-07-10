import configparser
import os
from dotenv import load_dotenv

def load_settings():
    config = configparser.ConfigParser()
    if os.path.exists('settings.ini'):
        config.read('settings.ini')
        defaults = config['DEFAULT']
    else:
        config['DEFAULT'] = {}
        defaults = config['DEFAULT']

    defaults.setdefault('hide_from_screen',  'False')
    defaults.setdefault('hide_from_taskbar', 'False')
    defaults.setdefault('always_on_top',     'False')
    defaults.setdefault('transparency',      '1.0')
    defaults.setdefault('theme',             'light')

    return config

def save_settings(settings):
    with open('settings.ini', 'w') as configfile:
        settings.write(configfile)

def get_username():
    load_dotenv()
    username = os.getenv('USERNAME') or os.getenv('USER')  
    if not username:
        try:
            username = os.getlogin()
        except Exception:
            username = 'User'
    return username

def get_openai_api_key():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not found in .env file.")
    return api_key